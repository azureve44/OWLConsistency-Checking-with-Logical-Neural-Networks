# OWL Consistency Verification on modified LUBM100 with LNN

## Description
Using a modified version of the Datapipeline developed in https://github.com/JustinMuecke/GLaMoR we refit LUBM100 to be usable for Ontology Consistency Verification.
Specifically we modify the modularization and embedding module and also slightly tweak the preprocessing process.
We include samples from the modified BioPortal dataset (see .csv files in GlaMoR/) by https://github.com/JustinMuecke/GLaMoR and samples from our modified LUBM100 dataset (see nsplits/).
Disclaimer: All provided samples are limited to 4096 body length. When regenerating a LUBM dataset using this pipeline you can disable this limit.

## Implementation of used models
For the GLMs, ModernBERT, RandomForest, and SVM models, we use the implementation from Mücke and Scherp, as well as use their models as is to train on the dataset splits.  
For the neuro-symbolic models, we proceeded with our implementation as follows:
We derive labels from whether injected_pattern is present in the row of the sample.
Then, vocabularies are built from the training split only, to avoid leakage and corruption of final metrics.
Finally, the results are aggregated over 5 random seeds.
For LINNs, we used the original implementation and encoded each ontology as a sequence of triples with per-ontology local entity IDs and globally shared predicate IDs. 
We replace the default feature embedding with a custom triple embedding module to enable IRI-agnostic structural generalisation across all ontologies. 
Finally, to train the model, we use class-balanced batches, Adam optimiser with cosine decay and validation-based early stopping.
For LTNs, we used raw ontology triples directly, since the implementation presented in the original paper allowed us to do this fairly easily. 
Going forward, each ontology was encoded as a padded set of subject, predicate and object-token IDs derived from a train-only vocabulary. Further, we implement an ontology embedding with a triple and set encoder and then trained an LTN predicate, e.g. Inconsistent(x), using the Real Logic binary-classification LTN objective that maximises satisfaction of positive and negative axioms.
For LNNs, we adapted the original model from the repo to use symbolic ontology-level features extracted from raw triples. Train-only features capture graph structure, predicate co-occurrence, OWL object expression operators, and count statistics. They are then grouped into logical subrules where their outputs are combined by a final disjunction. 
Finally, we include data-aware OR initialisation, supervision on the final trainable formulas and validation-based threshold tuning in our implementation.
For NLMs, we cast each ontology as a labelled multi-graph with local entity IDs and global shared predicate channels in a similar fashion as with LINN. 
To make the model perform ontology-level classification, we added a graph-level pooling head on top of the given Logic Machine, constructed dense adjacency tensors, projected sparse predicate channels, and explicitly masked and padded entities after each logic layer to preserve the learning signal.

## Installation
Clone the repo, then setup conda environments for each folder containing a model (i.e. LNN, NLR,.. also seefolders in GLaMoR/GLaMoR_Model_Training/).
Requirements for each conda env can be installed via requirements.txt in each folder.
Further, Docker is required for running the pipeline, see GLaMoR/GLaMoR-Datapipeline/docs/ for quick start. 

## Usage
Output of pipeline will be .csv files with the following header:
file_name consistency tokenized_length body injected_pattern

See implementations of different models for examples on how to use this to train different models.

