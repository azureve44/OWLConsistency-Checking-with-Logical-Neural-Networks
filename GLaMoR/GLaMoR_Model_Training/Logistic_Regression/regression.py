import os
import pickle
import re
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, make_scorer, precision_score, recall_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.svm import SVC
INCONSISTENT_PREFIX_RE = re.compile(r"^[^_]+_p\d+_\d+_")
SEEDS = list(range(5))
def _perform_grid_search(
    parameters: Dict[str, Dict],
    x_train: pd.DataFrame,
    y_train: pd.Series,
    cv,
    scoring: str = "accuracy",
) -> Tuple[object, str, Dict[str, Dict]]:
    """
    Run GridSearchCV for every model in `parameters` and return the best
    overall estimator (by accuracy) together with its name and per-model details.
    """
    scoring = {
        "accuracy": make_scorer(accuracy_score),
        "precision": make_scorer(precision_score, average="macro", zero_division=0),
        "recall": make_scorer(recall_score, average="macro", zero_division=0),
    }
    best_models = {}
    default_jobs = max(1, min(8, os.cpu_count() or 1))
    for model_name, config in parameters.items():
        model_start = time.time()
        grid_jobs = config.get("n_jobs", default_jobs)
        print(f"Computing Model: {model_name} (n_jobs={grid_jobs})")
        clf = GridSearchCV(
            estimator=config["model"],
            param_grid=config["parameters"],
            scoring=scoring,
            cv=cv,
            n_jobs=grid_jobs,
            pre_dispatch=grid_jobs,
            refit="accuracy",
            error_score="raise",
            verbose=config.get("verbose", 0),
        )
        clf.fit(x_train, y_train)
        elapsed_seconds = time.time() - model_start
        best_models[model_name] = {
            "estimator": clf.best_estimator_,
            "score": clf.best_score_,
            "best_params": clf.best_params_,
            "best_accuracy": clf.cv_results_["mean_test_accuracy"][clf.best_index_],
            "best_precision": clf.cv_results_["mean_test_precision"][clf.best_index_],
            "best_recall": clf.cv_results_["mean_test_recall"][clf.best_index_],
            "elapsed_seconds": elapsed_seconds,
        }
        print(f"  Best params:    {clf.best_params_}")
        print(f"  Best accuracy:  {best_models[model_name]['best_accuracy']:.4f}")
        print(f"  Best precision: {best_models[model_name]['best_precision']:.4f}")
        print(f"  Best recall:    {best_models[model_name]['best_recall']:.4f}")
        print(f"  Elapsed:        {elapsed_seconds:.1f}s")
    best_model_name = max(best_models, key=lambda name: best_models[name]["best_accuracy"])
    return best_models[best_model_name]["estimator"], best_model_name, best_models
def _embedding_path_for(filename: str, embeddings_dir: str) -> Optional[str]:
    stem = os.path.splitext(filename)[0]
    candidate_stems = [stem]
    stripped_stem = INCONSISTENT_PREFIX_RE.sub("", stem)
    if stripped_stem != stem:
        candidate_stems.append(stripped_stem)
    for candidate_stem in candidate_stems:
        npy_path = os.path.join(embeddings_dir, candidate_stem + ".npy")
        if os.path.isfile(npy_path):
            return npy_path
    return None
def _load_split(csv_path: str, embeddings_dir: str) -> pd.DataFrame:
    """Load a CSV split and attach the corresponding .npy embeddings as feature columns."""
    df = pd.read_csv(csv_path, header=0)
    rows = []
    normalized_hits = 0
    for row in df.itertuples(index=False):
        filename = row.file_name
        label = row.consistency
        direct_path = os.path.join(embeddings_dir, os.path.splitext(filename)[0] + ".npy")
        npy_path = _embedding_path_for(filename, embeddings_dir)
        if npy_path is not None:
            vec = np.load(npy_path)
            if npy_path != direct_path:
                normalized_hits += 1
            if vec.ndim != 1:
                raise ValueError(
                    f"Expected 1-D embedding in {npy_path}, got shape {vec.shape}. "
                    "Re-run the embed pipeline with the mean-aggregation fix applied to "
                    "GLaMoR-DataPipeline/embed/worker.py::_create_graph_embedding()."
                )
        else:
            vec = None
        rows.append((vec, filename, label))
    valid_vectors = [v for v, _, _ in rows if v is not None]
    if not valid_vectors:
        raise FileNotFoundError(
            f"No embeddings could be resolved for split: {csv_path}\n"
            f"Embeddings directory checked: {embeddings_dir}"
        )
    embed_size = valid_vectors[0].shape[0]
    feature_cols = [f"feature_{i}" for i in range(embed_size)]
    records = []
    skipped = 0
    for vec, fname, label in rows:
        if vec is not None:
            records.append(list(vec) + [label])
        else:
            print(f"  WARNING: no embedding for {fname} — skipping")
            skipped += 1
    if normalized_hits:
        print(f"  Resolved {normalized_hits}/{len(rows)} embeddings via prefix normalization")
    if skipped:
        print(f"  Skipped {skipped}/{len(rows)} rows (missing embeddings)")
    return pd.DataFrame(records, columns=feature_cols + ["y"])
