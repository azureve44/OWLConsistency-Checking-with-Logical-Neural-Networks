import os
import pandas as pd
from pathlib import Path

DATASET_DIR = "../dataset/ncit_subclass"
DATASET_NAME = "ncit_subclass"

def load_split(name):
    return pd.read_csv(
        os.path.join(DATASET_DIR, f"{DATASET_NAME}.{name}.csv"),
        sep="\t"
    )

def main():
    train = load_split("train")
    val = load_split("validation")
    test = load_split("test")

    # Collect all unique entities
    all_entities = set(train["uid"]) | set(train["iid"]) | \
                   set(val["uid"])   | set(val["iid"])   | \
                   set(test["uid"])  | set(test["iid"])

    print("Total unique entities:", len(all_entities))

    # Create mapping
    entity2id = {e: i for i, e in enumerate(sorted(all_entities))}

    # Replace IDs
    def encode(df):
        df["uid"] = df["uid"].map(entity2id)
        df["iid"] = df["iid"].map(entity2id)
        return df

    train = encode(train)
    val = encode(val)
    test = encode(test)

    # Save back
    train.to_csv(os.path.join(DATASET_DIR, f"{DATASET_NAME}.train.csv"),
                 sep="\t", index=False)
    val.to_csv(os.path.join(DATASET_DIR, f"{DATASET_NAME}.validation.csv"),
               sep="\t", index=False)
    test.to_csv(os.path.join(DATASET_DIR, f"{DATASET_NAME}.test.csv"),
                sep="\t", index=False)

    # Save mapping for later interpretation
    mapping_df = pd.DataFrame(entity2id.items(), columns=["entity", "id"])
    mapping_df.to_csv(os.path.join(DATASET_DIR, "entity_mapping.csv"),
                      sep="\t", index=False)

    print("Encoding complete.")


if __name__ == "__main__":
    main()
