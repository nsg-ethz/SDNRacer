import logging.config
import time
import os
import networkx as nx

import utils
import hb_events

logger = logging.getLogger(__name__)


class RankGroup:
  def __init__(self, repre, graphs, pingpong, nodataplane):
    """
    Class to store the rank groups (group of subgraphs). Each group has a score, representative graph to show to the user
    and a list of all clusters contained in the group.

    Args:
      repre:  Representative graph
      graphs: List of all graphs in this group
    """
    self.repre = repre                    # Representative Graph
    self.graphs = graphs                  # All clusters/Graphs
    self.repre_pingpong = pingpong        # Graph w/o controller-switch-pingpong (substituted node)
    self.repre_nodataplane = nodataplane  # Representative graph without dataplane traversal


class Rank:
  """
  Class to rank graphs/clusters and put them in the different rank groups.
  """

  def __init__(self, resultdir, max_groups=5,
               score_same_write=1,
               score_iso_branch=1,
               score_iso_nodataplane=1,
               score_iso_pingpong=1,
               threshold=1):
    self.resultdir = resultdir
    self.max_groups = int(max_groups)
    self.score_iso_branch = float(score_iso_branch)
    self.score_same_write = float(score_same_write)
    self.score_iso_nodataplane = float(score_iso_nodataplane)
    self.score_iso_pingpong = float(score_iso_pingpong)
    self.threshold = float(threshold)
    self.num_groups = 0
    self.groups = []

  def run(self, clusters):
    # Put the biggest cluster in the first group
    t_total = time.time()
    t_total_group = 0
    t_total_iso = 0
    t_total_dataplane = 0
    t_total_pingpong = 0
    t_total_write = 0
    while len(clusters) > 0 and len(self.groups) < self.max_groups:
      ttot = time.time()
      tstart = time.time()
      clusters.sort(key=len, reverse=True)
      c = clusters[0]
      r = clusters[0][0]
      pingpong = self.substitute_pingpong(r)
      nodataplane = self.remove_dataplanetraversals(r)
      self.groups.append(RankGroup(r, c, pingpong, nodataplane))
      clusters.remove(clusters[0])
      tgroup = time.time() - tstart
      t_total_group += tgroup

      # Calculate score
      cur_group = self.groups[-1]
      scores = []
      tiso = 0
      twrite = 0
      tdataplane = 0
      tpingpong = 0
      for ind, cluster in enumerate(clusters):
        score = 0

        # Isomorphic parts
        tstart = time.time()
        score += self.iso_branch(cur_group, cluster)
        tiso += time.time() - tstart

        # Same write event
        tstart = time.time()
        score += self.same_write_event(cur_group, cluster)
        twrite += time.time() - tstart

        # Isomorphic without dataplane traversal
        tstart = time.time()
        score += self.iso_no_dataplane(cur_group, cluster)
        tdataplane += time.time() - tstart

        # Isomorphic with reduced controller switch pingpong
        tstart = time.time()
        score += self.iso_substituted_pingpong(cur_group, cluster)
        tpingpong += time.time() - tstart

        scores.append([cluster, score])

      # Timing
      t_total_iso += tiso
      t_total_write += twrite
      t_total_dataplane += tdataplane
      t_total_pingpong += tpingpong

      # add clusters to group, remove them from clusters
      ind = 0
      for cluster, score in scores:
        if score / float(len(cluster)) > self.threshold:
          cur_group.graphs.extend(cluster)
          clusters.remove(cluster)
        ind += 1

      # Log group timing
      logger.debug("Timing group %d:" % (len(self.groups) - 1))
      logger.debug("\t Create Groupe: %8.3f s" % tgroup)
      logger.debug("\t Iso Branches:  %8.3f s" % tiso)
      logger.debug("\t Same write:    %8.3f s" % twrite)
      logger.debug("\t Iso no datapl: %8.3f s" % tdataplane)
      logger.debug("\t Iso pingpong:  %8.3f s" % tpingpong)
      logger.debug("\t TOTAL:         %8.3f s" % (time.time() - ttot))

    # Sort the groups based on the number of graphs in them
    self.groups.sort(key=lambda x: len(x.graphs), reverse=True)
    self.export_groups()

    # Print group info
    logger.info("Time information grouping:")
    logger.info("\t Create Groups: %f s" % t_total_group)
    logger.info("\t Iso branches:  %f s" % t_total_iso)
    logger.info("\t Same writes:   %f s" % t_total_write)
    logger.debug("\t Iso no datapl:%f s" % t_total_dataplane)
    logger.debug("\t Iso pingpong: %f s" % t_total_pingpong)
    logger.info("\t TOTAL:         %f s" % (time.time() - t_total))
    for ind, group in enumerate(self.groups):
      logger.info("Group %3d: %3d Graphs" % (ind, len(group.graphs)))

    rem_graphs = 0
    for g in clusters:
      rem_graphs += len(g)
    logger.info("Remaining: %d clusters, %d graphs" % (len(clusters), rem_graphs))

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
    graph = cluster[0]
    # Split the graph
    components = nx.weakly_connected_components(graph)

    if len(components) == 2:
      # Only interesting if the graph has two separate branches
      g1 = nx.DiGraph(graph.subgraph(components[0]))
      g2 = nx.DiGraph(graph.subgraph(components[1]))

      # Only consider "write branches"
      if not utils.has_write_event(g1):
        g1 = None
      if not utils.has_write_event(g2):
        g2 = None
    else:
      g1 = None
      g2 = None

    # Split the representative graph
    components = nx.weakly_connected_components(group.repre)  # Only consider first graph of the cluster

    if len(components) == 2:
      # Only interesting if the graph has two separate branches
      r1 = nx.DiGraph(group.repre.subgraph(components[0]))
      r2 = nx.DiGraph(group.repre.subgraph(components[1]))

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

    return self.score_iso_branch * len(cluster) if iso else 0

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
    for graph in group.graphs:
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

    return score

  def export_groups(self):
    for ind, group in enumerate(self.groups):
      export_path = os.path.join(self.resultdir, 'groups')
      if not os.path.exists(export_path):
        os.makedirs(export_path)
      nx.write_dot(group.repre, os.path.join(export_path, 'repre_%03d.dot' % ind))
      nx.write_dot(group.repre_nodataplane, os.path.join(export_path, 'repre_%03d_nodataplane.dot' % ind))
      nx.write_dot(group.repre_pingpong, os.path.join(export_path, 'repre_%03d_pingpong.dot' % ind))

  def iso_no_dataplane(self, cur_group, cluster):
    """
    Score based on isomorphism of the graphs without dataplane traversals.
    Args:
      cur_group:  RaceGroup
      cluster:  Cluster to check

    Returns:
      score
    """
    graph = self.remove_dataplanetraversals(cluster[0])

    if nx.is_isomorphic(graph, cur_group.repre, node_match=self.node_match, edge_match=self.edge_match):
      return self.score_iso_nodataplane * len(cluster)
    else:
      return 0

  def iso_substituted_pingpong(self, cur_group, cluster):
    """
    Score based on isomorphism of the graphs with substituted controller-switch-pingpong.
    Args:
      cur_group:  RaceGroup
      cluster:  Cluster to check

    Returns:
      score
    """
    graph = self.substitute_pingpong(cluster[0])
    if nx.is_isomorphic(graph, cur_group.repre, node_match=self.node_match, edge_match=self.edge_match):
      return self.score_iso_nodataplane * len(cluster)
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

    while stack:
      node = stack.pop()
      stack.extend(graph.successors(node))
      if graph.node[node]['event'] == 'DataplaneTraversal':
        for p in graph.predecessors(node):
          for s in graph.successors(node):
            graph.add_edge(p, s, {'label': '', 'rel': ''})

        graph.remove_node(node)

    return graph

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

        # Found Controller-Switch-PingPong -> find all nodes which are part of it
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

    return graph

