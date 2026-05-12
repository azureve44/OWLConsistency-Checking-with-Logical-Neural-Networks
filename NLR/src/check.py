import sys
sys.path.append("..")  # allow imports from ltnconvertor

import pandas as pd
from data_loaders.ProLogicDL import ProLogicDL
from data_processors.ProLogicDP import ProLogicDP

# Parameters
dataset = "nlr_data"
path = "../ltnconvertor/"

# Load data
dl = ProLogicDL(path=path, dataset=dataset)
print(f"Train CSV head:\n{dl.train_df.head()}")

# Initialize data processor (correct keyword arguments)
dp = ProLogicDP(dl,
                rank=0,
                shuffle_and=1,
                shuffle_or=1,
                train_sample_n=1,
                test_sample_n=100,
                sample_un_p=1.0,
                unlabel_test=0)

# Dry-run: prepare train data
dp.get_train_data(epoch=-1, model="NLR")

# Inspect the first training instance
train_data = dp.train_data
print("\nExample processed train data (first instance):")
for key, value in train_data.items():
    print(f"{key}: {value[0]}")  # just the first example
