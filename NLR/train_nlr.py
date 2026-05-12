"""
NLR for BioPortal ontology consistency verification:
per-ontology local entity IDs (graph-structural, IRI-agnostic)
Subjects and objects share a single entity table
"""
from __future__ import annotations
import ast
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import timedelta
from typing import List, Tuple
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             f1_score, precision_score, recall_score)
from sklearn.model_selection import StratifiedShuffleSplit
# hook upstream NLR repo onto sys.path before import NLR -> jacinle workaroiund
NLR_SRC = os.environ.get(
    "NLR_SRC", "/media/nvme2n1/lniederberger/models/NLR/src")
if NLR_SRC not in sys.path:
    sys.path.insert(0, NLR_SRC)
from models.NLR import NLR                         # noqa: E402
from utils.global_p import (                       # noqa: E402
    X, Y, TRAIN, TOTAL_BATCH_SIZE, K_OR_LENGTH,
    PREDICTION, LOSS, EMBEDDING_L2,
)
# config
TRAIN_CSV = "/media/nvme2n1/lniederberger/models/nsplits/train_data.csv"
VAL_CSV   = "/media/nvme2n1/lniederberger/models/nsplits/eval_data.csv"
TEST_CSV  = "/media/nvme2n1/lniederberger/models/nsplits/test_data.csv"
MAX_TRIPLES        = 2048 # 512 commented param for bioportal
MAX_LOCAL_ENTITY   = 1024   # local entity ids: 2..(MAX_LOCAL_ENTITY+1); overflow -> UNK_ID
MIN_PRED_FREQ      = 1
V_VECTOR_SIZE = 32 #64
LAYERS        = 1 #1
R_LOGIC       = 1e-3
R_LENGTH      = 1e-4
SIM_SCALE     = 5 #10
SIM_ALPHA     = 0.0
PROJ_DROPOUT  = 0.1
EPOCHS                = 60 #30
BATCH_SIZE            = 16
LEARNING_RATE         = 1e-4 #3e-4
WEIGHT_DECAY          = 1e-4
L2_BIAS               = 0
LOSS_SUM              = 1
GRAD_CLIP             = 2.0 # was 5.0 ?too aggressive? -> f1 crash from 0.69 to 0.33 in one epoch!!
THRESHOLD             = 0.5 # .55
SWEEP_VAL_THRESHOLD   = True
VAL_THRESHOLD_METRIC  = 'bacc'
VAL_THRESHOLD_GRID    = tuple(round(float(x), 2) for x in np.linspace(0.10, 0.90, 17))
EARLY_STOP_PATIENCE   = 16 #10
EARLY_STOP_MIN_DELTA  = 0.0
EARLY_STOP_METRIC     = 'bacc' # 'acc' | 'bacc' | 'f1'. bacc=(TPR+TNR)/2 - immune to
                              # 'predict-all-positive' trap that pumps F1 to 0.667.
USE_COSINE_LR         = True   # cosine annealing from LEARNING_RATE -> LEARNING_RATE/100
SHUFFLED_USE_FIXED_EPOCHS = True  # control: no val-based selection, eval final-epoch,
SEEDS                 =  [0, 1, 2, 3, 4] # [0]
RUN_SHUFFLED_LABEL_CONTROL = False # True
SHUFFLE_SEED_OFFSET   = 1000
USE_REPEATED_RESPLITS = False
REPEATED_RESPLIT_COUNT = 5
REPEATED_RESPLIT_SEED = 42
RESPLIT_VAL_RATIO = None  # derive from original train/val sizes when None
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[device] {DEVICE}"
      + (f" ({torch.cuda.get_device_name(0)})" if DEVICE.type == 'cuda' else ''))
