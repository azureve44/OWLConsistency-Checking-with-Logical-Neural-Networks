import os
from tokenize_modules import tokenizer_filter
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

INCONSISTENT_PREFIXES = ["AIO", "EID", "OIL", "OILWI", "OILWPI", "UE", "UEWI1", "UEWI2", "UEWPI", "UEWIP", "SOSINETO", "CSC", "OOR", "OOD"]

def _file_consistent(file_name : str) -> bool:
    return file_name.split("_")[0] not in INCONSISTENT_PREFIXES

def _process_file(file_name, token_filter):
    try:
        result = token_filter.main(file_name)
        token_length, body = result
        return [file_name, _file_consistent(file_name), token_length, body]
    except Exception as exception: 
        print(f"Couldn't tokenize {file_name}: {exception}")
        return []

def start_worker():
    dataset : pd.DataFrame = pd.DataFrame(columns=["file_name", "consistency", "tokenized_lenght", "body"])
    input_directory = "/input/"
    print("Worker Started...")
    token_filter = tokenizer_filter()
    print("Got Tokenizer...")
    rows = []

       

    file_list = [f for f in Path(input_directory).iterdir() if not f.name.startswith(".git")]

    rows = []
    max_threads = 4  # Set the maximum number of threads

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = {executor.submit(_process_file, file.name, token_filter): file for file in file_list}

        for future in tqdm(as_completed(futures), total=len(futures)):
            try:
                res = future.result()
                if res:
                    rows.append(res)
            except Exception as e:
                print(f"Error processing file: {e}")

    dataset = pd.DataFrame(rows, columns=["file_name", "consistency", "tokenized_length", "body"])

    output_path = Path("/output/dataset.csv")
    dataset.to_csv(output_path, index=False)
    print(f"Dataset saved to {output_path}")
    print("Finished Dataset Creation")


if __name__ == "__main__":
    start_worker()

