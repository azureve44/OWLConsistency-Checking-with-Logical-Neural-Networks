"""

Flow:
  CSV -> raw triple features -> vocab selection (df / supervised)
  -> optional absence expansion -> per-group top-K filter
  -> IBM LNN with or-neurons per feature group -> multi-seed evaluation

Model:
  One Or-neuron per feature group, combined by a final Or-neuron.
  Signed-evidence mode adds a symmetric ``Consistent`` head when
  train size >= SIGNED_EVIDENCE_MIN_TRAIN.

Usage::

    python train_lnn.py --train t.csv --val v.csv --test e.csv [options]
    python train_lnn.py --dry_run_features   # inspect vocab, skip LNN load
"""
from __future__ import annotations
import argparse
import ast
import csv
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
import numpy as np
import pandas as pd

TRAIN_CSV = "path/to/splits/nsplits/train_data.csv"
VAL_CSV = "path/to/splits/nsplits/eval_data.csv"
TEST_CSV = "path/to/splits/nsplits/test_data.csv"
DEFAULT_SEEDS = [0, 1, 2,3,4]
DEFAULT_EPOCHS = 100
DEFAULT_LR = 0.03              # prev: 0.015
DEFAULT_MAX_FEATURES = 128     # prev: 256
DEFAULT_MIN_DF = 5             # prev: 10
DEFAULT_THRESHOLD = 0.5
DEFAULT_INIT_WEIGHT = 0.1
DEFAULT_INIT_BIAS = -1.0
DEFAULT_FINAL_INIT_WEIGHT = 0.2
DEFAULT_FINAL_INIT_BIAS = -1.0
DEFAULT_NORMALIZE_INIT = True
DEFAULT_TOP_K_PER_GROUP = 10
SHUFFLE_SEED_OFFSET = 1000           # offset applied to seed when shuffling labels
FEATURE_PRESENT_BOUNDS = (0.75, 1.0) # LNN [lower, upper] belief for an active feature
FEATURE_ABSENT_BOUNDS = (0.0, 0.25)  # reserved; absent features currently use Fact.FALSE
_OP_TOKENS = {"some", "only", "max", "min", "exactly", "inverse", "and", "or", "not"}  # OWL class-expression keywords
_COUNT_BUCKETS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000]   # thresholds for n_* bucket features
_LENGTH_BUCKETS = [64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384]  # thresholds for tokenized_length features
ONTOLOGY_RULE_NAMES = [  # defined for future use; not wired into the default training path
    "rule_subclass_cycle",
    "rule_disjoint_subclass_conflict",
    "rule_disjoint_equivalent_mix",
    "rule_property_constraint_mix",
    "rule_negated_restriction",
]
SIGNED_EVIDENCE_MIN_TRAIN = 1000  # min train samples before polarity estimation is reliable

# Raw feature extraction / CSV loading helpers

def set_csv_field_limit() -> None:
    """Raise csv.field_size_limit to sys.maxsize, halving on OverflowError"""
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10

def is_injected(val: object) -> bool:
    """True if val is a non-empty, non-null, non-'none' string"""
    return pd.notna(val) and str(val).strip().lower() not in {"", "none", "nan"}

def parse_body(body: object) -> List[Tuple[str, str, str]]:
    """Parse a body string-or-list into ``(subject, predicate, object)`` triples"""
    if isinstance(body, str):
        try:
            triples = ast.literal_eval(body)
        except (SyntaxError, ValueError, TypeError):
            return []
    elif isinstance(body, list):
        triples = body
    else:
        return []
    out: List[Tuple[str, str, str]] = []
    for t in triples:
        if not isinstance(t, (list, tuple)) or len(t) != 3:
            continue
        s, p, o = t
        out.append((str(s).strip(), str(p).strip(), str(o).strip()))
    return out

def _norm_space(s: str) -> str:
    """Collapse runs of whitespace in s to a single space"""
    return re.sub(r"\s+", " ", str(s).strip())

def _safe_feature_value(s: str, max_len: int = 96) -> str:
    """Normalize whitespace and truncate s to max_len chars"""
    s = _norm_space(s)
    if len(s) > max_len:
        s = s[:max_len] + "…"
    return s

def tokenise_obj(o: str) -> List[str]:
    """Tokenize object expressions such as 'P some C' to 'inverse(P) some C'"""
    o = str(o).strip().rstrip(',')
    # Split at non-word punctuation but keep URI-ish fragments readable.
    raw = re.split(r"([\s(),;]+)", o)
    toks = []
    for tok in raw:
        tok = tok.strip()
        if not tok or tok in {",", "(", ")", ";"}:
            continue
        toks.append(tok)
    return toks

def _ops_in_obj(o: str) -> Set[str]:
    """OWL operator tokens present in o, e.g. ``{'some', 'and'}``"""
    ops = set()
    lower = f" {_norm_space(o).lower()} "
    for op in _OP_TOKENS:
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(op)}(?![A-Za-z0-9_])", lower):
            ops.add(op)
    return ops

def _bucket_features(prefix: str, value: int, buckets: Sequence[int]) -> Iterable[str]:
    """Yield ``prefix>={b}`` for each threshold b that value meets"""
    for b in buckets:
        if value >= b:
            yield f"{prefix}>={b}"

def _has_subclass_cycle(edges: Sequence[Tuple[str, str]]) -> bool:
    """True if the subclass edge list contains a directed cycle (DFS)"""
    graph: Dict[str, Set[str]] = defaultdict(set)
    nodes: Set[str] = set()
    for child, parent in edges:
        graph[child].add(parent)
        nodes.add(child)
        nodes.add(parent)
    visiting: Set[str] = set()
    visited: Set[str] = set()
    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, ()):  # pragma: no branch
            if dfs(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False
    return any(dfs(n) for n in nodes)

def extract_raw_features(row: Mapping[str, object], body_column: str = "body") -> Set[str]:
    """
    Return generic structural/token features derived from raw triples only
    """
    triples = parse_body(row.get(body_column, ""))
    feats: Set[str] = set()
    n_triples = len(triples)
    feats.update(_bucket_features("n_triples", n_triples, _COUNT_BUCKETS))
    tokenized_length = row.get("tokenized_length")
    try:
        tok_len = int(float(tokenized_length))
    except (TypeError, ValueError):
        tok_len = 0
    if tok_len > 0:
        feats.update(_bucket_features("tokenized_length", tok_len, _LENGTH_BUCKETS))
    subjects: Set[str] = set()
    objects: Set[str] = set()
    entities: Set[str] = set()
    pred_counts: Counter = Counter()
    subj_pred_counts: Dict[str, Counter] = defaultdict(Counter)
    subj_subclass_targets: Dict[str, Set[str]] = defaultdict(set)
    subclass_edges: List[Tuple[str, str]] = []
    subproperty_edges: List[Tuple[str, str]] = []
    unique_preds: Set[str] = set()
    obj_ops_seen: Set[str] = set()
    for s, p, o in triples:
        s = _safe_feature_value(s)
        p = _safe_feature_value(p)
        o_norm = _safe_feature_value(o)
        p_lower = p.lower()
        subjects.add(s)
        objects.add(o_norm)
        entities.add(s)
        entities.add(o_norm)
        pred_counts[p] += 1
        subj_pred_counts[s][p] += 1
        unique_preds.add(p)
        feats.add(f"pred={p}")
        if p_lower in {"subclassof", "subpropertyof", "equivalentto", "disjointwith", "disjointclasses", "domain", "range", "types"}:
            feats.add(f"owl_pred={p_lower}")
        if p_lower == "subclassof":
            subclass_edges.append((s, o_norm))
            subj_subclass_targets[s].add(o_norm)
            if s == o_norm:
                feats.add("graph:reflexive_subclass")
        elif p_lower == "subpropertyof":
            subproperty_edges.append((s, o_norm))
        ops = _ops_in_obj(o_norm)
        obj_ops_seen.update(ops)
        for op in ops:
            feats.add(f"obj_op={op}")
            feats.add(f"pred_op={p}::{op}")
        if '(' in o_norm or ')' in o_norm:
            feats.add(f"pred_has_paren_obj={p}")
        if ',' in o_norm:
            feats.add(f"pred_has_comma_obj={p}")
        # Object tokens are raw-triple information
        # The train-only document frequency filter below keeps only reusable tokens and avoids
        # a huge per-IRI vocabulary
        for tok in tokenise_obj(o_norm)[:8]:
            tl = tok.lower()
            if not tl or len(tl) > 96:
                continue
            if tl in _OP_TOKENS:
                continue
            tok = _safe_feature_value(tok)
            feats.add(f"obj_token={tok}")
            feats.add(f"pred_obj_token={p}::{tok}")
    feats.update(_bucket_features("n_subjects", len(subjects), _COUNT_BUCKETS))
    feats.update(_bucket_features("n_objects", len(objects), _COUNT_BUCKETS))
    feats.update(_bucket_features("n_entities", len(entities), _COUNT_BUCKETS))
    feats.update(_bucket_features("n_predicates", len(unique_preds), [1, 2, 3, 4, 5, 8, 12, 20, 40]))
    for p, c in pred_counts.items():
        for b in [1, 2, 3, 5, 10, 20, 50, 100]:
            if c >= b:
                feats.add(f"pred_count={p}>={b}")
    # Predicate co-occurrence features are generic and often transfer better
    # than raw entity names
    sorted_preds = sorted(unique_preds)
    for i, p1 in enumerate(sorted_preds[:24]):
        for p2 in sorted_preds[i + 1:24]:
            feats.add(f"pred_pair={p1}&&{p2}")
    if len(obj_ops_seen) >= 2:
        for op1 in sorted(obj_ops_seen):
            for op2 in sorted(obj_ops_seen):
                if op1 < op2:
                    feats.add(f"obj_op_pair={op1}&&{op2}")
    if subclass_edges:
        feats.add("graph:has_subclass_edges")
        if _has_subclass_cycle(subclass_edges):
            feats.add("graph:subclass_cycle")
        if any(len(targets) >= 2 for targets in subj_subclass_targets.values()):
            feats.add("graph:same_subject_multiple_subclass_targets")
        parents = {parent for _child, parent in subclass_edges}
        children = {child for child, _parent in subclass_edges}
        if parents & children:
            feats.add("graph:subclass_chain_len2")
    if subproperty_edges:
        feats.add("graph:has_subproperty_edges")
        parents = {parent for _child, parent in subproperty_edges}
        children = {child for child, _parent in subproperty_edges}
        if parents & children:
            feats.add("graph:subproperty_chain_len2")
    # Same-subject structural combinations, without checking anti-pattern truth
    for _s, pc in subj_pred_counts.items():
        if len(pc) >= 2:
            feats.add("graph:same_subject_multiple_predicates")
        if pc.get("SubClassOf", 0) >= 2:
            feats.add("graph:same_subject_repeated_subclassof")
    return feats

@dataclass
class SplitData:
    """Holds ids, labels and raw feature sets for one data split"""
    name: str
    ids: List[str]
    labels: np.ndarray
    feature_sets: List[Set[str]]
    @property
    def n_pos(self) -> int:
        return int(self.labels.sum())
    @property
    def n_neg(self) -> int:
        return int(len(self.labels) - self.labels.sum())

def label_from_row(row: Mapping[str, object], label_source: str, positive_consistency: str) -> int:
    """Return 1 (positive) or 0 from a CSV row using the configured label strategy"""
    if label_source == "injected_pattern":
        return 1 if is_injected(row.get("injected_pattern")) else 0
    if label_source == "consistency":
        return 1 if str(row.get("consistency", "")).strip().lower() == positive_consistency.lower() else 0
    raise ValueError(f"Unsupported label_source: {label_source}")

def load_split(path: str, split_name: str, args: "argparse.Namespace") -> SplitData:
    """Read a CSV split, optionally subsample it, and extract raw features"""
    df = pd.read_csv(path)
    if args.sample_frac < 1.0:
        y_tmp = df.apply(lambda r: label_from_row(r, args.label_source, args.positive_consistency), axis=1)
        parts = []
        rng = np.random.default_rng(args.sample_seed + {"train": 0, "val": 1, "test": 2}.get(split_name, 3))
        for y_val in [0, 1]:
            idx = np.flatnonzero(y_tmp.to_numpy() == y_val)
            if len(idx) == 0:
                continue
            k = max(1, int(round(len(idx) * args.sample_frac)))
            k = min(k, len(idx))
            parts.extend(rng.choice(idx, size=k, replace=False).tolist())
        parts = sorted(parts)
        df = df.iloc[parts].reset_index(drop=True)
    ids: List[str] = []
    labels: List[int] = []
    feature_sets: List[Set[str]] = []
    for i, row in df.iterrows():
        raw_id = str(row.get(args.id_column, f"row{i}")).strip() or f"row{i}"
        ids.append(f"{split_name}::{raw_id}")
        labels.append(label_from_row(row, args.label_source, args.positive_consistency))
        feature_sets.append(extract_raw_features(row, body_column=args.body_column))
    return SplitData(split_name, ids, np.asarray(labels, dtype=np.int64), feature_sets)

def build_feature_vocab(train_features: Sequence[Set[str]], max_features: int, min_df: int) -> List[str]:
    """Top-max_features features by document frequency (train-only, >= min_df)"""
    df_counter: Counter = Counter()
    for feats in train_features:
        df_counter.update(feats)
    candidates = [(feat, df) for feat, df in df_counter.items() if df >= min_df]
    # Sort by document frequency descending, then feature name for determinism.
    candidates.sort(key=lambda kv: (-kv[1], kv[0]))
    return [feat for feat, _df in candidates[:max_features]]

def build_feature_vocab_supervised(
    train_features: Sequence[Set[str]],
    train_labels: np.ndarray,
    max_features: int,
    min_df: int,
) -> List[str]:
    """
    Select train-only features by class separation
    avoids validation/test leakage because it uses only the training split
    """
    df_counter: Counter = Counter()
    pos_counter: Counter = Counter()
    neg_counter: Counter = Counter()

    y = np.asarray(train_labels, dtype=np.int64)
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())

    for feats, label in zip(train_features, y):
        df_counter.update(feats)
        if int(label) == 1:
            pos_counter.update(feats)
        else:
            neg_counter.update(feats)

    scored = []
    for feat, df in df_counter.items():
        if df < min_df:
            continue
        pos_rate = pos_counter[feat] / max(n_pos, 1)
        neg_rate = neg_counter[feat] / max(n_neg, 1)
        score = abs(pos_rate - neg_rate)
        scored.append((feat, score, df, pos_rate, neg_rate))

    scored.sort(key=lambda kv: (-kv[1], -kv[2], kv[0]))
    return [feat for feat, _score, _df, _pr, _nr in scored[:max_features]]

