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
  def __init__(self, repre, cluster, pingpong, nodataplane, single_send, return_path, write_ids):
    """
    Class to store the rank groups (group of subgraphs). Each group has a score, representative graph to show to the user
    and a list of all clusters contained in the group.

    """
    self.repre = repre                    # Representative Graph
    self.clusters = [cluster]             # All clusters
    self.graphs = cluster                 # All Graphs
    self.repre_pingpong = pingpong        # Graph w/o controller-switch-pingpong (substituted node)
    self.repre_nodataplane = nodataplane  # Representative graph without dataplane traversal
    self.single_send = single_send        # Indicates if the race is caused by a single send
    self.return_path = return_path        # Indicates if there is a HostHandle -> return path is affected
    self.write_ids = write_ids            # Set of all write-ids

  def add_cluster(self, cluster):
    self.clusters.append(cluster)
    self.graphs.extend(cluster)

  def add_group(self, group):
    self.clusters.extend(group.clusters)
    self.graphs.extend(group.graphs)
    self.write_ids.union(group.write_ids)


class Rank:
  """
  Class to rank graphs/clusters and put them in the different rank groups.
  """

  def __init__(self, resultdir, max_groups=5,
               score_same_write=1,
               score_iso_branch=1,
               score_iso_nodataplane=1,
               score_iso_pingpong=1,
               score_single_send=1,
               score_return_path=1,
               min_score=1,
               threshold=1):
    self.resultdir = resultdir
    self.max_groups = int(max_groups)
    self.score_iso_branch = float(score_iso_branch)
    self.score_same_write = float(score_same_write)
    self.score_iso_nodataplane = float(score_iso_nodataplane)
    self.score_iso_pingpong = float(score_iso_pingpong)
    self.score_single_send = float(score_single_send)
    self.score_return_path = float(score_return_path)
    self.min_score = float(min_score)
    self.threshold = float(threshold)
    self.num_groups = 0
    self.groups = []
    self.remaining = []
    self.timing = {}
    self.score_info = {}
    self.eval = {}

  def run(self, clusters):
    logger.info("Create groups")
    # create groups out of all clusters
    tstart = time.time()
    for cluster in clusters:
      r = cluster[0]
      pingpong = utils.substitute_pingpong(r)
      nodataplane = utils.remove_dataplanetraversals(r)
      single_send = utils.is_caused_by_single_send(r)
      return_path = utils.has_return_path(r)
      write_ids = utils.get_write_events(cluster)
      self.groups.append(Group(r, cluster, pingpong, nodataplane, single_send, return_path, write_ids))
    tgroup = time.time()

    # Calculate closeness
    logger.info("Calculate closeness matrix")
    # calculate closeness matrix
    mat = self.get_closeness_matrix()
    tmatrix = time.time()

    # Partitioning Around Medoids (PAM)
    medoids, clu, remaining, pam_iter = self.pam(mat)
    tmedoids = time.time()

    # Put groups together
    new_groups = []
    for c_ind, c in enumerate(clu):
      new_group = self.groups[c[0]]
      for ind in c[1:]:
        new_group.add_group(self.groups[ind])
      new_groups.append(new_group)
    tassign = time.time()

    self.groups = new_groups

    # Prepare timing dict
    self.timing['Cluster to groups'] = tgroup - tstart
    self.timing['Closeness Matrix'] = tmatrix - tgroup
    self.timing['PAM algorithm'] = tmedoids - tmatrix
    self.timing['Assign to clusters'] = tassign - tmedoids

    # Prepare eval dict
    self.eval['num_groups'] = self.num_groups
    self.eval['score_iso'] = self.score_iso_branch
    self.eval['score_write'] = self.score_same_write
    self.eval['score_nodataplane'] = self.score_iso_nodataplane
    self.eval['score_pingpong'] = self.score_iso_pingpong
    self.eval['score_single'] = self.score_single_send
    self.eval['score_return'] = self.score_return_path

  def pam(self, mat):
    """ Implementation of the Partitioning Around Medoids (k-medoids) clustering method."""

    # Initialization
    medoids = self.init_medoids()
    old_medoids = None
    num_iter = 0

    # algorithm
    while medoids != old_medoids:
      logger.debug("Iteration %d, Medoids: %s" % (num_iter, medoids))
      num_iter += 1
      old_medoids = medoids[:]
      clusters = [[x] for x in medoids]
      remaining = []

      # add all element to the next medoid cluster
      for ind in xrange(0, len(self.groups)):
        if ind in medoids:
          continue

        # Choose closest cluster (highest score in matrix)
        max_score = 0
        clust = None
        for cluster_ind, med in enumerate(medoids):
          if mat[ind, med] > max_score:
            max_score = mat[ind, med]
            clust = cluster_ind

        if clust is None:
          remaining.append(ind)
        else:
          clusters[clust].append(ind)

      # recalculate the cluster medoids (maximize sum of distance)
      for ind, cluster in enumerate(clusters):
        max_score = 0
        new_med = -1
        for med in cluster:
          score = sum([mat[med, x] for x in xrange(0, len(self.groups)) if x in cluster])
          if score > max_score:
            max_score = score
            new_med = med
        medoids[ind] = new_med

    return medoids, clusters, remaining, num_iter

  def init_medoids(self, method='random'):
    """
    Initialize the medoids with the choosen method

    Supported methods:
      'random': Return random medoids."""

    if method.lower() == 'random':
      if len(self.groups) < self.max_groups:
        # Todo: stop here, return clusters
        return xrange(0, len(self.groups))
      else:
        return random.sample(xrange(0, len(self.groups)), self.max_groups)
    else:
      raise RuntimeError("Invalid method for medoid initialization: %s" % method)

  def get_closeness_matrix(self):
    mat = np.zeros((len(self.groups), len(self.groups)))
    for ind1, g1 in enumerate(self.groups):
      for ind2, g2 in enumerate(self.groups[0:(ind1 + 1)]):
        if g1 == g2:
          mat[ind1, ind2] = None
        mat[ind1, ind2] = self.closeness(g1, g2)
        mat[ind2, ind1] = self.closeness(g1, g2)

    return mat

  def closeness(self, group1, group2):
    """
    Returns the distance between two points.
    """
    tot_score = 0
    # Isomorphic parts
    score = self.get_score_iso_components(group1, group2)
    tot_score += score
    if 'iso' not in self.eval:
      self.eval['iso'] = []
    self.eval['iso'].append(score)

    # Same write event
    score = self.get_score_same_write_event(group1, group2)
    tot_score += score
    if 'write' not in self.eval:
      self.eval['write'] = []
    self.eval['write'].append(score)

    # Caused by single send
    score = self.get_score_single_send(group1, group2)
    tot_score += score
    if 'single' not in self.eval:
      self.eval['single'] = []
    self.eval['single'].append(score)

    # Isomorphic without dataplane traversal
    score = self.get_score_iso_no_dataplane(group1, group2)
    tot_score += score
    if 'dataplane' not in self.eval:
      self.eval['dataplane'] = []
    self.eval['dataplane'].append(score)

    # Isomorphic with reduced controller switch pingpong
    score = self.get_socre_iso_pingpong(group1, group2)
    tot_score += score
    if 'pingpong' not in self.eval:
      self.eval['pingpong'] = []
    self.eval['pingpong'].append(score)

    # Return path affected
    score = self.get_score_return_path(group1, group2)
    if 'return' not in self.eval:
      self.eval['return'] = []
    self.eval['return'].append(score)

    if 'total' not in self.eval:
      self.eval['total'] = []
    self.eval['total'].append(tot_score)

    return tot_score

  def old_run(self, clusters):
    logger.info("Start Ranking")
    tstart = time.time()
    # Generate Groups
    # cluster list to store all scores and to which group they are assignes
    # Form: {'cluster': list_of_graphs, 'group': group_number, 'scores': [score_group_1, score_group_2, ...]}
    clusters.sort(key=len, reverse=True)
    cluster_scores = []
    for c in clusters:
      cluster_dict = {'cluster': c,
                      'pingpong': utils.substitute_pingpong(c[0]),
                      'nodataplane': utils.remove_dataplanetraversals(c[0]),
                      'group': None,
                      'scores': []}
      cluster_scores.append(cluster_dict)

    tdict = time.time()

    # First generate self.max_groups groups
    # Approach:
    #   - Put the first cluster (biggest) in the first group
    #   - Calculate score of all other clusters for this group
    #   - Put biggest cluster with smallest score in new group
    #   - Repeat until all groups are created
    #   Note: in repetive steps, use biggest cluster with lowest score for all groups
    logger.info("Generate Groups")
    cluster_ind = 0

    while len(self.groups) < self.max_groups and cluster_ind is not None:
      logger.debug("Generate group %d" % len(self.groups))

      # Generate next group
      c = cluster_scores[cluster_ind]['cluster']
      r = c[0]
      pingpong = utils.substitute_pingpong(r)
      nodataplane = utils.remove_dataplanetraversals(r)
      single_send = utils.is_caused_by_single_send(r)
      return_path = utils.has_return_path(r)
      write_ids = utils.get_write_events(c)
      self.groups.append(Group(r, c, pingpong, nodataplane, single_send, return_path, write_ids))

      # prepare next step
      cur_group = len(self.groups) - 1
      cluster_scores[cluster_ind]['group'] = cur_group

      # Calculate the score for all other clusters
      for cluster_ind, cluster_dict in enumerate(cluster_scores):
        # Only continue if the current cluster is not assigned yet
        if cluster_dict['group'] is None:
          score = self.calculate_score(self.groups[cur_group],
                                       cluster_dict['cluster'],
                                       cluster_dict['pingpong'],
                                       cluster_dict['nodataplane'],
                                       cur_group, cluster_ind)
          cluster_dict['scores'].append(score)

      # Get biggest cluster with lowest overall score
      min_score = sys.maxint
      cluster_ind = None
      for ind, cluster_dict in enumerate(cluster_scores):
        # Only consider unassigned clusters
        if cluster_dict['group'] is not None:
          continue

        # Check if there is a higher score than threshold -> continue with next
        if max(cluster_dict['scores']) > self.threshold:
          continue

        # Get score, Ignore scores for groups which are not calculated yet
        score = sum(cluster_dict['scores'])

        # Clusters are ordered in size, so the first graph with the smallest score is always the biggest
        if score == 0:
          cluster_ind = ind
          break

        elif score < min_score:
          min_score = score
          cluster_ind = ind

    tgroup = time.time()
    logger.info("Assign clusters to groups")

    # Now calculate the score for all clusters and groups
    num_graphs = 0
    for cluster_ind, cluster_dict in enumerate(cluster_scores):
      # Only calculate score if not already assigned
      if cluster_dict['group'] is None:
        for group_ind in range(0, len(self.groups)):
          if len(cluster_dict['scores']) <= ind:
            cluster_dict['scores'].append(self.calculate_score(self.groups[group_ind],
                                                               cluster_dict['cluster'],
                                                               cluster_dict['pingpong'],
                                                               cluster_dict['nodataplane'],
                                                               group_ind, cluster_ind))

        # If a cluster has score 0 for all groups or the max score is below the threshold -> put it in "Remaining"
        if sum(cluster_dict['scores']) == 0 or max(cluster_dict['scores']) < self.min_score:
          self.remaining.append(cluster_dict['cluster'])
          num_graphs += len(cluster_dict['cluster'])

        else:
          # Now assign the cluster to the group with the highest score
          # (take the first if there are multiple with the same score)
          max_score_ind = cluster_dict['scores'].index(max(cluster_dict['scores']))
          cluster_dict['group'] = max_score_ind
          self.groups[max_score_ind].add_cluster(cluster_dict['cluster'])

    logger.info("Export Graphs")
    tassign = time.time()

    #self.groups.sort(key=lambda x: x.num_graphs, reverse=True)
    self.export_groups()

    texport = time.time()

    logger.info("Finished ranking")

    self.print_scoredict(cluster_scores)

    self.timing['total time'] = texport - tstart    # Time Total
    self.timing['prepare clusters'] = tdict - tstart    # Time to prepare the clusters (score dict)
    self.timing['build groups'] = tgroup - tdict     # Time to build the groups
    self.timing['assign clusters'] = tassign - tgroup   # Time to assign the clusters to the groups
    self.timing['export groups'] = texport - tassign  # Time to export the graphs

  def old_calculate_score(self, group, cluster, pingpong, nodataplane, group_ind, cluster_ind):
    """
    Calculates the likeliness score of cluster to be in group.
    """
    # Isomorphic parts
    iso_score = self.get_score_iso_components(group, cluster)

    # Same write event
    same_write_score = self.get_score_same_write_event(group, cluster)

    # Caused by single send
    singe_send_score = self.get_score_single_send(group, cluster)

    # Isomorphic without dataplane traversal
    no_dataplane_score = self.get_score_iso_no_dataplane(group, nodataplane)

    # Isomorphic with reduced controller switch pingpong
    pingpong_score = self.get_socre_iso_pingpong(group, pingpong)

    score = iso_score + same_write_score + singe_send_score + no_dataplane_score + pingpong_score

    return score

  def get_score_iso_components(self, group1, group2):
    """
    Rank based on isomorphic branches of the graphs. Add score if a graph of cluster has a race brach which is
    isomorphic to a branch of the representative graph of the group.
    """
    return self.score_iso_branch if utils.iso_components(group1.repre, group2.repre) else 0

  def get_score_same_write_event(self, group1, group2):
    """
    Checks if the races are caused by the same write event. Increases score for each graph that is caused by the same
    write event as one graph from the group
    """

    # check how many graphs of the cluster have a write event in common with the group
    factor = len(group1.write_ids & group2.write_ids) / min(len(group1.write_ids), len(group2.write_ids))

    return factor * self.score_same_write

  def get_score_iso_no_dataplane(self, group1, group2):
    """
    Score based on isomorphism of the graphs without dataplane traversals.
    """
    if group1.repre_nodataplane is None or group2.repre_nodataplane is None:
      return 0
    elif utils.iso_components(group1.repre_nodataplane, group2.repre_nodataplane):
      return self.score_iso_nodataplane
    else:
      return 0

  def get_socre_iso_pingpong(self, group1, group2):
    """
    Score based on isomorphism of the graph components with substituted controller-switch-pingpong.
    """
    if group1.repre_pingpong is None or group2.repre_pingpong is None:
      return 0
    elif utils.iso_components(group1.repre_pingpong, group2.repre_pingpong):
      return self.score_iso_nodataplane
    else:
      return 0

  def get_score_single_send(self, group1, group2):
    """
    Score is achieved if both, the representative graph of the current group and the graphs in the cluster, are
    caused by a single send event or both aren't.
    """
    if group1.single_send == group2.single_send:
      return self.score_single_send
    else:
      return 0

  def get_score_return_path(self, group1, group2):
    """
    Get score if both, the representative graph of the current group and the graphs in the clusters, either contain a
    return path or both don't.
    """
    if group1.return_path == group2.return_path:
      return self.score_return_path
    else:
      return 0

  def export_groups(self):
    """ Exports the representative graphs in the result directory and creats a folder for each group
    to export all informative graphs in the group."""
    for ind, group in enumerate(self.groups):
      # Export representative graph
      nx.write_dot(group.repre, os.path.join(self.resultdir, 'repre_%03d.dot' % ind))
      # Create folder for the other graphs
      export_path = os.path.join(self.resultdir, 'group_%03d' % ind)
      if not os.path.exists(export_path):
        os.makedirs(export_path)
      # Export pingpong and nodataplane graphs if they exist
      if group.repre_nodataplane is not None:
        nx.write_dot(group.repre_nodataplane, os.path.join(export_path, 'nodataplane.dot'))
      if group.repre_pingpong is not None:
        nx.write_dot(group.repre_pingpong, os.path.join(export_path, 'pingpong.dot'))
      # export a graph for each isomorphic cluster
      for c_ind, cluster in enumerate(group.clusters):
        nx.write_dot(cluster[0], os.path.join(export_path, 'iso_%03d.dot' % c_ind))

  def print_scoredict(self, scoredict):
    logger.debug("Score Dictionary")
    num = self.max_groups
    len_cluster = 5
    sep_line = '-' * (4 + len_cluster + (num * 9))
    title = '|      |' + ' %6d |' * num

    logger.debug(sep_line)
    logger.debug(title % tuple(range(0, num)))
    logger.debug(sep_line)

    for ind, cluster_dict in enumerate(scoredict):
      line = '| %4d |' % ind
      for score in cluster_dict['scores']:
        if score is None:
          line += '  None  |'
        else:
          line += ' %6.4f |' % score
      logger.debug(line)

    logger.debug(sep_line)

  def print_timing(self):
    """ Logs the timing information."""
    logger.info("Timing:")

    for k, v in self.timing.iteritems():
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

