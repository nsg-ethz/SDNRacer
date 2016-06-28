import logging
import sys

import networkx as nx

import utils

logger = logging.getLogger(__name__)

class Preprocessor:
  # Provides different functions for preprocessing of the subgraphs
  def __init__(self):
    # set configuration options, all parameters must have default values!!
    pass

  def run(self, subgraphs):
    """
    Runs preprocessing functions depending on the configuration of the preprocessor.

    Args:
      subgraphs:  list of subgraphs

    Returns:      preprocessed list of subgraphs

    """
    subgraphs = self.extract_last_controller_action(subgraphs)

    return subgraphs



  def extract_last_controller_action(self, subgraphs):
    """
    only keeps nodes from the race events up to the last packet send that required controller action

    Args:
      subgraphs: List of graphs
      ignore_pid: Bool, Indicates if we can ignore pid edges or not (default True)

    Returns:

    """

    new_subgraphs = []

    logger.info("Remove all events before the one that led to the last controller action for both race events.")
    for graph in subgraphs:

      # find the race events (one of them has to be the only node with no children)
      race_i = None
      for node_id in graph:
        if not graph.successors(node_id):
          race_i = node_id
          break

      if not race_i:
        logger.error("Did not find the last element in the graph")
        sys.exit(-1)

      # Find the other race event (only for graph verification, not necessary for programm)
      if "FlowTableWrite" in graph.node[race_i]['label']:
        for pred in graph.predecessors(race_i):
          if "FlowTableWrite" in graph.node[pred]['label'] or "FlowTableRead" in graph.node[pred]['label']:
            race_k = pred
            break

      else:
        for pred in graph.predecessors(race_i):
          if "FlowTableWrite" in graph.node[pred]['label']:
            race_k = pred
            break

      if not race_k:
        logger.error("Did not find the second race event id")
        sys.exit(-1)

      # Find last controller handle for both events
      nodes_to_keep = utils.find_last_controllerhandle(graph, race_i)

      # Generate the new subgraph
      new_graph = nx.DiGraph(graph.subgraph(nodes_to_keep))
      new_subgraphs.append(new_graph)

    return new_subgraphs

