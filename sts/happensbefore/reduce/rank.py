import logging.config
import time
import os
import sys
import random
import numpy as np
import networkx as nx

import utils

logger = logging.getLogger(__name__)


class Group:
  def __init__(self, repre, cluster, pingpong, c_pingpong, nodataplane, single_send, return_path, write_ids):
    """
    Class to store the rank groups (group of subgraphs). Each group has a score, representative graph to show to the user
    and a list of all clusters contained in the group.

    """
    self.repre = repre                    # Representative Graph
    self.clusters = [cluster]             # All clusters
    self.graphs = cluster                 # All Graphs
    self.contains_pingpong = c_pingpong   # Indicates if the graph contains a controller-switch-pingpong
    self.single_send = single_send        # Indicates if the race is caused by a single send
    self.return_path = return_path        # Indicates if there is a HostHandle -> return path is affected
    self.write_ids = write_ids            # Set of all write-ids

  def add_cluster(self, cluster):
    self.clusters.append(cluster)
    self.graphs.extend(cluster)

  def add_group(self, group):
    # Representative graph is the one from the bigger group
    if len(group.graphs) > len(self.graphs):
      self.repre = group.repre

    # Add clusters and graphs from the added group
    self.clusters.extend(group.clusters)
    self.graphs.extend(group.graphs)

    # Add write ids
    self.write_ids.union(group.write_ids)

    # The booleans are true if any of the two groups are true
    self.contains_pingpong = self.contains_pingpong or group.contains_pingpong
    self.single_send = self.single_send or group.single_send
    self.return_path = self.return_path or group.return_path


