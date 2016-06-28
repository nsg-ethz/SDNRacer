

import logging
import itertools

import networkx as nx

import hb_events

# create logger
logger = logging.getLogger(__name__)


def find_last_controllerhandle(graph, node):
  """
  Traverses the graph upwards starting from node and returns list of all nodes up to the last controller handle
  including the packedsend or hostsend that led to this controller handle.

  Args:
    graph:  graph
    node:   node_id

  Returns:  list of nodes
  """

  nodes = []
  _find_last_controllerhandle(graph, node, nodes)
  return list(set(nodes))


def _find_last_controllerhandle(graph, node, nodes, found_controller_handle=False):
  """
  Recursive part of find_last_controller_handle
  """
  # Return if the node was already traversed
  if node in nodes:
    return

  nodes.append(node)

  # If we already found a controller handle and the current event was a "send" -> return
  if (found_controller_handle and
      (isinstance(graph.node[node]['event'], hb_events.HbPacketSend) or
       isinstance(graph.node[node]['event'], hb_events.HbHostSend))):
    return

  # If the current node is a controller handle -> set the controller_handle variable
  if "HbControllerHandle" in graph.node[node]['label']:
    found_controller_handle = True

  # traverse all predecessors
  predecessors = graph.predecessors(node)

  # If there are multiple predecessors check if two of them are connected. If yes, remove the one
  # which has a shorter path
  if len(predecessors) > 1:
    for n1, n2 in itertools.combinations(predecessors,2):
      if nx.has_path(graph, n1, n2):
        predecessors.remove(n1)
      elif nx.has_path(graph, n2, n1):
        predecessors.remove(n2)

  for pred in predecessors:
    _find_last_controllerhandle(graph, pred, nodes, found_controller_handle)

  return