def _evaluate(
    model,
    X: pd.DataFrame,
    y: pd.Series,
    split_name: str,
    verbose: bool = True,
) -> Dict[str, float]:
    preds = model.predict(X)
    acc = accuracy_score(y, preds)
    prec = precision_score(y, preds, average="macro", zero_division=0)
    rec = recall_score(y, preds, average="macro", zero_division=0)
    if verbose:
        print(f"  [{split_name:5s}]  accuracy={acc:.4f}  precision={prec:.4f}  recall={rec:.4f}")
    return {"accuracy": acc, "precision": prec, "recall": rec}
def _model_label(model_name: str) -> str:
    labels = {
        "random_forest": "Random Forest",
        "svm": "SVM",
        "logistic_regression": "Logistic Regression",
    }
    return labels.get(model_name, model_name.replace("_", " ").title())
def _build_parameter_grid(seed: int) -> Dict[str, Dict]:
    return {
        "random_forest": {
            "model": RandomForestClassifier(random_state=seed),
            "parameters": {
                "n_estimators": [25, 50, 100, 150],
                "max_features": ["sqrt", "log2", None],
                "max_depth": [None, 3, 6, 9, 12],
                "max_leaf_nodes": [5, 10, 20],
            },
        },
        "svm": {
            "model": SVC(random_state=seed),
            "parameters": {
                "C": [0.01, 0.1, 1, 10, 100],
                "kernel": ["rbf", "linear"],
                "gamma": ["scale", "auto"],
            },
        },
        # "logistic_regression": {
        #     "model": LogisticRegression(random_state=seed, max_iter=5000, tol=1e-3),
        #     "n_jobs": 1,
        #     "verbose": 1,
        #     "parameters": [
        #         {
        #             "penalty": ["l2"],
        #             "C": np.logspace(-4, 4, 8).tolist(),
        #             "solver": ["lbfgs"],
        #         },
        #         {
        #             "penalty": ["l1", "l2"],
        #             "C": np.logspace(-4, 4, 8).tolist(),
        #             "solver": ["liblinear"],
        #         },
        #     ],
        # },
    }