def is_absence_feature(feature_name: str) -> bool:
    """True if feature_name encodes a feature-absence predicat"""
    return feature_name.startswith("ABSENT::")

def base_feature_name(feature_name: str) -> str:
    """Strip the ``ABSENT::`` prefix, if present"""
    return feature_name[len("ABSENT::"):] if is_absence_feature(feature_name) else feature_name

def model_feature_active(feature_name: str, raw_features: Set[str]) -> bool:
    """True if the logical predicate fires: present-feature in set, or absent-feature not in set"""
    base = base_feature_name(feature_name)
    present = base in raw_features
    return (not present) if is_absence_feature(feature_name) else present

def expand_with_absence_features(feature_vocab: Sequence[str]) -> List[str]:
    """Add an absence-evidence predicate for every selected raw feature"""
    return list(feature_vocab) + [f"ABSENT::{feat}" for feat in feature_vocab]

def feature_group_name(feature_name: str) -> str:
    """Assign selected input predicates to coarse logical subrules"""
    base = base_feature_name(feature_name)
    if base.startswith("graph:"):
        return "graph"
    if base.startswith(("owl_pred=", "pred=", "pred_count=", "pred_pair=",
                        "pred_op=", "pred_has_")):
        return "predicate"
    if base.startswith(("obj_op=", "obj_op_pair=")):
        return "object_operator"
    if base.startswith(("obj_token=", "pred_obj_token=")):
        return "object_token"
    if base.startswith(("n_", "tokenized_length")):
        return "counts"
    return "other"

