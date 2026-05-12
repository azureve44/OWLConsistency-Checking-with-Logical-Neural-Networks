# LUBM100 run commands
## 1)
```bash
cd ./GLaMoR-DataPipeline
CONSOLIDATED_OWL_DIR=./data/lubm_c \
MANIFEST_PATH=./data/filtered_dataset.csv \
UNIVERSITY_LIMIT=100 \
./run_lubm_pipe.sh
```
This produces the Tokenization output used for training conversion at:
```text
./data/filtered_modules/dataset.csv
```
## 2) Create the `filtered_dataset.csv`
```bash
cd ./GLaMoR-DataPipeline
python -u build_filtered_dataset.py \
  --input data/filtered_modules/dataset.csv \
  --output data/filtered_modules/filtered_dataset.csv \
  --max-tokens 4096
```
## 3) Create `80/10/10` training splits
```bash
cd GLaMoR
python -u ./GLaMoR_Model_Training/dataset_creation.py \
--output-dir ./GLaMoR-DataPipeline/data/splits_max4096 \ 
--seed 42 \
./GLaMoR-DataPipeline/data/filtered_modules/filtered_dataset.csv

```
Outputs:
```text
./GLaMoR-DataPipeline/data/splits_max4096/train_data.csv
./GLaMoR-DataPipeline/data/splits_max4096/eval_data.csv
./GLaMoR-DataPipeline/data/splits_max4096/test_data.csv
./GLaMoR-DataPipeline/data/splits_max4096/split_summary.json
```
