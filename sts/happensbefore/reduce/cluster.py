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
    self.iso_comp = iso_comp

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
    if self.iso_comp:
      logger.debug("Cluster isomporphic components")
      clusters = self.cluster_iso_race_parts(clusters)
    else:
      logger.debug("Skip isomporphic components clustering")

    utils.write_clusters_info(clusters)

    utils.export_cluster_graphs(clusters, self.resultdir)

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

  def cluster_iso_race_parts(self, clusters):
    """
    Cluster graphs if parts of the subgraph are isomorphic, but only if the race event is a 'write'

    Args:
      clusters:

    Returns:

    """
    # First split up the connected components of the subgraphs.
    logger.debug("Cluster based on isomorphic components")
    tstart = time.time()
    subgraphs = []
    new_clusters = clusters[:]

    for ind, cluster in enumerate(clusters):
      components = nx.weakly_connected_components(cluster[0])  # Only consider first graph of the cluster

      if len(components) == 1:
        # In this case all nodes are connected
        logger.debug("Only one component in cluster %s" % ind)
        subgraphs.append([cluster[0], None])
      elif len(components) == 2:
        # The two race events are not connected -> generate two new graphs.
        g1 = nx.DiGraph(cluster[0].subgraph(components[0]))
        g2 = nx.DiGraph(cluster[0].subgraph(components[1]))

        if not utils.has_write_event(g1):
          g1 = None
        if not utils.has_write_event(g2):
          g2 = None

        subgraphs.append([g1, g2])
      else:
        # This case should not exist
        raise RuntimeError('cluster_iso_race_parts: More than two components exist.')

    tcomp = time.time()
    logger.debug("Created components in %f s" % (tcomp - tstart))

    # Find isomorphic parts
    # Try to add the smallest clusters to the biggest first
    for i in xrange(len(subgraphs) - 1, 0, -1):
      iso = None
      for k in xrange(0, i):
        assert k < i, "k bigger than i"

        # For all combination of the components
        for g1, g2 in itertools.product(subgraphs[i], subgraphs[k]):
          if g1 and g2 and nx.is_isomorphic(g1, g2, node_match=self.node_match, edge_match=self.edge_match):
            iso = k
            break
        if iso is not None:
          break

      if iso is not None:
        new_clusters[iso].extend(new_clusters[i])
        new_clusters[i] = None

    tiso = time.time()
    logger.debug("Checked all components in %f s" % (tiso - tcomp))

    # remove the empty clusters
    new_clusters = [x for x in new_clusters if x]
    new_clusters.sort(key=len, reverse=True)

    logger.debug("Finished cluster based on isomorphic components in %f s" % (time.time() - tstart))
    logger.debug("Clusters before iso components: %d" % len(clusters))
    logger.debug("Clusters after iso components:  %d" % len(new_clusters))

    return new_clusters


