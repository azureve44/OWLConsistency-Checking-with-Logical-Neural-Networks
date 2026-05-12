from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
import pandas as pd
COLUMNS = ["file_name", "consistency", "tokenized_length", "body", "injected_pattern"]
def normalise_consistency(value: Any) -> str:
    if pd.isna(value):
        return "Consistent"
    if isinstance(value, bool):
        return "Consistent" if value else "Inconsistent"
    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "consistent"}:
        return "Consistent"
    if lowered in {"false", "0", "inconsistent"}:
        return "Inconsistent"
    return str(value)
def normalise_body(value: Any) -> Any:
    if pd.isna(value) or not isinstance(value, str):
        return value
    return value.replace(" ", "").split('" comment', 1)[0]
def normalise_injected_pattern(value: Any) -> Any:
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    if text == "" or text.lower() in {"none", "nan", "<na>"}:
        return pd.NA
    return text
def split_like_notebook(df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["consistency"] = df["consistency"].map(normalise_consistency)
    df["body"] = df["body"].map(normalise_body)
    df["injected_pattern"] = df["injected_pattern"].map(normalise_injected_pattern)
    df = df[COLUMNS]
    inconsistent_dfs = {
        category: df[df["injected_pattern"] == category]
        for category in df["injected_pattern"].dropna().unique().tolist()
    }
    consistent_df = df[df["consistency"] == "Consistent"].sample(frac=1, random_state=seed).reset_index(drop=True)
    train_df = pd.DataFrame(columns=COLUMNS)
    eval_df = pd.DataFrame(columns=COLUMNS)
    test_df = pd.DataFrame(columns=COLUMNS)
    train_df = pd.concat([train_df, consistent_df[: int(len(consistent_df) * 0.8)]], ignore_index=True)
    eval_df = pd.concat([eval_df, consistent_df[int(len(consistent_df) * 0.8): int(len(consistent_df) * 0.9)]], ignore_index=True)
    test_df = pd.concat([test_df, consistent_df[int(len(consistent_df) * 0.9):]], ignore_index=True)
    for _, dataframe in inconsistent_dfs.items():
        dataframe = dataframe.sample(frac=1, random_state=seed).reset_index(drop=True)
        train_df = pd.concat([train_df, dataframe[: int(len(dataframe) * 0.8)]], ignore_index=True)
        eval_df = pd.concat([eval_df, dataframe[int(len(dataframe) * 0.8): int(len(dataframe) * 0.9)]], ignore_index=True)
        test_df = pd.concat([test_df, dataframe[int(len(dataframe) * 0.9):]], ignore_index=True)
    return train_df[COLUMNS], eval_df[COLUMNS], test_df[COLUMNS]
def summarise(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(df)),
        "consistency": {str(k): int(v) for k, v in df["consistency"].value_counts(dropna=False).sort_index().items()},
        "injected_pattern": {str(k): int(v) for k, v in df["injected_pattern"].fillna("<NA>").value_counts(dropna=False).sort_index().items()},
        "max_tokenized_length": int(pd.to_numeric(df["tokenized_length"], errors="coerce").max()),
    }
def main() -> None:
    parser = argparse.ArgumentParser(description="generate train/eval/test CSVs.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    df = pd.read_csv(args.input_csv)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Input CSV missing required columns: {missing}")
    train_df, eval_df, test_df = split_like_notebook(df, seed=args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    train_path = args.output_dir / "train_data.csv"
    eval_path = args.output_dir / "eval_data.csv"
    test_path = args.output_dir / "test_data.csv"
    train_df.to_csv(train_path, index=False)
    eval_df.to_csv(eval_path, index=False)
    test_df.to_csv(test_path, index=False)
    summary = {
        "input_csv": str(args.input_csv.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "seed": args.seed,
        "ratios": {"train": 0.8, "eval": 0.1, "test": 0.1},
        "train": summarise(train_df),
        "eval": summarise(eval_df),
        "test": summarise(test_df),
    }
    (args.output_dir / "split_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
if __name__ == "__main__":
    main()
