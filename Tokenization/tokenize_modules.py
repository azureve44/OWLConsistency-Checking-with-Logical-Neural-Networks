import random
import logging
from pathlib import Path
import json
from classifier import GraphT5Classifier
from graph_t5.tokenization_t5_fast import T5TokenizerFast as T5Tokenizer
from wrapper_functions import Graph, graph_to_graphT5, graph_to_set_of_triplets, get_embedding, Data
import numpy as np
from get_arguments import add_args_shared
from get_arguments import add_args
from get_arguments import get_args
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from tqdm import tqdm
from torch import tensor


class tokenizer_filter():
    def __init__(self):
        self.parser = ArgumentParser(
            formatter_class=ArgumentDefaultsHelpFormatter  # makes wandb log the default values
        )
        add_args_shared(self.parser)
        add_args(self.parser)
        self.args = get_args(self.parser)
        self.num_classes = 2
        self.model = GraphT5Classifier(config=GraphT5Classifier.get_config(num_classes=self.num_classes, modelsize=self.args.modelsize, num_additional_buckets=self.args.num_additional_buckets))


    def data_to_dataT5(self, graph:Graph, tokenizer:T5Tokenizer, label:str, label_to_index:dict, graph_representation:str, eos:str):
        """
        :param graph: graph to convert
        :param tokenizer: tokenizer of model
        :param label: label of the relation
        :param label_to_index: mapping from label to index
        :param graph_representation: how to represent the graph. 
        :param eos: end-of-sequence token. Can be `False` for not using an eos token. When using an eos token, there are two ways to use it: `bidirectional` means that the eos token is connected to every other node in the graph, with a relative position of positive infinity (from node to eos) or negative infinity (from eos to node). `unidirectional` means that the eos token is connected to every node in the graph with a relative position of positive infinity (from node to eos), but not the other way around (i.e. no connection from eos to other node). This means, that nodes do not get messages from the eos token, which preserves locality when using the local GLM
        """
        if graph_representation == 'lGLM':
            data = graph_to_graphT5(graph, tokenizer, how='local', eos=eos)
        elif graph_representation == 'set':
            data = graph_to_set_of_triplets(graph, tokenizer, order='random')
        elif graph_representation == 'gGLM':
            data = graph_to_graphT5(graph, tokenizer, how='global', eos=eos)
        elif graph_representation == 'list':
            data = graph_to_set_of_triplets(graph, tokenizer, order='alphabetical')
        else:
            raise ValueError(f"unknown graph_representation {graph_representation}")
        data.label = tensor(label_to_index[label])
        return data


    def main(self, file_name):
        random.seed(self.args.seed)
        np.random.seed(self.args.seed)
        file_path = Path(f"/input/{file_name}")
        with file_path.open("r", encoding="utf-8") as f:
            triple_list = json.load(f)
        graph = Graph(triple_list)
        label = "Consistent"
        label_to_index = {"Inconsistent": 0, "Consistent": 1}
        data = self.data_to_dataT5(graph, self.model.tokenizer, label, label_to_index, self.args.graph_representation, self.args.eos_usage)
        return (len(data.input_ids[0]), triple_list)




    