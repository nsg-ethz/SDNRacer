import logging.config
import time
import sys
import numpy as np
import scipy
import networkx as nx

import utils
import cluster

logger = logging.getLogger(__name__)


class ClusterAlgorithm:
  """
  Agglomerative clustering algorithm.
  """

  def __init__(self,
               resultdir,
               max_clusters=5,
               score_contains_pingpong=1,
               score_return_path=1,
               score_flow_expiry=1,
               score_flooding=1,
               score_num_roots=1,
               score_num_hostsends=1,
               score_num_proactive_race=1,
               linkage='complete',
               epsilon=1):
    self.resultdir = resultdir
    self.max_clusters = int(max_clusters)

    # Create score dictionary for all scores != 0. Form: 'function_name': score
    # The score is the weight of the feature
    self.score_dict = {}
    if float(score_contains_pingpong) != 0:
      self.score_dict['pingpong'] = float(score_contains_pingpong)
    if float(score_return_path) != 0:
      self.score_dict['return_path'] = float(score_return_path)
    if float(score_return_path) != 0:
      self.score_dict['flow_expiry'] = float(score_flow_expiry)
    if float(score_flooding) != 0:
      self.score_dict['flooding'] = float(score_flooding)
    if float(score_num_roots) != 0:
      self.score_dict['num_roots'] = float(score_num_roots)
    if float(score_num_hostsends) != 0:
      self.score_dict['num_hostsends'] = float(score_num_hostsends)
    if float(score_num_proactive_race) != 0:
      self.score_dict['num_proactive'] = float(score_num_proactive_race)
    # ADD FUNCTION AND WEIGHT FOR NEW FEATURES USED IN THE DISTANCE CALCULATION HERE

    # Agglomerative clustering parameters
    self.epsilon = float(epsilon)    # Epsilon is the maximum distance for any two graphs in a cluster
    self.linkage = linkage           # Linkage method

    # Dictionary for the evaluation
    self.eval = {'time': {}}

    # Clusters
    self.clusters = []

  def run(self, clusters):
    """
    Further clusters the initialized clusters with agglomerative clustering.

    Args:
      clusters: Initialized clusters

    Returns: List of final clusters, []

    """
    self.clusters = clusters
    # Calculate distance matrix
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
    fcluster = scipy.cluster.hierarchy.fcluster(linkage_matrix, t=self.epsilon, criterion='distance')

    self.clusters = self.create_new_clusters(fcluster)
    self.eval['time']['Assign new clusters'] = time.clock() - ts

    return self.clusters, []

  def create_new_clusters(self, fclusters):
    """
    Uses the output of fcluster to create the new clusters.
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
      for ind2, g2 in enumerate(self.clusters[:ind1]):
        if ind1 == ind2:
          continue
        mat[ind1, ind2] = self.distance(g1, g2)
        mat[ind2, ind1] = mat[ind1, ind2]

    return mat

  def distance(self, cluster1, cluster2):
    """
    Returns the distance between two clusters. Each feature functions returns a value between 1 and 0,
    then it is multiplied with its weight.
    """
    tot_dist = 0

    # Execute all scoring functions and save score for evaluation
    for f, s in self.score_dict.iteritems():
      dist = getattr(self, f)(cluster1, cluster2) * s
      tot_dist += dist

    return tot_dist

  def pingpong(self, cluster1, cluster2):
    """ Score based on similarity in terms of percentage of graphs which contain a controller-switch-pingpong"""
    return abs(cluster1.properties['pingpong'] - cluster2.properties['pingpong'])

  def return_path(self, cluster1, cluster2):
    """ Score based on similarity in terms of percentage of graphs containing a race on the return path."""
    return abs(cluster1.properties['return'] - cluster2.properties['return'])

  def flow_expiry(self, cluster1, cluster2):
    """ Score based on similarity in terms of percentage of graphs originate from AsyncFlowExpiry events."""
    return abs(cluster1.properties['flowexpiry'] - cluster2.properties['flowexpiry'])

  def flooding(self, cluster1, cluster2):
    """Score based on similarity in terms of percentage of graphs containing flooding."""
    return abs(cluster1.properties['flood'] - cluster2.properties['flood'])

  def num_proactive(self, cluster1, cluster2):
    """Score based on similarity in terms of percentage of graphs containing flooding."""
    if cluster1.properties['num_proactive'] == cluster2.properties['num_proactive']:
      return 0
    else:
      return 1

  def num_roots(self, cluster1, cluster2):
    """Score based on number of root events in the clusters"""
    if cluster1.properties['num_roots'] == cluster2.properties['num_roots']:
      return 0
    else:
      return 1

  def num_hostsends(self, cluster1, cluster2):
    """Score based on number of root events in the clusters"""
    if cluster1.properties['num_hostsends'] == cluster2.properties['num_hostsends']:
      return 0
    else:
      return 1

  # DEFINE FUNCTION FOR NEW FEATURE BASED DISTANCE CALCULATION HERE

