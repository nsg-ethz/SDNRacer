
import logging

import hb_events
import hb_sts_events

# create logger
logger = logging.getLogger(__name__)


def find_first_controllerhandle(graph):
  """
  Traverses the graph and returns list of all nodes above the first packet out which caused a controller handle.

  Args:
    graph: graph

  Returns: List of nodes which can be removed from the graph

  """

  # get all root nodes
  stack = [x for x in graph.nodes() if not graph.predecessors(x)]

  nodes = []

  while stack:
    curr_node = stack.pop()

    # If the current node is a packet out -> check if it leads to a controller handle
    if (isinstance(graph.node[curr_node]['event'], hb_events.HbHostSend) or
        isinstance(graph.node[curr_node]['event'], hb_events.HbPacketSend)):
      pass


def find_last_controllerhandle(graph):
  """
  Traverses the graph upwards starting from node and returns list of all nodes up to the last controller handle
  including the packet out (HbPacketSend, HbHostSend or HbHostHandle) that led to this controller handle.
  Note: The substituted controllerHandle and switchTraversals end with a HbPacketSend

  Args:
    graph:  graph

  Returns:  list of nodes
  """
  # find the race events (one of them has to be the only node with no children)
  stack = [x for x in graph.nodes() if not graph.successors(x)]

  # There have to be exactly two nodes with no successors, the race events
  assert len(stack) == 2, 'find_last_controllerhandle: Number of nodes with no successors not equal two.'

  nodes = []

  while stack:
    curr_node = stack.pop()

    if curr_node in nodes:
      continue

    # Check if we visited all successors before continuing
    if len(graph.successors(curr_node)) > 1:
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


def has_write_event(graph):
  """
  Returns if a graph has a write event in one of the leafnodes.
  """
  # Check all leaf nodes
  for node in (x for x in graph.nodes() if not graph.successors(x)):
    # there should not be any leaf node in a graph
    if is_write_event(node, graph):
          return True

  return False


def is_write_event(node, graph):
  """
  Returns if a node is a write event
  """
  if isinstance(graph.node[node]['event'], hb_events.HbMessageHandle):
    for op in graph.node[node]['event'].operations:
      if isinstance(op, hb_sts_events.TraceSwitchFlowTableWrite):
        return True

  return False
