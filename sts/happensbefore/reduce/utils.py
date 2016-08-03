
import logging

import hb_events
import hb_sts_events

# create logger
logger = logging.getLogger(__name__)

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
