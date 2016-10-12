"""
Old version of cluster_algorithm.py with implemented dbscan algorithm.

Not used anymore.
"""


import logging.config
import time
import numpy as np

import utils
import cluster

logger = logging.getLogger(__name__)


class ClusterAlgorithm:
  """
  Class to rank graphs/clusters and put them in the different rank groups.
  """

  def __init__(self,
               resultdir,
               max_groups=5,
               score_same_write=1,
               score_iso_components=1,
               score_contains_pingpong=1,
               score_single_send=1,
               score_return_path=1,
               score_flow_expiry=1,
               score_multi_send=1,
               epsilon=1,
               min_cluster_size=2):
    self.resultdir = resultdir
    self.max_groups = int(max_groups)

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
    self.min_cluster_size = float(min_cluster_size)

    # Dictionary for the evaluation
    self.eval = {'score': {},
                 'time': {}}

    # Clusters
    self.clusters = []
    self.remaining = []

  def run(self, clusters):
    self.clusters = clusters
    # Calculate closeness between all graphs
    tstart = time.clock()
    logger.debug("Calculate closeness matrix")
    closeness = self.get_closeness_matrix()
    self.eval['time']['Calculate distance matrix'] = time.clock() - tstart

    # Rund dbscan
    tstart = time.clock()
    logger.debug("Run DBScan algorithm")
    cluster_ind, outliers = self.db_scan(closeness)
    self.eval['time']['Run DBScan Algorithm'] = time.clock() - tstart

    # Create the new cluster list
    tstart = time.clock()
    logger.debug("Create new clusters")
    self.clusters, self.remaining = self.create_new_clusters(cluster_ind, outliers)
    self.eval['time']['Create new clusters'] = time.clock() - tstart

    self.eval['time']['Total'] = time.clock() - tstart

    return self.clusters, self.remaining

  def db_scan(self, closeness):
    """
    Clustering with the dbscan algorithm.
    Args:
      closeness: Closeness Matrix

    Returns:
      cluster_ind: List of the new clusters, (elements are indices of the current clusters in self.clusters)
      outliers:     List of the outliers, which are not part of a cluster (elements are indices of the current clusters)

    """
    # DBScan
    visited = []
    outliers = []
    cluster_ind = []
    in_cluster = []

    # Process all elements (indices in group list and distance matrix)
    for element in range(0, len(self.clusters)):
      if element in visited:
        continue

      visited.append(element)
      neighbors = self.get_neighbors(element, closeness)
      # If less then min_points in neighborhood -> outlier
      if len(neighbors) < self.min_cluster_size:
        outliers.append(element)
        continue

      # Element is a core point -> new cluster
      cluster = [element]
      in_cluster.append(element)

      # Add all points in the expanded neighborhood to this cluster
      while neighbors:
        neighbor = neighbors.pop()
        # If this point is not part of any cluster add it
        if neighbor not in in_cluster:
          cluster.append(neighbor)
          in_cluster.append(neighbor)

        # If the neighbor was not visited, check the neighborhood, if its a core point -> add its neighbors
        if neighbor not in visited:
          visited.append(neighbor)
          n_neighbors = self.get_neighbors(neighbor, closeness)
          if len(neighbors) >= self.min_cluster_size:
            neighbors.extend(n_neighbors)

      cluster_ind.append(cluster)

    # Different validation checks
    tstart = time.clock()
    # Check if all elements are visited exactly once
    assert len(visited) == len(set(visited)), "DBScan: Dublicates in visited."
    assert set(visited) == set(range(0, len(self.clusters))), "DBScan: Not all elements in visited"

    # Check if in_cluster is complete and there is no element in more than one cluster
    complete_in_clusters = []
    for c in cluster_ind:
      complete_in_clusters.extend(c)
    assert len(complete_in_clusters) == len(set(complete_in_clusters)), "DBScan: Same element in more than one cluster"
    assert set(in_cluster) == set(complete_in_clusters), "DBScan: in_cluster not complete"

    # Check if there are dublicate elements in outliers
    assert len(outliers) == len(set(outliers)), "DBScan: Dublicates in outliers"

    # Check if each element is either in a cluster or in outliers
    all_elements = set(in_cluster + outliers)
    assert all_elements == set(visited), "DBScan: Not all elements processed"
    self.eval['time']['DBScan Checks'] = time.clock() - tstart

    return cluster_ind, outliers

  def create_new_clusters(self, cluster_ind, outliers):
    """
    Creates a new list of clusters out of a list of clusters where each element is an index of a current cluster.
    Puts the outliers in a separate list.
    Args:
      cluster_ind: List of clusters, where each cluster element is an index in the current list
      outliers:    List of outliers, where each element is an index in the current list

    Returns:
      new_cluster: List of the new clusters (not indices anymore)
      remaining: List of the remaining cluster, which where not added to a group

    """
    new_clusters = []
    remaining = []
    for clust in cluster_ind:
      curr_cluster = cluster.Cluster()
      for c in clust:
        curr_cluster.add_graphs(self.clusters[c].graphs)

      # Update Properties and write_ids
      curr_cluster.update()
      new_clusters.append(curr_cluster)

    # Put outliers in remaining
    for c in outliers:
      remaining.append(self.clusters[c])

    return new_clusters, remaining

  def get_neighbors(self, p, closeness):
    """
    Returns all points around p within max distance of eps (including p)
    """
    neighbors = []
    for ind, x in enumerate(closeness[p]):
      if x >= self.epsilon:
        neighbors.append(ind)

    return neighbors

  def get_closeness_matrix(self):
    mat = np.zeros((len(self.clusters), len(self.clusters)))
    for ind1, g1 in enumerate(self.clusters):
      for ind2, g2 in enumerate(self.clusters[0:(ind1 + 1)]):
        if g1 == g2:
          mat[ind1, ind2] = 0
        mat[ind1, ind2] = self.closeness(g1, g2)
        mat[ind2, ind1] = mat[ind1, ind2]

    return mat

  def closeness(self, cluster1, cluster2):
    """
    Returns the closenes (grade of relation) between two graphs.
    """
    tot_score = 0

    # Execute all scoring functions and save score for evaluation
    for f, s in self.score_dict.iteritems():
      score = getattr(self, f)(cluster1, cluster2) * s
      tot_score += score

    # Invert score (closeness to distance)
    return tot_score

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
