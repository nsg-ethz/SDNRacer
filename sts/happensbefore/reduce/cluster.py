import logging.config
import os
import time
import sys
import networkx as nx

logging.config.fileConfig(os.path.dirname(__file__) + '/logging.conf', disable_existing_loggers=False)
logger = logging.getLogger(__name__)


class Cluster:
  # functions to cluster subgraphs

  def __init__(self, resultdir, no_iso=False):
    self.resultdir = resultdir
    self.no_iso = no_iso.lower() not in ['false', '0']  # convert from string 'false' or '0' to bool

  def run(self, subgraphs):
    # List of clusters, Each entry is a list of subgraphs in this cluster
    clusters = [[x] for x in subgraphs]

    # Call Cluster Functions
    if not self.no_iso:
      logger.debug("Cluster Iphomorphic graphs")
      clusters = self.cluster_iso(clusters)
    else:
      logger.debug("Skip Isomorphic clustering")
    return clusters

  def cluster_iso(self, clusters):
    '''
    Clusters based on isomorphism. Only takes first subgraph in each cluster into account.

    Args:
      clusters: list of clusters

    Returns: New list of clusters

    '''
    tstart = time.time()
    new_clusters = []

    # cluster isomorphic clusters based on the first subgraph in the cluster
    for cluster in clusters:
      curr = cluster[0]
      addgraph = True
      for new in new_clusters:
        if nx.is_isomorphic(curr, new[0], node_match=self.node_match):
          new.append(curr)
          addgraph = False
          break

      if addgraph:
        new_clusters.append([curr])

    # Sort clusters based on their size, the lower the cluster ind, the more graphs are in the cluster.
    new_clusters.sort(key=len, reverse=True)

    # Export a graph of each cluster and "overview" of clusters (one graph of each cluster)
    overview = []
    for ind, cluster in enumerate(new_clusters):
      export_path = os.path.join(self.resultdir, "iso_cluster_%03d.dot" % ind)
      nx.write_dot(cluster[0], export_path)
      overview.append(cluster[0])

    export_path = os.path.join(self.resultdir, "iso_clusters_overview.dot")
    nx.write_dot(nx.disjoint_union_all(overview), export_path)

    # Log infos
    logger.info("Timing Iso: %f" % (time.time() - tstart))
    logger.info("Clusters before iso: %d" % (len(clusters)))
    logger.info("Clusters after iso:  %d" % (len(new_clusters)))

    curr_size = sys.maxint
    start_ind = 0
    for ind, cluster in enumerate(new_clusters):
      if len(cluster) < curr_size:
        if not ind == 0:
          logger.debug("\tCluster %5d - %5d: %5d graphs each" % (start_ind, ind - 1, curr_size))
        curr_size = len(cluster)
        start_ind = ind


    logger.debug("\tCluster %5d - %5d: %5d graphs each" % (start_ind, ind, len(cluster)))

    return new_clusters

  def node_match(self, n1, n2):
    # Helperfunction for "cluster_iso"
    # it returns True if two nodes have the same event type
    return type(n1['event']) == type(n2['event'])
