import logging
import sys

import networkx as nx

import utils
import pattern

logger = logging.getLogger(__name__)


class Preprocessor:
  # Provides different functions for preprocessing of the subgraphs
  def __init__(self, extract_last_controller_action=True, substitute_patterns=None):
    # set configuration options, all parameters must have default values!!
    self.extract = extract_last_controller_action.lower() not in ['false', '0']

    if substitute_patterns == 'None':
      self.patterns = None
    else:
      patterns = substitute_patterns.split(',')
      self.patterns = []
      for p in patterns:
        if p.lower() == 'controllerhandle':
          self.patterns.append(pattern.ControllerHandle())
        else:
          raise RuntimeError("%s is not a valid option for pattern substitution." % p)

  def run(self, subgraphs):
    """
    Runs preprocessing functions depending on the configuration of the preprocessor.

    Args:
      subgraphs:  list of subgraphs

    Returns:      preprocessed list of subgraphs

    """
    if self.extract:
      subgraphs = self.extract_last_controller_action(subgraphs)
    if self.patterns:
      subgraphs = self.substitute_patterns(subgraphs)

    return subgraphs

  def extract_last_controller_action(self, subgraphs):
    """
    only keeps nodes from the race events up to the last packet send that required controller action

    Args:
      subgraphs: List of graphs

    Returns:
      new list of preprocessed subgraphs

    """

    new_subgraphs = []

    logger.info("Remove all events before the one that led to the last controller action for both race events.")
    for graph in subgraphs:

      # TODO: Rewrite with list comprehension -> should be faster
      # find the race events (one of them has to be the only node with no children)
      race_i = None
      for node_id in graph:
        if not graph.successors(node_id):
          race_i = node_id
          break

      if not race_i:
        logger.error("Did not find the last element in the graph")
        sys.exit(-1)

      # Find the other race event (only for graph verification, not necessary for program)
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

  def substitute_patterns(self, subgraphs):
    """
    Processes list of subgraphs and substitute all patterns in self.pattern.

    Args:
      subgraphs: list of subgraphs

    Returns
      new list of preprocessed subgraphs
    """
    new_subgraphs = []

    for p in self.patterns:
      for ind, subg in enumerate(subgraphs):
        patterns = p.find_pattern(subg)
        if patterns:
          print "Found patterns in subgraph %s" % ind
          print patterns
          sys.exit()

    return subgraphs