# 2. helpers
def _fmt_time(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total = td.total_seconds()
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"
def is_injected(val) -> bool:
    return pd.notna(val) and str(val).strip().lower() != 'none'
def parse_body(body) -> List[Tuple[str, str, str]]:
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

def canonicalize_triples(triples: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
    """Normalize ontology bodies  !!NOT USED!! """
    return sorted(
        triples,
        key=lambda t: (_norm_pred(t[1]), _norm_iri(t[0]), _norm_iri(t[2])),
    )
def _norm_iri(s: str) -> str:
    s = s.strip().rstrip(',').strip()
    s = re.sub(r'\s+', ' ', s)
    return s
def _norm_pred(p: str) -> str:
    return p.strip()
def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
# vocab + per-ontology-local encoding
PAD_ID, UNK_ID = 0, 1
FIRST_REAL_ID  = 2
def build_predicate_vocab(train_df: pd.DataFrame, min_freq: int = MIN_PRED_FREQ) -> dict:
    """predicates are the only globally-shared symbol  Train-only with UNK"""
    counter: Counter = Counter()
    for body in train_df['body']:
        for _, p, _ in parse_body(body):
            counter[_norm_pred(p)] += 1
    vocab = {}
    nxt = FIRST_REAL_ID
    for tok, c in counter.most_common():
        if c >= min_freq:
            vocab[tok] = nxt
            nxt += 1
    return vocab
def encode_dataframe(df: pd.DataFrame, pred_vocab: dict,
                     atom_vocab: dict, atom_to_spo: list,
                     max_triples: int = MAX_TRIPLES):
    """For each ontology row, give every distinct IRI a *local* id 2.. (capped
    at MAX_LOCAL_ENTITY+1, overflow -> UNK).
    Build atoms keyed by (s_local, p_global, o_local) and re-use ids across ontologies whenever the
    same triple (in the local sense) recurs
    """
    n = len(df)
    Xa = np.zeros((n, 1, max_triples), dtype=np.int64)
    L  = np.zeros(n, dtype=np.int64)
    Ya = np.zeros(n, dtype=np.float32)
    n_pred_unk = 0
    n_ent_overflow = 0
    n_local_entities_total = 0
    n_atoms_new = 0
    max_ent_in_one = 0
    for i, (_, row) in enumerate(df.iterrows()):
        triples = parse_body(row["body"])[:max_triples]
        if not triples:
            Xa[i, 0, 0] = UNK_ID
            L[i] = 1
            Ya[i] = 1.0 if is_injected(row["injected_pattern"]) else 0.0
            continue
        # Local entity table for THIS ontology only
        seen_ent: dict = {}
        def local_id(iri: str) -> int:
            nonlocal n_ent_overflow
            iri = _norm_iri(iri)
            if iri in seen_ent:
                return seen_ent[iri]
            nxt = FIRST_REAL_ID + len(seen_ent)
            if nxt >= FIRST_REAL_ID + MAX_LOCAL_ENTITY:
                n_ent_overflow += 1
                return UNK_ID
            seen_ent[iri] = nxt
            return nxt
        for k, (s, p, o) in enumerate(triples):
            s_loc = local_id(s)
            o_loc = local_id(o)
            p_norm = _norm_pred(p)
            if p_norm in pred_vocab:
                p_glb = pred_vocab[p_norm]
            else:
                p_glb = UNK_ID
                n_pred_unk += 1
            spo = (s_loc, p_glb, o_loc)
            if spo in atom_vocab:
                aid = atom_vocab[spo]
            else:
                aid = len(atom_to_spo)
                atom_vocab[spo] = aid
                atom_to_spo.append(spo)
                n_atoms_new += 1
            Xa[i, 0, k] = aid
        L[i] = len(triples)
        Ya[i] = 1.0 if is_injected(row["injected_pattern"]) else 0.0
        n_local_entities_total += len(seen_ent)
        if len(seen_ent) > max_ent_in_one:
            max_ent_in_one = len(seen_ent)
    return Xa, L, Ya, dict(
        n_pred_unk=n_pred_unk,
        n_ent_overflow=n_ent_overflow,
        n_atoms_new=n_atoms_new,
        avg_local_entities=n_local_entities_total / max(n, 1),
        max_local_entities=max_ent_in_one,
    )
def to_device_tensors(X_arr, L_arr, Y_arr):
    return (
        torch.as_tensor(X_arr, dtype=torch.long,  device=DEVICE),
        torch.as_tensor(L_arr, dtype=torch.long,  device=DEVICE),
        torch.as_tensor(Y_arr, dtype=torch.float, device=DEVICE),
    )
# compositional embedding: shared entity table + global predicate table
class LocalEntityTripleEmbedding(nn.Module):
    """
    Looks up an atom-id, indexes into ''atom_to_spo'' to get
    (s_local, p_global, o_local), embeds via a shared entity table
    (subjects and objects share parameters) and a global predicate table,
    then projects to V
    """
    def __init__(self, n_local_ent: int, n_pred: int,
                 v_size: int, atom_to_spo: torch.Tensor):
        super().__init__()
        self.entity_emb = nn.Embedding(n_local_ent, v_size, padding_idx=PAD_ID)
        self.pred_emb   = nn.Embedding(n_pred,      v_size, padding_idx=PAD_ID)
        self.proj       = nn.Linear(3 * v_size, v_size)
        self.dropout    = nn.Dropout(PROJ_DROPOUT)
        nn.init.xavier_uniform_(self.proj.weight)
        nn.init.zeros_(self.proj.bias)
        assert atom_to_spo.dtype == torch.long
        assert atom_to_spo.dim() == 2 and atom_to_spo.size(1) == 3
        self.register_buffer("atom_to_spo", atom_to_spo)
    def forward(self, atom_ids: torch.Tensor) -> torch.Tensor:
        spo = self.atom_to_spo[atom_ids]                       # (..., 3)
        s = self.entity_emb(spo[..., 0])                       # (..., V)
        p = self.pred_emb(  spo[..., 1])
        o = self.entity_emb(spo[..., 2])
        return self.dropout(self.proj(torch.cat([s, p, o], dim=-1)))  # (..., V)
# class-balanced batch iterator
def iterate_balanced_batches(idx_pos: np.ndarray, idx_neg: np.ndarray,
                             batch_size: int, rng: np.random.Generator):
    half = max(batch_size // 2, 1)
    rng.shuffle(idx_pos)
    rng.shuffle(idx_neg)
    n = max(len(idx_pos), len(idx_neg))
    for start in range(0, n, half):
        p  = idx_pos[start:start + half] if len(idx_pos) else np.array([], dtype=np.int64)
        ng = idx_neg[start:start + half] if len(idx_neg) else np.array([], dtype=np.int64)
        if len(p)  == 0 and len(idx_pos): p  = rng.choice(idx_pos, size=half, replace=True)
        if len(ng) == 0 and len(idx_neg): ng = rng.choice(idx_neg, size=half, replace=True)
        if len(p) == 0 and len(ng) == 0:
            continue
        yield np.concatenate([p, ng])
# model construction (with embedding swap)
def build_model(n_atoms: int, n_local_ent: int, n_pred: int,
                atom_to_spo: torch.Tensor, seed: int) -> NLR:
    model = NLR(
        variable_num=n_atoms,
        v_vector_size=V_VECTOR_SIZE,
        layers=LAYERS,
        r_logic=R_LOGIC,
        r_length=R_LENGTH,
        sim_scale=SIM_SCALE,
        sim_alpha=SIM_ALPHA,
        label_min=0,
        label_max=1,
        feature_num=n_atoms,
        loss_sum=LOSS_SUM,
        l2_bias=L2_BIAS,
        random_seed=seed,
        model_path=os.path.join("/tmp", f"nlr_seed{seed}.pt"),
    )
    del model.feature_embeddings
    model.feature_embeddings = LocalEntityTripleEmbedding(
        n_local_ent=n_local_ent, n_pred=n_pred,
        v_size=V_VECTOR_SIZE, atom_to_spo=atom_to_spo,
    )
    if hasattr(model, "l2_embeddings"):
        model.l2_embeddings = []
    if DEVICE.type == "cuda":
        model = model.cuda()
    return model
def make_feed_dict(X_t, L_t, Y_t, idx, train: bool):
    Xb = X_t[idx]
    A_max = int(L_t[idx].max().item())
    A_max = max(A_max, 1)
    Xb = Xb[:, :, :A_max].contiguous()
    return {
        X:                 Xb,
        Y:                 Y_t[idx],
        K_OR_LENGTH:       [A_max],
        TOTAL_BATCH_SIZE:  Xb.size(0),
        TRAIN:             train,
    }
# train / evaluate one seed (same structure)
@torch.no_grad()
def collect_split_predictions(model: NLR, tensors, batch_size: int = 256):
    X_t, L_t, Y_t = tensors
    n = Y_t.size(0)
    model.eval()
    y_true = Y_t.detach().cpu().numpy().astype(int)
    y_prob = np.zeros(n, dtype=np.float32)
    t0 = time.perf_counter()
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        idx = torch.arange(start, end, device=DEVICE)
        feed = make_feed_dict(X_t, L_t, Y_t, idx, train=False)
        out = model.predict(feed)
        prob = out[PREDICTION].detach().cpu().numpy()
        y_prob[start:end] = prob
    return y_true, y_prob, time.perf_counter() - t0

def _metrics_from_probs(y_true: np.ndarray, y_prob: np.ndarray, threshold: float, inf_seconds: float):
    y_pred = (y_prob >= threshold).astype(np.int64)
    return {
        "acc":  accuracy_score(y_true, y_pred),
        "bacc": balanced_accuracy_score(y_true, y_pred),
        "prec": precision_score(y_true, y_pred, zero_division=0),
        "rec":  recall_score(y_true, y_pred, zero_division=0),
        "f1":   f1_score(y_true, y_pred, zero_division=0),
        "threshold": float(threshold),
        "inference_seconds": inf_seconds,
    }

def select_best_threshold(y_true: np.ndarray, y_prob: np.ndarray, metric: str = VAL_THRESHOLD_METRIC):
    if not SWEEP_VAL_THRESHOLD or len(np.unique(y_true)) < 2:
        return THRESHOLD
    best_threshold = THRESHOLD
    best_metric = -np.inf
    best_distance = np.inf
    for threshold in VAL_THRESHOLD_GRID:
        m = _metrics_from_probs(y_true, y_prob, float(threshold), 0.0)
        score = float(m[metric])
        distance = abs(float(threshold) - THRESHOLD)
        if score > best_metric or (score == best_metric and distance < best_distance):
            best_metric = score
            best_distance = distance
            best_threshold = float(threshold)
    return best_threshold

def evaluate_split(model: NLR, tensors, batch_size: int = 256, threshold: float = THRESHOLD):
    y_true, y_prob, inf_seconds = collect_split_predictions(model, tensors, batch_size=batch_size)
    return _metrics_from_probs(y_true, y_prob, threshold=float(threshold), inf_seconds=inf_seconds)
def _snapshot_state(model: nn.Module):
    return {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
def _load_state(model: nn.Module, snap):
    model.load_state_dict({k: v.to(DEVICE) for k, v in snap.items()})
def run_one_seed(train_tensors, val_tensors, test_tensors,
                 n_atoms: int, n_local_ent: int, n_pred: int,
                 atom_to_spo: torch.Tensor,
                 seed: int, epochs: int = EPOCHS, lr: float = LEARNING_RATE,
                 verbose: bool = True,
                 shuffled_fixed: bool = False):
    seed_everything(seed)
    model = build_model(n_atoms=n_atoms, n_local_ent=n_local_ent, n_pred=n_pred,
                        atom_to_spo=atom_to_spo, seed=seed)
    optim = torch.optim.Adam(model.parameters(), lr=lr,
                             weight_decay=WEIGHT_DECAY)
    scheduler = (torch.optim.lr_scheduler.CosineAnnealingLR(
                     optim, T_max=epochs, eta_min=lr / 100.0)
                 if USE_COSINE_LR else None)
    X_tr, L_tr, Y_tr = train_tensors
    Y_tr_np = Y_tr.detach().cpu().numpy().astype(int)
    idx_pos = np.where(Y_tr_np == 1)[0]
    idx_neg = np.where(Y_tr_np == 0)[0]
    if verbose:
        n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"  [seed {seed}] NLR n_atoms={n_atoms}  "
              f"n_local_ent={n_local_ent} n_pred={n_pred}  "
              f"trainable params: {n_params:,}  (device={DEVICE})  "
              f"train pos={len(idx_pos)} neg={len(idx_neg)}")
    best_val_acc = -1.0
    best_epoch = -1
    best_state = None
    epochs_no_improve = 0
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    last_epoch = 0
    for epoch in range(epochs):
        ep_t0 = time.perf_counter()
        model.train()
        ep_loss = 0.0
        ep_seen = 0
        for batch_idx in iterate_balanced_batches(idx_pos.copy(), idx_neg.copy(),
                                                  BATCH_SIZE, rng):
            idx = torch.as_tensor(batch_idx, dtype=torch.long, device=DEVICE)
            feed = make_feed_dict(X_tr, L_tr, Y_tr, idx, train=True)
            out = model(feed)
            loss = out[LOSS]
            optim.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optim.step()
            bs = int(feed[TOTAL_BATCH_SIZE])
            ep_loss += float(loss.detach().item())
            ep_seen += bs
        val_m = evaluate_split(model, val_tensors)
        if verbose:
            print(f"  [seed {seed}] ep {epoch:03d}/{epochs}  "
                  f"loss/seen={ep_loss/max(ep_seen,1):.4f}  "
                  f"val_acc={val_m['acc']:.4f}  val_bacc={val_m['bacc']:.4f}  "
                  f"val_f1={val_m['f1']:.4f}  "
                  f"| epoch_time={time.perf_counter()-ep_t0:.1f}s")
        last_epoch = epoch
        if scheduler is not None:
            scheduler.step()
        if shuffled_fixed:
            # Train all epochs, the final model is evaluated below.
            best_state = None
            best_epoch = epoch
            best_val_acc = val_m[EARLY_STOP_METRIC]
            continue
        cur = val_m[EARLY_STOP_METRIC]
        if cur > best_val_acc + EARLY_STOP_MIN_DELTA:
            best_val_acc = cur
            best_epoch = epoch
            epochs_no_improve = 0
            best_state = _snapshot_state(model)
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= EARLY_STOP_PATIENCE:
                if verbose:
                    print(f"  [seed {seed}] early stop at ep {epoch:03d} "
                          f"(no val_{EARLY_STOP_METRIC} improvement for "
                          f"{EARLY_STOP_PATIENCE}; best ep {best_epoch:03d} "
                          f"{EARLY_STOP_METRIC}={best_val_acc:.4f})")
                break
    train_seconds = time.perf_counter() - t0
    if best_state is not None:
        _load_state(model, best_state)
    eval_threshold = THRESHOLD
    if SWEEP_VAL_THRESHOLD:
        val_true, val_prob, _ = collect_split_predictions(model, val_tensors)
        eval_threshold = select_best_threshold(val_true, val_prob, metric=VAL_THRESHOLD_METRIC)
        if verbose:
            print(f"  [seed {seed}] selected val threshold={eval_threshold:.2f} by val_{VAL_THRESHOLD_METRIC}")
    train_m = evaluate_split(model, train_tensors, threshold=eval_threshold)
    val_m   = evaluate_split(model, val_tensors, threshold=eval_threshold)
    test_m  = evaluate_split(model, test_tensors, threshold=eval_threshold)
    if verbose:
        for name, m in [("train", train_m), ("val", val_m), ("test", test_m)]:
            print(f"  [seed {seed}] {name:>5s} -> "
                  f"Acc {m['acc']:.4f}  Prec {m['prec']:.4f}  "
                  f"Rec {m['rec']:.4f}  F1 {m['f1']:.4f}  Thr {m['threshold']:.2f}  "
                  f"(infer {_fmt_time(m['inference_seconds'])})")
    del model, optim
    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()
    return {
        "train_seconds": train_seconds,
        "train": train_m, "val": val_m, "test": test_m,
        "eval_threshold": eval_threshold,
        "best_epoch": best_epoch, "stopped_epoch": last_epoch,
    }
# driver
def _run_all_seeds(label: str, train_tensors, val_tensors, test_tensors,
                   n_atoms: int, n_local_ent: int, n_pred: int,
                   atom_to_spo: torch.Tensor,
                   shuffle_train_labels: bool = False):
    print(f"\n{'#' * 78}\n# Experiment: {label}"
          f"{'  [shuffled train labels]' if shuffle_train_labels else ''}"
          f"\n{'#' * 78}")
    X_tr, L_tr, Y_tr = train_tensors
    all_runs = []
    for seed in SEEDS:
        print(f"\n=== Seed {seed} ({label}) ===")
        td = train_tensors
        if shuffle_train_labels:
            shuf_rng = np.random.default_rng(seed + SHUFFLE_SEED_OFFSET)
            Y_np = Y_tr.detach().cpu().numpy().copy()
            shuf_rng.shuffle(Y_np)
            Y_shuf = torch.as_tensor(Y_np, dtype=torch.float, device=DEVICE)
            td = (X_tr, L_tr, Y_shuf)
        run = run_one_seed(td, val_tensors, test_tensors,
                           n_atoms=n_atoms, n_local_ent=n_local_ent, n_pred=n_pred,
                           atom_to_spo=atom_to_spo, seed=seed,
                           epochs=EPOCHS, lr=LEARNING_RATE, verbose=True,
                           shuffled_fixed=(shuffle_train_labels and SHUFFLED_USE_FIXED_EPOCHS))
        all_runs.append(run)
    def agg(split, key):
        v = np.array([r[split][key] for r in all_runs])
        return v.mean(), v.std()
    train_secs = np.array([r["train_seconds"] for r in all_runs])
    test_inf   = np.array([r["test"]["inference_seconds"] for r in all_runs])
    print("\n" + "=" * 78)
    print(f"Aggregated over {len(SEEDS)} seeds (mean +/- std) - {label}")
    print("=" * 78)
    for split in ("train", "val", "test"):
        a_m, a_s = agg(split, "acc")
        p_m, p_s = agg(split, "prec")
        r_m, r_s = agg(split, "rec")
        f_m, f_s = agg(split, "f1")
        print(f"  {split:>5s} : Acc {a_m*100:5.2f} +/-{a_s*100:.2f}  "
              f"Prec {p_m*100:5.2f} +/-{p_s*100:.2f}  "
              f"Rec  {r_m*100:5.2f} +/-{r_s*100:.2f}  "
              f"F1 {f_m*100:5.2f} +/-{f_s*100:.2f}")
    print(f"  Training (wall): {_fmt_time(train_secs.mean())}  +/-{train_secs.std():.2f}s")
    print(f"  Test inference:  {_fmt_time(test_inf.mean())}  +/-{test_inf.std():.3f}s")
    a_m, a_s = agg("test", "acc")
    p_m, p_s = agg("test", "prec")
    r_m, r_s = agg("test", "rec")
    print("\n" + "=" * 78)
    print(f"Paper-table row - {label}:")
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
def _summarize_runs(label: str, all_runs):
    def agg(split, key):
        v = np.array([r[split][key] for r in all_runs])
        return v.mean(), v.std()
    train_secs = np.array([r["train_seconds"] for r in all_runs])
    test_inf   = np.array([r["test"]["inference_seconds"] for r in all_runs])
    print("\n" + "=" * 78)
    print(f"Aggregated over {len(all_runs)} runs (mean +/- std) - {label}")
    print("=" * 78)
    for split in ("train", "val", "test"):
        a_m, a_s = agg(split, "acc")
        p_m, p_s = agg(split, "prec")
        r_m, r_s = agg(split, "rec")
        f_m, f_s = agg(split, "f1")
        print(f"  {split:>5s} : Acc {a_m*100:5.2f} +/-{a_s*100:.2f}  "
              f"Prec {p_m*100:5.2f} +/-{p_s*100:.2f}  "
              f"Rec  {r_m*100:5.2f} +/-{r_s*100:.2f}  "
              f"F1 {f_m*100:5.2f} +/-{f_s*100:.2f}")
    print(f"  Training (wall): {_fmt_time(train_secs.mean())}  +/-{train_secs.std():.2f}s")
    print(f"  Test inference:  {_fmt_time(test_inf.mean())}  +/-{test_inf.std():.3f}s")
    a_m, a_s = agg("test", "acc")
    p_m, p_s = agg("test", "prec")
    r_m, r_s = agg("test", "rec")
    print("\n" + "=" * 78)
    print(f"Paper-table row - {label}:")
    print("=" * 78)
    print(
        f"{label} & "
        f"${a_m*100:5.2f}_{{({a_s*100:.2f})}}$ & "
        f"${p_m*100:5.2f}_{{({p_s*100:.2f})}}$ & "
        f"${r_m*100:5.2f}_{{({r_s*100:.2f})}}$ & "
        f"{_fmt_time(train_secs.mean())} & "
        f"{_fmt_time(test_inf.mean())}"
    )
    print("=" * 78)

def _encode_and_run_experiment(label: str, train_df: pd.DataFrame,
                               val_df: pd.DataFrame, test_df: pd.DataFrame,
                               shuffle_train_labels: bool = False):
    print("Building predicate vocabulary (train-only) ...")
    pred_vocab = build_predicate_vocab(train_df)
    n_pred = len(pred_vocab) + FIRST_REAL_ID
    n_local_ent = MAX_LOCAL_ENTITY + FIRST_REAL_ID
    print(f"  predicates: {len(pred_vocab):,d} unique  (n_pred={n_pred})")
    print(f"  local entity table size (shared subj/obj): n_local_ent={n_local_ent}")
    atom_vocab: dict = {}
    atom_to_spo: list = [(PAD_ID, PAD_ID, PAD_ID),
                         (UNK_ID, UNK_ID, UNK_ID)]
    atom_vocab[(PAD_ID, PAD_ID, PAD_ID)] = PAD_ID
    atom_vocab[(UNK_ID, UNK_ID, UNK_ID)] = UNK_ID
    print("Encoding splits (per-ontology local entity ids) ...")
    X_tr, L_tr, Y_tr, st_tr = encode_dataframe(train_df, pred_vocab, atom_vocab, atom_to_spo)
    X_va, L_va, Y_va, st_va = encode_dataframe(val_df,   pred_vocab, atom_vocab, atom_to_spo)
    X_te, L_te, Y_te, st_te = encode_dataframe(test_df,  pred_vocab, atom_vocab, atom_to_spo)
    n_atoms = len(atom_to_spo)
    print(f"  per-split shape: train_X={X_tr.shape}  val_X={X_va.shape}  test_X={X_te.shape}")
    print(f"  triples/ontology: train  min={L_tr.min()} med={int(np.median(L_tr))} mean={L_tr.mean():.1f} max={L_tr.max()} (capped {MAX_TRIPLES})")
    print(f"  total atoms (unique (s_loc, p_glb, o_loc) triples): {n_atoms:,d}")
    for split, st in (("train", st_tr), ("val", st_va), ("test", st_te)):
        print(f"  {split:>5s}: pred_unk={st['n_pred_unk']}  ent_overflow={st['n_ent_overflow']}  new_atoms={st['n_atoms_new']:,d}  avg_local_entities={st['avg_local_entities']:.1f}  max_local_entities={st['max_local_entities']}")
    atom_to_spo_t = torch.as_tensor(atom_to_spo, dtype=torch.long)
    train_tensors = to_device_tensors(X_tr, L_tr, Y_tr)
    val_tensors   = to_device_tensors(X_va, L_va, Y_va)
    test_tensors  = to_device_tensors(X_te, L_te, Y_te)
    return _run_all_seeds(label,
                          train_tensors, val_tensors, test_tensors,
                          n_atoms=n_atoms, n_local_ent=n_local_ent, n_pred=n_pred,
                          atom_to_spo=atom_to_spo_t,
                          shuffle_train_labels=shuffle_train_labels)

def main():
    print(f"[NLR_SRC] {NLR_SRC}")
    print("Loading CSVs ...")
    train_df = pd.read_csv(TRAIN_CSV)
    val_df   = pd.read_csv(VAL_CSV)
    test_df  = pd.read_csv(TEST_CSV)
    print(f"  train={len(train_df)}  val={len(val_df)}  test={len(test_df)}")
    print(f"  pos: train={train_df['injected_pattern'].apply(is_injected).sum()} val={val_df['injected_pattern'].apply(is_injected).sum()} test={test_df['injected_pattern'].apply(is_injected).sum()}")

    if USE_REPEATED_RESPLITS:
        pool_df = pd.concat([train_df, val_df], ignore_index=True)
        val_ratio = RESPLIT_VAL_RATIO if RESPLIT_VAL_RATIO is not None else (len(val_df) / max(len(pool_df), 1))
        labels = pool_df['injected_pattern'].apply(is_injected).astype(int).to_numpy()
        splitter = StratifiedShuffleSplit(
            n_splits=REPEATED_RESPLIT_COUNT,
            test_size=val_ratio,
            random_state=REPEATED_RESPLIT_SEED,
        )
        all_repeat_runs = []
        for repeat_idx, (tr_idx, va_idx) in enumerate(splitter.split(np.zeros(len(pool_df)), labels), start=1):
            rep_train_df = pool_df.iloc[tr_idx].reset_index(drop=True)
            rep_val_df   = pool_df.iloc[va_idx].reset_index(drop=True)
            print("\n" + "#" * 78)
            print(f"# Repeated resplit {repeat_idx}/{REPEATED_RESPLIT_COUNT}")
            print("#" * 78)
            print(f"  train={len(rep_train_df)}  val={len(rep_val_df)}  test={len(test_df)}")
            print(f"  pos: train={rep_train_df['injected_pattern'].apply(is_injected).sum()} val={rep_val_df['injected_pattern'].apply(is_injected).sum()} test={test_df['injected_pattern'].apply(is_injected).sum()}")
            runs = _encode_and_run_experiment(
                f"NLR [repeat {repeat_idx}]",
                rep_train_df, rep_val_df, test_df,
                shuffle_train_labels=False,
            )
            for run in runs:
                run['repeat_index'] = repeat_idx
            all_repeat_runs.extend(runs)
        print("\n" + "#" * 78)
        print("# Overall repeated-resplit summary")
        print("#" * 78)
        _summarize_runs("NLR [repeated resplits]", all_repeat_runs)
    else:
        _encode_and_run_experiment("NLR", train_df, val_df, test_df, shuffle_train_labels=False)
        if RUN_SHUFFLED_LABEL_CONTROL:
            _encode_and_run_experiment("NLR", train_df, val_df, test_df, shuffle_train_labels=True)

if __name__ == "__main__":
    main()
