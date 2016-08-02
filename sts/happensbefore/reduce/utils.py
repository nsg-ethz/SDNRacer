
import logging
import os
import itertools
import sys

import networkx as nx

import hb_events
import hb_sts_events

# create logger
logger = logging.getLogger(__name__)


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


def export_cluster_graphs(clusters, resultdir, prefix='cluster', export_overview=False):
  """
  Export the first graph of each cluster as .dot file.
  Args:
    clusters:   List of clusters
    resultdir:  Directory where to safe the graphs
    prefix:     Prefix of the exportet file names (default='cluster')
    export_overview:   Boolean which indicates if an overview should be exportet as well, attention: SLOW (default=False)

  """
  # Export a graph of each cluster and "overview" of clusters (one graph of each cluster)
  overview = []
  for ind, cluster in enumerate(clusters):
    export_path = os.path.join(resultdir, "%s_%03d.dot" % (prefix, ind))
    nx.write_dot(cluster[0], export_path)
    overview.append(cluster[0])

  # Export overview of all clusters
  if export_overview:
    export_path = os.path.join(resultdir, "%s_clusters_overview.dot" % prefix)
    nx.write_dot(nx.disjoint_union_all(overview), export_path)


def write_clusters_info(clusters, indent=True):
  """
  Writes the size of each cluster to the log (grouped by size).
  Args:
    clusters: List of clusters
    indent:   Boolean, indicates if the entries should be indented by a tab.
  """
  # First write the number of subgraphs and the number of clusters
  num_cluster = len(clusters)
  num_subgraphs = sum([len(x) for x in clusters])
  logger.debug("%sTotal Clusters: %d, Total Subgraphs: %d" % (indent, num_cluster, num_subgraphs))
  curr_size = sys.maxint
  start_ind = 0
  if indent:
    indent = "\t"
  else:
    indent = ""
  for ind, cluster in enumerate(clusters):
    if len(cluster) < curr_size:
      if not ind == 0:
        logger.debug("%sCluster %5d - %5d: %5d graphs each" % (indent, start_ind, ind - 1, curr_size))
      curr_size = len(cluster)
      start_ind = ind

  logger.debug("\tCluster %5d - %5d: %5d graphs each" % (start_ind, len(clusters) - 1, len(clusters[-1])))


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
