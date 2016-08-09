
import logging

import hb_events
import hb_sts_events

# create logger
logger = logging.getLogger(__name__)

def has_write_event(graph):
  """
  Returns if a graph has a write event in one of the leafnodes.
  """
  # Check all leaf nodes
  for node in (x for x in graph.nodes() if not graph.successors(x)):
    # there should not be any leaf node in a graph
    if is_write_event(node, graph):
          return True

  return False


def is_write_event(node, graph):
  """
  Returns if a node is a write event
  """
  if isinstance(graph.node[node]['event'], hb_events.HbMessageHandle):
    for op in graph.node[node]['event'].operations:
      if isinstance(op, hb_sts_events.TraceSwitchFlowTableWrite):
        return True

  return False


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
