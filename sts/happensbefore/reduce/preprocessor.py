import logging
import time

import networkx as nx

import utils
import pattern

logger = logging.getLogger(__name__)


class Preprocessor:
  # Provides different functions for preprocessing of the subgraphs
  def __init__(self, extract_last_controller_action=True, substitute_patterns=None):
    # set configuration options, all parameters must have default values!!
    self.extract = extract_last_controller_action.lower() not in ['false', '0']

    if substitute_patterns == 'None':
      self.patterns = None
    else:
      patterns = substitute_patterns.split(',')
      self.patterns = []
      for p in patterns:
        if p.strip().lower() == 'controllerhandle':
          self.patterns.append(pattern.ControllerHandle())
        elif p.strip().lower() == 'controllerhandlepid':
          self.patterns.append(pattern.ControllerHandlePid())
        elif p.strip().lower() == 'switchtraversal':
          self.patterns.append(pattern.SwitchTraversal())
        else:
          raise RuntimeError("%s is not a valid option for pattern substitution." % p)

  def run(self, subgraphs):
    """
    Runs preprocessing functions depending on the configuration of the preprocessor.

    Args:
      subgraphs:  list of subgraphs

    Returns:      preprocessed list of subgraphs

    """
    if self.extract:
      logger.debug('Extract last controller action')
      tstart = time.time()
      subgraphs = self.extract_last_controller_action(subgraphs)
      logger.debug('Time: %f' % (time.time() - tstart))

    if self.patterns:
      logger.debug('Detect and substitute patterns')
      tstart = time.time()
      subgraphs = self.substitute_patterns(subgraphs)
      logger.debug('Time: %f' % (time.time() - tstart))

    return subgraphs

  def extract_last_controller_action(self, subgraphs):
    """
    only keeps nodes from the race events up to the last packet send that required controller action

    Args:
      subgraphs: List of graphs

    Returns:
      new list of preprocessed subgraphs

    """

    new_subgraphs = []

    logger.info("Remove all events before the one that led to the last controller action for both race events.")
    for graph in subgraphs:
      # Find last controller handle for both events
      # nodes_to_keep = utils.find_last_controllerhandle(graph)
      nodes_to_keep = utils.find_last_controllerhandle(graph)

      # Generate the new subgraph
      new_graph = nx.DiGraph(graph.subgraph(nodes_to_keep))
      new_subgraphs.append(new_graph)

    return new_subgraphs

  def substitute_patterns(self, subgraphs):
    """
    Processes list of subgraphs and substitute all patterns in self.pattern.

    Args:
      subgraphs: list of subgraphs

    Returns
      new list of preprocessed subgraphs
    """
    logger.info("Search for patterns...")
    new_subgraphs = []

    for ind, subg in enumerate(subgraphs):
      g = subg
      for p in self.patterns:
        g = p.find_pattern(g)

        # Substitute multiple switch traversals
        if isinstance(p, pattern.SwitchTraversal):
          g = self.substitute_switchtraversal(g)

      new_subgraphs.append(g)

    return new_subgraphs

  def substitute_switchtraversal(self, graph):
    """
    Substitute multiple switchtraversals in a row with a single dataplane traversal
    """
    # Put all root nodes on the stack
    g = graph.copy()
    stack = [x for x in graph.nodes() if not graph.predecessors(x)]
    visited = []
    while stack:
      curr_node = stack.pop()
      # Only visit each node once
      if curr_node in visited:
        continue
      else:
        visited.append(curr_node)

      if g.node[curr_node]['event'] == 'switch':
        # prepare dataplane_traversal node
        g.node[curr_node]['label'] = "%s \\n %s \\n DPID: %d" % ('DataplaneTraversal',
                                                               curr_node, g.node[curr_node]['dpid'])
        g.node[curr_node]['dpid'] = [g.node[curr_node]['dpid']]

        # find all connected switch traversals
        dataplane_traversal_nodes = []
        next_node = curr_node
        while len(g.successors(next_node)) == 1 and g.node[g.successors(next_node)[0]]['event'] == 'switch':
          next_node = g.successors(next_node)[0]
          dataplane_traversal_nodes.append(next_node)

        # create edge
        for suc in g.successors(next_node):
          if not g.has_edge(curr_node, suc):
            g.add_edge(curr_node, suc)
            g.edge[curr_node][suc]['rel'] = g.edge[next_node][suc]['rel']
          stack.append(suc)

        # delete the nodes
        for n in dataplane_traversal_nodes:
          visited.append(n)
          dpid = g.node[n]['dpid']
          g.node[curr_node]['dpid'].append(dpid)
          g.node[curr_node]['label'] += ", %d" % (g.node[n]['dpid'])
          g.node[curr_node]['event_ids'].extend(g.node[n]['event_ids'])
          g.remove_node(n)

      else:
        stack.extend(g.successors(curr_node))

    return g

