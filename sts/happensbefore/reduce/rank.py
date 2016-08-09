import logging.config
import time
import os
import sys
import networkx as nx

import utils

logger = logging.getLogger(__name__)


class RankGroup:
  def __init__(self, repre, cluster, pingpong, nodataplane, single_send, return_path):
    """
    Class to store the rank groups (group of subgraphs). Each group has a score, representative graph to show to the user
    and a list of all clusters contained in the group.

    Args:
      repre:  Representative graph
      graphs: List of all graphs in this group
    """
    self.repre = repre                    # Representative Graph
    self.clusters = [cluster]             # All clusters/Graphs
    self.num_graphs = len(cluster)        # Number of all graphs in a group
    self.repre_pingpong = pingpong        # Graph w/o controller-switch-pingpong (substituted node)
    self.repre_nodataplane = nodataplane  # Representative graph without dataplane traversal
    self.single_send = single_send        # Indicates if the race is caused by a single send
    self.return_path = return_path        # Indicates if there is a HostHandle -> return path is affected

  def add_cluster(self, cluster):
    self.clusters.append(cluster)
    self.num_graphs += len(cluster)


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

  def run(self, clusters):
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
      self.groups.append(RankGroup(r, c, pingpong, nodataplane, single_send, return_path))

      # prepare next step
      cur_group = len(self.groups) - 1
      cluster_scores[cluster_ind]['group'] = cur_group

      # Calculate the score for all other clusters
      for ind, cluster_dict in enumerate(cluster_scores):
        # Only continue if the current cluster is not assigned yet
        if cluster_dict['group'] is None:
          score = self.calculate_score(self.groups[cur_group],
                                       cluster_dict['cluster'],
                                       cluster_dict['pingpong'],
                                       cluster_dict['nodataplane'])
          cluster_dict['scores'].append(score)

      # Get biggest cluster with lowest overall score
      min_score = sys.maxint
      cluster_ind = None
      for ind, cluster_dict in enumerate(cluster_scores):
        # Only consider unassigned clusters
        if cluster_dict['group'] is not None:
          continue

        print "Ind: %d, Scores: %s" % (ind, cluster_dict['scores'])
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
    remaining = []
    num_graphs = 0
    for cluster_dict in cluster_scores:
      # Only calculate score if not already assigned
      if cluster_dict['group'] is None:
        for ind in range(0, len(self.groups)):
          if len(cluster_dict['scores']) <= ind:
            cluster_dict['scores'].append(self.calculate_score(self.groups[ind],
                                                               cluster_dict['cluster'],
                                                               cluster_dict['pingpong'],
                                                               cluster_dict['nodataplane']))

        # If a cluster has score 0 for all groups or the max score is below the threshold -> put it in "Remaining"
        if sum(cluster_dict['scores']) == 0 or max(cluster_dict['scores']) < self.min_score:
          remaining.append(cluster_dict['cluster'])
          num_graphs += len(cluster_dict['cluster'])

        else:
          # Now assign the cluster to the group with the highest score
          # (take the first if there are multiple with the same score)
          max_score_ind = cluster_dict['scores'].index(max(cluster_dict['scores']))
          cluster_dict['group'] = max_score_ind
          self.groups[max_score_ind].add_cluster(cluster_dict['cluster'])

    logger.info("Export Graphs")
    tassign = time.time()

    self.groups.sort(key=lambda x: x.num_graphs, reverse=True)
    self.export_groups()

    texport = time.time()

    logger.info("Finished ranking")

    self.print_scoredict(cluster_scores)

    logger.info("Summary:")
    for ind, g in enumerate(self.groups):
      logger.info("\tGroup %3d: %4d Clusters, %5d Graphs" % (ind, len(g.clusters), g.num_graphs))
    logger.info("\tRemaining:  %4d Clusters, %5d Graphs" % (len(remaining), num_graphs))
    logger.info("Timing:")
    logger.info("\tBuild score dict:     %10.3f s" % (tdict - tstart))
    logger.info("\tGenerate groups:      %10.3f s" % (tgroup - tdict))
    logger.info("\tCalc. score & assign: %10.3f s" % (tassign - tgroup))
    logger.info("\tExport groups:        %10.3f s" % (texport - tassign))
    logger.info("\tTOTAL:                %10.3f s" % (texport - tstart))

  def calculate_score(self, group, cluster, pingpong, nodataplane):
    """
    Calculates the likeliness score of cluster to be in group.
    """
    score = 0

    # Isomorphic parts
    score += self.get_score_iso_components(group, cluster)

    # Same write event
    score += self.get_score_same_write_event(group, cluster)

    # Caused by single send
    score += self.get_score_single_send(group, cluster)

    # Isomorphic without dataplane traversal
    score += self.get_score_iso_no_dataplane(group, nodataplane)

    # Isomorphic with reduced controller switch pingpong
    score += self.get_socre_iso_pingpong(group, pingpong)

    return score

  def get_score_iso_components(self, group, cluster):
    """
    Rank based on isomorphic branches of the graphs. Add score if a graph of cluster has a race brach which is
    isomorphic to a branch of the representative graph of the group.

    Args:
      group:  RaceGroup
      cluster:  Cluster to check

    Returns:
      score
    """
    return self.score_iso_branch if utils.iso_components(cluster[0], group.repre) else 0

  def get_score_same_write_event(self, group, cluster):
    """
    Checks if the races are caused by the same write event. Increases score for each graph that is caused by the same
    write event as one graph from the group
    Args:
      group:    rank_group
      cluster:  cluster to check

    Returns:
      score
    """

    # Get the event ids of all write events in the group
    write_ids = []
    for cluster in group.clusters:
      for graph in cluster:
        # get leaf nodes
        for node in (x for x in graph.nodes() if not graph.successors(x)):
          if utils.is_write_event(node, graph):
            write_ids.append(node)

    # check how many graphs of the cluster have a write event in common with the group
    score = 0
    for graph in cluster:
      common_write = False
      for node in (x for x in graph.nodes() if not graph.successors(x)):
        if node in write_ids:
          score += self.score_same_write
          common_write = True
          break
      if common_write:
        break

    return score / float(len(cluster))

  def get_score_iso_no_dataplane(self, cur_group, nodataplane):
    """
    Score based on isomorphism of the graphs without dataplane traversals.
    Args:
      cur_group:  RaceGroup
      nodataplane: if a graph is submittet, it is used instead of removing the dataplane events from the cluster

    Returns:
      score
    """
    if nodataplane is None or cur_group.repre_nodataplane is None:
      return 0
    elif utils.iso_components(nodataplane, cur_group.repre_nodataplane):
      return self.score_iso_nodataplane
    else:
      return 0

  def get_socre_iso_pingpong(self, cur_group, pingpong):
    """
    Score based on isomorphism of the graph components with substituted controller-switch-pingpong.
    Args:
      cur_group:  RaceGroup
      pingpong: If a graph is submittet, it is used instead of calculating the graph with substituted pingpongs

    Returns:
      score
    """
    if pingpong is None or cur_group.repre_pingpong is None:
      return 0
    elif utils.iso_components(pingpong, cur_group.repre_pingpong):
      return self.score_iso_nodataplane
    else:
      return 0

  def get_score_single_send(self, cur_group, cluster):
    """
    Score is achieved if both, the representative graph of the current group and the graphs in the cluster are
    caused by a single send event.
    Args:
      cur_group:  RaceGroup
      cluster:  Cluster to check

    Returns:
      score
    """
    if cur_group.single_send and utils.is_caused_by_single_send(cluster[0]):
      return self.score_single_send
    else:
      return 0

  def get_score_return_path(self, cur_group, cluster):
    """
    Get score if both, the representative graph of the current group and the graphs in the clusters contain a return
    path.
    Args:
      cur_group:  RaceGroup
      cluster:  Cluster to check

    Returns:
      score
    """
    if cur_group.return_path and utils.has_return_path(cluster[0]):
      return self.score_return_path
    else:
      return 0

  def export_groups(self):
    for ind, group in enumerate(self.groups):
      export_path = os.path.join(self.resultdir, 'groups')
      if not os.path.exists(export_path):
        os.makedirs(export_path)
      nx.write_dot(group.repre, os.path.join(export_path, 'repre_%03d.dot' % ind))

      if group.repre_nodataplane is not None:
        nx.write_dot(group.repre_nodataplane, os.path.join(export_path, 'repre_%03d_nodataplane.dot' % ind))
      if group.repre_pingpong is not None:
        nx.write_dot(group.repre_pingpong, os.path.join(export_path, 'repre_%03d_pingpong.dot' % ind))

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



