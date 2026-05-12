"""
LTN learns from raw triples

Each ontology x is a set of (subject, predicate, object)
We learn:
    - token embeddings  (entities/classes/properties + structural tokens
      for axiom keywords like 'some', 'only', 'inverse', 'max', ...)
    - a triple encoder MLP   f_triple : R^{3E} -> R^H
    - a set encoder          g_onto    : pool({f_triple(t)}) -> R^H
    - an LTN predicate       Inconsistent(x) : R^H -> [0,1]   (sigmoid MLP)
* LTN axioms (Real Logic, t-norm: product / aggregator: pMeanError p=2):
        Forall  x_pos in INCONSISTENT_ONTOLOGIES :   Inconsistent(x_pos)
        Forall  x_neg in CONSISTENT_ONTOLOGIES   : ~ Inconsistent(x_neg)
  Training maximises SatAgg (loss = 1 - sat_agg)
  see LTN binary-classification recipe from the official tutorials
  (logictensornetworks/.../examples/binary_classification, and
   https://logictensornetworks.github.io/LTNtorch/learningltn.html)
Outputs

Per-split sklearn metrics (acc / prec / rec / F1) for train, val, test
Wall-clock training and test-inference time (fmt_time HH:MM:SS.ss)
mean ± std aggregation over multiple seeds
Run
    python -u train/train_ltn.py
"""
from __future__ import annotations
# noinspection PyCallingNonCallable,PyTypeChecker
# (PyCharm cannot resolve tf.keras.Model.__call__ on subclassed models;
#  the calls below are valid at runtime.)
import ast
import os

# CUDA libs bootstrap (must run BEFORE import tensorflow)
def _bootstrap_cuda_libs():
    import sys, glob, importlib.util
    if os.environ.get('_LTN_CUDA_BOOTSTRAPPED') == '1':
        return
    try:
        spec = importlib.util.find_spec('nvidia')
    except (ValueError, ModuleNotFoundError):
        return
    if spec is None or not spec.submodule_search_locations:
        return
    base = spec.submodule_search_locations[0]
    lib_dirs = sorted({d for d in glob.glob(os.path.join(base, '*/lib'))
                       if os.path.isdir(d)})
    if not lib_dirs:
        return
    cur = os.environ.get('LD_LIBRARY_PATH', '')
    new = ':'.join(lib_dirs) + (':' + cur if cur else '')
    if cur == new:
        return
    os.environ['LD_LIBRARY_PATH'] = new
    os.environ['_LTN_CUDA_BOOTSTRAPPED'] = '1'
    os.execv(sys.executable, [sys.executable] + sys.argv)

_bootstrap_cuda_libs()

import random
import re
import time
from collections import Counter
from datetime import timedelta
from typing import List, Sequence, Tuple
import numpy as np
import pandas as pd
import tensorflow as tf
# noinspection PyUnresolvedReferences
try:
    import keras  # type: ignore  # standalone Keras 3
except ImportError:  # pragma: no cover
    from tensorflow import keras  # type: ignore
from sklearn.metrics import (accuracy_score, f1_score, precision_score,
                             recall_score)
import ltn  # logictensornetworks (TF backend)

TRAIN_CSV = "path/to/nsplits/train_data.csv"
VAL_CSV   = "path/to/nsplits/eval_data.csv"
TEST_CSV  = "path/to/nsplits/test_data.csv"
EMB_DIM         = 128
HID_DIM         = 512
MAX_VOCAB       = 20000
MAX_TRIPLES     = 256
BATCH_SIZE      = 64           # bigger batch -> much better GPU utilisation
EPOCHS          = 80          # upper bound
LEARNING_RATE   = 3e-4
P_MEAN_ERROR    = 2
SEEDS           = [0,1,2,3,4]
THRESHOLD       = 0.5
EARLY_STOP_PATIENCE   = 16
EARLY_STOP_MIN_DELTA  = 1e-3
# Shuffled-labels sanity-check
# permutation of the train labels (val/test labels stay real)
RUN_SHUFFLED_LABEL_CONTROL = False
SHUFFLE_SEED_OFFSET = 1000  # decouple shuffle RNG from training RNG
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

_gpus = tf.config.list_physical_devices('GPU')
if _gpus:
    try:
        for _g in _gpus:
            tf.config.experimental.set_memory_growth(_g, True)
        # Pin to a single GPU
        tf.config.set_visible_devices(_gpus[0], 'GPU')
        print(f'[GPU] using {_gpus[0].name} (of {len(_gpus)} visible)')
    except RuntimeError as _e:
        print(f'[GPU] config error (continuing on CPU): {_e}')
