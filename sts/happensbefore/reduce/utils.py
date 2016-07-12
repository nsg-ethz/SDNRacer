
import logging
import itertools

import networkx as nx

import hb_events

# create logger
logger = logging.getLogger(__name__)


def find_last_controllerhandle(graph, node):
  """
  Traverses the graph upwards starting from node and returns list of all nodes up to the last controller handle
  including the packet out (HbPacketSend, HbHostSend or HbHostHandle) that led to this controller handle.
  Note: The substituted controllerHandle and switchTraversals end with a HbPacketSend

  Args:
    graph:  graph
    node:   node_id

  Returns:  list of nodes
  """

  stack = [node]
  nodes = []

  while stack:
    curr_node = stack.pop()

    if curr_node in nodes:
      continue

    # Check if we visited all successors before continuing
    if graph.successors(curr_node) > 1:
      all_successors_visited = True
      for successor in graph.successors(curr_node):
        if successor not in nodes:
          all_successors_visited = False
          break
      if not all_successors_visited:
        continue

    nodes.append(curr_node)

    if isinstance(graph.node[curr_node]['event'], hb_events.HbControllerHandle):
      # found the first controller handle in this branch
      stack_controllerhandle = graph.predecessors(curr_node)
      while stack_controllerhandle:
        curr_controllerhandle = stack_controllerhandle.pop()
        nodes.append(curr_controllerhandle)
        if isinstance(graph.node[curr_controllerhandle]['event'],
                      (hb_events.HbPacketSend, hb_events.HbHostSend, hb_events.HbHostHandle)):
          continue

        else:
          # In this case, we didn't find the packet out event that led to the controller handle
          stack_controllerhandle.extend(graph.predecessors(curr_controllerhandle))

    else:
      stack.extend(graph.predecessors(curr_node))

  return nodes


def find_last_controllerhandle_old(graph, node):
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
    for n1, n2 in itertools.combinations(predecessors ,2):
      if nx.has_path(graph, n1, n2):
        predecessors.remove(n1)
      elif nx.has_path(graph, n2, n1):
        predecessors.remove(n2)

  for pred in predecessors:
    _find_last_controllerhandle(graph, pred, nodes, found_controller_handle)

  return
