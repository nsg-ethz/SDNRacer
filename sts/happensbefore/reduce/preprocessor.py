import logging
import time
import itertools
import sys
import networkx as nx

import utils
import hb_events

logger = logging.getLogger(__name__)


class Preprocessor:
  # Provides different functions for preprocessing of the subgraphs
  def __init__(self, hb_graph, races, remove_nodes=True, remove_pid=True, remove_proactive=True):
    # set configuration options
    self.remove_nodes = remove_nodes.lower() not in ['false', '0']
    self.remove_pid = remove_pid.lower() not in ['false', '0']
    self.hb_graph = hb_graph
    self.races = races
    self.eval = {'time': {}}

  def run(self):
    """
    Runs preprocessing functions depending on the configuration of the preprocessor.
    """
    tstart = time.clock()

    # Remove dispensable edges ('time' and 'dep_raw')
    logger.debug('Remove dispensable edges')
    self.remove_dispensable_edges()
    self.eval['time']['Remove dispensable edges'] = time.clock() - tstart

    # Remove unpersuasive nodes
    if self.remove_nodes:
      logger.debug('Remove unpersuasive nodes')
      self.remove_dispensable_nodes()

    # Remove dispensable pid edges
    if self.remove_pid:
      logger.debug('Remove dispensable pid edges')
      self.remove_dispensable_pid_edges()

    # Remove proactive delete_all nodes and according barrier request
    if self.remove_proactive:
      logger.debug("Remove proactive nodes")
      self.remove_proactive()

    self.eval['time']['Total'] = time.clock() - tstart

    return

  def remove_proactive(self):
    """ Removes the initial Proactive barrier_request after the removal of all flow rules in all switches at startup.
    If there are other root events, no nodes are removed."""
    # All root nodes
    roots = [x for x in self.hb_graph.nodes() if not self.hb_graph.predecessors(x)]

    nodes = []
    remove_nodes = True
    for root in roots:
      # Case 1 Floodlight: Init consist of Barrier - RemoveFlows - Barrier
      # First Event has to be HbMessageHandle with MsgType OFPT_BARRIER_REQUEST
      if (isinstance(self.hb_graph.node[root]['event'], hb_events.HbMessageHandle) and
          self.hb_graph.node[root]['event'].msg_type == 18):
        nodes.append(root)
        suc = self.hb_graph.successors(root)

        # Second event has to be HbMessageHandle with MsgType OFPT_FLOW_MOD
        if (len(suc) == 1 and
            isinstance(self.hb_graph.node[suc[0]]['event'], hb_events.HbMessageHandle) and
            self.hb_graph.node[suc[0]]['event'].msg_type == 14):
          nodes.append(suc[0])
          suc = self.hb_graph.successors(suc[0])

          # Third event has to be HbMessageHandle with MsgType OFPT_BARRIER_REQUEST
          if (len(suc) == 1 and
              isinstance(self.hb_graph.node[suc[0]]['event'], hb_events.HbMessageHandle) and
              self.hb_graph.node[suc[0]]['event'].msg_type == 18):
            nodes.append(suc[0])

      # Case 2 POX: Init consist of RemoveFlows - Barrier
      # First Event has to be HbMessageHandle with MsgType OFPT_BARRIER_REQUEST
      if (isinstance(self.hb_graph.node[root]['event'], hb_events.HbMessageHandle) and
              self.hb_graph.node[root]['event'].msg_type == 14):
        nodes.append(root)
        suc = self.hb_graph.successors(root)

        # Second event has to be HbMessageHandle with MsgType OFPT_FLOW_MOD
        if (len(suc) == 1 and
              isinstance(self.hb_graph.node[suc[0]]['event'], hb_events.HbMessageHandle) and
                self.hb_graph.node[suc[0]]['event'].msg_type == 18):
          nodes.append(suc[0])

    self.hb_graph.remove_nodes_from(nodes)

    return

  def remove_dispensable_edges(self):
    """
    Removes all edges which where only added to filter harmfull races ('time' and 'dep_raw')
    Args:
      graph: hb_graph

    Returns: hb_graph with removed edges
    """
    # Remove unnecessary edges
    for src, dst, data in self.hb_graph.edges(data=True):
      if data.get('rel', None) in ['time', 'dep_raw']:
        self.hb_graph.remove_edge(src, dst)

    return

  def remove_dispensable_pid_edges(self):
    """
    Removes pid edges between two events if there is another patch via the controller.
    Args:
      graph: graph to check

    Returns:
      graph without the pid edges
    """
    tstart = time.clock()
    # get all root nodes
    stack = [x for x in self.hb_graph.nodes() if not self.hb_graph.predecessors(x)]
    visited = []

    while stack:
      curr_node = stack.pop()
      if curr_node in visited:
        continue
      else:
        visited.append(curr_node)

      # Check if there are less than two successors -> continue with successors
      suc = self.hb_graph.successors(curr_node)
      if len(suc) > 2:
        stack.extend(suc)
        continue

      else:
        # for each combination of the edges
        mid_node = None
        pid_node = None
        processed = []
        for suc1, suc2 in itertools.combinations(suc, 2):
          # Check if one edge is 'mid' and the other 'pid'
          if (self.hb_graph.edge[curr_node][suc1]['rel'] == 'mid' and
                  self.hb_graph.edge[curr_node][suc2]['rel'] == 'pid'):
            mid_node = suc[0]
            pid_node = suc[1]

          elif (self.hb_graph.edge[curr_node][suc[0]]['rel'] == 'pid' and
                    self.hb_graph.edge[curr_node][suc[1]]['rel'] == 'mid'):
            mid_node = suc[1]
            pid_node = suc[0]

          if not mid_node or not pid_node:
            # not dispensable edges -> continue with the next nodes
            continue

          # Check if the longer path is MessageSend -> ControllerHandle -> ControllerSend and to node after is the node
          # where the pid edge ends
          if isinstance(self.hb_graph.node[mid_node]['event'], hb_events.HbMessageSend):
            mid_suc = self.hb_graph.successors(mid_node)
            if len(mid_suc) == 1 and isinstance(self.hb_graph.node[mid_suc[0]]['event'], hb_events.HbControllerHandle):
              # It's possible that a controllerhandle causes multiple controller sends -> check all of them
              mid_suc = self.hb_graph.successors(mid_suc[0])
              for n in mid_suc:
                if isinstance(self.hb_graph.node[n]['event'], hb_events.HbControllerSend):
                  n = self.hb_graph.successors(n)
                  if len(n) == 1 and n[0] == pid_node:
                    # In this case, the pid-edge is dispensable
                    self.hb_graph.remove_edge(curr_node, pid_node)
                    stack.append(pid_node)
                    # pid already added to stack
                    processed.append(pid_node)

        # Add not processed nodes to stack
        stack.extend([x for x in suc if not x in processed])

    self.eval['time']['Remove unpersuasive nodes'] = time.clock() - tstart
    return

  def remove_dispensable_nodes(self):
    """
    Removes all events that happen after (are below) a race event.
    """
    # Generate list with all race ids
    race_ids = [x for race in self.races for x in (race.i_event.eid, race.k_event.eid)]

    tstart = time.clock()
    logger.debug("Total nodes before removal: %d" % self.hb_graph.number_of_nodes())

    nodes_removed = 1
    tot_nodes_removed = 0
    while nodes_removed > 0:
      nodes_removed = 0
      # Get leave nodes
      leaf_nodes = [x for x in self.hb_graph.nodes_iter() if not self.hb_graph.successors(x)]
      for leaf in leaf_nodes:
        # If a leaf node is not part of a race, add it for removal
        if leaf not in race_ids:
          self.hb_graph.remove_node(leaf)
          nodes_removed += 1

      tot_nodes_removed += nodes_removed

    # Check that still all races are in the graph
    for race in race_ids:
      assert self.hb_graph.has_node(race), "Race event with id %s not in graph" % race

    logger.debug("Total nodes after removal: %d" % self.hb_graph.number_of_nodes())

    self.eval['time']['Remove pid edges'] = time.clock() - tstart
    return