class Rank:
  """
  Class to rank graphs/clusters and put them in the different rank groups.
  """

  def __init__(self, resultdir, max_groups=5,
               score_same_write=1,
               score_iso_components=1,
               score_contains_pingpong=1,
               score_single_send=1,
               score_return_path=1,
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

    # Maximum score
    self.max_score = sum(self.score_dict.values())

    # DB Scan variables
    self.epsilon = float(epsilon)
    self.min_cluster_size = float(min_cluster_size)

    self.num_groups = 0
    self.groups = []
    self.remaining = []
    self.timing = {}
    self.score_info = {}

    # Dictionary for the evaluation
    self.eval = {'general': {},
                 'score': {},
                 'time': {}}

  def run(self, clusters):
    logger.info("Create groups")
    # create groups out of all clusters
    tstart = time.clock()
    for cluster in clusters:
      r = cluster[0]
      pingpong = None  # utils.substitute_pingpong(r)
      c_pingpong = utils.contains_pingpong(r)
      nodataplane = None  # utils.remove_dataplanetraversals(r)
      single_send = utils.is_caused_by_single_send(r)
      return_path = utils.has_return_path(r)
      write_ids = utils.get_write_events(cluster)
      self.groups.append(Group(r, cluster, pingpong, c_pingpong, nodataplane, single_send, return_path, write_ids))
    self.eval['time']['Cluster to groups'] = time.clock() - tstart

    # Clustering
    tstart = time.clock()
    self.groups = self.cluster()
    self.eval['time']['Total Ranking'] = time.clock() - tstart

  def cluster(self):
    """ Clustering with DBScan"""
    tstart = time.clock()
    # First get the closeness matrix
    logger.info("Calculate distance matrix")
    # calculate closeness matrix
    dist_mat = self.get_distance_matrix()
    self.eval['time']['Calculate distance matrix'] = time.clock() - tstart

    # DBScan
    tstart = time.clock()
    visited = []
    outliers = []
    clusters = []
    in_cluster = []

    # Process all elements (indices in group list and distance matrix)
    for element in range(0, len(self.groups)):
      if element in visited:
        continue

      visited.append(element)
      neighbors = self.get_neighbors(element, self.epsilon, dist_mat)
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
          n_neighbors = self.get_neighbors(neighbor, self.epsilon, dist_mat)
          if len(neighbors) >= self.min_cluster_size:
            neighbors.extend(n_neighbors)

      clusters.append(cluster)

    self.eval['time']['DBScan'] = time.clock() - tstart

    # Different validation checks
    tstart = time.clock()
    # Check if all elements are visited exactly once
    assert len(visited) == len(set(visited)), "DBScan: Dublicates in visited."
    assert set(visited) == set(range(0, len(self.groups))), "DBScan: Not all elements in visited"

    # Check if in_cluster is complete and there is no element in more than one cluster
    complete_in_clusters = []
    for c in clusters:
      complete_in_clusters.extend(c)
    assert len(complete_in_clusters) == len(set(complete_in_clusters)), "DBScan: Same element in more than one cluster"
    assert set(in_cluster) == set(complete_in_clusters), "DBScan: in_cluster not complete"

    # Check if there are dublicate elements in outliers
    assert len(outliers) == len(set(outliers)), "DBScan: Dublicates in outliers"

    # Check if each element is either in a cluster or in outliers
    all_elements = set(in_cluster + outliers)
    assert all_elements == set(visited), "DBScan: Not all elements processed"

    self.eval['time']['DBScan Checks'] = time.clock() - tstart

    # Create the new groups
    tstart = time.clock()
    new_groups = []
    for cluster in clusters:
      curr_group = self.groups[cluster[0]]
      for group in cluster[1:]:
        curr_group.add_group(self.groups[group])

      new_groups.append(curr_group)

    # Put outliers in remaining
    for group in outliers:
      self.remaining.append(self.groups[group].clusters)

    return new_groups

  def get_neighbors(self, p, eps, dist_mat):
    """
    Returns all points around p within max distance of eps (including p)
    """
    neighbors = []
    for ind, x in enumerate(dist_mat[p]):
      if x <= eps:
        neighbors.append(ind)

    return neighbors

  def get_distance_matrix(self):
    mat = np.zeros((len(self.groups), len(self.groups)))
    for ind1, g1 in enumerate(self.groups):
      for ind2, g2 in enumerate(self.groups[0:(ind1 + 1)]):
        if g1 == g2:
          mat[ind1, ind2] = 0
        mat[ind1, ind2] = self.distance(g1, g2)
        mat[ind2, ind1] = mat[ind1, ind2]

    return mat

  def distance(self, group1, group2):
    """
    Returns the distance between two graphs.
    """
    tot_score = 0

    # Execute all scoring functions and save score for evaluation
    for f, score in self.score_dict.iteritems():
      if getattr(self, f)(group1, group2):
        tot_score += score
        self.eval['score'][f] = score
      else:
        self.eval['score'][f] = 0

    # Invert score (closeness to distance)
    return self.max_groups - tot_score

  def iso_components(self, group1, group2):
    """
    Returns True if one or more components (separate branches) of the representative graphs of the two groups are
    isomorphic.
    """
    return utils.iso_components(group1.repre, group2.repre)

  def common_write_event(self, group1, group2):
    """
    Returns True if the two groups have write race-event ids in common.
    """
    # Check if the sets are not empty
    if not len(group1.write_ids) > 0 or not len(group2.write_ids) > 0:
      # Should not happen, export graphs and raise error
      nx.drawing.nx_agraph.write_dot(group1.repre, os.path.join(self.resultdir, 'error_group1.dot'))
      nx.drawing.nx_agraph.write_dot(group2.repre, os.path.join(self.resultdir, 'error_group2.dot'))
      raise RuntimeError("One ore more groups contain no write ids! See exported graphs.")

    # Give score if they have at least one common element
    return not group1.write_ids.isdisjoint(group2.write_ids)

  def pingpong(self, group1, group2):
    """ Returns True if both graphs contain a controller-switch-pingpong or both don't"""
    return group1.contains_pingpong == group2.contains_pingpong

  def single_send(self, group1, group2):
    """
    Returns True if both, the representative graph of the current group and the graphs in the cluster, are
    caused by a single send event or both aren't.
    """
    return group1.single_send == group2.single_send

  def return_path(self, group1, group2):
    """
    Returns True if both, the representative graph of the current group and the graphs in the clusters, either contain a
    return path or both don't.
    """
    return group1.return_path == group2.return_path

  def export_groups(self):
    """ Exports the representative graphs in the result directory and creats a folder for each group
    to export all informative graphs in the group."""
    for ind, group in enumerate(self.groups):
      # Export representative graph
      nx.drawing.nx_agraph.write_dot(group.repre, os.path.join(self.resultdir, 'repre_%03d.dot' % ind))
      # Create folder for the other graphs
      export_path = os.path.join(self.resultdir, 'group_%03d' % ind)
      if not os.path.exists(export_path):
        os.makedirs(export_path)
      for c_ind, cluster in enumerate(group.clusters):
        nx.drawing.nx_agraph.write_dot(cluster[0], os.path.join(export_path, 'iso_%03d.dot' % c_ind))

    # Export outliers (remaining)
    export_path = os.path.join(self.resultdir, 'rest')
    if not os.path.exists(export_path):
      os.makedirs(export_path)
    for ind, cluster in enumerate(self.remaining):
      nx.drawing.nx_agraph.write_dot(cluster[0], os.path.join(export_path, 'iso_%03d.dot' % ind))

  def print_timing(self):
    """ Logs the timing information."""
    logger.info("Timing:")

    for k, v in self.eval['time'].iteritems():
      logger.info("\t%s: %f s" % (k, v))

  def print_summary(self):
    """ Prints the group summary"""

    # Calculate number of remaining graphs
    num_graphs = sum([len(x) for x in self.remaining])

    # log summary
    logger.info("Summary:")
    for ind, g in enumerate(self.groups):
      logger.info("\tGroup %3d: %4d Clusters, %5d Graphs" % (ind, len(g.clusters), len(g.graphs)))
    logger.info("\tRemaining:  %4d Clusters, %5d Graphs" % (len(self.remaining), num_graphs))