else:
    print('[GPU] none detected; running on CPU')

def _fmt_time(seconds: float) -> str:
    """HH:MM:SS.ss"""
    td = timedelta(seconds=seconds)
    total = td.total_seconds()
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"
def is_injected(val) -> bool:
    return pd.notna(val) and str(val).strip().lower() != "none"
def parse_body(body) -> List[Tuple[str, str, str]]:
    """stringified list of triples -> tuples"""
    if isinstance(body, str):
        try:
            triples = ast.literal_eval(body)
        except (SyntaxError, ValueError):
            return []
    elif isinstance(body, list):
        triples = body
    else:
        return []
    out = []
    for t in triples:
        if not isinstance(t, (list, tuple)) or len(t) != 3:
            continue
        s, p, o = t
        out.append((str(s).strip(), str(p).strip(), str(o).strip()))
    return out
_OP_TOKENS = {"some", "only", "max", "min", "exactly", "inverse",
              "and", "or", "not"}
def tokenise_obj(o: str) -> List[str]:
    """
    tokeniser for object expressions like 'P some C', 'PsomeC',
    'inverse(P) some C', 'P max 1 C'
    """
    o = o.strip().rstrip(",")
    parts = re.split(r"(\W+)", o)
    return [p.strip() for p in parts if p and p.strip() and p.strip() != ","]

PAD_TOKEN = "<PAD>"
UNK_TOKEN = "<UNK>"
def build_vocab(df: pd.DataFrame, max_vocab: int = MAX_VOCAB) -> dict:
    counter: Counter = Counter()
    for body in df["body"]:
        for s, p, o in parse_body(body):
            counter[s] += 1
            counter[p] += 1
            for tok in tokenise_obj(o):
                counter[tok] += 1
    most = counter.most_common(max_vocab - 2)
    vocab = {PAD_TOKEN: 0, UNK_TOKEN: 1}
    for tok, _ in most:
        vocab[tok] = len(vocab)
    return vocab
def _detect_op(o_toks: List[str]) -> str:
    for t in o_toks:
        tl = t.lower()
        if tl in {"some", "only", "max", "min", "exactly", "inverse"}:
            return tl
    return ""
def augment_vocab_with_pred_ops(df: pd.DataFrame, vocab: dict) -> dict:
    """
    Add 'predicate::op' composite tokens so the predicate slot can
    distinguish 'SubClassOf::some' from 'SubClassOf::only', etc
    """
    extras: Counter = Counter()
    for body in df["body"]:
        for s, p, o in parse_body(body):
            op = _detect_op(tokenise_obj(o))
            if op:
                extras[f"{p}::{op}"] += 1
    for k, _ in extras.most_common():
        if k not in vocab and len(vocab) < MAX_VOCAB:
            vocab[k] = len(vocab)
    return vocab
def encode_pred(pred: str, o_toks: List[str], vocab: dict) -> int:
    op = _detect_op(o_toks)
    key = f"{pred}::{op}" if op else pred
    if key in vocab:
        return vocab[key]
    return vocab.get(pred, vocab[UNK_TOKEN])
def encode_obj(o_toks: List[str], vocab: dict) -> int:
    """First non-operator token wins
    fall back to first token/ PAD
    """
    for t in o_toks:
        if t.lower() not in _OP_TOKENS:
            return vocab.get(t, vocab[UNK_TOKEN])
    return vocab.get(o_toks[0], vocab[UNK_TOKEN]) if o_toks else vocab[PAD_TOKEN]