def _summarize_seed_results(seed_results: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    metrics_records = []
    for result in seed_results:
        for split_name, metrics in result["metrics"].items():
            metrics_records.append(
                {
                    "seed": result["seed"],
                    "best_model": result["best_model"],
                    "split": split_name,
                    **metrics,
                }
            )
    metrics_df = pd.DataFrame(metrics_records)
    summary_df = (
        metrics_df.groupby("split")[["accuracy", "precision", "recall"]]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary_df.columns = [
        "split" if col == ("split", "") else f"{col[0]}_{col[1]}"
        for col in summary_df.columns.to_flat_index()
    ]
    return metrics_df, summary_df.fillna(0.0)
def _summarize_model_seed_results(model_seed_results: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    model_metrics_df = pd.DataFrame(model_seed_results)
    summary_df = (
        model_metrics_df.groupby("model_name")[["accuracy", "precision", "recall", "elapsed_seconds", "inference_seconds"]]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary_df.columns = [
        "model_name" if col == ("model_name", "") else f"{col[0]}_{col[1]}"
        for col in summary_df.columns.to_flat_index()
    ]
    return model_metrics_df, summary_df.fillna(0.0)
def _print_aggregate_summary(seed_results: List[Dict], summary_df: pd.DataFrame) -> None:
    print("\n=== Aggregate metrics across seeds ===")
    for split_name in ["train", "eval", "test"]:
        row = summary_df.loc[summary_df["split"] == split_name]
        if row.empty:
            continue
        row = row.iloc[0]
        print(
            f"  [{split_name:5s}] "
            f"accuracy mean={row['accuracy_mean']:.4f} std={row['accuracy_std']:.4f} | "
            f"precision mean={row['precision_mean']:.4f} std={row['precision_std']:.4f} | "
            f"recall mean={row['recall_mean']:.4f} std={row['recall_std']:.4f}"
        )
    best_model_counts = Counter(result["best_model"] for result in seed_results)
    print("\nBest model selections across seeds:")
    for model_name, count in best_model_counts.items():
        print(f"  {model_name}: {count}/{len(seed_results)}")
def _fmt_time(seconds: float) -> str:
    total = float(seconds)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def _format_mean_std_latex(mean_value: float, std_value: float) -> str:
    return f"${mean_value * 100:5.2f}_{{({std_value * 100:.2f})}}$"


def _print_latex_model_rows(model_summary_df: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("Paper-table rows (use in tab:result-bioportal)")
    print("=" * 78)
    for model_name in model_summary_df["model_name"]:
        row = model_summary_df.loc[model_summary_df["model_name"] == model_name].iloc[0]
        print(
            f"{_model_label(model_name)} & "
            f"{_format_mean_std_latex(row['accuracy_mean'], row['accuracy_std'])} & "
            f"{_format_mean_std_latex(row['precision_mean'], row['precision_std'])} & "
            f"{_format_mean_std_latex(row['recall_mean'], row['recall_std'])} & "
            f"{_fmt_time(row['elapsed_seconds_mean'])} & "
            f"{_fmt_time(row['inference_seconds_mean'])} \\\\"
        )
    print("=" * 78)


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    EMBEDDINGS_DIR = os.path.normpath(os.path.join(base_dir, "../embeddings"))
    SPLITS_DIR = os.path.normpath(os.path.join(base_dir, "../../../nsplits"))
    print("Loading splits …")
    print(f"  Embeddings dir: {EMBEDDINGS_DIR}")
    print(f"  Splits dir:     {SPLITS_DIR}")
    train_df = _load_split(os.path.join(SPLITS_DIR, "train_data.csv"), EMBEDDINGS_DIR)
    eval_df = _load_split(os.path.join(SPLITS_DIR, "eval_data.csv"), EMBEDDINGS_DIR)
    test_df = _load_split(os.path.join(SPLITS_DIR, "test_data.csv"), EMBEDDINGS_DIR)
    feature_cols = [c for c in train_df.columns if c != "y"]
    X_train, y_train = train_df[feature_cols], train_df["y"]
    X_eval, y_eval = eval_df[feature_cols], eval_df["y"]
    X_test, y_test = test_df[feature_cols], test_df["y"]
    print(f"Train: {len(X_train)}  Eval: {len(X_eval)}  Test: {len(X_test)}")
    print(f"Classes in train split: {sorted(map(str, y_train.unique()))}")
    if y_train.nunique() < 2:
        raise ValueError(
            "Training data contains fewer than 2 classes after loading embeddings. "
            "Check the embeddings directory and filename normalization logic."
        )
    seed_results: List[Dict] = []
    model_seed_results: List[Dict] = []
    for seed in SEEDS:
        print(f"\n{'=' * 18} Seed {seed} {'=' * 18}")
        parameter_grid = _build_parameter_grid(seed)
        cv_splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
        model, best_name, all_model_results = _perform_grid_search(parameter_grid, X_train, y_train, cv=cv_splitter)
        print(f"\nBest model overall for seed {seed}: {best_name}")
        print("--- Final evaluation ---")
        split_metrics = {
            "train": _evaluate(model, X_train, y_train, "train"),
            "eval": _evaluate(model, X_eval, y_eval, "eval"),
            "test": _evaluate(model, X_test, y_test, "test"),
        }
        seed_results.append({"seed": seed, "best_model": best_name, "metrics": split_metrics})
        for model_name, model_result in all_model_results.items():
            inference_start = time.time()
            test_metrics = _evaluate(model_result["estimator"], X_test, y_test, "test", verbose=False)
            inference_seconds = time.time() - inference_start
            model_seed_results.append(
                {
                    "seed": seed,
                    "model_name": model_name,
                    **test_metrics,
                    "elapsed_seconds": model_result["elapsed_seconds"],
                    "inference_seconds": inference_seconds,
                }
            )
        output_path = os.path.join(base_dir, f"regression_seed{seed}.pkl")
        with open(output_path, "wb") as f:
            pickle.dump(model, f)
        print(f"Model saved → {output_path}")
    metrics_df, summary_df = _summarize_seed_results(seed_results)
    model_metrics_df, model_summary_df = _summarize_model_seed_results(model_seed_results)
    metrics_output_path = os.path.join(base_dir, "regression_seed_metrics.csv")
    summary_output_path = os.path.join(base_dir, "regression_summary.csv")
    model_metrics_output_path = os.path.join(base_dir, "regression_model_seed_metrics.csv")
    model_summary_output_path = os.path.join(base_dir, "regression_model_summary.csv")
    metrics_df.to_csv(metrics_output_path, index=False)
    summary_df.to_csv(summary_output_path, index=False)
    model_metrics_df.to_csv(model_metrics_output_path, index=False)
    model_summary_df.to_csv(model_summary_output_path, index=False)
    _print_aggregate_summary(seed_results, summary_df)
    _print_latex_model_rows(model_summary_df)
    print(f"\nPer-seed metrics saved → {metrics_output_path}")
    print(f"Aggregate summary saved → {summary_output_path}")
    print(f"Per-model seed metrics saved → {model_metrics_output_path}")
    print(f"Per-model summary saved → {model_summary_output_path}")
