import ast
import copy
import os
import random
import time
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import torch
import wandb
from sklearn.metrics import accuracy_score, precision_score, recall_score
from torch.optim import AdamW
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm
from transformers import AutoTokenizer, ModernBertForSequenceClassification
SEEDS = [0, 1, 2] # time: [0, 1, 2,3,4]
MODEL_NAME = "answerdotai/ModernBERT-base"
RUN_LABEL = "ModernBert"
EARLY_STOPPING_MIN_DELTA = 0.01
def _fmt_time(seconds: float) -> str:
    total = float(seconds)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"
def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
def _load_data() -> Tuple[Dict[str, List], Dict[str, pd.Series], Dict[str, int]]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    splits_dir = os.path.normpath(os.path.join(base_dir, "../../../nsplits"))
    train_df = pd.read_csv(os.path.join(splits_dir, "train_data.csv"), header=0)
    eval_df = pd.read_csv(os.path.join(splits_dir, "eval_data.csv"), header=0)
    test_df = pd.read_csv(os.path.join(splits_dir, "test_data.csv"), header=0)
    graph_dict = {
        "train": [ast.literal_eval(triples) for triples in train_df["body"]],
        "eval": [ast.literal_eval(triples) for triples in eval_df["body"]],
        "test": [ast.literal_eval(triples) for triples in test_df["body"]],
    }
    label_2_index = {"Inconsistent": 1, "Consistent": 0}
    label_dict = {
        "train": train_df["consistency"].map(label_2_index),
        "eval": eval_df["consistency"].map(label_2_index),
        "test": test_df["consistency"].map(label_2_index),
    }
    return graph_dict, label_dict, label_2_index
def _graph_to_text(triples) -> str:
    return " ".join([f"{s} {p} {o}." for s, p, o in triples])
def _tokenize_split(tokenizer, graphs: List, labels: List[int], max_input_length: int = 4096) -> TensorDataset:
    texts = [_graph_to_text(graph) for graph in graphs]
    encodings = tokenizer(
        texts,
        padding="max_length",
        truncation=True,
        max_length=max_input_length,
        return_tensors="pt",
    )
    label_tensor = torch.tensor(labels, dtype=torch.long)
    return TensorDataset(encodings["input_ids"], encodings["attention_mask"], label_tensor)
def _run_train_epoch(model, dataloader: DataLoader, optimizer, device: str) -> Tuple[float, float]:
    model.train()
    total_loss = 0.0
    all_preds = []
    all_labels = []
    for batch in tqdm(dataloader, leave=False):
        input_ids, attention_mask, labels = [x.to(device) for x in batch]
        output = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
        loss = output.loss
        logits = output.logits
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        total_loss += loss.item() * len(labels)
        all_preds.append(logits.argmax(dim=-1).detach().cpu())
        all_labels.append(labels.detach().cpu())
    preds = torch.cat(all_preds).numpy()
    labels = torch.cat(all_labels).numpy()
    avg_loss = total_loss / max(len(labels), 1)
    avg_accuracy = accuracy_score(labels, preds)
    return avg_loss, avg_accuracy
def _run_eval_epoch(model, dataloader: DataLoader, device: str) -> Dict[str, float]:
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_labels = []
    with torch.no_grad():
        for batch in tqdm(dataloader, leave=False):
            input_ids, attention_mask, labels = [x.to(device) for x in batch]
            output = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            total_loss += output.loss.item() * len(labels)
            all_preds.append(output.logits.argmax(dim=-1).detach().cpu())
            all_labels.append(labels.detach().cpu())
    preds = torch.cat(all_preds).numpy()
    labels = torch.cat(all_labels).numpy()
    return {
        "loss": total_loss / max(len(labels), 1),
        "acc": accuracy_score(labels, preds),
        "prec": precision_score(labels, preds, zero_division=0),
        "rec": recall_score(labels, preds, zero_division=0),
    }
