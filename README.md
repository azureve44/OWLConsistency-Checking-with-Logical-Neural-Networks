# OWL Consistency Verification on modified LUBM100 with LNN

## Description
Using a modified version of the Datapipeline developed in https://github.com/JustinMuecke/GLaMoR we refit LUBM100 to be usable for Ontology Consistency Verification.
Specifically we modify the modularization and embedding module and also slightly tweak the preprocessing process.
We include samples from the modified BioPortal dataset (see .csv files in GlaMoR/) by https://github.com/JustinMuecke/GLaMoR and samples from our modified LUBM100 dataset (see nsplits/).
Disclaimer: All provided samples are limited to 4096 body length. When regenerating a LUBM dataset using this pipeline you can disable this limit.

## Installation
Clone the repo, then setup conda environments for each folder containing a model (i.e. LNN, NLR,.. also seefolders in GLaMoR/GLaMoR_Model_Training/).
Requirements for each conda env can be installed via requirements.txt in each folder.
Further, Docker is required for running the pipeline, see GLaMoR/GLaMoR-Datapipeline/docs/ for quick start. 

## Usage
Output of pipeline will be .csv files with the following header:
file_name consistency tokenized_length body injected_pattern

See implementations of different models for examples on how to use this to train different models.

