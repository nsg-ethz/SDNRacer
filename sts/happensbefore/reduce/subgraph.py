

import os
import sys
import time
import logging
import collections
import networkx as nx

import utils
import hb_events
import hb_sts_events
from pox.openflow.libopenflow_01 import ofp_action_output

# create logger
logger = logging.getLogger(__name__)


class Subgraph:
  def __init__(self, hb_graph, races, resultdir):
    self.resultdir = os.path.join(resultdir, 'subgraphs')
    if not os.path.exists(self.resultdir):
      os.makedirs(self.resultdir)

    self.hb_graph = hb_graph
    self.races = races
    self.subgraphs = []
    self.eval = {'time': {}}

  def run(self):
    tstart = time.clock()
    logger.debug("Generate subgraphs")
    self.generate_subgraphs()

    logger.debug("Set subgraph attributes")
    self.set_attributes()

    self.eval['time']['Total'] = time.clock() - tstart

    return self.subgraphs

  def generate_subgraphs(self):
    """
    Generate all subgraphs from self.races and self.hb_graph.
    """
    tstart = time.clock()
    # Loop through all races
    for ind, race in enumerate(self.races):
      # logger.debug("Get Subgraph for race %d" % ind)
      stack = [race[0], race[1]]
      nodes = []

      # Get all nodes in this subgraph
      while stack:
        curr_node = stack.pop()
        if curr_node in nodes:
          continue
        else:
          stack.extend(self.hb_graph.predecessors(curr_node))
          nodes.append(curr_node)

      # Generate subgraph
      subg = nx.DiGraph(self.hb_graph.subgraph(nodes), race=race, index=ind)
      subg.node[subg.graph['race'][0]]['color'] = 'red'
      subg.node[subg.graph['race'][1]]['color'] = 'red'

      # TODO Add config option
      # nx.drawing.nx_agraph.write_dot(subg, os.path.join(self.resultdir, 'graph_%03d.dot' % ind))

      # Check if the graph is loop free
      cycles = list(nx.simple_cycles(subg))
      if cycles:
        logger.error("Cycles found in graph %d (Size: %d)" % (ind, len(subg.nodes())))

      self.subgraphs.append(subg)

    self.eval['time']['Generate subgraphs'] = time.clock() - tstart
    return

  def set_attributes(self):
    """
    Sets subgraph attributes which are later used for the clustering/ranking.
    """
    tstart = time.clock()
    for g in self.subgraphs:
      # Nodes (Original list of node ids to reconstruct it later if necessary)
      g.graph['nodes'] = g.nodes()

      # Roots (use to determine from how much send events this race origins)
      roots = [x for x in g.nodes() if not g.predecessors(x)]
      g.graph['num_roots'] = len(roots)

      # Set if the race is with a AsyncFlowExpiry event
      flow_expiry = False
      for r in roots:
        if isinstance(g.node[r]['event'], hb_events.HbAsyncFlowExpiry):
          flow_expiry = True
          break
      g.graph['flowexpiry'] = flow_expiry

      # Return path affected
      if len([x for x in g.nodes() if isinstance(g.node[x]['event'], hb_events.HbHostHandle)]) > 0:
        g.graph['return'] = True
      else:
        g.graph['return'] = False

      # Write events (list of all race-write-events in the graph)
      write_events = []
      i_event = g.graph['race'][0]
      k_event = g.graph['race'][1]
      if utils.is_write_event(i_event, g):
        write_events.append(i_event)
      if utils.is_write_event(k_event, g):
        write_events.append(k_event)

      assert len(write_events) > 0, 'No write-race-events in subgraph %d' % g.graph['index']
      g.graph['write_ids'] = write_events

      # Controller-Switch-Pingpong (Indicates if graph contains controller switch pingpong)
      g.graph['pingpong'] = utils.contains_pingpong(g)

      # Check if there is flooding in the graph
      flooding = False
      # Get MessageHandles:
      msg_handles = [g.node[e]['event'] for e in g.nodes() if isinstance(g.node[e]['event'], hb_events.HbMessageHandle)]
      for e in msg_handles:
        # Check if type is OFPT_PACKET_OUT (13)
        if e.msg_type == 13:
          # Check if there is a flooding in actions
          if hasattr(e, 'msg') and getattr(e.msg, 'actions', None):
            for action in e.msg.actions:
              if isinstance(action, ofp_action_output) and action.port == 65531:
                flooding = True
                break

            if flooding:
              break

      g.graph['flood'] = flooding

      # Number of hostsends
      g.graph['num_hostsends'] = len([x for x in roots if isinstance(g.node[x]['event'], hb_events.HbHostSend)])

      # Proactive Race event
      g.graph['num_proactive'] = 0
      for rid in g.graph['race']:
        if g.node[rid].get('cmd_type') == 'Proactive':
          g.graph['num_proactive'] += 1

    self.eval['time']['Get subgraph attributes'] = time.clock() - tstart

    return



