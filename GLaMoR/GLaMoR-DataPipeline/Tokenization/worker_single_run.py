import csv
import os
from multiprocessing import get_context
from pathlib import Path
import pandas as pd
from tqdm import tqdm
from tokenize_modules import tokenizer_filter
INCONSISTENT_PREFIXES = [
    "AIO",
    "EID",
    "OIL",
    "OILWI",
    "OILWPI",
    "UE",
    "UEWI1",
    "UEWI2",
    "UEWPI",
    "UEWIP",
    "SOSINETO",
    "CSC",
    "OOR",
    "OOD",
]
_TOKEN_FILTER = None
def _init_token_filter():
    global _TOKEN_FILTER
    _TOKEN_FILTER = tokenizer_filter()
def _file_consistent(file_name: str) -> bool:
    return file_name.split("_")[0] not in INCONSISTENT_PREFIXES
def _process_file(file_name: str, token_filter):
    try:
        token_length, body = token_filter.main(file_name)
        consistency = _file_consistent(file_name)
        return {
            "file_name": file_name,
            "consistency": consistency,
            "tokenized_length": token_length,
            "body": body,
        }
    except Exception as exception:
        print(f"Couldn't tokenize {file_name}: {exception}")
        return None
def _process_file_with_global_filter(file_name: str):
    global _TOKEN_FILTER
    return _process_file(file_name, _TOKEN_FILTER)
def _write_predictions(rows: list[dict], output_dir: Path) -> Path:
    predictions_path = output_dir / "predictions.csv"
    with predictions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file_name", "consistency"])
        for row in rows:
            writer.writerow(
                [
                    row["file_name"],
                    "consistent" if bool(row["consistency"]) else "inconsistent",
                ]
            )
    return predictions_path
def start_worker():
    input_directory = Path("/input")
    print("Worker Started...")
    file_list = sorted(
        f for f in input_directory.iterdir() if f.is_file() and not f.name.startswith(".git")
    )
    rows: list[dict] = []
    requested_threads = max(1, int(os.getenv("MAX_THREADS", "1")))
    worker_count = min(requested_threads, len(file_list), os.cpu_count() or 1) if file_list else 1
    if worker_count > 1:
        print(f"Using {worker_count} worker processes for tokenization.")
        with get_context("spawn").Pool(processes=worker_count, initializer=_init_token_filter) as pool:
            for res in tqdm(
                pool.imap_unordered(_process_file_with_global_filter, [file.name for file in file_list]),
                total=len(file_list),
            ):
                if res:
                    rows.append(res)
    else:
        token_filter = tokenizer_filter()
        print("Got Tokenizer...")
        for file in tqdm(file_list, total=len(file_list)):
            res = _process_file(file.name, token_filter)
            if res:
                rows.append(res)
    rows.sort(key=lambda row: row["file_name"])
    dataset = pd.DataFrame(rows, columns=["file_name", "consistency", "tokenized_length", "body"])
    output_dir = Path(os.getenv("OUTPUT_DIR", "/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = output_dir / "dataset.csv"
    dataset.to_csv(dataset_path, index=False)
    predictions_path = _write_predictions(rows, output_dir)
    print(f"Dataset saved to {dataset_path}")
    print(f"Predictions saved to {predictions_path}")
    print("Finished Dataset Creation")
if __name__ == "__main__":
    start_worker()
