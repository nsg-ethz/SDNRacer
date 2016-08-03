import logging
import time

import networkx as nx

import utils
import hb_events

logger = logging.getLogger(__name__)


class Preprocessor:
  # Provides different functions for preprocessing of the subgraphs
  def __init__(self, extract_last_controller_action=True, substitute_patterns=True, remove_pid=True):
    # set configuration options, all parameters must have default values!!
    self.extract = extract_last_controller_action.lower() not in ['false', '0']
    self.substitute = substitute_patterns.lower() not in ['false', '0']
    self.remove_pid = remove_pid

  def run(self, subgraphs):
    """
    Runs preprocessing functions depending on the configuration of the preprocessor.

    Args:
      subgraphs:  list of subgraphs

    Returns:      preprocessed list of subgraphs

    """
    # Remove dispensable pid edges
    if self.remove_pid:
      logger.debug('Remove dispensable pid edges')
      tstart = time.time()
      subgraphs = self.remove_dispensable_pid_edges(subgraphs)
      logger.debug('Time: %f' % (time.time() - tstart))

    if self.extract:
      logger.debug('Extract last controller action')
      tstart = time.time()
      subgraphs = self.extract_last_controller_action(subgraphs)
      logger.debug('Time: %f' % (time.time() - tstart))

    if self.substitute:
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
    Processes list of subgraphs and substitute all know patterns.

    Args:
      subgraphs: list of subgraphs

    Returns
      new list of preprocessed subgraphs
    """
    logger.info("Search for patterns...")
    new_subgraphs = []

    for subg in subgraphs:
      new_subgraphs.append(self._substitute(subg))

    return new_subgraphs

  def _substitute(self, graph):
    """
    Substitute known patterns in a graph. At the moment, this are ControllerHandes and DataplaneTraversals
    Args:
      graph:  graph

    Returns:
      graph with substituted patterns

    """
    # Put all root nodes on the stack
    stack = [x for x in graph.nodes() if not graph.predecessors(x)]
    visited = []
    while stack:
      curr_node = stack.pop()
      # Check if the node still exists in the graph
      if curr_node not in graph.nodes():
        continue

      # Only visit each node once
      if curr_node in visited:
        continue
      else:
        visited.append(curr_node)

      # Check for controller handle
      if isinstance(graph.node[curr_node]['event'], hb_events.HbControllerHandle):
        # found a controller handle, check if the previous event is a MessageSend and the successors are ControllerSend
        pre = graph.predecessors(curr_node)
        suc = graph.successors(curr_node)

        # First check the cases which should not exist and raise error if they do
        if not (len(pre) == 1 and isinstance(graph.node[pre[0]]['event'], hb_events.HbMessageSend)):
          raise RuntimeError("ControllerHandle %d has != 1 predecessor or predecessor is not MessageSend" % curr_node)

        for s in suc:
          if not isinstance(graph.node[s]['event'], hb_events.HbControllerSend):
            raise RuntimeError("Controllerhandle %d predecessor %d is not ControllerSend" % (curr_node, s))

        # Substitute ControllerHandle
        # First redirect outgoing edges to the first node of the ControllerHandle
        for s in suc:
          for n in graph.successors(s):
            graph.add_edge(pre[0], n)
            graph.edge[pre[0]][n]['rel'] = graph.edge[s][n]['rel']
            # add them to the stack
            stack.append(n)

        # Now Modify the information in the first node
        graph.node[pre[0]]['event'] = 'ControllerHandle'
        graph.node[pre[0]]['event_ids'] = pre + [curr_node] + suc
        label = 'ControllerHandle \\n'
        old_label = graph.node[pre[0]]['label']
        old_label = old_label.split("\\n")
        for s in old_label:
          s = s.strip()
          if "DPID" in s or "MsgType" in s or "XID" in s:
            label = label + s + "\\n"
        graph.node[pre[0]]['label'] = label
        graph.node[pre[0]]['color'] = 'green'

        # Remove the nodes
        graph.remove_node(curr_node)
        graph.remove_nodes_from(suc)

      # Check for dataplane traversal
      elif isinstance(graph.node[curr_node]['event'], (hb_events.HbPacketHandle, hb_events.HbHostHandle)):
        n = [curr_node]
        s = graph.successors(curr_node)
        ids = []
        label = 'DataplaneTraversal \\n'

        while True:
          if (len(s) == 1 and
              isinstance(graph.node[n[0]]['event'], hb_events.HbPacketHandle) and
              isinstance(graph.node[s[0]]['event'], hb_events.HbPacketSend)):
            # Found switch traversal in this case
            ids.append(n[0])
            ids.append(s[0])

            label += 'DPID: %d \\n' % graph.node[n[0]]['event'].dpid

          elif (len(s) == 1 and
                isinstance(graph.node[n[0]]['event'], hb_events.HbHostHandle) and
                isinstance(graph.node[s[0]]['event'], hb_events.HbHostSend)):
            # Found host traversal in this case
            ids.append(n[0])
            ids.append(s[0])

            label += 'HID: %d \\n' % graph.node[n[0]]['event'].hid

          else:
            break

          # Only continue if s has only one successor
          if len(graph.successors(s[0])) == 1:
            n = graph.successors(s[0])
            s = graph.successors(n[0])
          else:
            break

        # If we found ids -> Substitute
        if ids:
          # Redirect edges
          for s in graph.successors(ids[-1]):
            graph.add_edge(ids[0], s)
            graph.edge[ids[0]][s]['rel'] = graph.edge[ids[-1]][s]['rel']

          # Modify first node to hold all needed information
          graph.node[ids[0]]['event'] = 'DataplaneTraversal'
          graph.node[ids[0]]['event_ids'] = ids
          graph.node[ids[0]]['label'] = label
          graph.node[ids[0]]['color'] = 'green'

          # remove all other nodes
          graph.remove_nodes_from(ids[1:])

          # Add successors for further processing
          stack.extend(graph.successors(curr_node))

        else:
          # No dataplanetraversal found -> continue with successors
          stack.extend(graph.successors(curr_node))

      # Other event types are not part of a pattern -> continue with successors
      else:
        # continue with the successors
        stack.extend(graph.successors(curr_node))

    return graph

  def remove_dispensable_pid_edges(self, subgraphs):
    """
    Processes list of subgraphs and substitute all know patterns.

    Args:
      subgraphs: list of subgraphs

    Returns
      new list of preprocessed subgraphs
    """
    logger.info("Remove dispensable pid edges...")
    new_subgraphs = []

    for subg in subgraphs:
      new_subgraphs.append(self._remove_dispensable_pid_edges(subg))

    return new_subgraphs

  def _remove_dispensable_pid_edges(self, graph):
    """
    Removes pid edges between two events if there is another patch via the controller.
    Args:
      graph: graph to check

    Returns:
      graph without the pid edges
    """
    # get all root nodes
    stack = [x for x in graph.nodes() if not graph.predecessors(x)]

    while stack:
      curr_node = stack.pop()

      # Check if there are two successors
      suc = graph.successors(curr_node)
      if not len(suc) == 2:
        stack.extend(suc)
        continue

      else:
        # Check if one edge is 'mid' and the other 'pid'
        if (graph.edge[curr_node][suc[0]]['rel'] == 'mid' and
            graph.edge[curr_node][suc[1]]['rel'] == 'pid'):
          mid_node = suc[0]
          pid_node = suc[1]

        elif (graph.edge[curr_node][suc[0]]['rel'] == 'pid' and
              graph.edge[curr_node][suc[1]]['rel'] == 'mid'):
          mid_node = suc[1]
          pid_node = suc[0]

        else:
          # not dispensable edge -> continue with the next nodes
          stack.extend(suc)
          continue

        # Check if the longer path is MessageSend -> ControllerHandle -> ControllerSend and to node after is the node
        # where the pid edge ends
        if isinstance(graph.node[mid_node]['event'], hb_events.HbMessageSend):
          suc = graph.successors(mid_node)
          if len(suc) == 1 and isinstance(graph.node[suc[0]]['event'], hb_events.HbControllerHandle):
            # It's possible that a controllerhandle causes multiple controller sends -> check all of them
            suc = graph.successors(suc[0])
            for n in suc:
              if isinstance(graph.node[n]['event'], hb_events.HbControllerSend):
                n = graph.successors(n)
                if len(n) == 1 and n[0] == pid_node:
                  # In this case, the pid-edge is dispensable
                  graph.remove_edge(curr_node, pid_node)
                  stack.append(pid_node)
                  continue

        # In any of the other cases -> continue with successors
        stack.extend(graph.successors(curr_node))

    return graph
