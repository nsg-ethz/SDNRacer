import logging.config
import time
import os
import networkx as nx

import utils

logger = logging.getLogger(__name__)


class RankGroup:
  def __init__(self, repre, graphs):
    """
    Class to store the rank groups (group of subgraphs). Each group has a score, representative graph to show to the user
    and a list of all clusters contained in the group.

    Args:
      repre:  Representative graph
      graphs: List of all graphs in this group
    """
    self.repre = repre  # Representative Graph
    self.graphs = graphs  # All clusters/Graphs


class Rank:
  """
  Class to rank graphs/clusters and put them in the different rank groups.
  """

  def __init__(self, resultdir, max_groups=5, score_same_write=1, score_iso_branch=1, threshold=1):
    self.resultdir = resultdir
    self.max_groups = int(max_groups)
    self.score_iso_branch = float(score_iso_branch)
    self.score_same_write = float(score_same_write)
    self.threshold = float(threshold)
    self.num_groups = 0
    self.groups = []

  def run(self, clusters):
    # Put the biggest cluster in the first group
    while len(clusters) > 0 and len(self.groups) < self.max_groups:
      clusters.sort(key=len, reverse=True)
      self.groups.append(RankGroup(clusters[0][0], clusters[0]))
      logger.debug("Group %2d" % len(self.groups))
      clusters.remove(clusters[0])

      # Calculate score
      cur_group = self.groups[-1]
      scores = []
      tiso = 0
      twrite = 0
      for ind, cluster in enumerate(clusters):
        score = 0
        tstart = time.time()
        score += self.iso_branch(cur_group, cluster)
        tiso = time.time() - tstart
        tstart = time.time()
        score += self.same_write_event(cur_group, cluster)
        twrite = time.time() - tstart
        scores.append([cluster, score])

      # add clusters to group, remove them from clusters
      ind = 0
      for cluster, score in scores:
        logger.debug("\tCluster %4d: Score %4.2f" % (ind, score / float(len(cluster))))
        if score / float(len(cluster)) > self.threshold:
          cur_group.graphs.extend(cluster)
          clusters.remove(cluster)
        ind += 1

    # Sort the groups based on the number of graphs in them
    self.groups.sort(key=lambda x: len(x.graphs), reverse=True)
    self.export_groups(self.resultdir)
    # Print group info
    logger.info("Time information grouping:")
    logger.info("\t Iso branches: %f" % tiso)
    logger.info("\t Same writes:  %f" % twrite)
    for ind, group in enumerate(self.groups):
      logger.info("Group %3d: %3d Graphs" % (ind, len(group.graphs)))

    rem_graphs = 0
    for g in clusters:
      rem_graphs += len(g)
    logger.info("Remaining: %d clusters, %d graphs" % (len(clusters), rem_graphs))

  def iso_branch(self, group, cluster):
    """
    Rank based on isomorphic branches of the graphs. Add score if a graph of cluster has a race brach which is
    isomorphic to a branch of the representative graph of the group.

    Args:
      group:  RaceGroup
      cluster:  Cluster to check

    Returns:
      self.score_iso if the branches are isomorphic or 0 if not
    """
    graph = cluster[0]
    # Split the graph
    components = nx.weakly_connected_components(graph)

    if len(components) == 2:
      # Only interesting if the graph has two separate branches
      g1 = nx.DiGraph(graph.subgraph(components[0]))
      g2 = nx.DiGraph(graph.subgraph(components[1]))

      # Only consider "write branches"
      if not utils.has_write_event(g1):
        g1 = None
      if not utils.has_write_event(g2):
        g2 = None
    else:
      g1 = None
      g2 = None

    # Split the representative graph
    components = nx.weakly_connected_components(group.repre)  # Only consider first graph of the cluster

    if len(components) == 2:
      # Only interesting if the graph has two separate branches
      r1 = nx.DiGraph(group.repre.subgraph(components[0]))
      r2 = nx.DiGraph(group.repre.subgraph(components[1]))

      # Only consider "write branches"
      if not utils.has_write_event(r1):
        r1 = None
      if not utils.has_write_event(r2):
        r2 = None
    else:
      r1 = None
      r2 = None

    # Find isomorphic parts
    iso = False
    if g1 and r1 and nx.is_isomorphic(g1, r1, node_match=self.node_match, edge_match=self.edge_match):
      iso = True
    elif g1 and r2 and nx.is_isomorphic(g1, r2, node_match=self.node_match, edge_match=self.edge_match):
      iso = True
    elif g2 and r1 and nx.is_isomorphic(g2, r1, node_match=self.node_match, edge_match=self.edge_match):
      iso = True
    elif g2 and r2 and nx.is_isomorphic(g2, r2, node_match=self.node_match, edge_match=self.edge_match):
      iso = True

    return self.score_iso_branch * len(cluster) if iso else 0

  def node_match(self, n1, n2):
    # it returns True if two nodes have the same event type
    return type(n1['event']) == type(n2['event'])

  def edge_match(self, e1, e2):
    # it returns True if two edges have the same relation
    return e1['rel'] == e2['rel']

  def same_write_event(self, group, cluster):
    """
    Checks if the races are caused by the same write event. Increases score for each graph that is caused by the same
    write event as one graph from the group
    Args:
      group:    rank_group
      cluster:  cluster to check

    Returns:
      score
    """

    # Get the event ids of all write events in the group
    write_ids = []
    for graph in group.graphs:
      # get leaf nodes
      for node in (x for x in graph.nodes() if not graph.successors(x)):
        if utils.is_write_event(node, graph):
          write_ids.append(node)

    # check how many graphs of the cluster have a write event in common with the group
    score = 0
    for graph in cluster:
      common_write = False
      for node in (x for x in graph.nodes() if not graph.successors(x)):
        if node in write_ids:
          score += self.score_same_write
          common_write = True
          break
      if common_write:
        break

    return score

  def export_groups(self, resultdir):
    for ind, group in enumerate(self.groups):
      export_path = os.path.join(self.resultdir, 'groups')
      if not os.path.exists(export_path):
        os.makedirs(export_path)
      nx.write_dot(group.repre, os.path.join(export_path, 'representative_%03d.dot' % ind))



