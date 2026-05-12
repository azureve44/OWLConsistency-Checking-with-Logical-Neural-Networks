# GLaMoR

This Repository contains all the code required to run the GLaMoR-Pipeline.
## Project Structure
```
├──GLaMoR-DataPipeline

├──GLaMoR-Model_Training
│  
├──.gitignore/
├──.gitmodules
├──README.md
├──LICENSE
```

## Requirements
The System is split into two components, the Data Pipeline and the Model Training. The requirements for the two components are listed below
### Data Pipeline
If you want to use the code as provided, it is enough to have docker-compose installed on the system and read 
```
READ GLaMoR/GLaMoR-DataPipeline/docs/howto-run-lubm-pipeline.md
```
Remember to update the mountings as well as environment variables according to your setup.

### Model Training
To train the models, a `requirements.txt` file is available for most of them. If it's missing, make sure you have the following installed:

- scikit-learn  
- pandas  
- numpy  
- torch

## Citation
A citation will be provided upon publication.
