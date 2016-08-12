import logging.config
import time
import os
import sys
import networkx as nx

logger = logging.getLogger(__name__)


class Cluster:
  # functions to cluster subgraphs

  def __init__(self, resultdir, iso=True):
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

    self.write_clusters_info(clusters)
    #self.export_cluster_graphs(clusters, 'iso_cluster')

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

  def export_cluster_graphs(self, clusters, prefix='cluster', export_overview=False):
    """
    Export the first graph of each cluster as .dot file.
    Args:
      clusters:   List of clusters
      prefix:     Prefix of the exportet file names (default='cluster')
      export_overview:   Boolean which indicates if an overview should be exportet as well, attention: SLOW (default=False)

    """
    # Export a graph of each cluster and "overview" of clusters (one graph of each cluster)
    overview = []
    for ind, cluster in enumerate(clusters):
      export_path = os.path.join(self.resultdir, "%s_%03d.dot" % (prefix, ind))
      nx.write_dot(cluster[0], export_path)
      overview.append(cluster[0])

    # Export overview of all clusters
    if export_overview:
      export_path = os.path.join(self.resultdir, "%s_clusters_overview.dot" % prefix)
      nx.write_dot(nx.disjoint_union_all(overview), export_path)

  def write_clusters_info(self, clusters, indent=True):
    """
    Writes the size of each cluster to the log (grouped by size).
    Args:
      clusters: List of clusters
      indent:   Boolean, indicates if the entries should be indented by a tab.
    """
    # First write the number of subgraphs and the number of clusters
    num_cluster = len(clusters)
    num_subgraphs = sum([len(x) for x in clusters])
    logger.debug("Total Clusters: %d, Total Subgraphs: %d" % (num_cluster, num_subgraphs))
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

    logger.debug("%sCluster %5d - %5d: %5d graphs each" % (indent, start_ind, len(clusters) - 1, len(clusters[-1])))