def encode_ontology(triples: Sequence[Tuple[str, str, str]],
                    vocab: dict,
                    max_triples: int = MAX_TRIPLES
                    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    s_ids = np.zeros(max_triples, dtype=np.int32)
    p_ids = np.zeros(max_triples, dtype=np.int32)
    o_ids = np.zeros(max_triples, dtype=np.int32)
    n = min(len(triples), max_triples)
    for i in range(n):
        s, p, o = triples[i]
        o_toks = tokenise_obj(o)
        s_ids[i] = vocab.get(s, vocab[UNK_TOKEN])
        p_ids[i] = encode_pred(p, o_toks, vocab)
        o_ids[i] = encode_obj(o_toks, vocab)
    return s_ids, p_ids, o_ids, n
def encode_dataframe(df: pd.DataFrame, vocab: dict
                     ) -> Tuple[np.ndarray, np.ndarray, np.ndarray,
                                np.ndarray, np.ndarray]:
    n = len(df)
    S = np.zeros((n, MAX_TRIPLES), dtype=np.int32)
    P = np.zeros((n, MAX_TRIPLES), dtype=np.int32)
    O = np.zeros((n, MAX_TRIPLES), dtype=np.int32)
    L = np.zeros(n, dtype=np.int32)
    Y = np.zeros(n, dtype=np.int32)
    for i, (_, row) in enumerate(df.iterrows()):
        triples = parse_body(row["body"])
        s_ids, p_ids, o_ids, ln = encode_ontology(triples, vocab)
        S[i] = s_ids
        P[i] = p_ids
        O[i] = o_ids
        L[i] = ln
        Y[i] = 1 if is_injected(row["injected_pattern"]) else 0
    return S, P, O, L, Y

class OntologyEncoder(keras.Model):
    """
    Pools triple embeddings into a single ontology vector
    inputs:
        s_ids, p_ids, o_ids  : int32  [B, T]
        lengths              : int32  [B]
    output:
        ontology embedding   : float32 [B, H]
    """
    def __init__(self, vocab_size: int, emb_dim: int = EMB_DIM,
                 hid_dim: int = HID_DIM, **kwargs):
        super().__init__(**kwargs)
        self.embed = keras.layers.Embedding(vocab_size, emb_dim)
        self.triple_mlp = keras.Sequential([
            keras.layers.Dense(hid_dim, activation="relu"),
            keras.layers.Dense(hid_dim, activation="relu"),
        ])
        self.onto_mlp = keras.Sequential([
            keras.layers.Dense(hid_dim, activation="relu"),
            keras.layers.Dense(hid_dim, activation="relu"),
        ])
    def call(self, inputs):
        s_ids, p_ids, o_ids, lengths = inputs
        s_e = self.embed(s_ids)
        p_e = self.embed(p_ids)
        o_e = self.embed(o_ids)
        triple_in = tf.concat([s_e, p_e, o_e], axis=-1)        # [B,T,3E]
        triple_h  = self.triple_mlp(triple_in)                  # [B,T,H]
        T = tf.shape(s_ids)[1]
        rng = tf.range(T)[None, :]
        mask = tf.cast(rng < lengths[:, None], tf.float32)      # [B,T]
        mask_exp = mask[..., None]
        # Mean pool
        sum_h = tf.reduce_sum(triple_h * mask_exp, axis=1)
        denom = tf.maximum(tf.reduce_sum(mask, axis=1, keepdims=True), 1.0)
        mean_h = sum_h / denom                                   # [B,H]
        # Max pool
        very_neg = tf.fill(tf.shape(triple_h), tf.constant(-1e9))
        masked_h = tf.where(mask_exp > 0, triple_h, very_neg)
        max_h = tf.reduce_max(masked_h, axis=1)                  # [B,H]
        pooled = tf.concat([mean_h, max_h], axis=-1)             # [B,2H]
        return self.onto_mlp(pooled)                             # [B,H]
class InconsistentScorer(keras.Model):
    """LTN predicate body: ontology embedding -> [0,1]"""
    def __init__(self, hid_dim: int = HID_DIM, **kwargs):
        super().__init__(**kwargs)
        self.net = keras.Sequential([
            keras.layers.Dense(hid_dim, activation="relu"),
            keras.layers.Dense(hid_dim // 2, activation="relu"),
            keras.layers.Dense(1, activation="sigmoid"),
        ])
    def call(self, x):
        return tf.squeeze(self.net(x), axis=-1)

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)
def make_axioms_fn(encoder: OntologyEncoder, scorer: InconsistentScorer):
    Not    = ltn.Wrapper_Connective(ltn.fuzzy_ops.Not_Std())
    Forall = ltn.Wrapper_Quantifier(
        ltn.fuzzy_ops.Aggreg_pMeanError(p=P_MEAN_ERROR), semantics="forall")
    SatAgg = ltn.Wrapper_Formula_Aggregator(
        ltn.fuzzy_ops.Aggreg_pMeanError(p=P_MEAN_ERROR))
    inconsistent_pred = ltn.Predicate(scorer)
    def axioms(pos_inputs, neg_inputs):
        emb_pos = encoder(pos_inputs)
        emb_neg = encoder(neg_inputs)
        x_pos = ltn.Variable("x_pos", emb_pos)
        x_neg = ltn.Variable("x_neg", emb_neg)
        ax_pos = Forall(x_pos, inconsistent_pred(x_pos))
        ax_neg = Forall(x_neg, Not(inconsistent_pred(x_neg)))
        sat = SatAgg([ax_pos, ax_neg])
        return sat, ax_pos, ax_neg
    return axioms, inconsistent_pred
def iterate_batches(idx_pos: np.ndarray, idx_neg: np.ndarray,
                    batch_size: int, rng: np.random.Generator):
    half = max(batch_size // 2, 1)
    rng.shuffle(idx_pos)
    rng.shuffle(idx_neg)
    n = max(len(idx_pos), len(idx_neg))
    for start in range(0, n, half):
        p = idx_pos[start:start + half] if len(idx_pos) else np.array([], dtype=np.int64)
        ng = idx_neg[start:start + half] if len(idx_neg) else np.array([], dtype=np.int64)
        if len(p) == 0 and len(idx_pos):
            p = rng.choice(idx_pos, size=half, replace=True)
        if len(ng) == 0 and len(idx_neg):
            ng = rng.choice(idx_neg, size=half, replace=True)
        if len(p) == 0 and len(ng) == 0:
            continue
        yield np.asarray(p), np.asarray(ng)
def make_gpu_tensors(S, P, O, L):
    """Upload split tensors to device once"""
    return (
        tf.constant(S, dtype=tf.int32),
        tf.constant(P, dtype=tf.int32),
        tf.constant(O, dtype=tf.int32),
        tf.constant(L, dtype=tf.int32),
    )

def gather_inputs_tf(tensors, idx):
    S_t, P_t, O_t, L_t = tensors
    idx = tf.cast(idx, tf.int32)
    return (tf.gather(S_t, idx),
            tf.gather(P_t, idx),
            tf.gather(O_t, idx),
            tf.gather(L_t, idx))
def predict_scores(encoder, scorer, tensors, n, batch_size=256):
    out = np.zeros(n, dtype=np.float32)
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        idx = tf.range(start, end, dtype=tf.int32)
        # noinspection PyCallingNonCallable
        emb = encoder(gather_inputs_tf(tensors, idx))
        # noinspection PyCallingNonCallable
        out[start:end] = scorer(emb).numpy()
    return out
def evaluate_split(encoder, scorer, tensors, Y, threshold=THRESHOLD):
    t0 = time.perf_counter()
    scores = predict_scores(encoder, scorer, tensors, len(Y))
    y_pred = (scores >= threshold).astype(np.int32)
    inf_secs = time.perf_counter() - t0
    return {
        "acc":  accuracy_score(Y, y_pred),
        "prec": precision_score(Y, y_pred, zero_division=0),
        "rec":  recall_score(Y, y_pred, zero_division=0),
        "f1":   f1_score(Y, y_pred, zero_division=0),
        "inference_seconds": inf_secs,
    }
def run_one_seed(train_data, val_data, test_data, vocab_size: int,
                 seed: int, epochs: int, lr: float, verbose: bool = True):
    set_seed(seed)
    S_tr, P_tr, O_tr, L_tr, Y_tr = train_data
    S_va, P_va, O_va, L_va, Y_va = val_data
    S_te, P_te, O_te, L_te, Y_te = test_data

    # Upload each split once
    # subsequent batching is pure on-device gather
    train_tensors = make_gpu_tensors(S_tr, P_tr, O_tr, L_tr)
    val_tensors   = make_gpu_tensors(S_va, P_va, O_va, L_va)
    test_tensors  = make_gpu_tensors(S_te, P_te, O_te, L_te)

    encoder = OntologyEncoder(vocab_size=vocab_size)
    scorer  = InconsistentScorer()

    # Build models so .trainable_variables is populated
    warm_idx = tf.range(min(2, len(S_tr)), dtype=tf.int32)
    # noinspection PyCallingNonCallable
    _ = encoder(gather_inputs_tf(train_tensors, warm_idx))
    # noinspection PyCallingNonCallable
    _ = scorer(tf.zeros([1, HID_DIM], dtype=tf.float32))

    axioms_fn, _ = make_axioms_fn(encoder, scorer)
    # noinspection PyArgumentList,PyUnresolvedReferences
    optimizer = tf.keras.optimizers.Adam(learning_rate=lr)
    trainables = encoder.trainable_variables + scorer.trainable_variables

    # Single graph-compiled train step
    @tf.function(input_signature=[
        tf.TensorSpec(shape=[None], dtype=tf.int32),
        tf.TensorSpec(shape=[None], dtype=tf.int32),
    ])
    def train_step(pos_idx, neg_idx):
        pos_inputs = gather_inputs_tf(train_tensors, pos_idx)
        neg_inputs = gather_inputs_tf(train_tensors, neg_idx)
        with tf.GradientTape() as tape:
            sat, _, _ = axioms_fn(pos_inputs, neg_inputs)
            loss = 1.0 - sat.tensor
        grads = tape.gradient(loss, trainables)
        optimizer.apply_gradients(zip(grads, trainables))
        return sat.tensor

    rng = np.random.default_rng(seed)
    idx_pos = np.where(Y_tr == 1)[0]
    idx_neg = np.where(Y_tr == 0)[0]
    if verbose:
        print(f"  [seed {seed}] train pos={len(idx_pos)} neg={len(idx_neg)}")

    best_val_acc = -1.0
    best_weights = None
    best_epoch = -1
    epochs_no_improve = 0
    history = []

    t0 = time.perf_counter()
    for epoch in range(epochs):
        ep_t0 = time.perf_counter()
        sat_acc = tf.constant(0.0, dtype=tf.float32)
        n_steps = 0
        for pos_idx, neg_idx in iterate_batches(idx_pos.copy(), idx_neg.copy(),
                                                BATCH_SIZE, rng):
            sat_t = train_step(tf.constant(pos_idx, dtype=tf.int32),
                               tf.constant(neg_idx, dtype=tf.int32))
            sat_acc += sat_t          # stays on device, no per-step sync
            n_steps += 1
        train_sat = float(sat_acc.numpy() / max(n_steps, 1))

        val_metrics = evaluate_split(encoder, scorer, val_tensors, Y_va)
        history.append({"epoch": epoch, "train_sat": train_sat,
                        **{f"val_{k}": v for k, v in val_metrics.items()
                           if k != "inference_seconds"}})
        if verbose:
            print(f"  [seed {seed}] epoch {epoch:03d} | sat={train_sat:.4f} "
                  f"| val_acc={val_metrics['acc']:.4f} "
                  f"val_f1={val_metrics['f1']:.4f} "
                  f"| epoch_time={time.perf_counter() - ep_t0:.1f}s")

        if val_metrics["acc"] > best_val_acc + EARLY_STOP_MIN_DELTA:
            best_val_acc = val_metrics["acc"]
            best_epoch = epoch
            epochs_no_improve = 0
            best_weights = (
                [v.numpy().copy() for v in encoder.trainable_variables],
                [v.numpy().copy() for v in scorer.trainable_variables],
            )
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= EARLY_STOP_PATIENCE:
                if verbose:
                    print(f"  [seed {seed}] early stop at epoch {epoch:03d} "
                          f"(no val_acc improvement for "
                          f"{EARLY_STOP_PATIENCE} epochs; "
                          f"best epoch {best_epoch:03d} "
                          f"acc={best_val_acc:.4f})")
                break

    train_seconds = time.perf_counter() - t0

    if best_weights is not None:
        for v, w in zip(encoder.trainable_variables, best_weights[0]):
            v.assign(w)
        for v, w in zip(scorer.trainable_variables, best_weights[1]):
            v.assign(w)

    train_metrics = evaluate_split(encoder, scorer, train_tensors, Y_tr)
    val_metrics   = evaluate_split(encoder, scorer, val_tensors,   Y_va)
    test_metrics  = evaluate_split(encoder, scorer, test_tensors,  Y_te)
    if verbose:
        for name, m in [("train", train_metrics),
                        ("val",   val_metrics),
                        ("test",  test_metrics)]:
            print(f"  [seed {seed}] {name:>5s} -> "
                  f"Acc {m['acc']:.4f}  Prec {m['prec']:.4f}  "
                  f"Rec {m['rec']:.4f}  F1 {m['f1']:.4f}  "
                  f"(infer {_fmt_time(m['inference_seconds'])})")
    return {
        "train_seconds": train_seconds,
        "train": train_metrics,
        "val":   val_metrics,
        "test":  test_metrics,
        "history": history,
        "best_epoch": best_epoch,
        "stopped_epoch": epoch,
    }

def _run_all_seeds(label: str, train_data, val_data, test_data,
                   vocab_size: int, shuffle_train_labels: bool = False):
    """
    Run SEEDS x training pipeline
    """
    print(f"\n{'#' * 78}\n# Experiment: {label}"
          f"{'  [shuffled train labels]' if shuffle_train_labels else ''}"
          f"\n{'#' * 78}")
    all_runs = []
    for seed in SEEDS:
        print(f"\n=== Seed {seed} ({label}) ===")
        td = train_data
        if shuffle_train_labels:
            S, P, O, L, Y = train_data
            shuf_rng = np.random.default_rng(seed + SHUFFLE_SEED_OFFSET)
            Y_shuf = Y.copy()
            shuf_rng.shuffle(Y_shuf)
            td = (S, P, O, L, Y_shuf)
        run = run_one_seed(td, val_data, test_data,
                           vocab_size=vocab_size,
                           seed=seed, epochs=EPOCHS, lr=LEARNING_RATE,
                           verbose=True)
        all_runs.append(run)
    def agg(split, key):
        vals = np.array([r[split][key] for r in all_runs])
        return vals.mean(), vals.std()
    train_secs = np.array([r["train_seconds"] for r in all_runs])
    test_inf   = np.array([r["test"]["inference_seconds"] for r in all_runs])
    print("\n" + "=" * 78)
    print(f"Aggregated over {len(SEEDS)} seeds (mean +/- std) -- {label}")
    print("=" * 78)
    for split in ["train", "val", "test"]:
        a_m, a_s = agg(split, "acc")
        p_m, p_s = agg(split, "prec")
        r_m, r_s = agg(split, "rec")
        f_m, f_s = agg(split, "f1")
        print(f"  {split:>5s} : Acc {a_m*100:5.2f} +/-{a_s*100:.2f}  "
              f"Prec {p_m*100:5.2f} +/-{p_s*100:.2f}  "
              f"Rec {r_m*100:5.2f} +/-{r_s*100:.2f}  "
              f"F1 {f_m*100:5.2f} +/-{f_s*100:.2f}")
    print(f"  Training (wall): {_fmt_time(train_secs.mean())}  +/-{train_secs.std():.2f}s")
    print(f"  Test inference:  {_fmt_time(test_inf.mean())}  +/-{test_inf.std():.3f}s")
    a_m, a_s = agg("test", "acc")
    p_m, p_s = agg("test", "prec")
    r_m, r_s = agg("test", "rec")
    print("\n" + "=" * 78)
    print(f"Paper-table row: {label}:")
    print("=" * 78)
    print(
        f"{label} & "
        f"${a_m*100:5.2f}_{{({a_s*100:.2f})}}$ & "
        f"${p_m*100:5.2f}_{{({p_s*100:.2f})}}$ & "
        f"${r_m*100:5.2f}_{{({r_s*100:.2f})}}$ & "
        f"{_fmt_time(train_secs.mean())} & "
        f"{_fmt_time(test_inf.mean())} \\\\"
    )
    print("=" * 78)
    return all_runs
def main():
    print("Loading CSVs ...")
    train_df = pd.read_csv(TRAIN_CSV)
    val_df   = pd.read_csv(VAL_CSV)
    test_df  = pd.read_csv(TEST_CSV)
    print(f"  train={len(train_df)}  val={len(val_df)}  test={len(test_df)}")
    print(f"  pos: train={train_df['injected_pattern'].apply(is_injected).sum()} "
          f"val={val_df['injected_pattern'].apply(is_injected).sum()} "
          f"test={test_df['injected_pattern'].apply(is_injected).sum()}")
    print("Building vocab from train split ...")
    vocab = build_vocab(train_df, max_vocab=MAX_VOCAB)
    vocab = augment_vocab_with_pred_ops(train_df, vocab)
    print(f"  vocab size = {len(vocab)} (capped at {MAX_VOCAB})")
    print("Tensorising splits ...")
    train_data = encode_dataframe(train_df, vocab)
    val_data   = encode_dataframe(val_df,   vocab)
    test_data  = encode_dataframe(test_df,  vocab)
    print(f"  triple-tensor shape per split: {train_data[0].shape}, "
          f"{val_data[0].shape}, {test_data[0].shape}")
    # Main run: real labels
    _run_all_seeds("LTN",
                   train_data, val_data, test_data,
                   vocab_size=len(vocab),
                   shuffle_train_labels=False)
    #Sanity-check: shuffled train labels
    if RUN_SHUFFLED_LABEL_CONTROL:
        _run_all_seeds("LTN",
                       train_data, val_data, test_data,
                       vocab_size=len(vocab),
                       shuffle_train_labels=True)
if __name__ == "__main__":
    main()
