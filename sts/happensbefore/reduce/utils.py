
import sys
import time
import logging
import networkx as nx
from networkx.algorithms import isomorphism

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


def remove_dataplanetraversals(g):
  """
  Returns a copy of the graph g with removed dataplane traversals.
  """
  # First copy the representative graph
  graph = g.copy()

  # Now remove all DataplaneTraversals
  stack = [x for x in graph.nodes() if not graph.predecessors(x)]
  visited = []

  found_dataplanetraversal = False
  while stack:
    node = stack.pop()
    if node in visited:
      continue
    else:
      visited.append(node)

    stack.extend(graph.successors(node))
    if graph.node[node]['event'] == 'DataplaneTraversal':
      found_dataplanetraversal = True
      for p in graph.predecessors(node):
        for s in graph.successors(node):
          graph.add_edge(p, s, {'label': '', 'rel': ''})

      graph.remove_node(node)

  return graph if found_dataplanetraversal else None


def contains_pingpong(graph):
  """
  Takes a graph g and substitute all controller handles (messagesend -> controllerhandle -> controllersend) with
  a single "controllerhandle" node.
  """
  tstart = time.clock()
  # Create dummy controller handle for graph subgraph isomorphism check.
  controller_dummy = nx.DiGraph()
  controller_dummy.add_node(1, {'event': hb_events.HbMessageSend(None, None, None)})
  controller_dummy.add_node(2, {'event': hb_events.HbControllerHandle(None, None)})
  controller_dummy.add_node(3, {'event': hb_events.HbControllerSend(None, None)})
  controller_dummy.add_node(4, {'event': hb_events.HbMessageHandle(None, None)})
  controller_dummy.add_node(5, {'event': hb_events.HbMessageSend(None, None, None)})
  controller_dummy.add_node(6, {'event': hb_events.HbControllerHandle(None, None)})
  controller_dummy.add_node(7, {'event': hb_events.HbControllerSend(None, None)})
  controller_dummy.add_edge(1, 2)
  controller_dummy.add_edge(2, 3)
  controller_dummy.add_edge(3, 4)
  controller_dummy.add_edge(4, 5)
  controller_dummy.add_edge(5, 6)
  controller_dummy.add_edge(6, 7)

  # Check if this pattern is in the graph
  graph_matcher = isomorphism.DiGraphMatcher(graph, controller_dummy, node_match=node_match)
  for match in graph_matcher.subgraph_isomorphisms_iter():
    # Check if the message origins from the same switch
    e1 = (key for key, value in match.items() if value == 1).next()
    e2 = (key for key, value in match.items() if value == 5).next()
    if graph.node[e1]['event'].dpid == graph.node[e2]['event'].dpid:
      return True

  return False


def iso_components(graph1, graph2):
  """
  Return True if any components of the graph are isomorphic.
  """
  # Split graph1
  components = list(nx.weakly_connected_components(graph1))

  if len(components) == 2:
    # Only interesting if the graph has two separate branches
    g1 = nx.DiGraph(graph1.subgraph(components[0]))
    g2 = nx.DiGraph(graph1.subgraph(components[1]))

    # Only consider "write branches"
    if not has_write_event(g1):
      g1 = None
    if not has_write_event(g2):
      g2 = None
  else:
    g1 = None
    g2 = None

  # Split split graph 2
  components = list(nx.weakly_connected_components(graph2))  # Only consider first graph of the cluster

  if len(components) == 2:
    # Only interesting if the graph has two separate branches
    r1 = nx.DiGraph(graph2.subgraph(components[0]))
    r2 = nx.DiGraph(graph2.subgraph(components[1]))

    # Only consider "write branches"
    if not has_write_event(r1):
      r1 = None
    if not has_write_event(r2):
      r2 = None
  else:
    r1 = None
    r2 = None

  # Find isomorphic parts
  iso = False
  if g1 and r1 and nx.is_isomorphic(g1, r1, node_match=node_match, edge_match=edge_match):
    iso = True
  elif g1 and r2 and nx.is_isomorphic(g1, r2, node_match=node_match, edge_match=edge_match):
    iso = True
  elif g2 and r1 and nx.is_isomorphic(g2, r1, node_match=node_match, edge_match=edge_match):
    iso = True
  elif g2 and r2 and nx.is_isomorphic(g2, r2, node_match=node_match, edge_match=edge_match):
    iso = True
  elif nx.is_isomorphic(graph1, graph2, node_match=node_match, edge_match=edge_match):
    iso = True

  return iso


def node_match(n1, n2):
  # it returns True if two nodes have the same event type
  return type(n1['event']) == type(n2['event'])


def edge_match(e1, e2):
  # it returns True if two edges have the same relation
  return e1['rel'] == e2['rel']
