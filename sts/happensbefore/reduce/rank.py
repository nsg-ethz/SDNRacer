import logging.config
import time
import os
import sys
import networkx as nx

import utils
import hb_events

logger = logging.getLogger(__name__)


class RankGroup:
  def __init__(self, repre, cluster, pingpong, nodataplane, single_send):
    """
    Class to store the rank groups (group of subgraphs). Each group has a score, representative graph to show to the user
    and a list of all clusters contained in the group.

    Args:
      repre:  Representative graph
      graphs: List of all graphs in this group
    """
    self.repre = repre                    # Representative Graph
    self.clusters = [cluster]              # All clusters/Graphs
    self.num_graphs = len(cluster)
    self.repre_pingpong = pingpong        # Graph w/o controller-switch-pingpong (substituted node)
    self.repre_nodataplane = nodataplane  # Representative graph without dataplane traversal
    self.single_send = single_send        # Indicates if the race is caused by a single send

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
               min_score=1,
               threshold=1):
    self.resultdir = resultdir
    self.max_groups = int(max_groups)
    self.score_iso_branch = float(score_iso_branch)
    self.score_same_write = float(score_same_write)
    self.score_iso_nodataplane = float(score_iso_nodataplane)
    self.score_iso_pingpong = float(score_iso_pingpong)
    self.score_single_send = float(score_single_send)
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
                      'pingpong': self.substitute_pingpong(c[0]),
                      'nodataplane': self.remove_dataplanetraversals(c[0]),
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
      pingpong = self.substitute_pingpong(r)
      nodataplane = self.remove_dataplanetraversals(r)
      single_send = self.is_caused_by_single_send(r)
      cur_group = len(self.groups)
      self.groups.append(RankGroup(r, c, pingpong, nodataplane, single_send))
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

        # Check if all scores are more than threshold -> continue with next
        if min(cluster_dict['scores']) > self.threshold:
          continue

        # Get score, Ignore scores for groups which are not calculated yet
        score = sum(cluster_dict['scores'])

        # Clusters are ordered in size, so the first graph with the smallest score is always the biggest
        if score == 0:
          cluster_ind = ind
          min_score = 0
          break

        elif score < min_score:
          min_score = score
          cluster_ind = ind

      logger.debug("\tLowest: Cluster %d, Score %f (%s)" % (cluster_ind, min_score, cluster_scores[cluster_ind]['scores']))

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

    self.groups.sort(key=lambda x: len(x.clusters), reverse=True)
    self.export_groups()

    texport = time.time()

    logger.info("Finished ranking")

    self.print_scoredict(cluster_scores)

    logger.info("Summary:")
    for ind, g in enumerate(self.groups):
      logger.info("\tGroup %s: %4d Clusters, %5d Graphs" % (ind, len(g.clusters), g.num_graphs))
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
    score += self.iso_branch(group, cluster)

    # Same write event
    score += self.same_write_event(group, cluster)

    # Caused by single send
    score += self.get_score_single_send(group, cluster)

    # Isomorphic without dataplane traversal
    score += self.iso_no_dataplane(group, nodataplane)

    # Isomorphic with reduced controller switch pingpong
    score += self.iso_substituted_pingpong(group, pingpong)

    return score

  def iso_branch(self, group, cluster):
    """
    Rank based on isomorphic branches of the graphs. Add score if a graph of cluster has a race brach which is
    isomorphic to a branch of the representative graph of the group.

    Args:
      group:  RaceGroup
      cluster:  Cluster to check

    Returns:
      score
    """
    return self.score_iso_branch if self.iso_components(cluster[0], group.repre) else 0

  def iso_components(self, graph1, graph2):
    """
    Return True if any components of the graph are isomorphic.
    """
    # Split the graph
    components = nx.weakly_connected_components(graph1)

    if len(components) == 2:
      # Only interesting if the graph has two separate branches
      g1 = nx.DiGraph(graph1.subgraph(components[0]))
      g2 = nx.DiGraph(graph1.subgraph(components[1]))

      # Only consider "write branches"
      if not utils.has_write_event(g1):
        g1 = None
      if not utils.has_write_event(g2):
        g2 = None
    else:
      g1 = None
      g2 = None

    # Split the representative graph
    components = nx.weakly_connected_components(graph2)  # Only consider first graph of the cluster

    if len(components) == 2:
      # Only interesting if the graph has two separate branches
      r1 = nx.DiGraph(graph2.subgraph(components[0]))
      r2 = nx.DiGraph(graph2.subgraph(components[1]))

      # Only consider "write branches"
      if not utils.has_write_event(r1):
        r1 = None
      if not utils.has_write_event(r2):
        r2 = None
    else:
      r1 = None
      r2 = None

    # Find isomorphic parts
    iso = False
    if g1 and r1 and nx.is_isomorphic(g1, r1, node_match=self.node_match, edge_match=self.edge_match):
      iso = True
    elif g1 and r2 and nx.is_isomorphic(g1, r2, node_match=self.node_match, edge_match=self.edge_match):
      iso = True
    elif g2 and r1 and nx.is_isomorphic(g2, r1, node_match=self.node_match, edge_match=self.edge_match):
      iso = True
    elif g2 and r2 and nx.is_isomorphic(g2, r2, node_match=self.node_match, edge_match=self.edge_match):
      iso = True

    return iso

  def node_match(self, n1, n2):
    # it returns True if two nodes have the same event type
    return type(n1['event']) == type(n2['event'])

  def edge_match(self, e1, e2):
    # it returns True if two edges have the same relation
    return e1['rel'] == e2['rel']

  def same_write_event(self, group, cluster):
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

  def iso_no_dataplane(self, cur_group, nodataplane):
    """
    Score based on isomorphism of the graphs without dataplane traversals.
    Args:
      cur_group:  RaceGroup
      cluster:  Cluster to check
      nodataplane: if a graph is submittet, it is used instead of removing the dataplane events from the cluster

    Returns:
      score
    """
    if nodataplane is None or cur_group.repre_nodataplane is None:
      return 0
    elif self.iso_components(nodataplane, cur_group.repre_nodataplane):
      return self.score_iso_nodataplane
    else:
      return 0

  def iso_substituted_pingpong(self, cur_group, pingpong):
    """
    Score based on isomorphism of the graph components with substituted controller-switch-pingpong.
    Args:
      cur_group:  RaceGroup
      cluster:  Cluster to check
      pingpong: If a graph is submittet, it is used instead of calculating the graph with substituted pingpongs

    Returns:
      score
    """
    if pingpong is None or cur_group.pingpong is None:
      return 0
    elif self.iso_components(pingpong, cur_group.repre_pingpong):
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
    if cur_group.single_send and self.is_caused_by_single_send(cluster[0]):
      return self.score_single_send
    else:
      return 0

  def remove_dataplanetraversals(self, g):
    """
    Returns a copy of the graph g with removed dataplane traversals.
    """
    # First copy the representative graph
    graph = g.copy()

    # Now remove all DataplaneTraversals
    stack = [x for x in graph.nodes() if not graph.predecessors(x)]

    found_dataplanetraversal = False
    while stack:
      node = stack.pop()
      stack.extend(graph.successors(node))
      if graph.node[node]['event'] == 'DataplaneTraversal':
        found_dataplanetraversal = True
        for p in graph.predecessors(node):
          for s in graph.successors(node):
            graph.add_edge(p, s, {'label': '', 'rel': ''})

        graph.remove_node(node)

    return graph if found_dataplanetraversal else None

  def substitute_pingpong(self, g):
    """
    Checks if the graph contains a controller-switch-pingpong and substitute it with a single node.
    Returns:
      graph with substituted nodes
    """
    # First copy graph
    graph = g.copy()

    # Now check for controller-switch-pingpong
    stack = [x for x in graph.nodes() if not graph.predecessors(x)]
    found_pingpong = False

    while stack:
      curr_node = stack.pop()

      if graph.node[curr_node]['event'] == 'ControllerHandle':
        # Found first controllerhandle -> No get dpid of switch
        pre = graph.predecessors(curr_node)
        suc = graph.successors(curr_node)
        dpid = graph.node[pre[0]]['event'].dpid

        if len(pre) != 1 or len(suc) != 1:
          # Not PingPong -> continue with successors
          stack.extend(suc)
          continue

        # Check if the next node is a MessageHandle with the same dpid
        if not (isinstance(graph.node[suc[0]]['event'], hb_events.HbMessageHandle) or
                graph.node[suc[0]]['event'].dpid == dpid):
          # Not PingPong -> continue with successors
          stack.extend(suc)
          continue

        # Check if the event after is again a controllerhandle
        node = graph.successors(suc[0])
        if not len(node) == 1 or not graph.node[node[0]]['event'] == 'ControllerHandle':
          # Not PingPong -> continue with successors
          stack.extend(suc)
          continue

        # Found Controller-Switch-PingPong
        found_pingpong = True
        # find all nodes which are part of it
        ids = [curr_node, suc[0], node[0]]  # NodeIds which are part of the pingpong
        num = 2
        node = graph.successors(node[0])
        if len(node) == 1:
          suc = graph.successors(node[0])

          while len(suc) == 1 and len(node) == 1:
            # Check if there is another pingpong
            if (isinstance(graph.node[node[0]]['event'], hb_events.HbMessageHandle) and
                    graph.node[node[0]]['event'].dpid == dpid and
                    graph.node[suc[0]]['event'] == 'ControllerHandle'):
              # Found another pingpong -> add ids
              num += 1
              ids.append(node[0])
              ids.append(suc[0])
              node = graph.successors(node[0])
              if len(node) != 1:
                break
              else:
                suc = graph.successors(node[0])

            else:
              break

        # Substitute nodes
        for n in graph.successors(ids[-1]):
          graph.add_edge(ids[0], n, graph.edge[ids[-1]][n])
          # add them to the stack
          stack.append(n)

        # Now Modify the information in the first node
        graph.node[ids[0]]['event'] = 'PingPong'
        graph.node[ids[0]]['event_ids'] = []  # Not relevant since this is only a copy
        graph.node[ids[0]]['label'] = 'PingPong \\n DPID: %d \\n Num: %d' % (dpid, num)
        graph.node[ids[0]]['color'] = 'green'

        # Remove the nodes
        graph.remove_nodes_from(ids[1:])

      else:
        stack.extend(graph.successors(curr_node))

    return graph if found_pingpong else None

  def is_caused_by_single_send(self, graph):
    """
    Returns if the race is caused by a single send (e.g. one host send).
    """
    if (len([x for x in graph.nodes() if not graph.predecessors(x)]) == 1 and
        len([x for x in graph.nodes() if not graph.successors(x)]) == 2):
      return True
    else:
      return False

  def print_scoredict(self, scoredict):
    logger.debug("Score Dictionary")
    num = self.max_groups + 1
    len_cluster = 5
    sep_line = '-' * (4 + len_cluster + (num * 9))
    title = '|      |' + ' %6d |' * (num - 1) + '  Total |'

    logger.debug(sep_line)
    logger.debug(title % tuple(range(0, num - 1)))
    logger.debug(sep_line)

    for ind, cluster_dict in enumerate(scoredict):
      line = '| %4d |' % ind
      tot = 0
      for score in cluster_dict['scores']:
        if score is None:
          line += '  None  |'
        else:
          line += ' %6.4f |' % score
          tot += score
      line += ' %6.4f |' % tot
      logger.debug(line)

    logger.debug(sep_line)



