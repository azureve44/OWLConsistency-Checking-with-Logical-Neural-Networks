"""
Neural Logic Machine (NLM) for BioPortal ontology consistency verification
Entity locality:

inside each ontology every distinct IRI gets a sequential integer 0, 1, 2, ... capped at MAX_ENTITIES-1.
Predicates remain globally indexed (train-only vocabulary).

script auto-adds "repo"/third_party/Jacinle to sys.path so jactorch is importable
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

_REPO    = os.path.dirname(os.path.abspath(__file__))
_JACINLE = os.path.join(_REPO, "third_party", "Jacinle")
for _p in [_REPO, _JACINLE]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
from difflogic.nn.neural_logic import LogicMachine  # noqa: E402

TRAIN_CSV = "path/to/splits/train_data.csv"
VAL_CSV   = "path/to/splits/eval_data.csv"
TEST_CSV  = "path/to/splits/test_data.csv"

MAX_ENTITIES  = 256
MAX_TRIPLES   = 1024    # biop: 1024
MIN_PRED_FREQ = 1
NLM_DEPTH       = 3     # biop: 4
NLM_BREADTH     = 2     # binary relations (max arity handled = 2)
NLM_ATTRIBUTES  = 32    # biop: 48
NLM_HIDDEN_DIM  = [128] # biop: 256
NLM_IO_RESIDUAL = True  # re-inject the original (mask, adj) at every layer so
                        # the validity-of-entity signal is never lost

PRED_EMB_DIM   = 16     # biop: 24
# classifier head
CLF_HIDDEN_DIM = 128    # biop: 256
DROPOUT        = 0.2    # biop: 0.1

EPOCHS               = 150   # biop: 80
BATCH_SIZE           = 16    # biop: 32
EVAL_BATCH_SIZE      = 16    # biop: 32
LEARNING_RATE        = 3e-3
WEIGHT_DECAY         = 1e-4     # biop: 1e-5
GRAD_CLIP            = 1.0
THRESHOLD            = 0.5
USE_COSINE_LR        = True     # cosine anneal LEARNING_RATE -> LR/100 over EPOCHS
EARLY_STOP_PATIENCE  = 20       # biop: 16
EARLY_STOP_MIN_DELTA = 0.018     # require >=1-2 val samples to flip (1/57~0.018)  biop: 1e-4
EARLY_STOP_METRIC    = "bacc"   # "acc" | "bacc" | "f1"
# sanity check
SEEDS                      = [0, 1, 2, 3, 4]
RUN_SHUFFLED_LABEL_CONTROL = True
SHUFFLED_USE_FIXED_EPOCHS  = True  # control: no val-based snapshot -> no leakage
SHUFFLE_SEED_OFFSET        = 1000
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[device] {DEVICE}"
      + (f" ({torch.cuda.get_device_name(0)})" if DEVICE.type == "cuda" else ""))

def _fmt_time(seconds: float) -> str:
    t = timedelta(seconds=seconds).total_seconds()
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"
def is_injected(val) -> bool:
    return pd.notna(val) and str(val).strip().lower() != "none"
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
def _norm_iri(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().rstrip(",").strip())
def _norm_pred(p: str) -> str:
    return p.strip()
def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

# Predicate channel layout inside adj tensor (0-indexed):
#   channel 0         = UNK predicate  (unknown / too-rare predicates)
#   channel 1 .. N    = known predicates  (N = len(pred_vocab))
# total channels  N_PRED_CH = len(pred_vocab) + 1
def build_predicate_vocab(train_df: pd.DataFrame,
                           min_freq: int = MIN_PRED_FREQ) -> dict:
    """Build train-only predicate vocabulary:  pred_str -> channel_id in [1..N].
    Channel 0 is reserved for UNK.
    """
    counter: Counter = Counter()
    for body in train_df["body"]:
        for _, p, _ in parse_body(body):
            counter[_norm_pred(p)] += 1
    vocab: dict = {}
    nxt = 1
    for tok, cnt in counter.most_common():
        if cnt >= min_freq:
            vocab[tok] = nxt
            nxt += 1
    return vocab
def encode_dataframe(df: pd.DataFrame,
                     pred_vocab: dict,
                     max_entities: int = MAX_ENTITIES,
                     max_triples: int = MAX_TRIPLES):
    """Encode each ontology row into compact triple arrays.
    Returns

    spo_arr  :  int16 ndarray [n, max_triples, 3]
                valid entry stores (s_node_idx, pred_ch, o_node_idx)
                -1 means the slot is unused / overflowed
    lengths  : int32 ndarray [n]   stored triple count per ontology
    n_ents   : int32 ndarray [n]   valid entity count (0 .. max_entities-1)
    labels   : float32 ndarray [n]
    stats    : dict
    """
    n = len(df)
    spo_arr = np.full((n, max_triples, 3), -1, dtype=np.int16)
    lengths = np.zeros(n, dtype=np.int32)
    n_ents  = np.zeros(n, dtype=np.int32)
    labels  = np.zeros(n, dtype=np.float32)
    n_pred_unk                    = 0
    n_ent_overflow                = 0  # endpoint overflow attempts (not unique IRIs)
    n_triples_raw                 = 0
    n_triples_cap_dropped         = 0
    n_triples_entity_dropped      = 0
    n_rows_entity_at_cap          = 0
    n_rows_with_entity_drop       = 0
    n_ent_total                   = 0
    max_ent_in_one                = 0
    for i, (_, row) in enumerate(df.iterrows()):
        all_triples = parse_body(row["body"])
        n_triples_raw += len(all_triples)
        if len(all_triples) > max_triples:
            n_triples_cap_dropped += len(all_triples) - max_triples
        triples = all_triples[:max_triples]
        labels[i] = 1.0 if is_injected(row["injected_pattern"]) else 0.0
        if not triples:
            continue
        ent_map: dict = {}
        row_had_entity_drop = False
        def node_idx(iri: str) -> int:
            nonlocal n_ent_overflow
            iri = _norm_iri(iri)
            if iri in ent_map:
                return ent_map[iri]
            idx = len(ent_map)
            if idx >= max_entities:
                n_ent_overflow += 1
                return -1   # overflow -> drop triple
            ent_map[iri] = idx
            return idx
        k_valid = 0
        for s_iri, p_raw, o_iri in triples:
            s_idx = node_idx(s_iri)
            o_idx = node_idx(o_iri)
            if s_idx < 0 or o_idx < 0:
                n_triples_entity_dropped += 1
                row_had_entity_drop = True
                continue
            p_ch = pred_vocab.get(_norm_pred(p_raw), 0)   # 0 = UNK
            if p_ch == 0:
                n_pred_unk += 1
            spo_arr[i, k_valid, 0] = s_idx
            spo_arr[i, k_valid, 1] = p_ch
            spo_arr[i, k_valid, 2] = o_idx
            k_valid += 1
            if k_valid >= max_triples:
                break
        lengths[i] = k_valid
        n_ents[i]  = len(ent_map)
        if len(ent_map) >= max_entities:
            n_rows_entity_at_cap += 1
        if row_had_entity_drop:
            n_rows_with_entity_drop += 1
        n_ent_total += len(ent_map)
        if len(ent_map) > max_ent_in_one:
            max_ent_in_one = len(ent_map)
    n_triples_stored = int(lengths.sum())
    return spo_arr, lengths, n_ents, labels, dict(
        n_pred_unk=n_pred_unk,
        n_ent_overflow=n_ent_overflow,
        n_triples_raw=n_triples_raw,
        n_triples_stored=n_triples_stored,
        n_triples_cap_dropped=n_triples_cap_dropped,
        n_triples_entity_dropped=n_triples_entity_dropped,
        n_triples_dropped=n_triples_entity_dropped,  # backward-compatible alias
        n_rows_entity_at_cap=n_rows_entity_at_cap,
        n_rows_with_entity_drop=n_rows_with_entity_drop,
        pct_triples_retained=100.0 * n_triples_stored / max(n_triples_raw, 1),
        avg_local_entities=n_ent_total / max(n, 1),
        max_local_entities=max_ent_in_one,
    )

def build_adj(spo_t: torch.Tensor,
              lengths_t: torch.Tensor,
              n_pred_ch: int,
              max_entities: int = None) -> torch.Tensor:
    """Build multi-hot adjacency tensor from a batch of compact triple arrays
    Parameters

    spo_t     : [B, T, 3] long  : (s_node, pred_ch, o_node), -1=invalid
    lengths_t : [B] long        : stored triple count per ontology
    n_pred_ch : int             : total predicate channels (incl. UNK=0)

    Returns

    adj : [B, N, N, n_pred_ch] float32, N is max_entities or MAX_ENTITIES
    """
    B, T, _ = spo_t.shape
    n_nodes = MAX_ENTITIES if max_entities is None else int(max_entities)
    n_nodes = max(1, min(n_nodes, MAX_ENTITIES))
    t_range = torch.arange(T, device=spo_t.device).unsqueeze(0)  # [1, T]
    s = spo_t[:, :, 0]   # [B, T]
    p = spo_t[:, :, 1]   # [B, T]
    o = spo_t[:, :, 2]   # [B, T]
    valid = (
        (t_range < lengths_t.unsqueeze(1))
        & (s >= 0) & (s < n_nodes)
        & (p >= 0) & (p < n_pred_ch)
        & (o >= 0) & (o < n_nodes)
    )   # [B, T] bool
    b_idx = torch.arange(B, device=spo_t.device).unsqueeze(1).expand(B, T)
    mb = b_idx[valid]
    ms = s[valid]
    mp = p[valid]
    mo = o[valid]
    adj = torch.zeros(B, n_nodes, n_nodes, n_pred_ch,
                      device=spo_t.device, dtype=torch.float32)
    if mb.numel() > 0:
        adj[mb, ms, mo, mp] = 1.0
    return adj
def batch_num_nodes(n_ents_t: torch.Tensor) -> int:
    """Smallest dense N needed for this batch, clamped to [1, MAX_ENTITIES]."""
    if n_ents_t.numel() == 0:
        return 1
    return max(1, min(int(n_ents_t.max().item()), MAX_ENTITIES))

class OntologyNLM(nn.Module):
    """NLM-based ontology consistency classifier
    Inputs
    ------
    adj    : [B, N, N, n_pred_ch]  multi-hot adjacency
    n_ents : [B]                   number of valid entity nodes per graph
    Output
    ------
    logit : [B]   raw pre-sigmoid logit for inconsistency
    """
    def __init__(self,
                 n_pred_ch: int,
                 nlm_depth: int       = NLM_DEPTH,
                 nlm_breadth: int     = NLM_BREADTH,
                 nlm_attributes: int  = NLM_ATTRIBUTES,
                 nlm_hidden_dim: list = None,
                 pred_emb_dim: int    = PRED_EMB_DIM,
                 io_residual: bool    = NLM_IO_RESIDUAL,
                 clf_hidden_dim: int  = CLF_HIDDEN_DIM,
                 dropout: float       = DROPOUT):
        super().__init__()
        if nlm_hidden_dim is None:
            nlm_hidden_dim = list(NLM_HIDDEN_DIM)
        # Predicate-channel embedding (shared across all (i,j) positions)
        # Acts as 1x1 conv over the channel dim
        # Sigmoid keeps values in [0,1]
        # so the LogicMachine sees probabilistic-truth-valued predicates
        self.pred_proj = nn.Sequential(
            nn.Linear(n_pred_ch, pred_emb_dim, bias=True),
            nn.Sigmoid(),
        )
        # NLM input layout:  nullary=0, unary=1 (validity), binary=pred_emb_dim
        input_dims = [0] * (nlm_breadth + 1)
        input_dims[1] = 1
        input_dims[2] = pred_emb_dim
        self.nlm = LogicMachine(
            depth=nlm_depth,
            breadth=nlm_breadth,
            input_dims=input_dims,
            output_dims=nlm_attributes,
            logic_hidden_dim=nlm_hidden_dim,
            exclude_self=True,
            residual=False,
            io_residual=io_residual,
        )
        self._io_residual = io_residual
        self._input_dims  = input_dims
        d_null   = self.nlm.output_dims[0]
        d_unary  = self.nlm.output_dims[1]
        d_binary = self.nlm.output_dims[2]
        pool_dim = d_null + d_unary * 2 + d_binary * 2
        self.classifier = nn.Sequential(
            nn.Linear(pool_dim, clf_hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(clf_hidden_dim, 1),
            # NOTE: no Sigmoid, we return logits for BCEWithLogitsLoss
        )
        self._d_null   = d_null
        self._d_unary  = d_unary
        self._d_binary = d_binary
        nn.init.xavier_uniform_(self.pred_proj[0].weight, gain=2.0)
        nn.init.zeros_(self.pred_proj[0].bias)
        # classifier head: kaiming for ReLU
        for m in self.classifier:
            if isinstance(m, nn.Linear):
                nn.init.kaiming_uniform_(m.weight, nonlinearity='relu')
                nn.init.zeros_(m.bias)
    def _run_nlm_masked(self, unary, adj, ent_msk):
        """
        Run LogicMachine layer-by-layer, re-masking padded entity slots
        between layers so that the Reducer's min/max never see padding
        Mirrors LogicMachine.forward but injects masks; supports io_residual
        """
        unary_msk  = ent_msk.unsqueeze(-1).float()                   # [B,N,1]
        binary_msk = (ent_msk.unsqueeze(2) & ent_msk.unsqueeze(1)
                      ).unsqueeze(-1).float()                        # [B,N,N,1]
        # Pre-mask inputs (defensive, build_adj is already mask-clean)
        unary = unary * unary_msk
        adj   = adj   * binary_msk
        f = [None, unary, adj]
        inputs = [None, unary, adj]
        # Re-implement LogicMachine.forward with masking
        # we support both plain (last-layer output) and io_residual (concat across layers)
        # modes, matching difflogic/nn/neural_logic/layer.py::LogicMachine
        def merge(x, y):
            if x is None: return y
            if y is None: return x
            return torch.cat([x, y], dim=-1)
        outputs_io = [None, None, None]
        for i, layer in enumerate(self.nlm.layers):
            if i > 0 and self._io_residual:
                f = [merge(fi, ii) for fi, ii in zip(f, inputs)]
            f = layer(f)
            # Mask out invalid entity slots so they cannot poison the next
            # layer's Reducer (min/max) or the final pooling
            if f[1] is not None:
                f[1] = f[1] * unary_msk
            if f[2] is not None:
                f[2] = f[2] * binary_msk
            if self._io_residual:
                outputs_io = [merge(o, ff) for o, ff in zip(outputs_io, f)]
        return outputs_io if self._io_residual else f
    def forward(self, adj: torch.Tensor, n_ents: torch.Tensor) -> torch.Tensor:
        B, N = adj.shape[0], adj.shape[1]
        t_idx   = torch.arange(N, device=adj.device).unsqueeze(0)   # [1, N]
        ent_msk = (t_idx < n_ents.unsqueeze(1))                     # [B, N] bool
        # Densify predicate channels: [B,N,N,P] -> [B,N,N,pred_emb_dim]
        adj_emb = self.pred_proj(adj)
        unary   = ent_msk.float().unsqueeze(-1)                     # [B,N,1]
        outputs = self._run_nlm_masked(unary, adj_emb, ent_msk)
        unary_msk  = ent_msk.float().unsqueeze(-1)                  # [B,N,1]
        binary_msk = (ent_msk.unsqueeze(2) & ent_msk.unsqueeze(1)
                      ).float().unsqueeze(-1)                       # [B,N,N,1]
        cnt_u = ent_msk.float().sum(dim=1, keepdim=True).clamp(min=1.0)         # [B,1]
        cnt_b = binary_msk.squeeze(-1).sum(dim=[1, 2]).clamp(min=1.0)           # [B]
        features = []
        # Nullary
        if outputs[0] is not None and self._d_null > 0:
            features.append(outputs[0])
        # Unary -> mean+max over valid entities
        if outputs[1] is not None and self._d_unary > 0:
            u_out = outputs[1] * unary_msk
            u_mean = u_out.sum(dim=1) / cnt_u
            u_max  = u_out.masked_fill(unary_msk == 0, -1e9).max(dim=1).values
            features += [u_mean, u_max]
        # Binary -> mean+max over valid pairs
        if outputs[2] is not None and self._d_binary > 0:
            b_out = outputs[2] * binary_msk
            b_mean = b_out.sum(dim=[1, 2]) / cnt_b.unsqueeze(-1)
            b_max  = (b_out.masked_fill(binary_msk == 0, -1e9)
                       .view(B, N * N, -1).max(dim=1).values)
            features += [b_mean, b_max]
        pooled = torch.cat(features, dim=-1)
        return self.classifier(pooled).squeeze(-1)  # raw logits [B]
def iterate_balanced_batches(idx_pos: np.ndarray, idx_neg: np.ndarray,
                             batch_size: int, rng: np.random.Generator):
    half = max(batch_size // 2, 1)
    rng.shuffle(idx_pos)
    rng.shuffle(idx_neg)
    n = max(len(idx_pos), len(idx_neg))
    for start in range(0, n, half):
        p  = idx_pos[start:start + half] if len(idx_pos) else np.array([], dtype=np.int64)
        ng = idx_neg[start:start + half] if len(idx_neg) else np.array([], dtype=np.int64)
        if len(p)  == 0 and len(idx_pos): p  = rng.choice(idx_pos, half, replace=True)
        if len(ng) == 0 and len(idx_neg): ng = rng.choice(idx_neg, half, replace=True)
        if len(p) == 0 and len(ng) == 0:
            continue
        yield np.concatenate([p, ng])

@torch.no_grad()
def evaluate_split(model: OntologyNLM,
                   spo_t: torch.Tensor,
                   lengths_t: torch.Tensor,
                   n_ents_t: torch.Tensor,
                   Y_np: np.ndarray,
                   n_pred_ch: int,
                   batch_size: int = EVAL_BATCH_SIZE) -> dict:
    model.eval()
    n = Y_np.shape[0]
    y_pred = np.zeros(n, dtype=np.int64)
    t0 = time.perf_counter()
    for start in range(0, n, batch_size):
        end   = min(start + batch_size, n)
        nents_b = n_ents_t[start:end]
        n_nodes = batch_num_nodes(nents_b)
        adj_b = build_adj(spo_t[start:end], lengths_t[start:end], n_pred_ch,
                          max_entities=n_nodes)
        logit = model(adj_b, nents_b)
        prob  = torch.sigmoid(logit).detach().cpu().numpy()
        y_pred[start:end] = (prob >= THRESHOLD).astype(int)
    return {
        "acc":  accuracy_score(Y_np, y_pred),
        "bacc": balanced_accuracy_score(Y_np, y_pred),
        "prec": precision_score(Y_np, y_pred, zero_division=0),
        "rec":  recall_score(Y_np, y_pred, zero_division=0),
        "f1":   f1_score(Y_np, y_pred, zero_division=0),
        "inference_seconds": time.perf_counter() - t0,
    }

def _snapshot(model: nn.Module) -> dict:
    return {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
def _restore(model: nn.Module, snap: dict) -> None:
    model.load_state_dict({k: v.to(DEVICE) for k, v in snap.items()})
def run_one_seed(split_data: tuple,
                 n_pred_ch: int,
                 seed: int,
                 epochs: int = EPOCHS,
                 lr: float   = LEARNING_RATE,
                 verbose: bool = True,
                 shuffled_fixed: bool = False) -> dict:
    """
    Train NLM for one random seed
    split_data = (train_tuple, val_tuple, test_tuple)
    Each tuple: (spo_t, lengths_t, n_ents_t, Y_t
    shuffled_fixed=True: train all epochs, return final-epoch model
    """
    seed_everything(seed)
    (spo_tr, len_tr, nent_tr, Y_tr), \
    (spo_va, len_va, nent_va, Y_va), \
    (spo_te, len_te, nent_te, Y_te) = split_data
    model = OntologyNLM(n_pred_ch=n_pred_ch).to(DEVICE)
    crit  = nn.BCEWithLogitsLoss()
    opt   = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=WEIGHT_DECAY)
    sched = (
        torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=lr / 100.0)
        if USE_COSINE_LR else None
    )
    Y_tr_np  = Y_tr.cpu().numpy().astype(int)
    idx_pos  = np.where(Y_tr_np == 1)[0]
    idx_neg  = np.where(Y_tr_np == 0)[0]
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    if verbose:
        print(f"  [seed {seed}] NLM  n_pred_ch={n_pred_ch}  "
              f"MAX_ENTITIES={MAX_ENTITIES}  depth={NLM_DEPTH}  "
              f"attrs={NLM_ATTRIBUTES}  params={n_params:,}  device={DEVICE}  "
              f"train pos={len(idx_pos)} neg={len(idx_neg)}")
    best_metric = -1.0
    best_epoch  = -1
    best_state  = None
    no_improve  = 0
    last_epoch  = 0
    rng = np.random.default_rng(seed)
    t0  = time.perf_counter()
    for epoch in range(epochs):
        ep_t0 = time.perf_counter()
        model.train()
        ep_loss = ep_seen = 0
        for bidx in iterate_balanced_batches(idx_pos.copy(), idx_neg.copy(),
                                             BATCH_SIZE, rng):
            idx_t = torch.as_tensor(bidx, dtype=torch.long, device=DEVICE)
            nents_b = nent_tr[idx_t]
            n_nodes = batch_num_nodes(nents_b)
            adj_b = build_adj(spo_tr[idx_t], len_tr[idx_t], n_pred_ch,
                              max_entities=n_nodes)
            logit = model(adj_b, nents_b)
            loss  = crit(logit, Y_tr[idx_t])
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            opt.step()
            ep_loss += float(loss.item()) * idx_t.size(0)
            ep_seen += idx_t.size(0)
        Y_va_np = Y_va.cpu().numpy().astype(int)
        val_m   = evaluate_split(model, spo_va, len_va, nent_va, Y_va_np, n_pred_ch)
        if verbose:
            print(f"  [seed {seed}] ep {epoch:03d}/{epochs}  "
                  f"loss={ep_loss/max(ep_seen,1):.4f}  "
                  f"val_acc={val_m['acc']:.4f}  val_bacc={val_m['bacc']:.4f}  "
                  f"val_f1={val_m['f1']:.4f}  "
                  f"| ep_time={time.perf_counter()-ep_t0:.1f}s")
        last_epoch = epoch
        if sched is not None:
            sched.step()
        if shuffled_fixed:
            best_state  = None
            best_epoch  = epoch
            best_metric = val_m[EARLY_STOP_METRIC]
            continue
        cur = val_m[EARLY_STOP_METRIC]
        if cur > best_metric + EARLY_STOP_MIN_DELTA:
            best_metric = cur
            best_epoch  = epoch
            no_improve  = 0
            best_state  = _snapshot(model)
        else:
            no_improve += 1
            if no_improve >= EARLY_STOP_PATIENCE:
                if verbose:
                    print(f"  [seed {seed}] early stop ep {epoch:03d} "
                          f"(no val_{EARLY_STOP_METRIC} improvement for "
                          f"{EARLY_STOP_PATIENCE}; best ep {best_epoch:03d} "
                          f"{EARLY_STOP_METRIC}={best_metric:.4f})")
                break
    train_secs = time.perf_counter() - t0
    if best_state is not None:
        _restore(model, best_state)
    def _eval(spo, lens, nents, Y):
        return evaluate_split(model, spo, lens, nents,
                              Y.cpu().numpy().astype(int), n_pred_ch)
    train_m = _eval(spo_tr, len_tr, nent_tr, Y_tr)
    val_m   = _eval(spo_va, len_va, nent_va, Y_va)
    test_m  = _eval(spo_te, len_te, nent_te, Y_te)
    if verbose:
        for nm, m in [("train", train_m), ("val", val_m), ("test", test_m)]:
            print(f"  [seed {seed}] {nm:>5s} -> "
                  f"Acc {m['acc']:.4f}  Prec {m['prec']:.4f}  "
                  f"Rec {m['rec']:.4f}  F1 {m['f1']:.4f}  "
                  f"(infer {_fmt_time(m['inference_seconds'])})")
    del model, opt
    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()
    return {"train_seconds": train_secs,
            "train": train_m, "val": val_m, "test": test_m,
            "best_epoch": best_epoch, "stopped_epoch": last_epoch}

def _run_all_seeds(label: str,
                   split_data: tuple,
                   n_pred_ch: int,
                   shuffle_train_labels: bool = False):
    print(f"\n{'#'*78}\n# Experiment: {label}"
          f"{'  [shuffled train labels]' if shuffle_train_labels else ''}\n{'#'*78}")
    (spo_tr, len_tr, nent_tr, Y_tr), va, te = split_data
    all_runs = []
    for seed in SEEDS:
        print(f"\n=== Seed {seed} ({label}) ===")
        td = (spo_tr, len_tr, nent_tr, Y_tr)
        if shuffle_train_labels:
            shuf_rng = np.random.default_rng(seed + SHUFFLE_SEED_OFFSET)
            Y_np = Y_tr.cpu().numpy().copy()
            shuf_rng.shuffle(Y_np)
            Y_shuf = torch.as_tensor(Y_np, dtype=torch.float32, device=DEVICE)
            td = (spo_tr, len_tr, nent_tr, Y_shuf)
        run = run_one_seed(
            split_data=(td, va, te),
            n_pred_ch=n_pred_ch,
            seed=seed,
            epochs=EPOCHS,
            lr=LEARNING_RATE,
            verbose=True,
            shuffled_fixed=(shuffle_train_labels and SHUFFLED_USE_FIXED_EPOCHS),
        )
        all_runs.append(run)
    def agg(split, key):
        v = np.array([r[split][key] for r in all_runs])
        return v.mean(), v.std()
    train_secs = np.array([r["train_seconds"] for r in all_runs])
    test_inf   = np.array([r["test"]["inference_seconds"] for r in all_runs])
    print("\n" + "="*78)
    print(f"Aggregated over {len(SEEDS)} seeds (mean +/- std)")
    print("="*78)
    for split in ("train", "val", "test"):
        a_m, a_s = agg(split, "acc")
        p_m, p_s = agg(split, "prec")
        r_m, r_s = agg(split, "rec")
        f_m, f_s = agg(split, "f1")
        print(f"  {split:>5s} : Acc {a_m*100:5.2f} +/-{a_s*100:.2f}  "
              f"Prec {p_m*100:5.2f} +/-{p_s*100:.2f}  "
              f"Rec  {r_m*100:5.2f} +/-{r_s*100:.2f}  "
              f"F1 {f_m*100:5.2f} +/-{f_s*100:.2f}")
    print(f"  Training (wall): {_fmt_time(train_secs.mean())} +/-{train_secs.std():.2f}s")
    print(f"  Test inference:  {_fmt_time(test_inf.mean())} +/-{test_inf.std():.3f}s")
    a_m, a_s = agg("test", "acc")
    p_m, p_s = agg("test", "prec")
    r_m, r_s = agg("test", "rec")
    print("\n" + "="*78)
    print(f"Paper-table row (use in tab:result-bioportal)")
    print("="*78)
    print(
        f"{label} & "
        f"${a_m*100:5.2f}_{{({a_s*100:.2f})}}$ & "
        f"${p_m*100:5.2f}_{{({p_s*100:.2f})}}$ & "
        f"${r_m*100:5.2f}_{{({r_s*100:.2f})}}$ & "
        f"{_fmt_time(train_secs.mean())} & "
        f"{_fmt_time(test_inf.mean())} \\\\"
    )
    print("="*78)

def main():
    print("Loading CSVs ...")
    train_df = pd.read_csv(TRAIN_CSV)
    val_df   = pd.read_csv(VAL_CSV)
    test_df  = pd.read_csv(TEST_CSV)
    print(f"  train={len(train_df)}  val={len(val_df)}  test={len(test_df)}")
    print(f"  pos: train={train_df['injected_pattern'].apply(is_injected).sum()} "
          f"val={val_df['injected_pattern'].apply(is_injected).sum()} "
          f"test={test_df['injected_pattern'].apply(is_injected).sum()}")
    print("Building predicate vocab (train-only) ...")
    pred_vocab = build_predicate_vocab(train_df)
    n_pred_ch  = len(pred_vocab) + 1   # +1 for UNK channel 0
    print(f"  {len(pred_vocab):,} unique predicates -> n_pred_ch={n_pred_ch}")
    # Encode splits
    print(f"Encoding splits (per-ontology local entity ids, cap={MAX_ENTITIES}) ...")
    spo_tr, len_tr, nent_tr, Y_tr, st_tr = encode_dataframe(train_df, pred_vocab)
    spo_va, len_va, nent_va, Y_va, st_va = encode_dataframe(val_df,   pred_vocab)
    spo_te, len_te, nent_te, Y_te, st_te = encode_dataframe(test_df,  pred_vocab)
    for sp, st in [("train", st_tr), ("val", st_va), ("test", st_te)]:
        print(f"  {sp:>5s}: pred_unk={st['n_pred_unk']}  "
              f"overflow_endpoint_attempts={st['n_ent_overflow']}  "
              f"rows_at_entity_cap={st['n_rows_entity_at_cap']}  "
              f"rows_with_entity_drop={st['n_rows_with_entity_drop']}  "
              f"avg_entities={st['avg_local_entities']:.1f}  "
              f"max_entities={st['max_local_entities']}")
        print(f"         triples: raw={st['n_triples_raw']}  "
              f"stored={st['n_triples_stored']}  "
              f"cap_dropped={st['n_triples_cap_dropped']}  "
              f"entity_dropped={st['n_triples_entity_dropped']}  "
              f"retained={st['pct_triples_retained']:.1f}%")
    for sp, lens in [("train", len_tr), ("val", len_va), ("test", len_te)]:
        print(f"  {sp:>5s}: triples  min={lens.min()} "
              f"med={int(np.median(lens))} "
              f"mean={lens.mean():.1f} max={lens.max()}")
    # Architecture sanity check
    _m = OntologyNLM(n_pred_ch=n_pred_ch)
    _n = sum(p.numel() for p in _m.parameters() if p.requires_grad)
    print(f"\n[model] trainable params: {_n:,}  "
          f"NLM output_dims: {_m.nlm.output_dims}"
          f"  (null={_m._d_null}, unary={_m._d_unary}, binary={_m._d_binary})")
    del _m
    # to GPU
    def to_dev(a, dt):
        return torch.as_tensor(a, dtype=dt, device=DEVICE)
    train_data = (to_dev(spo_tr, torch.long), to_dev(len_tr, torch.long),
                  to_dev(nent_tr, torch.long), to_dev(Y_tr, torch.float32))
    val_data   = (to_dev(spo_va, torch.long), to_dev(len_va, torch.long),
                  to_dev(nent_va, torch.long), to_dev(Y_va, torch.float32))
    test_data  = (to_dev(spo_te, torch.long), to_dev(len_te, torch.long),
                  to_dev(nent_te, torch.long), to_dev(Y_te, torch.float32))
    split_data = (train_data, val_data, test_data)
    # Real-label experiment
    _run_all_seeds("NLM",
                   split_data=split_data,
                   n_pred_ch=n_pred_ch,
                   shuffle_train_labels=False)
    # sanity check
    if RUN_SHUFFLED_LABEL_CONTROL:
        _run_all_seeds("NLM (shuffled-labels control)",
                       split_data=split_data,
                       n_pred_ch=n_pred_ch,
                       shuffle_train_labels=True)
if __name__ == "__main__":
    main()
