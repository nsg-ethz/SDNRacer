import logging.config
import time
import sys
import numpy as np
import scipy

import utils
import cluster

logger = logging.getLogger(__name__)


class ClusterAlgorithm:
  """
  Class to rank graphs/clusters and put them in the different rank groups.
  """

  def __init__(self,
               resultdir,
               max_clusters=5,
               score_same_write=1,
               score_iso_components=1,
               score_contains_pingpong=1,
               score_single_send=1,
               score_return_path=1,
               score_flow_expiry=1,
               score_multi_send=1,
               linkage='complete',
               epsilon=1):
    self.resultdir = resultdir
    self.max_clusters = int(max_clusters)

    # Create score dictionary for all scores != 0. Form: 'function_name': score
    self.score_dict = {}
    if float(score_iso_components) != 0:
      self.score_dict['iso_components'] = float(score_iso_components)
    if float(score_same_write) != 0:
      self.score_dict['common_write_event'] = float(score_same_write)
    if float(score_contains_pingpong) != 0:
      self.score_dict['pingpong'] = float(score_contains_pingpong)
    if float(score_single_send) != 0:
      self.score_dict['single_send'] = float(score_single_send)
    if float(score_return_path) != 0:
      self.score_dict['return_path'] = float(score_return_path)
    if float(score_return_path) != 0:
      self.score_dict['flow_expiry'] = float(score_flow_expiry)
    if float(score_return_path) != 0:
      self.score_dict['multi_send'] = float(score_multi_send)

    # Maximum score
    self.max_score = sum(self.score_dict.values())

    # DB Scan variables
    self.epsilon = float(epsilon)
    self.linkage = linkage

    # Dictionary for the evaluation
    self.eval = {'score': {},
                 'time': {}}
    for f in self.score_dict.keys():
      self.eval['score'][f] = []

    # Clusters
    self.clusters = []
    self.remaining = []

  def run(self, clusters):
    self.clusters = clusters
    # Calculate closeness between all graphs
    ts = time.clock()
    logger.debug("Calculate distance matrix")
    distance = scipy.spatial.distance.squareform(self.distance_matrix())
    self.eval['time']['Calculate distance matrix'] = time.clock() - ts

    ts = time.clock()
    logger.debug("Calculate clustering")
    linkage_matrix = scipy.cluster.hierarchy.linkage(distance, method=self.linkage)
    self.eval['time']['Calculate clustering'] = time.clock() - ts

    ts = time.clock()
    logger.debug("Assign new clusters")

    # If there is the max distance given in the config cluster first with distance criterion
    if self.epsilon > 0:
      fcluster = scipy.cluster.hierarchy.fcluster(linkage_matrix, t=self.epsilon, criterion='distance')
      # If there is a maximum number of clusters in the config or the number of cluster after
      if max(fcluster) > self.max_clusters > 0:
        logger.info("To much clusters after distance based clustering -> use max_clusters instead.")
        fcluster = scipy.cluster.hierarchy.fcluster(linkage_matrix, t=self.max_clusters, criterion='maxclust')
    elif self.max_clusters > 0:
      fcluster = scipy.cluster.hierarchy.fcluster(linkage_matrix, t=self.max_clusters, criterion='maxclust')
    else:
      raise RuntimeError("Neither max distance (epsilon) nor max number of clusters (max_clusters) given.")

    self.clusters = self.create_new_clusters(fcluster)
    self.eval['time']['Assign new clusters'] = time.clock() - ts

    return self.clusters, self.remaining

  def create_new_clusters(self, fclusters):
    """
    Assigns the current clusters to the new clusters returnd by the fcluster function.
    """
    new_clusters = [None] * max(fclusters)

    # Generate all new clusters and assign the graphs of the current clusters to them
    for ind, clu in enumerate(fclusters):
      if new_clusters[clu - 1] is None:
        new_clusters[clu - 1] = cluster.Cluster()
      new_clusters[clu - 1].add_graphs(self.clusters[ind].graphs)

    # Update all properties
    for c in new_clusters:
      c.update()

    return new_clusters

  def distance_matrix(self):
    """
    Calculates and returns distance matrix, where element mat[i][k] represents the distance between cluster i and k.
    """
    mat = np.zeros((len(self.clusters), len(self.clusters)))
    for ind1, g1 in enumerate(self.clusters):
      for ind2, g2 in enumerate(self.clusters[0:(ind1 + 1)]):
        if g1 == g2:
          mat[ind1, ind2] = 0
        mat[ind1, ind2] = self.distance(g1, g2)
        mat[ind2, ind1] = mat[ind1, ind2]

    return mat

  def distance(self, cluster1, cluster2):
    """
    Returns the distance between two clusters.
    """
    tot_score = 0

    # Execute all scoring functions and save score for evaluation
    for f, s in self.score_dict.iteritems():
      score = getattr(self, f)(cluster1, cluster2) * s
      tot_score += score
      self.eval['score'][f].append(score)

    # Invert score (closeness to distance)
    return self.max_score - tot_score

  def iso_components(self, cluster1, cluster2):
    """
    Score based on isomorphism of isomorphic connected parts of the graphs.
    """
    assert cluster1.representative is not None, 'Representative is None'
    assert cluster2.representative is not None, 'Representative is None'
    return 1 if utils.iso_components(cluster1.representative, cluster2.representative) else 0

  def common_write_event(self, cluster1, cluster2):
    """
    Score based on percentage of graphs of the smaller group which have a write id in common with graphs of
    the bigger group.
    """
    if len(cluster1.graphs) >= len(cluster2.graphs):
      write_ids = cluster1.write_ids
      graphs = cluster2.graphs
    else:
      write_ids = cluster2.write_ids
      graphs = cluster1.graphs

    # Common write events
    common = 0
    # count each graph that has a write_race_id in common with another one
    for graph in graphs:
      for w_id in graph.graph['write_ids']:
        if w_id in write_ids:
          common += 1
          # Cont each graph only once! -> break
          break

    return common / len(graphs)

  def pingpong(self, cluster1, cluster2):
    """ Score based on similarity in terms of percentage of graphs which contain a controller-switch-pingpong"""
    return 1 - abs(cluster1.properties['pingpong'] - cluster2.properties['pingpong'])

  def single_send(self, cluster1, cluster2):
    """ Score based on similarity in terms of percentage of graphs origin from a single event. """
    return 1 - abs(cluster1.properties['single'] - cluster2.properties['single'])

  def return_path(self, cluster1, cluster2):
    """ Score based on similarity in terms of percentage of graphs containing a race on the return path."""
    return 1 - abs(cluster1.properties['return'] - cluster2.properties['return'])

  def flow_expiry(self, cluster1, cluster2):
    """ Score based on similarity in terms of percentage of graphs originate from AsyncFlowExpiry events."""
    return 1 - abs(cluster1.properties['flowexpiry'] - cluster2.properties['flowexpiry'])

  def multi_send(self, cluster1, cluster2):
    """ Score based on similarity in terms of percentage of graphs origin from more than two events."""
    return 1 - abs(cluster1.properties['multi'] - cluster2.properties['multi'])