def build_feature_groups(feature_vocab: Sequence[str]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    for feat in feature_vocab:
        grouped[feature_group_name(feat)].append(feat)
    preferred_order = ["graph", "predicate", "object_operator", "object_token", "counts", "other"]
    ordered: Dict[str, List[str]] = {}
    for name in preferred_order:
        if grouped.get(name):
            ordered[name] = grouped[name]
    for name in sorted(set(grouped) - set(ordered)):
        ordered[name] = grouped[name]
    return ordered

def _install_matplotlib_stub() -> None:
    """
    pyplot stub for headless training-only imports:

    Some environments have a matplotlib wheel compiled
    against NumPy 1.x while runtime NumPy is 2.x, which makes importing LNN fail even though this we never plot

    stub keeps training usable without changing the project package or the conda environment

    Set LNN_RAW_USE_REAL_MATPLOTLIB=1 if want the real matplotlib import during this script
    """
    if os.environ.get("LNN_RAW_USE_REAL_MATPLOTLIB") == "1":
        return
    import types

    class _PyplotStub(types.ModuleType):
        def __getattr__(self, name):
            # Do not synthesize dunder attributes:
            # inspect/torch expect values like __file__ to be strings or absent, not callables.
            if name.startswith("__") and name.endswith("__"):
                raise AttributeError(name)
            def _noop(*_args, **_kwargs):
                return None
            return _noop

    mpl = types.ModuleType("matplotlib")
    mpl.__file__ = "<matplotlib-stub>"
    pyplot = _PyplotStub("matplotlib.pyplot")
    pyplot.__file__ = "<matplotlib.pyplot-stub>"
    mpl.pyplot = pyplot  # type: ignore[attr-defined]
    sys.modules["matplotlib"] = mpl
    sys.modules["matplotlib.pyplot"] = pyplot

def _install_numpy_compat_aliases() -> None:
    """Patch removed NumPy 2.x aliases (float_, int_, bool_, …) so LNN can import"""
    alias_map = {
        "float_": np.float64,
        "complex_": np.complex128,
        "int_": np.int64,
        "bool_": np.bool_,
        "float": float,
        "complex": complex,
        "int": int,
        "bool": bool,
    }
    for name, value in alias_map.items():
        if not hasattr(np, name):
            try:
                setattr(np, name, value)
            except Exception:
                pass

# LNN helper layer

def _fmt_time(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS.ss``"""
    td = timedelta(seconds=float(seconds))
    total = td.total_seconds()
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"

def set_seed(seed: int) -> None:
    """Seed Python, NumPy, and (if available) PyTorch RNGs"""
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch  # type: ignore
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass

def parse_seeds(seed_arg: str) -> List[int]:
    """Parse a comma-separated seed string into a non-empty list of ints"""
    seeds = []
    for part in str(seed_arg).split(','):
        part = part.strip()
        if part:
            seeds.append(int(part))
    if not seeds:
        raise ValueError("--seeds must contain at least one integer")
    return seeds

def binary_metrics(y_true: Sequence[int], y_pred: Sequence[int], scores: Optional[Sequence[float]] = None) -> Dict[str, float]:
    """Compute acc, bacc, prec, rec, f1 and confusion-matrix counts; optionally score stats"""
    yt = np.asarray(y_true, dtype=np.int64)
    yp = np.asarray(y_pred, dtype=np.int64)
    tp = int(((yt == 1) & (yp == 1)).sum())
    fp = int(((yt == 0) & (yp == 1)).sum())
    tn = int(((yt == 0) & (yp == 0)).sum())
    fn = int(((yt == 1) & (yp == 0)).sum())
    n = len(yt)
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    tnr = tn / (tn + fp) if (tn + fp) else 0.0
    bacc = 0.5 * (rec + tnr)
    out: Dict[str, float] = {
        "acc": acc, "bacc": bacc, "prec": prec, "rec": rec, "f1": f1,
        "tp": float(tp), "fp": float(fp), "tn": float(tn), "fn": float(fn),
    }
    if scores is not None and len(scores):
        sc = np.asarray(scores, dtype=float)
        out["mean_score"] = float(sc.mean())
        out["min_score"] = float(sc.min())
        out["max_score"] = float(sc.max())
    return out

def best_threshold_for_bacc(y_true: Sequence[int], scores: Sequence[float]) -> Tuple[float, float]:
    """Return ``(threshold, bacc)`` maximising balanced accuracy on scores"""
    yt = np.asarray(y_true, dtype=np.int64)
    sc = np.asarray(scores, dtype=float)
    if len(sc) == 0:
        return DEFAULT_THRESHOLD, 0.0
    uniq = np.unique(sc)
    candidates: List[float] = [DEFAULT_THRESHOLD, float(max(0.0, uniq[0] - 1e-12))]
    if len(uniq) > 1:
        candidates.extend(float(x) for x in ((uniq[:-1] + uniq[1:]) / 2.0))
    candidates.extend(float(x) for x in uniq)
    candidates.append(float(min(1.0, uniq[-1] + 1e-12)))
    best_t, best_bacc = DEFAULT_THRESHOLD, -1.0
    for t in candidates:
        m = binary_metrics(yt, (sc >= t).astype(np.int64), sc)
        if m["bacc"] > best_bacc:
            best_t, best_bacc = float(t), float(m["bacc"])
    return best_t, best_bacc

def best_threshold_for_metric(y_true: Sequence[int], scores: Sequence[float], metric: str) -> Tuple[float, float]:
    """Return ``(threshold, metric_value)`` maximising metric; ties broken by bacc then lower threshold"""
    yt = np.asarray(y_true, dtype=np.int64)
    sc = np.asarray(scores, dtype=float)
    if len(sc) == 0:
        return DEFAULT_THRESHOLD, 0.0
    metric = str(metric).lower()
    if metric == "bacc":
        return best_threshold_for_bacc(yt, sc)
    uniq = np.unique(sc)
    candidates: List[float] = [DEFAULT_THRESHOLD, float(max(0.0, uniq[0] - 1e-12))]
    if len(uniq) > 1:
        candidates.extend(float(x) for x in ((uniq[:-1] + uniq[1:]) / 2.0))
    candidates.extend(float(x) for x in uniq)
    candidates.append(float(min(1.0, uniq[-1] + 1e-12)))
    best_t, best_value = DEFAULT_THRESHOLD, -1.0
    best_bacc = -1.0
    for t in candidates:
        m = binary_metrics(yt, (sc >= t).astype(np.int64), sc)
        value = float(m.get(metric, 0.0))
        # Tie-break with balanced accuracy, then lower threshold for recall.
        if value > best_value or (value == best_value and (m["bacc"] > best_bacc or (m["bacc"] == best_bacc and t < best_t))):
            best_t, best_value, best_bacc = float(t), value, float(m["bacc"])
    return best_t, best_value

def score_class_summary(y_true: Sequence[int], scores: Sequence[float]) -> Dict[str, float]:
    """Per-class (pos/neg) score statistics: mean, std, min, q25, median, q75, max"""
    yt = np.asarray(y_true, dtype=np.int64)
    sc = np.asarray(scores, dtype=float)
    out: Dict[str, float] = {}
    for label, name in [(1, "pos"), (0, "neg")]:
        vals = sc[yt == label]
        out[f"{name}_n"] = float(len(vals))
        if len(vals):
            out[f"{name}_score_mean"] = float(vals.mean())
            out[f"{name}_score_std"] = float(vals.std())
            out[f"{name}_score_min"] = float(vals.min())
            out[f"{name}_score_q25"] = float(np.quantile(vals, 0.25))
            out[f"{name}_score_median"] = float(np.quantile(vals, 0.50))
            out[f"{name}_score_q75"] = float(np.quantile(vals, 0.75))
            out[f"{name}_score_max"] = float(vals.max())
    return out

def _import_lnn() -> tuple:
    """Install compatibility shims, then import and return the core LNN symbols"""
    _install_numpy_compat_aliases()
    _install_matplotlib_stub()
    from lnn import Predicate, Variable, Fact, Model, World, Iff, Or, And, Implies, Not, Loss, Direction
    return Predicate, Variable, Fact, Model, World, Iff, Or, And, Implies, Not, Loss, Direction

@dataclass
class NativeLNNArtifacts:
    """All IBM-LNN objects produced by ``build_native_lnn``; passed between training helpers"""
    model: object
    feature_preds: Dict[str, object]
    ontology_rule_preds: Dict[str, object]
    ontology_rule_formulas: Dict[str, object]
    ontology_rule_final: Optional[object]
    group_preds: Dict[str, object]
    consistent_group_preds: Dict[str, object]
    group_disjunctions: Dict[str, object]
    consistent_group_disjunctions: Dict[str, object]
    target_pred: object
    consistent_pred: object
    final_disjunction: object
    consistent_final_disjunction: Optional[object]
    all_formulas: Dict[str, object]
    feature_groups: Dict[str, List[str]]
    signed_evidence: bool
    feature_polarities: Dict[str, int]
    Fact: object
    Direction: object
    Loss: object

def _init_or_neuron(formula: object, weight: float, bias: float, normalize: bool = False) -> None:
    """Fill all Or-neuron weights with weight (optionally 1/√n scaled) and bias"""
    try:
        import torch  # type: ignore
        with torch.no_grad():
            n = int(formula.neuron.weights.numel())
            w = float(weight) / math.sqrt(max(n, 1)) if normalize else float(weight)
            formula.neuron.weights.fill_(w)
            formula.neuron.bias.fill_(float(bias))
    except Exception as exc:
        print(f"  (warning: could not initialize Or neuron: {exc})", flush=True)

def compute_feature_polarities(split: SplitData, feature_vocab: Sequence[str]) -> Dict[str, int]:
    """
    Return +1 for inconsistency evidence and -1 for consistency evidence
    Polarity is estimated on the training split only, using the difference in
    active feature rate between positive and negative labels
    the sign only decides which logical evidence head a raw predicate feeds;
    LNN learns the connective parameters via "Loss.SUPERVISED"
    """
    pos_total = max(1, int(np.sum(split.labels)))
    neg_total = max(1, int(len(split.labels) - np.sum(split.labels)))
    out: Dict[str, int] = {}
    for feat in feature_vocab:
        active_pos = 0
        active_neg = 0
        for y, feats in zip(split.labels, split.feature_sets):
            if model_feature_active(feat, feats):
                if int(y) == 1:
                    active_pos += 1
                else:
                    active_neg += 1
        score = (active_pos / pos_total) - (active_neg / neg_total)
        out[feat] = 1 if score >= 0 else -1
    return out

def ontology_rule_atoms_from_features(feats: Set[str]) -> Set[str]:
    """
    Ontology-level rule atoms generic logical conditions over
    OWL-style predicates/graph structure,
    then composed into LNN formulas
    (`And`, `Or`, `Implies`) in 'build_native_lnn'
    """
    out: Set[str] = set()
    has_subclass = "owl_pred=subclassof" in feats or any(f.startswith("pred=SubClassOf") for f in feats)
    has_disjoint = "owl_pred=disjointwith" in feats or any("DisjointClasses" in f or "DisjointWith" in f for f in feats)
    has_equiv = "owl_pred=equivalentto" in feats or any("Equivalent" in f for f in feats)
    has_subproperty = "owl_pred=subpropertyof" in feats or any("SubPropertyOf" in f for f in feats)
    has_domain = "owl_pred=domain" in feats or any("Domain" in f for f in feats)
    has_range = "owl_pred=range" in feats or any("Range" in f for f in feats)
    has_negation = any(f in {"obj_op=not", "obj_op=only", "obj_op=max", "obj_op=min", "obj_op=exactly"} for f in feats)
    if "graph:subclass_cycle" in feats:
        out.add("rule_subclass_cycle")
    if has_subclass and has_disjoint and ("graph:same_subject_multiple_subclass_targets" in feats or "graph:subclass_chain_len2" in feats):
        out.add("rule_disjoint_subclass_conflict")
    if has_equiv and has_disjoint:
        out.add("rule_disjoint_equivalent_mix")
    if has_subproperty and has_domain and has_range:
        out.add("rule_property_constraint_mix")
    if has_subclass and has_negation:
        out.add("rule_negated_restriction")
    return out

def make_balanced_or(Or: object, formulas: Sequence[object], init_weight: float, init_bias: float, normalize_init: bool) -> Optional[object]:
    """Wrap formulas in a learnable Or-neuron, or return the single formula directly"""
    if not formulas:
        return None
    if len(formulas) == 1:
        return formulas[0]
    formula = Or(formulas, activation={"bias_learning": True, "weights_learning": True})
    _init_or_neuron(formula, init_weight, init_bias, normalize=normalize_init)
    return formula

def build_native_lnn(
    feature_vocab: Sequence[str],
    init_weight: float,
    init_bias: float,
    final_init_weight: float,
    final_init_bias: float,
    normalize_init: bool,
    feature_polarities: Optional[Mapping[str, int]] = None,
    signed_evidence: bool = False,
    enable_ontology_rules: bool = False,
) -> NativeLNNArtifacts:
    Predicate, Variable, Fact, Model, World, Iff, Or, And, Implies, Not, Loss, Direction = _import_lnn()
    if not feature_vocab:
        raise ValueError("Feature vocabulary is empty; lower --min_df or increase --sample_frac")
    polarities = {feat: int((feature_polarities or {}).get(feat, 1)) for feat in feature_vocab}
    feature_preds = {feat: Predicate(f"Feature_{i:04d}") for i, feat in enumerate(feature_vocab)}
    ontology_rule_preds = {name: Predicate(f"Ontology_{name}") for name in ONTOLOGY_RULE_NAMES}
    feature_groups = build_feature_groups(feature_vocab)
    group_preds = {name: Predicate(f"Inconsistent_{name}") for name in feature_groups}
    consistent_group_preds = {name: Predicate(f"Consistent_{name}") for name in feature_groups}
    target = Predicate("Inconsistent")
    consistent = Predicate("Consistent")
    x = Variable("x")
    model = Model()
    group_disjunctions: Dict[str, object] = {}
    consistent_group_disjunctions: Dict[str, object] = {}
    all_formulas: Dict[str, object] = {}
    ontology_rule_formulas: Dict[str, object] = {}
    ontology_rule_final = None
    if enable_ontology_rules:
        rule_inputs = [ontology_rule_preds[name](x) for name in ONTOLOGY_RULE_NAMES]
        # Compose rule atoms into actual logical ontology-rule formulas
        # These formulae are added to the final Inconsistent evidence disjunction and
        # also asserted as implications to the target predicate.
        named_rules = {
            "rule_subclass_cycle": ontology_rule_preds["rule_subclass_cycle"](x),
            "rule_disjoint_subclass_conflict": And(
                ontology_rule_preds["rule_disjoint_subclass_conflict"](x),
                Or(ontology_rule_preds["rule_subclass_cycle"](x), Not(ontology_rule_preds["rule_subclass_cycle"](x))),
            ),
            "rule_disjoint_equivalent_mix": ontology_rule_preds["rule_disjoint_equivalent_mix"](x),
            "rule_property_constraint_mix": ontology_rule_preds["rule_property_constraint_mix"](x),
            "rule_negated_restriction": ontology_rule_preds["rule_negated_restriction"](x),
        }
        for rule_name, formula in named_rules.items():
            ontology_rule_formulas[rule_name] = formula
            all_formulas[f"ONTO_{rule_name}"] = formula
        ontology_rule_final = make_balanced_or(Or, list(ontology_rule_formulas.values()), final_init_weight, final_init_bias, normalize_init)
        if ontology_rule_final is not None:
            all_formulas["OR_ontology_rules"] = ontology_rule_final
    def make_feature_or(group_feats: Sequence[str], weight: float, bias: float):
        inputs = [feature_preds[feat](x) for feat in group_feats]
        if not inputs:
            return None
        if len(inputs) == 1:
            # Avoid IBM LNN unary connective grounding shape issues.
            return inputs[0]
        formula = Or(inputs, activation={"bias_learning": True, "weights_learning": True})
        _init_or_neuron(formula, weight, bias, normalize=normalize_init)
        return formula
    for group_name, group_feats in feature_groups.items():
        if signed_evidence:
            inconsistent_feats = [feat for feat in group_feats if polarities.get(feat, 1) >= 0]
            consistent_feats = [feat for feat in group_feats if polarities.get(feat, 1) < 0]
        else:
            inconsistent_feats = list(group_feats)
            consistent_feats = []
        group_formula = make_feature_or(inconsistent_feats, init_weight, init_bias)
        if group_formula is not None:
            group_disjunctions[group_name] = group_formula
            all_formulas[f"OR_{group_name}"] = group_formula
            model.add_knowledge(Iff(group_preds[group_name](x), group_formula), world=World.OPEN)
        consistent_formula = make_feature_or(consistent_feats, init_weight, init_bias)
        if consistent_formula is not None:
            consistent_group_disjunctions[group_name] = consistent_formula
            all_formulas[f"OR_consistent_{group_name}"] = consistent_formula
            model.add_knowledge(Iff(consistent_group_preds[group_name](x), consistent_formula), world=World.OPEN)
    if not group_disjunctions:
        raise ValueError("No inconsistency evidence groups were created; disable --signed_evidence or adjust features")
    group_decision_formulas = list(group_disjunctions.values())
    if ontology_rule_final is not None:
        group_decision_formulas.append(ontology_rule_final)
    if len(group_decision_formulas) == 1:
        final_or = group_decision_formulas[0]
    else:
        final_or = Or(group_decision_formulas, activation={"bias_learning": True, "weights_learning": True})
        _init_or_neuron(final_or, final_init_weight, final_init_bias, normalize=normalize_init)
    all_formulas["OR_final"] = final_or
    model.add_knowledge(Iff(target(x), final_or), world=World.OPEN)
    if ontology_rule_final is not None:
        model.add_knowledge(Implies(ontology_rule_final, target(x)), world=World.OPEN)
    consistent_final_or = None
    if signed_evidence and consistent_group_disjunctions:
        consistent_decision_formulas = list(consistent_group_disjunctions.values())
        if len(consistent_decision_formulas) == 1:
            consistent_final_or = consistent_decision_formulas[0]
        else:
            consistent_final_or = Or(consistent_decision_formulas, activation={"bias_learning": True, "weights_learning": True})
            _init_or_neuron(consistent_final_or, final_init_weight, final_init_bias, normalize=normalize_init)
        all_formulas["OR_consistent_final"] = consistent_final_or
        model.add_knowledge(Iff(consistent(x), consistent_final_or), world=World.OPEN)
    else:
        model.add_knowledge(Iff(consistent(x), Not(target(x))), world=World.OPEN)
    all_formulas["Inconsistent"] = target
    all_formulas["Consistent"] = consistent
    for group_name, pred in group_preds.items():
        all_formulas[f"Inconsistent_{group_name}"] = pred
    for group_name, pred in consistent_group_preds.items():
        all_formulas[f"Consistent_{group_name}"] = pred
    return NativeLNNArtifacts(
        model=model,
        feature_preds=feature_preds,
        ontology_rule_preds=ontology_rule_preds,
        ontology_rule_formulas=ontology_rule_formulas,
        ontology_rule_final=ontology_rule_final,
        group_preds=group_preds,
        consistent_group_preds=consistent_group_preds,
        group_disjunctions=group_disjunctions,
        consistent_group_disjunctions=consistent_group_disjunctions,
        target_pred=target,
        consistent_pred=consistent,
        final_disjunction=final_or,
        consistent_final_disjunction=consistent_final_or,
        all_formulas=all_formulas,
        feature_groups=feature_groups,
        signed_evidence=signed_evidence,
        feature_polarities=polarities,
        Fact=Fact,
        Direction=Direction,
        Loss=Loss,
    )

def add_split_facts(art: NativeLNNArtifacts, split: SplitData, feature_vocab: Sequence[str], with_labels: bool) -> None:
    """Populate LNN predicates with feature observations; attach labels if with_labels"""
    Fact = art.Fact
    feature_data: Dict[str, Dict[str, object]] = {feat: {} for feat in feature_vocab}
    ontology_rule_data: Dict[str, Dict[str, object]] = {name: {} for name in art.ontology_rule_preds}
    target_data: Dict[str, object] = {}
    consistent_data: Dict[str, object] = {}
    group_data: Dict[str, Dict[str, object]] = {name: {} for name in art.group_preds}
    target_labels: Dict[str, object] = {}
    consistent_labels: Dict[str, object] = {}
    for oid, y, feats in zip(split.ids, split.labels, split.feature_sets):
        target_data[oid] = Fact.UNKNOWN
        consistent_data[oid] = Fact.UNKNOWN
        for group_name in group_data:
            group_data[group_name][oid] = Fact.UNKNOWN
        for feat in feature_vocab:
            feature_data[feat][oid] = (
                FEATURE_PRESENT_BOUNDS if model_feature_active(feat, feats) else Fact.FALSE
            )
        active_rule_atoms = ontology_rule_atoms_from_features(feats)
        for rule_name in ontology_rule_data:
            ontology_rule_data[rule_name][oid] = (
                FEATURE_PRESENT_BOUNDS if rule_name in active_rule_atoms else Fact.FALSE
            )
        if with_labels:
            if int(y) == 1:
                target_labels[oid] = Fact.TRUE
                consistent_labels[oid] = Fact.FALSE
            else:
                target_labels[oid] = Fact.FALSE
                consistent_labels[oid] = Fact.TRUE
    for feat, pred in art.feature_preds.items():
        pred.add_data(feature_data[feat])
    for rule_name, pred in art.ontology_rule_preds.items():
        pred.add_data(ontology_rule_data[rule_name])
    for group_name, pred in art.group_preds.items():
        pred.add_data(group_data[group_name])
    for group_name, pred in art.consistent_group_preds.items():
        pred.add_data(group_data[group_name])
    art.target_pred.add_data(target_data)
    art.consistent_pred.add_data(consistent_data)
    if with_labels:
        art.target_pred.add_labels(target_labels)
        art.consistent_pred.add_labels(consistent_labels)
        try:
            art.final_disjunction.add_labels(target_labels)
        except Exception:
            pass
        if art.consistent_final_disjunction is not None:
            try:
                art.consistent_final_disjunction.add_labels(consistent_labels)
            except Exception:
                pass

def resolve_inference_direction(art: NativeLNNArtifacts, inference_direction: str) -> Optional[object]:
    """Map a direction name to the LNN Direction enum value, or None for bidirectional"""
    direction = str(inference_direction).lower()
    if direction == "bidirectional":
        return None
    if direction == "upward":
        return art.Direction.UPWARD
    if direction == "downward":
        return art.Direction.DOWNWARD
    raise ValueError(f"Unsupported inference direction: {inference_direction}")

def infer_model(art: NativeLNNArtifacts, inference_direction: str, max_infer_steps: int = 0) -> object:
    """Run ``model.infer`` with the resolved direction and optional step cap"""
    direction = resolve_inference_direction(art, inference_direction)
    kw = {}
    if max_infer_steps and max_infer_steps > 0:
        kw["max_steps"] = int(max_infer_steps)
    if direction is None:
        return art.model.infer(**kw)
    return art.model.infer(direction=direction, **kw)

def _formula_bounds(formula: object, oid: str) -> Tuple[float, float, str]:
    """Return ``(lower, upper, state_str)`` for formula at ontology id oid"""
    try:
        data = formula.get_data(oid)
        if "torch" in sys.modules:
            import torch  # type: ignore
            if isinstance(data, torch.Tensor):
                flat = data.detach().float().cpu().view(-1).numpy()
                if len(flat) >= 2:
                    return float(flat[0]), float(flat[1]), str(formula.state(oid))
                if len(flat) == 1:
                    v = float(flat[0])
                    return v, v, str(formula.state(oid))
    except Exception:
        pass
    try:
        state = str(formula.state(oid))
    except Exception:
        return 0.0, 1.0, "MISSING"
    upper = state.upper()
    if upper.endswith("TRUE"):
        return 1.0, 1.0, state
    if upper.endswith("FALSE"):
        return 0.0, 0.0, state
    return 0.0, 1.0, state

def bound_summary_for_split(art: NativeLNNArtifacts, split: SplitData) -> Dict[str, float]:
    """Aggregate mean lower/upper bounds and contradiction counts over a split"""
    inc_l, inc_u, con_l, con_u = [], [], [], []
    for oid in split.ids:
        l, u, _ = _formula_bounds(art.final_disjunction, oid)
        inc_l.append(l); inc_u.append(u)
        if art.consistent_final_disjunction is not None:
            l2, u2, _ = _formula_bounds(art.consistent_final_disjunction, oid)
            con_l.append(l2); con_u.append(u2)
    out = {
        "inc_lower_mean": float(np.mean(inc_l)) if inc_l else 0.0,
        "inc_upper_mean": float(np.mean(inc_u)) if inc_u else 0.0,
        "inc_width_mean": float(np.mean(np.asarray(inc_u) - np.asarray(inc_l))) if inc_l else 0.0,
        "inc_contradictions": float(sum(1 for l, u in zip(inc_l, inc_u) if l > u)),
    }
    if con_l:
        out.update({
            "con_lower_mean": float(np.mean(con_l)),
            "con_upper_mean": float(np.mean(con_u)),
            "con_width_mean": float(np.mean(np.asarray(con_u) - np.asarray(con_l))),
            "con_contradictions": float(sum(1 for l, u in zip(con_l, con_u) if l > u)),
        })
    return out

def _formula_score(formula: object, oid: str) -> Tuple[float, str]:
    """Scalar score in [0,1] for formula at oid: midpoint of the belief interval"""
    try:
        data = formula.get_data(oid)
        if "torch" in sys.modules:
            import torch  # type: ignore
            if isinstance(data, torch.Tensor):
                flat = data.detach().float().cpu().view(-1).numpy()
                if len(flat) >= 2:
                    return float((flat[0] + flat[1]) / 2.0), str(formula.state(oid))
                if len(flat) == 1:
                    return float(flat[0]), str(formula.state(oid))
    except Exception:
        pass
    try:
        state = str(formula.state(oid))
    except Exception:
        return 0.5, "MISSING"
    upper = state.upper()
    if upper.endswith("TRUE"):
        return 1.0, state
    if upper.endswith("FALSE"):
        return 0.0, state
    return 0.5, state

def _target_or_final_score(primary: object, fallback: object, oid: str, fallback_prefix: str) -> Tuple[float, str]:
    """Score primary; fall back to fallback when primary is UNKNOWN/MISSING"""
    score, state = _formula_score(primary, oid)
    if state.endswith("UNKNOWN") or state == "MISSING":
        score, state = _formula_score(fallback, oid)
        return score, f"{fallback_prefix}:{state}"
    return score, state

def score_split(art: NativeLNNArtifacts, split: SplitData, feature_vocab: Sequence[str], inference_direction: str, prediction_mode: str, max_infer_steps: int) -> Tuple[List[float], Counter, float]:
    """Add facts, run inference, return ``(scores, state_counts, elapsed_seconds)``"""
    t0 = time.perf_counter()
    add_split_facts(art, split, feature_vocab, with_labels=False)
    infer_model(art, inference_direction, max_infer_steps)
    scores: List[float] = []
    states: Counter = Counter()
    for oid in split.ids:
        inc_score, inc_state = _target_or_final_score(art.target_pred, art.final_disjunction, oid, "Final")
        inc_l, inc_u, _ = _formula_bounds(art.final_disjunction, oid)
        if art.signed_evidence and art.consistent_final_disjunction is not None:
            con_score, con_state = _target_or_final_score(
                art.consistent_pred, art.consistent_final_disjunction, oid, "ConsistentFinal"
            )
            con_l, con_u, _ = _formula_bounds(art.consistent_final_disjunction, oid)
            if prediction_mode == "bounds":
                # Combine inc lower-bound with (1 - con upper-bound): agreement -> high score
                score = max(0.0, min(1.0, 0.5 * (inc_l + (1.0 - con_u))))
            else:
                # Shift difference into [0,1]: pure inconsistent -> 1, pure consistent -> 0
                score = max(0.0, min(1.0, 0.5 * (inc_score - con_score + 1.0)))
            state = f"Signed(inc={inc_state},con={con_state})"
        else:
            score, state = (inc_l, inc_state) if prediction_mode == "bounds" else (inc_score, inc_state)
        scores.append(float(score))
        states[state] += 1
    return scores, states, time.perf_counter() - t0

def state_counts_for_split(art: NativeLNNArtifacts, split: SplitData, names: Sequence[str]) -> Dict[str, Dict[str, int]]:
    """Count LNN state labels (TRUE/FALSE/UNKNOWN/…) per formula over split"""
    out: Dict[str, Dict[str, int]] = {}
    for name in names:
        formula = art.all_formulas[name]
        c: Counter = Counter()
        for oid in split.ids:
            try:
                c[str(formula.state(oid))] += 1
            except Exception:
                c["MISSING"] += 1
        out[name] = dict(c)
    return out

def format_state_counts(counts: Mapping[str, Mapping[str, int]], max_items: int = 4) -> str:
    """One-line summary of state-count dicts for console logging"""
    parts = []
    for name, c in counts.items():
        top = ",".join(f"{k.split('.')[-1]}:{v}" for k, v in Counter(c).most_common(max_items))
        parts.append(f"{name}[{top}]")
    return "  ".join(parts)

def evaluate_split(art: NativeLNNArtifacts, split: SplitData, feature_vocab: Sequence[str], threshold: float, split_name: str, inference_direction: str, prediction_mode: str, max_infer_steps: int) -> Dict[str, float]:
    """Score split, print metrics, and return the full metrics dict"""
    scores, states, infer_s = score_split(art, split, feature_vocab, inference_direction, prediction_mode, max_infer_steps)
    y_pred = [1 if s >= threshold else 0 for s in scores]
    m = binary_metrics(split.labels, y_pred, scores)
    m["inference_seconds"] = infer_s
    m.update(bound_summary_for_split(art, split))
    m.update(score_class_summary(split.labels, scores))
    print(
        f"  {split_name:>5s} -> Acc {m['acc']:.4f}  BAcc {m['bacc']:.4f}  "
        f"Prec {m['prec']:.4f}  Rec {m['rec']:.4f}  F1 {m['f1']:.4f}  "
        f"Score μ/min/max {m.get('mean_score', 0):.3f}/{m.get('min_score', 0):.3f}/{m.get('max_score', 0):.3f}  "
        f"Bounds incL/incU/w {m.get('inc_lower_mean', 0):.3f}/{m.get('inc_upper_mean', 0):.3f}/{m.get('inc_width_mean', 0):.3f}  "
        f"Thr {threshold:.4f}  mode={prediction_mode}  (infer {_fmt_time(infer_s)})",
        flush=True,
    )
    print(
        f"          class scores: pos μ/min/max {m.get('pos_score_mean', 0):.3f}/{m.get('pos_score_min', 0):.3f}/{m.get('pos_score_max', 0):.3f}  "
        f"neg μ/min/max {m.get('neg_score_mean', 0):.3f}/{m.get('neg_score_min', 0):.3f}/{m.get('neg_score_max', 0):.3f}",
        flush=True,
    )
    if states:
        print("          target states: " + ", ".join(f"{k}:{v}" for k, v in states.most_common(4)), flush=True)
    return m

def _loss_to_float(loss_value: object) -> float:
    """Recursively reduce a nested loss value (tensor / list / scalar) to a Python float"""
    if isinstance(loss_value, (list, tuple)):
        vals = [_loss_to_float(v) for v in loss_value]
        return float(sum(vals)) if vals else 0.0
    try:
        if hasattr(loss_value, "detach"):
            return float(loss_value.detach().cpu())
        return float(loss_value)
    except Exception:
        return 0.0

def _train_return_loss(train_return: object) -> Tuple[float, List[float]]:
    """Unpack ``Model.train(...)`` output into ``(total_loss, per-component list)``"""
    try:
        (running_loss, loss_history), _inference_history = train_return
    except Exception:
        return _loss_to_float(train_return), []
    components: List[float] = []
    if loss_history:
        last = loss_history[-1]
        if isinstance(last, (list, tuple)):
            components = [_loss_to_float(v) for v in last]
        else:
            components = [_loss_to_float(last)]
        return float(sum(components)), components
    if running_loss:
        return _loss_to_float(running_loss[-1]), []
    return 0.0, []

def train_native_lnn(
    art: NativeLNNArtifacts,
    train_split: SplitData,
    feature_vocab: Sequence[str],
    epochs: int,
    lr: float,
    losses: Sequence[str],
    monitor_every: int,
    inference_direction: str,
    max_infer_steps: int,
    loss_coeffs: Mapping[str, float],
    bidir_after_epoch: int,
    early_stopping: bool = False,
    early_stopping_patience: int = 20,
    early_stopping_min_delta: float = 5e-4,
    early_stopping_warmup: int = 15,
) -> Tuple[float, List[Dict[str, object]]]:
    loss_lookup = {
        "supervised": art.Loss.SUPERVISED,
        "logical": art.Loss.LOGICAL,
        "contradiction": art.Loss.CONTRADICTION,
        "uncertainty": art.Loss.UNCERTAINTY,
    }
    lnn_losses = {loss_lookup[name]: float(loss_coeffs.get(name, 1.0)) for name in losses}
    history: List[Dict[str, object]] = []
    final_loss = 0.0
    best_loss = float("inf")
    epochs_since_improvement = 0
    stopped_early = False
    monitor_names = [
        name for name in (
            ["Inconsistent", "OR_final", "Consistent", "OR_consistent_final"]
            + [f"OR_{g}" for g in art.feature_groups.keys()]
            + [f"OR_consistent_{g}" for g in art.feature_groups.keys()]
            + [f"Inconsistent_{g}" for g in art.feature_groups.keys()]
            + [f"Consistent_{g}" for g in art.feature_groups.keys()]
        )
        if name in art.all_formulas
    ]
    for epoch in range(1, epochs + 1):
        ep_t0 = time.perf_counter()
        epoch_direction_name = "upward" if (inference_direction == "bidirectional" and bidir_after_epoch > 0 and epoch <= bidir_after_epoch) else inference_direction
        direction = resolve_inference_direction(art, epoch_direction_name)
        train_kwargs = {"losses": lnn_losses, "learning_rate": lr, "epochs": 1}
        if direction is not None:
            train_kwargs["direction"] = direction
        if max_infer_steps and max_infer_steps > 0:
            train_kwargs["max_steps"] = int(max_infer_steps)
        train_return = art.model.train(**train_kwargs)
        infer_model(art, epoch_direction_name, max_infer_steps)
        final_loss, loss_components = _train_return_loss(train_return)
        rec: Dict[str, object] = {
            "epoch": epoch,
            "loss": final_loss,
            "loss_components": loss_components,
            "seconds": time.perf_counter() - ep_t0,
        }
        if epoch == 1 or epoch == epochs or (monitor_every > 0 and epoch % monitor_every == 0):
            counts = state_counts_for_split(art, train_split, monitor_names)
            rec["state_counts"] = counts
            comp = ""
            if loss_components:
                comp = "  components=" + ",".join(
                    f"{name}:{value:.6f}(coef={float(loss_coeffs.get(name, 1.0)):.3g})"
                    for name, value in zip(losses, loss_components)
                )
            print(
                f"    epoch {epoch:03d}/{epochs}  direction={epoch_direction_name}  loss={final_loss:.6f}{comp}  "
                f"time={_fmt_time(float(rec['seconds']))}  {format_state_counts(counts)}",
                flush=True,
            )
        history.append(rec)
        # ── early stopping ────────────────────────────────────────────────
        if early_stopping and epoch > early_stopping_warmup:
            if best_loss - final_loss > early_stopping_min_delta:
                best_loss = final_loss
                epochs_since_improvement = 0
            else:
                epochs_since_improvement += 1
                if epochs_since_improvement >= early_stopping_patience:
                    print(
                        f"    early stopping at epoch {epoch:03d}/{epochs}: "
                        f"no improvement > {early_stopping_min_delta:g} in last "
                        f"{early_stopping_patience} epochs (best loss={best_loss:.6f}, "
                        f"current={final_loss:.6f}, warmup={early_stopping_warmup})",
                        flush=True,
                    )
                    stopped_early = True
                    break
        elif early_stopping:
            # During warmup, track best loss but don't count toward patience
            if final_loss < best_loss:
                best_loss = final_loss
    if early_stopping and not stopped_early:
        print(
            f"    training completed without triggering early stopping "
            f"(best loss={best_loss:.6f}, final={final_loss:.6f})",
            flush=True,
        )
    return final_loss, history

def _agg(runs: Sequence[Mapping[str, object]], split: str, key: str) -> Tuple[float, float]:
    vals = np.asarray([float(run[split][key]) for run in runs], dtype=float)  # type: ignore[index]
    return float(vals.mean()), float(vals.std())

def print_aggregate(label: str, runs: Sequence[Mapping[str, object]]) -> None:
    train_secs = np.asarray([float(r["train_seconds"]) for r in runs], dtype=float)
    test_inf = np.asarray([float(r["test"]["inference_seconds"]) for r in runs], dtype=float)  # type: ignore[index]
    print("\n" + "=" * 78)
    print(f"Aggregated over {len(runs)} seed(s) -- {label}")
    print("=" * 78)
    for split in ["train", "val", "test"]:
        a_m, a_s = _agg(runs, split, "acc")
        b_m, b_s = _agg(runs, split, "bacc")
        p_m, p_s = _agg(runs, split, "prec")
        r_m, r_s = _agg(runs, split, "rec")
        f_m, f_s = _agg(runs, split, "f1")
        print(
            f"  {split:>5s} : Acc {a_m100:5.2f} +/-{a_s100:.2f}  "
            f"BAcc {b_m100:5.2f} +/-{b_s100:.2f}  "
            f"Prec {p_m100:5.2f} +/-{p_s100:.2f}  "
            f"Rec {r_m100:5.2f} +/-{r_s100:.2f}  "
            f"F1 {f_m100:5.2f} +/-{f_s100:.2f}"
        )
    print(f"  Training (wall): {_fmt_time(train_secs.mean())}  +/-{train_secs.std():.2f}s")
    print(f"  Test inference:  {_fmt_time(test_inf.mean())}  +/-{test_inf.std():.3f}s")
    a_m, a_s = _agg(runs, "test", "acc")
    p_m, p_s = _agg(runs, "test", "prec")
    r_m, r_s = _agg(runs, "test", "rec")
    print("\n" + "=" * 78)
    print(f"Paper-table row -- {label}:")
    print("=" * 78)
    print(
        f"{label} & "
        f"${a_m100:5.2f}_{{({a_s100:.2f})}}$ & "
        f"${p_m100:5.2f}_{{({p_s100:.2f})}}$ & "
        f"${r_m100:5.2f}_{{({r_s100:.2f})}}$ & "
        f"{_fmt_time(train_secs.mean())} & "
        f"{_fmt_time(test_inf.mean())} \\\\"  # LaTeX row ending
    )
    print("=" * 78)

def save_json(path: str, payload: Mapping[str, object]) -> None:
    """Serialise payload as indented JSON, creating parent directories as needed"""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

def validate_args(args: argparse.Namespace) -> None:
    """Validate CLI args and populate derived fields (loss_list, loss_coeffs, early_stopping_warmup)"""
    if not (0 < args.sample_frac <= 1):
        raise ValueError("--sample_frac must satisfy 0 < sample_frac <= 1")
    if args.max_features <= 0 or args.min_df <= 0 or args.epochs <= 0 or args.lr <= 0:
        raise ValueError("--max_features, --min_df, --epochs, and --lr must be positive")
    if not (0 <= args.threshold <= 1):
        raise ValueError("--threshold must be in [0, 1]")
    valid = {"supervised", "logical", "contradiction", "uncertainty"}
    losses = [x.strip().lower() for x in args.losses.split(',') if x.strip()]
    bad = [x for x in losses if x not in valid]
    if bad:
        raise ValueError(f"Unsupported --losses entries: {bad}")
    if not losses:
        raise ValueError("--losses must contain at least one entry")
    for name in ["supervised_coeff", "logical_coeff", "contradiction_coeff", "uncertainty_coeff"]:
        if getattr(args, name) < 0:
            raise ValueError(f"--{name} must be non-negative")
    if args.bidir_after_epoch < 0:
        raise ValueError("--bidir_after_epoch must be >= 0")
    if args.early_stopping_patience <= 0:
        raise ValueError("--early_stopping_patience must be > 0")
    if args.early_stopping_min_delta < 0:
        raise ValueError("--early_stopping_min_delta must be >= 0")
    if args.early_stopping_warmup < 0:
        args.early_stopping_warmup = max(args.bidir_after_epoch, 15)
    if getattr(args, "init_noise_std_frac", 0.0) < 0:
        raise ValueError("--init_noise_std_frac must be >= 0")
    args.loss_list = losses
    args.loss_coeffs = {
        "supervised": args.supervised_coeff,
        "logical": args.logical_coeff,
        "contradiction": args.contradiction_coeff,
        "uncertainty": args.uncertainty_coeff,
    }

def load_splits_and_features(args: "argparse.Namespace") -> Tuple[SplitData, SplitData, SplitData, List[str], List[str]]:
    """Load all three splits and build the feature vocabulary from the train split only"""
    set_csv_field_limit()
    train_split = load_split(args.train, "train", args)
    val_split = load_split(args.val, "val", args)
    test_split = load_split(args.test, "test", args)
    if args.feature_selection == "supervised":
        raw_vocab = build_feature_vocab_supervised(train_split.feature_sets, train_split.labels, args.max_features, args.min_df)
    else:
        raw_vocab = build_feature_vocab(train_split.feature_sets, args.max_features, args.min_df)
    feature_vocab = expand_with_absence_features(raw_vocab) if args.include_absence_features else list(raw_vocab)
    return train_split, val_split, test_split, raw_vocab, feature_vocab

# diagnostics

FIXED_DEFAULTS = {
    "epochs": DEFAULT_EPOCHS,
    "lr": DEFAULT_LR,
    "seeds": ",".join(map(str, DEFAULT_SEEDS)),
    "threshold_metric": "bacc",
    "losses": "supervised",
    "supervised_coeff": 1.0,
    "logical_coeff": 1.0,
    "contradiction_coeff": 0.0,
    "uncertainty_coeff": 0.0,
    "max_features": DEFAULT_MAX_FEATURES,
    "min_df": DEFAULT_MIN_DF,
    "feature_selection": "supervised",
    "signed_evidence": False,
    "ontology_rules": False,
    "inference_direction": "upward",
    "max_infer_steps": 0,
    "bidir_after_epoch": 0,
    "prediction_mode": "score",
    "init_weight": DEFAULT_INIT_WEIGHT,
    "init_bias": DEFAULT_INIT_BIAS,
    "final_init_weight": DEFAULT_FINAL_INIT_WEIGHT,
    "final_init_bias": DEFAULT_FINAL_INIT_BIAS,
    "top_k_per_group": DEFAULT_TOP_K_PER_GROUP,
}
def robust_best_threshold(
    y_true: Sequence[int],
    scores: Sequence[float],
    metric: str,
) -> Tuple[float, float, float]:
    """Pick a threshold that maximises 'metric' but is not degenerate
    Returns ``(threshold, metric_value, bacc)``.
    If  best balanced accuracy across thresholds is <= 0.51 (model essentially random), we
    fall back to the median of ``scores`` so downstream metrics expose
    the failure honestly instead of being masked by an all-positive
    threshold (rec=1.0, f1=2*p/(p+1))
    """
    yt = np.asarray(y_true, dtype=np.int64)
    sc = np.asarray(scores, dtype=float)
    if len(sc) == 0:
        return DEFAULT_THRESHOLD, 0.0, 0.0
    metric = str(metric).lower()
    uniq = np.unique(sc)
    candidates: List[float] = [DEFAULT_THRESHOLD, float(max(0.0, uniq[0] - 1e-12))]
    if len(uniq) > 1:
        candidates.extend(float(x) for x in ((uniq[:-1] + uniq[1:]) / 2.0))
    candidates.extend(float(x) for x in uniq)
    candidates.append(float(min(1.0, uniq[-1] + 1e-12)))
    best_t, best_value, best_bacc = DEFAULT_THRESHOLD, -1.0, -1.0
    overall_best_bacc = -1.0
    for t in candidates:
        m = binary_metrics(yt, (sc >= t).astype(np.int64), sc)
        value = float(m["bacc"]) if metric == "bacc" else float(m.get(metric, 0.0))
        bacc = float(m["bacc"])
        overall_best_bacc = max(overall_best_bacc, bacc)
        # Reject thresholds where one class gets zero predictions.
        degenerate = (m["tp"] + m["fp"] == 0) or (m["tn"] + m["fn"] == 0)
        score_tuple = (value, bacc, -abs(t - 0.5))
        best_tuple = (best_value, best_bacc, -abs(best_t - 0.5))
        if (not degenerate) and score_tuple > best_tuple:
            best_t, best_value, best_bacc = float(t), value, bacc
    if overall_best_bacc <= 0.51:
        median = float(np.median(sc))
        m = binary_metrics(yt, (sc >= median).astype(np.int64), sc)
        return median, float(m["bacc"] if metric == "bacc" else m.get(metric, m["bacc"])), float(m["bacc"])
    return best_t, best_value, best_bacc

def _expected_feature_rates(train_split: SplitData, feature_vocab: Sequence[str]) -> Dict[str, float]:
    """Per-feature activation rate on the training split"""
    n = max(1, len(train_split.ids))
    rates = {}
    for feat in feature_vocab:
        active = 0
        for fs in train_split.feature_sets:
            if model_feature_active(feat, fs):
                active += 1
        rates[feat] = active / n
    return rates

def data_aware_reinit_or_neurons(art: NativeLNNArtifacts, train_split: SplitData, feature_vocab: Sequence[str], c: float = 0.5,
                                 verbose: bool = True) -> None:
    """Re-initialise each OR neuron so its output sits near c/2 (~0.25)
    for a typical train sample"""
    try:
        import torch  # type: ignore
    except Exception as exc:
        if verbose:
            print(f"  (warn: torch not importable, skipping data-aware init: {exc})")
        return
    rates = _expected_feature_rates(train_split, feature_vocab)
    polarities = art.feature_polarities or {}
    # group-level OR neurons (Inconsistent side)
    group_expected_out: Dict[str, float] = {}
    for group_name, group_feats in art.feature_groups.items():
        formula = art.group_disjunctions.get(group_name)
        if formula is None or not hasattr(formula, "neuron") or not hasattr(formula.neuron, "weights"):
            continue
        if art.signed_evidence:
            inputs = [f for f in group_feats if polarities.get(f, 1) >= 0]
        else:
            inputs = list(group_feats)
        if len(inputs) <= 1:
            continue  # passthrough, not a trainable OR
        mu_sum = float(sum(rates.get(f, 0.0) for f in inputs))
        if mu_sum < 1e-3:
            mu_sum = 1.0  # cold group; leave it cold
        try:
            with torch.no_grad():
                w = c / mu_sum
                formula.neuron.weights.fill_(float(w))
                formula.neuron.bias.fill_(float(-c / 2.0))
            # Approx expected output for OR_final init (clipped to [0,1]).
            group_expected_out[group_name] = max(0.0, min(1.0, c - c / 2.0))
            if verbose:
                print(f"    init OR_{group_name}: n={len(inputs)} mu_sum={mu_sum:.2f} "
                      f"w={w:.4f} bias={-c/2.0:+.3f}")
        except Exception as exc:
            if verbose:
                print(f"  (warn: could not re-init OR_{group_name}: {exc})")
    # group-level OR neurons (Consistent side, signed-evidence only)
    if art.signed_evidence:
        for group_name, group_feats in art.feature_groups.items():
            formula = art.consistent_group_disjunctions.get(group_name)
            if formula is None or not hasattr(formula, "neuron") or not hasattr(formula.neuron, "weights"):
                continue
            inputs = [f for f in group_feats if polarities.get(f, 1) < 0]
            if len(inputs) <= 1:
                continue
            mu_sum = float(sum(rates.get(f, 0.0) for f in inputs))
            if mu_sum < 1e-3:
                mu_sum = 1.0
            try:
                with torch.no_grad():
                    w = c / mu_sum
                    formula.neuron.weights.fill_(float(w))
                    formula.neuron.bias.fill_(float(-c / 2.0))
            except Exception as exc:
                if verbose:
                    print(f"  (warn: could not re-init OR_consistent_{group_name}: {exc})")
    # final OR over group sub-ORs
    final = art.final_disjunction
    if final is not None and hasattr(final, "neuron") and hasattr(final.neuron, "weights"):
        try:
            with torch.no_grad():
                n_inputs = int(final.neuron.weights.numel())
                if n_inputs > 1:
                    # Each sub-OR has expected output approx c/2 = 0.25
                    expected_sum = max(0.1, n_inputs * (c / 2.0))
                    w = c / expected_sum
                    final.neuron.weights.fill_(float(w))
                    final.neuron.bias.fill_(float(-c / 2.0))
                    if verbose:
                        print(f"    init OR_final: n={n_inputs} expected_sum={expected_sum:.2f} "
                              f"w={w:.4f} bias={-c/2.0:+.3f}")
        except Exception as exc:
            if verbose:
                print(f"  (warn: could not re-init OR_final: {exc})")
    # consistent_final_disjunction (signed-evidence only)
    cfinal = art.consistent_final_disjunction
    if cfinal is not None and hasattr(cfinal, "neuron") and hasattr(cfinal.neuron, "weights"):
        try:
            with torch.no_grad():
                n_inputs = int(cfinal.neuron.weights.numel())
                if n_inputs > 1:
                    expected_sum = max(0.1, n_inputs * (c / 2.0))
                    w = c / expected_sum
                    cfinal.neuron.weights.fill_(float(w))
                    cfinal.neuron.bias.fill_(float(-c / 2.0))
        except Exception as exc:
            if verbose:
                print(f"  (warn: could not re-init OR_consistent_final: {exc})")

def perturb_or_neurons(art: NativeLNNArtifacts, std_frac: float, seed: int, verbose: bool = True) -> None:
    """
    Apply small seed-dependent Gaussian noise to every OR neuron's per-input
    weights so different --seeds land in different parameter basins

    The noise is multiplicative around the existing (data-aware) weight value:
        w_i <- w_i * (1 + N(0, std_frac))
    Biases are left untouched so the mean pre-activation stays at c/2
    """
    if std_frac is None or std_frac <= 0.0:
        return
    try:
        import torch  # type: ignore
    except Exception as exc:
        if verbose:
            print(f"  (warn: torch unavailable, skipping init noise: {exc})")
        return
    gen = torch.Generator(device="cpu")
    gen.manual_seed(int(seed) * 1_000_003 + 17)
    formulas = []
    formulas.extend(art.group_disjunctions.values())
    if getattr(art, "consistent_group_disjunctions", None):
        formulas.extend(art.consistent_group_disjunctions.values())
    if getattr(art, "final_disjunction", None) is not None:
        formulas.append(art.final_disjunction)
    if getattr(art, "consistent_final_disjunction", None) is not None:
        formulas.append(art.consistent_final_disjunction)
    perturbed = 0
    with torch.no_grad():
        for formula in formulas:
            if formula is None or not hasattr(formula, "neuron") or not hasattr(formula.neuron, "weights"):
                continue
            w = formula.neuron.weights
            if w.numel() <= 1:
                continue
            noise = torch.randn(w.shape, generator=gen, dtype=w.dtype, device=w.device) * float(std_frac)
            w.mul_(1.0 + noise).clamp_(min=0.0)
            perturbed += 1
    if verbose:
        print(f"    init noise: perturbed {perturbed} OR neurons with std_frac={std_frac:.3g} (seed={seed})")

def add_split_facts_no_pred_labels(art: NativeLNNArtifacts, split: SplitData, feature_vocab: Sequence[str], with_labels: bool) -> None:
    """Like ``add_split_facts`` but only labels the trainable OR formulas, not the open-world predicates.

    Used during training so the OPEN-world pred labels do not interfere with LNN supervision.
    """
    Fact = art.Fact
    feature_data = {feat: {} for feat in feature_vocab}
    ontology_rule_data = {name: {} for name in art.ontology_rule_preds}
    target_data = {}
    consistent_data = {}
    group_data = {name: {} for name in art.group_preds}
    target_labels = {}
    consistent_labels = {}
    for oid, y, feats in zip(split.ids, split.labels, split.feature_sets):
        target_data[oid] = Fact.UNKNOWN
        consistent_data[oid] = Fact.UNKNOWN
        for group_name in group_data:
            group_data[group_name][oid] = Fact.UNKNOWN
        for feat in feature_vocab:
            feature_data[feat][oid] = (
                FEATURE_PRESENT_BOUNDS
                if model_feature_active(feat, feats) else Fact.FALSE
            )
        active = ontology_rule_atoms_from_features(feats)
        for rule_name in ontology_rule_data:
            ontology_rule_data[rule_name][oid] = (
                FEATURE_PRESENT_BOUNDS if rule_name in active else Fact.FALSE
            )
        if with_labels:
            if int(y) == 1:
                target_labels[oid] = Fact.TRUE
                consistent_labels[oid] = Fact.FALSE
            else:
                target_labels[oid] = Fact.FALSE
                consistent_labels[oid] = Fact.TRUE
    for feat, pred in art.feature_preds.items():
        pred.add_data(feature_data[feat])
    for rule_name, pred in art.ontology_rule_preds.items():
        pred.add_data(ontology_rule_data[rule_name])
    for group_name, pred in art.group_preds.items():
        pred.add_data(group_data[group_name])
    for group_name, pred in art.consistent_group_preds.items():
        pred.add_data(group_data[group_name])
    art.target_pred.add_data(target_data)
    art.consistent_pred.add_data(consistent_data)
    if with_labels:
        # Only label the trainable formulas
        # NOT the OPEN-world predicates
        try:
            art.final_disjunction.add_labels(target_labels)
        except Exception:
            pass
        if art.consistent_final_disjunction is not None:
            try:
                art.consistent_final_disjunction.add_labels(consistent_labels)
            except Exception:
                pass

def filter_top_k_per_group(feature_vocab: Sequence[str], train_split: SplitData, top_k: int) -> List[str]:
    """
    Return a feature subset keeping only the top-K most label-correlated
    features per logical group, computed on the train split only
    """
    if top_k is None or top_k <= 0:
        return list(feature_vocab)
    groups = build_feature_groups(feature_vocab)
    n = max(1, len(train_split.ids))
    pos_total = max(1, int(np.sum(train_split.labels)))
    neg_total = max(1, n - pos_total)
    scores = {}
    for feat in feature_vocab:
        ap = an = 0
        for y, fs in zip(train_split.labels, train_split.feature_sets):
            if model_feature_active(feat, fs):
                if int(y) == 1:
                    ap += 1
                else:
                    an += 1
        # Absolute log-odds-ish score; tied breaker = total support
        rate_p = ap / pos_total
        rate_n = an / neg_total
        scores[feat] = (abs(rate_p - rate_n), rate_p + rate_n)
    keep = []
    for gname, gfeats in groups.items():
        ranked = sorted(gfeats, key=lambda f: scores.get(f, (0.0, 0.0)), reverse=True)
        keep.extend(ranked[:top_k])
    # Preserve original order
    keep_set = set(keep)
    return [f for f in feature_vocab if f in keep_set]

def dump_neuron_params(art: NativeLNNArtifacts, label: str, max_groups: int = 6) -> None:
    """Print weight/bias statistics for the first max_groups Or-neurons (debug aid)"""
    try:
        import torch  # type: ignore
    except Exception:
        return
    print(f"  [{label}] neuron parameter snapshot:", flush=True)
    items = list(art.group_disjunctions.items())[:max_groups]
    for gname, formula in items:
        try:
            with torch.no_grad():
                w = formula.neuron.weights.detach().float().view(-1)
                b = float(formula.neuron.bias.detach().float().view(-1)[0])
            print(f"    OR_{gname}: w mean={float(w.mean()):.4f} std={float(w.std()):.4f} "
                  f"min={float(w.min()):.4f} max={float(w.max()):.4f} bias={b:+.4f}",
                  flush=True)
        except Exception as exc:
            print(f"    OR_{gname}: <unreadable: {exc}>", flush=True)
    final = art.final_disjunction
    if final is not None and hasattr(final, "neuron") and hasattr(final.neuron, "weights"):
        try:
            import torch  # type: ignore
            with torch.no_grad():
                w = final.neuron.weights.detach().float().view(-1)
                b = float(final.neuron.bias.detach().float().view(-1)[0])
            print(f"    OR_final  : w={[f'{x:.4f}' for x in w.tolist()]} bias={b:+.4f}", flush=True)
        except Exception as exc:
            print(f"    OR_final  : <unreadable: {exc}>", flush=True)

def run_one_seed_fixed(
    train_split,
    val_split,
    test_split,
    feature_vocab,
    *,
    seed: int,
    epochs: int,
    lr: float,
    losses: Sequence[str],
    threshold: float,
    tune_threshold_on_val: bool,
    monitor_every: int,
    init_weight: float,
    init_bias: float,
    final_init_weight: float,
    final_init_bias: float,
    normalize_init: bool,
    shuffle_train_labels: bool,
    signed_evidence: bool,
    enable_ontology_rules: bool,
    inference_direction: str,
    prediction_mode: str,
    max_infer_steps: int,
    loss_coeffs: Mapping[str, float],
    threshold_metric: str,
    bidir_after_epoch: int,
    early_stopping: bool = False,
    early_stopping_patience: int = 20,
    early_stopping_min_delta: float = 5e-4,
    early_stopping_warmup: int = 15,
    data_aware_init: bool = True,
    data_aware_init_c: float = 0.5,
    init_noise_std_frac: float = 0.05,
    debug_neurons: bool = False,
) -> Dict[str, object]:
    """Full train-eval cycle for one seed: build LNN, init, train, tune threshold, evaluate all splits"""
    set_seed(seed)
    train_for_seed = train_split
    if shuffle_train_labels:
        rng = np.random.default_rng(seed + SHUFFLE_SEED_OFFSET)
        labels = train_split.labels.copy()
        rng.shuffle(labels)
        train_for_seed = SplitData(
            train_split.name, train_split.ids, labels, train_split.feature_sets
        )
    effective_signed = signed_evidence and len(train_for_seed.ids) >= SIGNED_EVIDENCE_MIN_TRAIN
    if signed_evidence and not effective_signed:
        print(
            f"  [seed {seed}] WARNING: --signed_evidence disabled because train size "
            f"{len(train_for_seed.ids)} < {SIGNED_EVIDENCE_MIN_TRAIN}; per-feature "
            f"polarity is too noisy at this scale.",
            flush=True,
        )
    feature_polarities = (
        compute_feature_polarities(train_for_seed, feature_vocab) if effective_signed else None
    )
    art = build_native_lnn(
        feature_vocab, init_weight, init_bias, final_init_weight, final_init_bias, normalize_init,
        feature_polarities=feature_polarities, signed_evidence=effective_signed,
        enable_ontology_rules=enable_ontology_rules,
    )
    print(
        f"  [seed {seed}] LNN train pos={train_for_seed.n_pos} neg={train_for_seed.n_neg} "
        f"features={len(feature_vocab)} groups="
        + ",".join(f"{k}:{len(v)}" for k, v in art.feature_groups.items())
        + (" signed_evidence=on" if effective_signed else " signed_evidence=off")
        + (" ontology_rules=on" if enable_ontology_rules else " ontology_rules=off")
        + f" inference={inference_direction} prediction={prediction_mode}"
        + f" threshold_metric={threshold_metric}"
        + (f" bidir_after_epoch={bidir_after_epoch}" if bidir_after_epoch > 0 else ""),
        flush=True,
    )
    if data_aware_init:
        print(f"  [seed {seed}] data-aware OR re-initialisation:", flush=True)
        data_aware_reinit_or_neurons(art, train_for_seed, feature_vocab, c=data_aware_init_c)
    if init_noise_std_frac and init_noise_std_frac > 0.0:
        perturb_or_neurons(art, init_noise_std_frac, seed)
    if debug_neurons:
        dump_neuron_params(art, f"seed {seed} after init")
    add_split_facts_no_pred_labels(art, train_for_seed, feature_vocab, with_labels=True)
    t0 = time.perf_counter()
    final_loss, history = train_native_lnn(
        art, train_for_seed, feature_vocab, epochs, lr, losses, monitor_every,
        inference_direction, max_infer_steps, loss_coeffs, bidir_after_epoch,
        early_stopping=early_stopping,
        early_stopping_patience=early_stopping_patience,
        early_stopping_min_delta=early_stopping_min_delta,
        early_stopping_warmup=early_stopping_warmup,
    )
    train_seconds = time.perf_counter() - t0
    if debug_neurons:
        dump_neuron_params(art, f"seed {seed} after training")
    # Health check on final-epoch state counts.
    if effective_signed and history:
        last = history[-1].get("state_counts", {}) or {}
        c_final = last.get("OR_consistent_final", {}) or {}
        contras = sum(v for k, v in c_final.items() if "CONTRADICTION" in k.upper())
        total = sum(c_final.values()) or 1
        if contras / total > 0.2:
            print(
                f"  [seed {seed}] WARNING: Consistent head was in CONTRADICTION on "
                f"{contras}/{total} ({contras/total:.0%}) train samples at the final "
                f"epoch. Polarity assignment is unreliable; results untrustworthy.",
                flush=True,
            )
    print(f"  [seed {seed}] training finished in {_fmt_time(train_seconds)}; "
          f"loss={final_loss:.6f}", flush=True)
    final_threshold = threshold
    threshold_val_metric = None
    threshold_val_bacc = None
    if tune_threshold_on_val:
        val_scores, _states, infer_s = score_split(
            art, val_split, feature_vocab, inference_direction, prediction_mode, max_infer_steps
        )
        final_threshold, threshold_val_metric, threshold_val_bacc = robust_best_threshold(
            val_split.labels, val_scores, threshold_metric
        )
        print(
            f"  [seed {seed}] tuned threshold on val: {final_threshold:.6f} "
            f"(val {threshold_metric}={threshold_val_metric:.4f} bacc={threshold_val_bacc:.4f}, "
            f"infer {_fmt_time(infer_s)})",
            flush=True,
        )
    train_m = evaluate_split(art, train_split, feature_vocab, final_threshold, "train",
                             inference_direction, prediction_mode, max_infer_steps)
    val_m = evaluate_split(art, val_split, feature_vocab, final_threshold, "val",
                           inference_direction, prediction_mode, max_infer_steps)
    test_m = evaluate_split(art, test_split, feature_vocab, final_threshold, "test",
                            inference_direction, prediction_mode, max_infer_steps)
    return {
        "seed": seed,
        "train_seconds": train_seconds,
        "final_loss": final_loss,
        "threshold": final_threshold,
        "threshold_metric": threshold_metric,
        "threshold_val_metric": threshold_val_metric,
        "threshold_val_bacc": threshold_val_bacc,
        "loss_coeffs": dict(loss_coeffs),
        "bidir_after_epoch": bidir_after_epoch,
        "history": history,
        "train": train_m,
        "val": val_m,
        "test": test_m,
    }

def parse_args() -> argparse.Namespace:
    """Define and parse all CLI arguments"""
    p = argparse.ArgumentParser(
        description="LNN trainer for OWL ontology consistency classification.",
    )
    p.add_argument("--train", default=TRAIN_CSV)
    p.add_argument("--val", default=VAL_CSV)
    p.add_argument("--test", default=TEST_CSV)
    p.add_argument("--id_column", default="file_name")
    p.add_argument("--body_column", default="body")
    p.add_argument("--label_source", choices=["injected_pattern", "consistency"],
                   default="injected_pattern")
    p.add_argument("--positive_consistency", default="Inconsistent")
    p.add_argument("--epochs", type=int, default=FIXED_DEFAULTS["epochs"])
    p.add_argument("--lr", type=float, default=FIXED_DEFAULTS["lr"])
    p.add_argument("--seeds", default=FIXED_DEFAULTS["seeds"])
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--threshold_metric", choices=["bacc", "f1", "acc"],
                   default=FIXED_DEFAULTS["threshold_metric"])
    p.add_argument("--losses", default=FIXED_DEFAULTS["losses"])
    p.add_argument("--supervised_coeff", type=float, default=FIXED_DEFAULTS["supervised_coeff"])
    p.add_argument("--logical_coeff", type=float, default=FIXED_DEFAULTS["logical_coeff"])
    p.add_argument("--contradiction_coeff", type=float, default=FIXED_DEFAULTS["contradiction_coeff"])
    p.add_argument("--uncertainty_coeff", type=float, default=FIXED_DEFAULTS["uncertainty_coeff"])
    p.add_argument("--max_features", type=int, default=FIXED_DEFAULTS["max_features"])
    p.add_argument("--min_df", type=int, default=FIXED_DEFAULTS["min_df"])
    p.add_argument("--feature_selection", choices=["supervised", "df"],
                   default=FIXED_DEFAULTS["feature_selection"])
    p.add_argument("--include_absence_features", action="store_true")
    p.add_argument("--signed_evidence", action="store_true",
                   default=FIXED_DEFAULTS["signed_evidence"],
                   help="Auto-disabled when train split < %d samples." % SIGNED_EVIDENCE_MIN_TRAIN)
    p.add_argument("--ontology_rules", action="store_true",
                   default=FIXED_DEFAULTS["ontology_rules"])
    p.add_argument("--inference_direction",
                   choices=["upward", "downward", "bidirectional"],
                   default=FIXED_DEFAULTS["inference_direction"])
    p.add_argument("--max_infer_steps", type=int, default=FIXED_DEFAULTS["max_infer_steps"])
    p.add_argument("--bidir_after_epoch", type=int, default=FIXED_DEFAULTS["bidir_after_epoch"])
    p.add_argument("--early_stopping", dest="early_stopping", action="store_true",
                   default=True,
                   help="Stop training when train loss stops improving (loss-trajectory based).")
    p.add_argument("--no_early_stopping", dest="early_stopping", action="store_false")
    p.add_argument("--early_stopping_patience", type=int, default=20,
                   help="Epochs without >min_delta improvement before stopping. "
                        "Tuned to survive the long mid-training plateau seen in this model.")
    p.add_argument("--early_stopping_min_delta", type=float, default=5e-4,
                   help="Minimum loss decrease to count as an improvement.")
    p.add_argument("--early_stopping_warmup", type=int, default=-1,
                   help="Epochs to skip before patience counter starts. "
                        "-1 = auto (max(bidir_after_epoch, 15)).")
    p.add_argument("--prediction_mode", choices=["score", "bounds"],
                   default=FIXED_DEFAULTS["prediction_mode"])
    p.add_argument("--sample_frac", type=float, default=1.0)
    p.add_argument("--sample_seed", type=int, default=42)
    p.add_argument("--monitor_every", type=int, default=1)
    p.add_argument("--init_weight", type=float, default=FIXED_DEFAULTS["init_weight"])
    p.add_argument("--init_bias", type=float, default=FIXED_DEFAULTS["init_bias"])
    p.add_argument("--final_init_weight", type=float, default=FIXED_DEFAULTS["final_init_weight"])
    p.add_argument("--final_init_bias", type=float, default=FIXED_DEFAULTS["final_init_bias"])
    p.add_argument("--normalize_init", dest="normalize_init", action="store_true",
                   default=DEFAULT_NORMALIZE_INIT)
    p.add_argument("--no_normalize_init", dest="normalize_init", action="store_false")
    p.add_argument("--data_aware_init", dest="data_aware_init", action="store_true",
                   default=True,
                   help="Re-initialise OR neurons using train-set activation stats so each OR sits near boundary at init.")
    p.add_argument("--no_data_aware_init", dest="data_aware_init", action="store_false")
    p.add_argument("--data_aware_init_c", type=float, default=0.5,
                   help="Target activation level for each OR neuron at init (output ~ c/2).")
    p.add_argument("--init_noise_std_frac", type=float, default=0.05,
                   help="Multiplicative Gaussian noise stddev applied to OR weights after data-aware "
                        "init, seeded per --seeds. 0 = disable (deterministic across seeds).")
    p.add_argument("--top_k_per_group", type=int, default=0,
                   help="Keep only the top-K most label-correlated features per logical group "
                        "(0 = disabled). Strongly recommended: try 6-10 for selective ORs.")
    p.add_argument("--debug_neurons", action="store_true",
                   help="Dump OR neuron weight/bias before and after training (sanity check).")
    p.add_argument("--tune_threshold_on_val", dest="tune_threshold_on_val",
                   action="store_true", default=True)
    p.add_argument("--no_tune_threshold_on_val", dest="tune_threshold_on_val",
                   action="store_false")
    p.add_argument("--run_shuffled_label_control", action="store_true")
    p.add_argument("--dry_run_features", action="store_true")
    p.add_argument("--json_out", default="")
    return p.parse_args()

def main() -> None:
    """Entry point: parse args, load data, run multi-seed experiment, print/save results"""
    args = parse_args()
    validate_args(args)
    print("Loading CSV splits and extracting raw features ...", flush=True)
    train_split, val_split, test_split, raw_vocab, feature_vocab = load_splits_and_features(args)
    if getattr(args, "top_k_per_group", 0) and args.top_k_per_group > 0:
        before = len(feature_vocab)
        feature_vocab = filter_top_k_per_group(feature_vocab, train_split, args.top_k_per_group)
        print(f"  top_k_per_group={args.top_k_per_group}: {before} -> {len(feature_vocab)} features", flush=True)
    groups = build_feature_groups(feature_vocab)
    print(f"  train={len(train_split.ids)} val={len(val_split.ids)} test={len(test_split.ids)}")
    print(f"  positives: train={train_split.n_pos} val={val_split.n_pos} test={test_split.n_pos}")
    print(f"  selected raw features={len(raw_vocab)} max={args.max_features} "
          f"min_df={args.min_df} selection={args.feature_selection}")
    print("  evidence=" + ("presence+absence" if args.include_absence_features else "presence-only")
          + ("; signed heads" if args.signed_evidence else "; single inconsistency head")
          + ("; ontology rules" if args.ontology_rules else "; no ontology rules")
          + f"; inference={args.inference_direction}; max_steps={args.max_infer_steps}"
          + f"; prediction={args.prediction_mode}; threshold_metric={args.threshold_metric}"
          + f"; bidir_after_epoch={args.bidir_after_epoch}")
    print("  groups=" + ", ".join(f"{k}:{len(v)}" for k, v in groups.items()))
    print("  top features:")
    for feat in raw_vocab[:20]:
        print(f"    {feat}")
    if args.dry_run_features:
        print("--dry_run_features set; exiting before importing/training LNN")
        return
    seeds = parse_seeds(args.seeds)
    payload: Dict[str, object] = {
        "config": vars(args),
        "feature_vocab": feature_vocab,
        "feature_groups": groups,
        "runs": {},
    }
    def run_all(label: str, shuffle: bool) -> List[Dict[str, object]]:
        print(f"\n{'#' * 78}\n# Experiment: {label}"
              f"{' [shuffled train labels]' if shuffle else ''}\n{'#' * 78}")
        runs: List[Dict[str, object]] = []
        for seed in seeds:
            print(f"\n=== Seed {seed} ===", flush=True)
            runs.append(run_one_seed_fixed(
                train_split, val_split, test_split, feature_vocab,
                seed=seed, epochs=args.epochs, lr=args.lr, losses=args.loss_list,
                threshold=args.threshold, tune_threshold_on_val=args.tune_threshold_on_val,
                monitor_every=args.monitor_every, init_weight=args.init_weight,
                init_bias=args.init_bias, final_init_weight=args.final_init_weight,
                final_init_bias=args.final_init_bias, normalize_init=args.normalize_init,
                shuffle_train_labels=shuffle, signed_evidence=args.signed_evidence,
                enable_ontology_rules=args.ontology_rules,
                inference_direction=args.inference_direction,
                prediction_mode=args.prediction_mode, max_infer_steps=args.max_infer_steps,
                loss_coeffs=args.loss_coeffs, threshold_metric=args.threshold_metric,
                bidir_after_epoch=args.bidir_after_epoch,
                early_stopping=args.early_stopping,
                early_stopping_patience=args.early_stopping_patience,
                early_stopping_min_delta=args.early_stopping_min_delta,
                early_stopping_warmup=args.early_stopping_warmup,
                data_aware_init=args.data_aware_init,
                data_aware_init_c=args.data_aware_init_c,
                init_noise_std_frac=args.init_noise_std_frac,
                debug_neurons=args.debug_neurons,
            ))
        print_aggregate(label, runs)
        return runs
    payload["runs"]["real_labels"] = run_all(
        "LNN", False
    )  # type: ignore[index]
    if args.run_shuffled_label_control:
        payload["runs"]["shuffled_labels"] = run_all(
            "LNN", True
        )  # type: ignore[index]
    if args.json_out:
        save_json(args.json_out, payload)
        print(f"Wrote JSON results to: {args.json_out}")

if __name__ == "__main__":
    main()
