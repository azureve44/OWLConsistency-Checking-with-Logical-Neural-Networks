from functools import partial
import copy
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path
import json 
from tqdm import tqdm
import torch
from torch import nn
from typing import List, Tuple, Dict, Union, Optional, Generator
import random
import time
import numpy as np
import sys
import os, sys
import logging
import wandb
import pandas as pd
import get_args
from models.graph_T5.classifier import GraphT5Classifier
from models.graph_T5.graph_t5 import T5TokenizerFast as T5Tokenizer
from models.graph_T5.wrapper_functions import Graph, graph_to_graphT5, graph_to_set_of_triplets, get_embedding, Data
from json.decoder import JSONDecodeError
import ast
import pickle
from datetime import datetime
PREFIXES : List[str] = ["AIO","EID","OIL","OILWI","OILWPI","UE","UEWI1","UEWI2","UEWPI","UEWIP","SOSINETO","CSC","OOR","OOD"]
MAX_LENGTH = 4096
EARLY_STOPPING_MIN_DELTA = 0.01

def export_confusion_matrix(preds: torch.Tensor, labels: torch.Tensor, file_path: str = "Exports/gGLMsmall_confusion.csv"):
    """
    Computes and exports the confusion matrix to a CSV file.

    :param preds: Tensor of shape (batch_size, num_classes) OR (batch_size,)
    :param labels: Tensor of shape (batch_size,)
    :param file_path: File path to save the confusion matrix (CSV format)
    """
    # Convert logits to class indices if necessary
    if preds.dim() > 1:
        preds = preds.argmax(dim=1)  # Convert softmax/logits to class predictions

    num_classes = 2  # Number of classes

    # Compute confusion matrix
    confusion_matrix = torch.zeros((num_classes, num_classes), dtype=torch.int32)
    
    for true_label, predicted_label in zip(labels, preds):
        confusion_matrix[true_label, predicted_label] += 1

    # Convert to DataFrame for easy exporting
    df = pd.DataFrame(confusion_matrix.numpy(), 
                      index=[f"True_{i}" for i in range(num_classes)], 
                      columns=[f"Pred_{i}" for i in range(num_classes)])

    export_dir = Path("Exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    output_file = export_dir / f"localbase{file_path}.pt"
    df.to_csv(output_file)
    print(f"Confusion matrix saved to {output_file}")
    # Calculate positive class (assumed to be class 1) metrics
    # True Positives: correctly predicted positive cases
    tp = confusion_matrix[1, 1].item()
    # False Negatives: positive cases predicted as negative
    fn = confusion_matrix[1, 0].item()
    # False Positives: negative cases predicted as positive
    fp = confusion_matrix[0, 1].item()

    # Compute recall (sensitivity) for positive class
    recall = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 0.0
    # Compute precision for positive class
    precision = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 0.0

    return recall, precision



def load_data_deprecated():
    
    df = pd.read_csv("dataset.csv", header=0)
    subset_df = df[df["tokenized_length"] < MAX_LENGTH]

    ## Filter data by token length
    subset_df["labels"] = subset_df["file_name"].map(lambda x : "Inconsistent" if x.split("_")[0] in PREFIXES else "Consistent")

    ## Check how many consistent data points there are
    consistent_data = subset_df.loc[subset_df["labels"] == "Consistent"]
    posistive_training_examples = len(consistent_data)
    print(f"posistive training examples: {posistive_training_examples}")

    ## Check how many consistent data points there are
    inconsistent_data = subset_df.loc[subset_df["labels"] == "Inconsistent"]
    inconsistent_data = inconsistent_data.sample(frac=1).reset_index(drop=True)
    inconsistent_data = inconsistent_data[:posistive_training_examples]
    print(f"negative training examples: {len(inconsistent_data)}")

    ## Combine into one train/test set
    combined_data = pd.concat([consistent_data, inconsistent_data], ignore_index=True)
    combined_data = combined_data.sample(frac=1).reset_index(drop=True)
    combined_data.to_csv("Training_data.csv", index=False)

    ## Load as Graph data
    data = combined_data["body"].map(lambda x : x.replace(" ", "").replace("\'", "\"").split("\" comment")[0]).tolist()

    all_labels = combined_data["labels"].tolist()
    labels = []
    graphs = []
    errors : int = 0
    names = combined_data["file_name"]
    for triples, label , name in tqdm(zip(data, all_labels, names), total = len(data)):
        try:
            jsonified = json.loads(triples)
        except JSONDecodeError:
            print(name)
            print(triples)
            print(label)
        while jsonified:
            try:
                graphs.append(Graph(jsonified))
                labels.append(label)
                break
            except: 
                jsonified = jsonified[:-1]
                continue 
   
    label_to_index = {"Inconsistent" : 1, "Consistent" : 0}

    ## Split dataset 
    graph_dict = {"train": graphs[:int(0.7*len(graphs))], "test": graphs[int(0.7*len(graphs)):int(0.85*len(graphs))], "eval" : graphs[int(0.85*len(graphs)):]}
    label_dict = {"train" : labels[:int(0.7*len(labels))], "test": labels[int(0.7*len((labels))):int(0.85*len((labels)))], "eval": labels[int(0.85*len((labels))):]}
    print(f"Datapoints not being able to be jsonified: {errors}")
#    assert set(labels['train']) == set(labels['dev']) == set(labels['test']), (set(labels['train']), set(labels['dev']), set(labels['test']))
    return graph_dict, label_dict, label_to_index

def load_data(leave_out = ""):
    train_df = pd.read_csv("../../../nsplits/train_data.csv", header=0)
    eval_df = pd.read_csv("../../../nsplits/eval_data.csv", header=0)
    test_df = pd.read_csv("../../../nsplits/test_data.csv", header=0)

    if(leave_out):
        train_df = train_df[~train_df["injected_pattern"].fillna("").str.startswith(leave_out)]
        eval_df = eval_df[~eval_df["injected_pattern"].fillna("").str.startswith(leave_out)]


    train_graphs = [Graph(ast.literal_eval(triples)) for triples in train_df["body"]]
    eval_graphs = [Graph(ast.literal_eval(triples))for triples in eval_df["body"]]
    test_graphs = [Graph(ast.literal_eval(triples))for triples in test_df["body"]]

    graph_dict= {"train" : train_graphs, "eval":eval_graphs, "test":test_graphs}
    label_dict= {"train" : train_df["consistency"], "eval" : eval_df["consistency"], "test" : test_df["consistency"]} 
    label_2_index = {"Inconsistent" : 1, "Consistent" : 0}
    return graph_dict, label_dict, label_2_index


def data_to_dataT5(graph:Graph, tokenizer:T5Tokenizer, label:str, label_to_index:dict, graph_representation:str, eos:str):
    """
    :param graph: graph to convert
    :param tokenizer: tokenizer of model
    :param label: label of the relation
    :param label_to_index: mapping from label to index
    :param graph_representation: how to represent the graph. 
    :param eos: end-of-sequence token. Can be `False` for not using an eos token. When using an eos token, there are two ways to use it: `bidirectional` means that the eos token is connected to every other node in the graph, with a relative position of positive infinity (from node to eos) or negative infinity (from eos to node). `unidirectional` means that the eos token is connected to every node in the graph with a relative position of positive infinity (from node to eos), but not the other way around (i.e. no connection from eos to other node). This means, that nodes do not get messages from the eos token, which preserves locality when using the local GLM
    """
    if graph_representation == 'lGLM':
        data = graph_to_graphT5(graph, tokenizer, how='local', eos=eos)
    elif graph_representation == 'set':
        data = graph_to_set_of_triplets(graph, tokenizer, order='random')
    elif graph_representation == 'gGLM':
        data = graph_to_graphT5(graph, tokenizer, how='global', eos=eos)
    elif graph_representation == 'list':
        data = graph_to_set_of_triplets(graph, tokenizer, order='alphabetical')
    else:
        raise ValueError(f"unknown graph_representation {graph_representation}")
    data.label = torch.tensor(label_to_index[label])
    return data

def get_batch(data_instances:List[Data], pad_token_id:int, device:str):
    """
    can be implemented more efficiently with nested tensors, but they are currently unstable
    """
    max_seq_len = max([data.input_ids.shape[1] for data in data_instances])

    if data_instances[0].relative_position is None:
        assert data_instances[0].sparsity_mask is None
        assert data_instances[0].use_additional_bucket is None
        is_sequence_transformer = True
    else:
        assert data_instances[0].sparsity_mask is not None
        assert data_instances[0].use_additional_bucket is not None
        is_sequence_transformer = False

    # intialize tensors
    input_ids = torch.ones((len(data_instances), max_seq_len), dtype=torch.long, device=device) * pad_token_id
    if not is_sequence_transformer:
        relative_position = torch.zeros((len(data_instances), max_seq_len, max_seq_len), dtype=torch.long, device=device)
        sparsity_mask = torch.zeros((len(data_instances), max_seq_len, max_seq_len), dtype=torch.bool, device=device)
        use_additional_bucket = torch.zeros((len(data_instances), max_seq_len, max_seq_len), dtype=torch.bool, device=device)

    # fill tensors
    for i, data in enumerate(data_instances):
        data.input_ids = data.input_ids.to(device)
        input_ids[i, :data.input_ids.shape[1]] = data.input_ids
        input_ids = input_ids.to(device)
        if not is_sequence_transformer:
            relative_position[i, :data.relative_position.shape[1], :data.relative_position.shape[2]] = data.relative_position
            sparsity_mask[i, :data.sparsity_mask.shape[1], :data.sparsity_mask.shape[2]] = data.sparsity_mask
            use_additional_bucket[i, :data.use_additional_bucket.shape[1], :data.use_additional_bucket.shape[2]] = data.use_additional_bucket

    if is_sequence_transformer:
        relative_position = None # [None] * len(data_instances)
        sparsity_mask = None # [None] * len(data_instances)
        use_additional_bucket = None # [None] * len(data_instances)

    indices = [data.indices for data in data_instances]
    label = torch.tensor([data.label for data in data_instances], device=device)

    return input_ids, relative_position, sparsity_mask, use_additional_bucket, indices, label

def chunker(data_list:List[Data], batch_size:int):
    """
    returns a generator that yields batches of size batch_size
    """
    return (data_list[pos:pos + batch_size] for pos in range(0, len(data_list), batch_size))

def get_accuracy(preds:torch.Tensor, label:torch.Tensor):
    """
    :param preds: shape (batch_size, num_classes)
    :param label: shape (batch_size)
    """
    return (preds.argmax(dim=1) == label).sum().item() / len(label) * 100

def get_precision(preds: torch.Tensor, label: torch.Tensor, num_classes: int = 2):
    """
    :param preds: shape (batch_size, num_classes)
    :param label: shape (batch_size)
    :param num_classes: the number of classes in the classification task
    """
    preds = preds.argmax(dim=1)
    
    precision_per_class = []
    for i in range(num_classes):
        true_positive = ((preds == i) & (label == i)).sum().item()
        false_positive = ((preds == i) & (label != i)).sum().item()
        precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0
        precision_per_class.append(precision)
    
    return sum(precision_per_class) / len(precision_per_class) * 100

def get_recall(preds: torch.Tensor, labels: torch.Tensor, num_classes: int):
    """
    :param preds: shape (batch_size, num_classes)
    :param label: shape (batch_size)
    :param num_classes: the number of classes in the classification task
    """
    """
    Computes the sensitivity (recall for the positive class).

    :param preds: Tensor of shape (batch_size, num_classes) containing logits or probabilities.
    :param labels: Tensor of shape (batch_size,) containing the true class labels.
    :param positive_class: The index of the positive class (default is 1).
    :return: Sensitivity as a percentage.
    """
    # Convert logits to class predictions if necessary
    if preds.dim() > 1:
        preds = preds.argmax(dim=1)
    
    # True Positives: predicted positive and actual positive
    true_positive = ((preds == 1) & (labels == 1)).sum().item()
    # False Negatives: predicted negative but actual positive
    false_negative = ((preds != 1) & (labels == 1)).sum().item()

    if (true_positive + false_negative) == 0:
        # Avoid division by zero if there are no positive cases in the labels
        return 0.0

    sensitivity = true_positive / (true_positive + false_negative) * 100
    return sensitivity

def run_eval_epoch(model: GraphT5Classifier, data: List[Data], criterion: nn.Module, batch_size: int, device: str, pattern:str):
    with torch.no_grad():
        losses = []
        accuracies = []
        precisions = []
        recalls = []
        weights = []

        all_preds = []
        all_labels = []

        for data_instances in chunker(data, batch_size):
            # Create batch
            logging.debug("get batch")
            input_ids, relative_position, sparsity_mask, use_additional_bucket, indices, label = get_batch(
                data_instances, pad_token_id=model.tokenizer.pad_token_id, device=device
            )

            logging.debug("forward")
            logits = model.forward(
                input_ids=input_ids,
                relative_position=relative_position,
                sparsity_mask=sparsity_mask,
                use_additional_bucket=use_additional_bucket,
            )

            logging.debug("get loss and accuracy")
            loss = criterion(logits, label)
            accuracy = get_accuracy(logits, label)
            recall = get_recall(logits, label, 2)
            precision = get_precision(logits, label, 2)

            # Collect predictions and labels for confusion matrix
            all_preds.append(logits.argmax(dim=1))  # Convert logits to class indices
            all_labels.append(label)

            losses.append(loss.item())
            accuracies.append(accuracy)
            weights.append(len(label))

        logging.debug("aggregate loss and accuracy")
        loss = np.average(losses, weights=weights)
        accuracy = np.average(accuracies, weights=weights)
        # Concatenate all predictions and labels, then export confusion matrix
        all_preds = torch.cat(all_preds)
        all_labels = torch.cat(all_labels)
        recall, precision = export_confusion_matrix(all_preds, all_labels, pattern)

        return loss, accuracy, precision, recall

    return loss, accuracy, precision, recall

def run_train_epoch(model:GraphT5Classifier, data:List[Data], criterion:nn.Module, optimizer:torch.optim.Optimizer, batch_size:int, gradient_accumulation_steps:int, device:str):
    print("running train epochs")

    losses = []
    accuracies = []
    weights = []
    optimizer.zero_grad()

    random.shuffle(data)

    for i, data_instances in tqdm(enumerate(chunker(data, batch_size)), total=len(data)//batch_size):
        # create batch
        input_ids, relative_position, sparsity_mask, use_additional_bucket, indices, label = get_batch(data_instances, pad_token_id=model.tokenizer.pad_token_id, device=device)
        logits = model.forward(
            input_ids=input_ids.to(device),
            relative_position=relative_position.to(device),
            sparsity_mask=sparsity_mask.to(device),
            use_additional_bucket=use_additional_bucket.to(device),
        )


        loss = criterion(logits, label)
        # loss = logits.sum()

        loss.backward()

        if (i+1) % gradient_accumulation_steps == 0 or (i+1) == len(data)//batch_size:
            optimizer.step()
            optimizer.zero_grad()

        accuracy = get_accuracy(logits, label)
        losses.append(loss.item())
        accuracies.append(accuracy)
        weights.append(len(label)) 

    loss = np.average(losses, weights=weights)
    accuracy = np.average(accuracies, weights=weights)
    return loss, accuracy

def _fmt_time(seconds: float) -> str:
    total = float(seconds)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"
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
            f"  {split:>5s} : Acc {a_m:5.2f} +/-{a_s:.2f}  "
            f"Prec {p_m:5.2f} +/-{p_s:.2f}  "
            f"Rec  {r_m:5.2f} +/-{r_s:.2f}"
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
        f"${a_m:5.2f}_{{({a_s:.2f})}}$ & "
        f"${p_m:5.2f}_{{({p_s:.2f})}}$ & "
        f"${r_m:5.2f}_{{({r_s:.2f})}}$ & "
        f"{_fmt_time(train_secs.mean())} & "
        f"{_fmt_time(test_inf.mean())} \\\\" 
    )
    print("=" * 78)
def main(args, leave_out=""):
    if not args.device.startswith('cuda'):
        logging.warning(f'using CPU {args.device}, training might be slow.')
    else:
        logging.info(f'using GPU {args.device}')
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.device.startswith('cuda') and torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    logging.info('load data')
    graphs, labels, label_to_index = load_data(leave_out)
    logging.info('load T5 encoder')
    num_classes = len(label_to_index)
    model = GraphT5Classifier(config=GraphT5Classifier.get_config(num_classes=num_classes, modelsize=args.modelsize, num_additional_buckets=args.num_additional_buckets))
    if args.num_additional_buckets != 0:
        logging.info(f'init relative position bias with {args.num_additional_buckets} additional buckets')
        model.t5model.init_relative_position_bias(modelsize=args.modelsize, init_decoder=False, init_additional_buckets_from=args.init_additional_buckets_from)
    if args.reset_params:
        logging.info('resetting model parameters')
        get_args.reset_params(model=model)
    model.to(args.device)
    if not args.reload_data:
        logging.info('convert data to T5 input')
        data = {split: [data_to_dataT5(graph, model.tokenizer, label, label_to_index, args.graph_representation, eos=args.eos_usage) for graph, label in tqdm(zip(graphs[split], labels[split]), total=len(labels[split]))] for split in ['train', 'test', 'eval']}
    else:
        data = None
    criterion = args.criterion()
    optimizer = args.optimizer(model.parameters(), lr=args.learning_rate)
    best_epoch = 0
    best_eval_loss = float('inf')
    best_state = copy.deepcopy(model.state_dict())
    stopped_early = False
    best_eval_metrics = {"acc": float('nan'), "prec": float('nan'), "rec": float('nan'), "loss": float('inf')}
    train_loss = train_accuracy = float('nan')
    eval_loss = eval_accuracy = eval_precision = eval_recall = float('nan')
    last_epoch = -1
    logging.info('train the model')
    train_start = time.time()
    for epoch in range(args.num_epochs):
        if args.reload_data:
            logging.info('convert data to T5 input')
            data = {split: [data_to_dataT5(graph, model.tokenizer, label, label_to_index, args.graph_representation, eos=args.eos_usage) for graph, label in tqdm(zip(graphs[split], labels[split]), total=len(labels[split]))] for split in ['train', 'test', 'eval']}
        train_loss, train_accuracy = run_train_epoch(model=model, data=data['train'], criterion=criterion, optimizer=optimizer, batch_size=args.train_batch_size, gradient_accumulation_steps=args.gradient_accumulation_steps, device=args.device)
        logging.info(f'train - epoch={epoch} # train_loss={train_loss:.2f} # train_accuracy={train_accuracy:.2f}')
        eval_loss, eval_accuracy, eval_precision, eval_recall = run_eval_epoch(model=model, data=data['eval'], criterion=criterion, batch_size=args.eval_batch_size, device=args.device, pattern=leave_out)
        logging.info(f'eval  - epoch={epoch} # eval_loss={eval_loss:.2f} # eval_accuracy={eval_accuracy:.2f}')
        if best_eval_loss - eval_loss >= EARLY_STOPPING_MIN_DELTA:
            best_epoch = epoch
            best_eval_loss = eval_loss
            best_state = copy.deepcopy(model.state_dict())
            best_eval_metrics = {"acc": eval_accuracy, "prec": eval_precision, "rec": eval_recall, "loss": eval_loss}
        if wandb.run is not None:
            wandb.log(
                {
                    "epoch": epoch,
                    "best_epoch": best_epoch,
                    "stopped_early": float(stopped_early),
                    "train/accuracy": train_accuracy,
                    "train/loss": train_loss,
                    "eval/accuracy": eval_accuracy,
                    "eval/loss": eval_loss,
                    "eval/precision": eval_precision,
                    "eval/recall": eval_recall,
                    "eval/best_accuracy": best_eval_metrics["acc"],
                    "eval/best_loss": best_eval_metrics["loss"],
                }
            )
        last_epoch = epoch
        if epoch - best_epoch >= args.early_stopping:
            logging.info(f'stopped early at epoch {epoch}')
            stopped_early = True
            break
    train_seconds = time.time() - train_start
    if wandb.run is not None:
        for epoch in range(last_epoch + 1, args.num_epochs):
            wandb.log(
                {
                    "epoch": epoch,
                    "best_epoch": best_epoch,
                    "stopped_early": float(stopped_early),
                    "train/accuracy": train_accuracy,
                    "train/loss": train_loss,
                    "eval/accuracy": eval_accuracy,
                    "eval/loss": eval_loss,
                    "eval/precision": eval_precision,
                    "eval/recall": eval_recall,
                    "eval/best_accuracy": best_eval_metrics["acc"],
                    "eval/best_loss": best_eval_metrics["loss"],
                }
            )
    model.load_state_dict(best_state)
    train_loss_final, train_acc_final, train_prec_final, train_rec_final = run_eval_epoch(model=model, data=data['train'], criterion=criterion, batch_size=args.eval_batch_size, device=args.device, pattern=leave_out)
    eval_loss_final, eval_acc_final, eval_prec_final, eval_rec_final = run_eval_epoch(model=model, data=data['eval'], criterion=criterion, batch_size=args.eval_batch_size, device=args.device, pattern=leave_out)
    inf_start = time.time()
    test_loss, test_accuracy, test_precision, test_recall = run_eval_epoch(model=model, data=data['test'], criterion=criterion, batch_size=args.eval_batch_size, device=args.device, pattern=leave_out)
    inference_seconds = time.time() - inf_start
    if wandb.run is not None:
        wandb.log(
            {
                "time/training_seconds": train_seconds,
                "time/inference_seconds": inference_seconds,
                "test/accuracy": test_accuracy,
                "test/loss": test_loss,
                "test/precision": test_precision,
                "test/recall": test_recall,
            }
        )
    return {
        "seed": args.seed,
        "best_epoch": best_epoch,
        "train_seconds": train_seconds,
        "train": {"loss": train_loss_final, "acc": train_acc_final, "prec": train_prec_final, "rec": train_rec_final},
        "eval": {"loss": eval_loss_final, "acc": eval_acc_final, "prec": eval_prec_final, "rec": eval_rec_final},
        "test": {"loss": test_loss, "acc": test_accuracy, "prec": test_precision, "rec": test_recall, "inference_seconds": inference_seconds},
    }
if __name__ == "__main__":
    parser = ArgumentParser(
        formatter_class=ArgumentDefaultsHelpFormatter  # makes wandb log the default values
    )
    get_args.add_args_shared(parser)
    get_args.add_args(parser)
    args = get_args.load_args(parser)

    args.device = 'cuda:2' if torch.cuda.is_available() and args.device.startswith('cuda') else 'cpu'
    
    # logging
    root = logging.getLogger()
    root.setLevel(args.logging_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(args.logging_level)
    formatter = logging.Formatter(f"%(asctime)s [%(levelname)s] %(filename)s, Line %(lineno)d\n%(message)s",datefmt=f"%H:%M:%S",)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # logging.basicConfig(
    #     level=args.logging_level,
    #     # format=f"%(asctime)s [%(levelname)s] %(message)s (Line %(lineno)d in %(filename)s)",
    #     format=f"%(asctime)s [%(levelname)s] %(filename)s, Line %(lineno)d\n%(message)s",
    #     datefmt=f"%H:%M:%S",
    # )

    # wandb
    
    
    name = f'gGLMbase'
    wandb_run = wandb.init(
        mode=args.wandb_mode,
        project="GLM",
        name=name,
        # Track hyperparameters and run metadata
        config=args.__dict__,
        tags=['gocal', 'base'],
        reinit=True,
    )
    SEEDS = [0, 1, 2,3,4] # [0, 1, 2, 3, 4]
    run_label = f"{args.graph_representation}{args.modelsize.replace('t5-', '')}"
    all_runs = []
    for seed in SEEDS:
        seed_args = copy.deepcopy(args)
        seed_args.seed = seed
        wandb_run = wandb.init(
            mode=seed_args.wandb_mode,
            project="GLM",
            name=f"{run_label}-seed{seed}",
            config=seed_args.__dict__,
            tags=['gocal', 'base', f'seed-{seed}'],
            reinit=True,
        )
        run = main(seed_args)
        all_runs.append(run)
        logging.info("done with main")
        wandb.finish()
    _aggregate_and_print(all_runs, run_label)

        
