import logging.config
import time
import itertools
import networkx as nx

import utils
import hb_events
import hb_sts_events

logger = logging.getLogger(__name__)


class Cluster:
  # functions to cluster subgraphs

  def __init__(self, resultdir, iso=True, iso_comp=True):
    self.resultdir = resultdir
    self.iso = iso.lower() not in ['false', '0']  # convert from string 'false' or '0' to bool

  def run(self, subgraphs):
    # List of clusters, Each entry is a list of subgraphs in this cluster
    clusters = [[x] for x in subgraphs]

    # Call Cluster Functions
    if self.iso:
      logger.debug("Cluster Isomorphic graphs")
      clusters = self.cluster_iso(clusters)
    else:
      logger.debug("Skip Isomorphic clustering")

    utils.write_clusters_info(clusters)
    utils.export_cluster_graphs(clusters, self.resultdir, 'iso_cluster')

    return clusters

  def cluster_iso(self, clusters):
    """
    Clusters based on isomorphism. Only takes first subgraph in each cluster into account.

    Args:
      clusters: list of clusters

    Returns: New list of clusters

    """
    tstart = time.time()
    new_clusters = []

    # cluster isomorphic clusters based on the first subgraph in the cluster
    for cluster in clusters:
      curr = cluster[0]
      addgraph = True
      for new in new_clusters:
        if nx.is_isomorphic(curr, new[0], node_match=self.node_match, edge_match=self.edge_match):
          new.append(curr)
          addgraph = False
          break

      if addgraph:
        new_clusters.append([curr])

    # Sort clusters based on their size, the lower the cluster ind, the more graphs are in the cluster.
    new_clusters.sort(key=len, reverse=True)

    # Log info
    logger.info("Timing Iso: %f" % (time.time() - tstart))
    logger.info("Clusters before iso: %d" % (len(clusters)))
    logger.info("Clusters after iso:  %d" % (len(new_clusters)))

    return new_clusters

  def node_match(self, n1, n2):
    # Helperfunction for "cluster_iso"
    # it returns True if two nodes have the same event type
    return type(n1['event']) == type(n2['event'])

  def edge_match(self, e1, e2):
    # Helperfunction for "cluster_iso"
    # it returns True if two edges have the same relation
    return e1['rel'] == e2['rel']



