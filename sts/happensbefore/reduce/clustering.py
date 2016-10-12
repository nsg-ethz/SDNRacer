import logging.config
import time
import os
import sys
import itertools
import networkx as nx
from networkx.algorithms import isomorphism

import utils
import cluster_algorithm
import cluster

logger = logging.getLogger(__name__)

class Clustering:
  def __init__(self, resultdir):
    """
    Class to cluster the subgraphs
    """
    self.resultdir = resultdir
    self.graphs = []
    self.clusters = []
    self.remaining = []
    self.eval = {'time': {},
                 'info': {},
                 'iso init total': 0}

    self.t_is_is = 0
    self.t_matcher = 0

  def run(self, graphs, algorithm):
    self.graphs = graphs

    # Initialize clusters
    tstart = time.clock()
    logger.debug("Initialize clusters with isomorphic graphs")
    self.initialize_clusters()

    self.write_clusters_info()

    # Clustering
    logger.debug("Start Clustering")
    # Check if there are more than two clusters
    if len(self.clusters) <= 1:
      logger.info("Only one cluster left after isomorphic initialization.")
      self.eval['time']['Total'] = time.clock() - tstart
      algorithm.eval['time']['Calculate distance matrix'] = 0.0
      algorithm.eval['time']['Calculate clustering'] = 0.0
      algorithm.eval['time']['Assign new clusters'] = 0.0
    else:
      self.clusters, self.remaining = algorithm.run(self.clusters)
      self.write_clusters_info()

    # Merge Eval dicts so that only this one is needed later
    self.eval['score'] = algorithm.eval['score']
    for k, v in algorithm.eval['time'].iteritems():
      self.eval['time'][k] = v

    self.eval['time']['Total'] = time.clock() - tstart

    return

  def initialize_clusters(self):
    """
    Initializes the clusters: Put all isomorphic graphs in a separate cluster.
    """
    tstart = time.clock()
    logger.debug("Number of graphs: %d" % len(self.graphs))

    # Sort graphs based on number of nodes
    self.graphs.sort(key=len, reverse=True)

    # Put all isomorphic graphs in groups
    stack = self.graphs[:]  # Copy of graph list to process
    groups = []  # List groups of graphs which are later used to create the clusters
    groups_timeout = []

    for ind, curr_graph in enumerate(self.graphs):
      # logger.debug("Process graph %5d (%5d of %5d)" % (curr_graph.graph['index'], ind, len(self.graphs)))
      added = False
      # Check if the current graph is isomorphic with a graph from a existing group of graphs
      for group in reversed(groups):
        # Because of the odering (sorted and reversed) we can break as soon as the graph is smaller
        # as the graphs in the current group.
        if len(group[0]) > len(group[0]):
          break
        if nx.faster_could_be_isomorphic(group[0], curr_graph):

          # Check isomorphism with timeout
          try:
            with utils.timeout(2):
              if nx.is_isomorphic(group[0], curr_graph, node_match=utils.node_match, edge_match=utils.edge_match):
                group.append(curr_graph)
                added = True
                break
          except utils.TimeoutError:
            groups_timeout.append([curr_graph])
            added = True
            logger.debug("Timeout in isomorphic check. Len graphs: %d, %d" % (len(group[0]), len(curr_graph)))
            break
          finally:
            self.eval['iso init total'] += 1

      # if not -> prepare new cluster
      if not added:
        groups.append([curr_graph])

    # Add isomorphic cluster id to graph for evaluation
    for ind, group in enumerate(groups):
      for graph in group:
        graph.graph['iso_cluster'] = ind

    # Create new cluster out of all groups and append it to the cluster list
    for group in groups:
      self.clusters.append(cluster.Cluster(group))

    for graph in groups_timeout:
      self.clusters.append(cluster.Cluster(graph))

    logger.debug("Number of clusters after iso: %d" % len(self.clusters))

    self.eval['info']['Number of graphs'] = len(self.graphs)
    self.eval['info']['Number of clusters after iso'] = len(self.clusters)
    self.eval['iso init timeout'] = len(groups_timeout)

    self.eval['time']['Initialize cluster'] = time.clock() - tstart
    return

  def write_clusters_info(self):
    """
    Writes the size of each cluster to the log (grouped by size).
    """
    logger.debug("Cluster Info")
    logger.debug("\tTotal Clusters: %d, Total Subgraphs: %d" % (len(self.clusters), len(self.graphs)))

    # sort the clusters based on size
    self.clusters.sort(key=lambda x: len(x.graphs), reverse=True)
    curr_size = sys.maxint
    start_ind = 0
    for ind, cluster in enumerate(self.clusters):
      if len(cluster.graphs) < curr_size:
        if not ind == 0:
          logger.debug("\tCluster %5d - %5d: %5d graphs each" % (start_ind, ind - 1, curr_size))
        curr_size = len(cluster.graphs)
        start_ind = ind

    logger.debug("\tCluster %5d - %5d: %5d graphs each" % (start_ind, len(self.clusters) - 1, curr_size))

  def export_clusters(self):
    """ Exports the representative graphs in the result directory and creats a folder for each group
    to export all informative graphs in the group."""
    for ind, cluster in enumerate(self.clusters):
      # Export representative graph
      nx.drawing.nx_agraph.write_dot(cluster.representative, os.path.join(self.resultdir, 'cluster_%03d.dot' % ind))
      # Create folder for the other graphs
      export_path = os.path.join(self.resultdir, 'cluster_%03d' % ind)
      if not os.path.exists(export_path):
        os.makedirs(export_path)
      iso_exported = []
      for graph in cluster.graphs:
        if 'iso_cluster' not in graph.graph:
          nx.drawing.nx_agraph.write_dot(graph, os.path.join(export_path, 'iso_timeout_%03d.dot' % graph.graph['index']))
        elif 'iso_cluster' in graph.graph and graph.graph['iso_cluster'] not in iso_exported:
          nx.drawing.nx_agraph.write_dot(graph, os.path.join(export_path, 'iso_%03d.dot' % graph.graph['iso_cluster']))
          iso_exported.append(graph.graph['iso_cluster'])
        nx.drawing.nx_agraph.write_dot(graph, os.path.join(export_path, 'graph_%03d.dot' % graph.graph['index']))

    # Export outliers (remaining)
    if self.remaining:
      export_path = os.path.join(self.resultdir, 'rest')
      if not os.path.exists(export_path):
        os.makedirs(export_path)
      for cluster in self.remaining:
        for graph in cluster.graphs:
          nx.drawing.nx_agraph.write_dot(graph, os.path.join(export_path, 'graph_%03d.dot' % graph.graph['index']))

      raise RuntimeError("There are graphs ramining!")