def _aggregate_and_print(all_runs: List[Dict], label: str) -> None:
    def agg(split: str, key: str):
        values = np.array([run[split][key] for run in all_runs], dtype=float)
        return values.mean(), values.std()
    train_secs = np.array([run["train_seconds"] for run in all_runs], dtype=float)
    test_inf = np.array([run["test"]["inference_seconds"] for run in all_runs], dtype=float)
    print("\n" + "=" * 78)
    print(f"Aggregated over {len(all_runs)} seeds (mean +/- std) - {label}")
    print("=" * 78)
    for split in ("train", "eval", "test"):
        a_m, a_s = agg(split, "acc")
        p_m, p_s = agg(split, "prec")
        r_m, r_s = agg(split, "rec")
        print(
            f"  {split:>5s} : Acc {a_m * 100:5.2f} +/-{a_s * 100:.2f}  "
            f"Prec {p_m * 100:5.2f} +/-{p_s * 100:.2f}  "
            f"Rec  {r_m * 100:5.2f} +/-{r_s * 100:.2f}"
        )
    print(f"  Training (wall): {_fmt_time(train_secs.mean())}  +/-{train_secs.std():.2f}s")
    print(f"  Test inference:  {_fmt_time(test_inf.mean())}  +/-{test_inf.std():.3f}s")
    a_m, a_s = agg("test", "acc")
    p_m, p_s = agg("test", "prec")
    r_m, r_s = agg("test", "rec")
    print("\n" + "=" * 78)
    print(f"Paper-table row (use in tab:result-bioportal) - {label}:")
    print("=" * 78)
    print(
        f"{label} & "
        f"${a_m * 100:5.2f}_{{({a_s * 100:.2f})}}$ & "
        f"${p_m * 100:5.2f}_{{({p_s * 100:.2f})}}$ & "
        f"${r_m * 100:5.2f}_{{({r_s * 100:.2f})}}$ & "
        f"{_fmt_time(train_secs.mean())} & "
        f"{_fmt_time(test_inf.mean())} \\\\" 
    )
    print("=" * 78)
def main(batch_size: int, device: str, lr: float, wd: float, seed: int, num_epochs: int = 50, early_stopping: int = 5) -> Dict:
    _seed_everything(seed)
    graphs, labels, _ = _load_data()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    train_dataset = _tokenize_split(tokenizer, graphs["train"], labels["train"].tolist())
    eval_dataset = _tokenize_split(tokenizer, graphs["eval"], labels["eval"].tolist())
    test_dataset = _tokenize_split(tokenizer, graphs["test"], labels["test"].tolist())
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    train_eval_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=False)
    eval_loader = DataLoader(eval_dataset, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    model = ModernBertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2).to(device)
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=wd)
    best_epoch = 0
    best_eval_loss = float("inf")
    best_state = copy.deepcopy(model.state_dict())
    stopped_early = False
    print(f"\n=== Seed {seed} ({RUN_LABEL}) ===")
    train_start = time.time()
    for epoch in range(num_epochs):
        train_loss, train_accuracy = _run_train_epoch(model, train_loader, optimizer, device)
        eval_metrics = _run_eval_epoch(model, eval_loader, device)
        if best_eval_loss - eval_metrics["loss"] >= EARLY_STOPPING_MIN_DELTA:
            best_epoch = epoch
            best_eval_loss = eval_metrics["loss"]
            best_state = copy.deepcopy(model.state_dict())
        if wandb.run is not None:
            wandb.log(
                {
                    "epoch": epoch,
                    "best_epoch": best_epoch,
                    "stopped_early": float(stopped_early),
                    "train/accuracy": train_accuracy,
                    "train/loss": train_loss,
                    "eval/accuracy": eval_metrics["acc"],
                    "eval/precision": eval_metrics["prec"],
                    "eval/recall": eval_metrics["rec"],
                    "eval/loss": eval_metrics["loss"],
                    "eval/best_loss": best_eval_loss,
                }
            )
        if epoch - best_epoch >= early_stopping:
            stopped_early = True
            break
    train_seconds = time.time() - train_start
    model.load_state_dict(best_state)
    train_metrics = _run_eval_epoch(model, train_eval_loader, device)
    eval_metrics = _run_eval_epoch(model, eval_loader, device)
    inference_start = time.time()
    test_metrics = _run_eval_epoch(model, test_loader, device)
    test_metrics["inference_seconds"] = time.time() - inference_start
    if wandb.run is not None:
        wandb.log(
            {
                "time/training_seconds": train_seconds,
                "time/inference_seconds": test_metrics["inference_seconds"],
                "test/accuracy": test_metrics["acc"],
                "test/precision": test_metrics["prec"],
                "test/recall": test_metrics["rec"],
                "test/loss": test_metrics["loss"],
            }
        )
    return {
        "seed": seed,
        "best_epoch": best_epoch,
        "train": train_metrics,
        "eval": eval_metrics,
        "test": test_metrics,
        "train_seconds": train_seconds,
    }
if __name__ == "__main__":
    batch_size = 4 # dcreased from 8
    device = "cuda:2" if torch.cuda.is_available() else "cpu"
    lr = 1e-5
    wd = 1e-4
    wandb_mode = os.environ.get("WANDB_MODE", "disabled")
    all_runs = []
    for seed in SEEDS:
        wandb_run = wandb.init(
            mode=wandb_mode,
            project="modernBert",
            name=f"{RUN_LABEL}-seed{seed}-lr{lr}-wd{wd}",
            config={
                "learning_rate": lr,
                "weight_decay": wd,
                "seed": seed,
                "batch_size": batch_size,
            },
            reinit=True,
        )
        run = main(batch_size=batch_size, device=device, lr=lr, wd=wd, seed=seed)
        all_runs.append(run)
        wandb_run.finish()
    _aggregate_and_print(all_runs, RUN_LABEL)
