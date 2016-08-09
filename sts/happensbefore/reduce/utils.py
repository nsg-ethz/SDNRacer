
import logging
import networkx as nx

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


def remove_dataplanetraversals(g):
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


def substitute_pingpong(g):
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


def is_caused_by_single_send(graph):
  """
  Returns if the race is caused by a single send (e.g. one host send).
  """
  if (len([x for x in graph.nodes() if not graph.predecessors(x)]) == 1 and
          len([x for x in graph.nodes() if not graph.successors(x)]) == 2):
    return True
  else:
    return False


def has_return_path(graph):
  """
  Return True if the graph contains a HostHandle followed by a HostSend (contains a return path of the packet).
  """
  # Traverse graph
  stack = [x for x in graph.nodes() if not graph.predecessors(x)]

  while stack:
    node = stack.pop()
    stack.extend(graph.successors(node))
    # Check both cases: either a substituted DataplaneTraversal or the original HostHandle event
    if graph.node[node]['event'] == 'DataplaneTraversal':
      # Check if the dataplane traversals contains a HostId
      if 'HID' in graph.node[node]['label']:
        return True

    elif isinstance(graph.node[node]['event'], hb_events.HbHostHandle):
      # Check if is it followed by a single host send
      suc = graph.successors(node)
      if len(suc) == 1 and isinstance(graph.node[suc[0]]['event'], hb_events.HbHostSend):
        return True

  return False


def iso_components(graph1, graph2):
  """
  Return True if any components of the graph are isomorphic.
  """
  # Split graph1
  components = nx.weakly_connected_components(graph1)

  if len(components) == 2:
    # Only interesting if the graph has two separate branches
    g1 = nx.DiGraph(graph1.subgraph(components[0]))
    g2 = nx.DiGraph(graph1.subgraph(components[1]))

    # Only consider "write branches"
    if not has_write_event(g1):
      g1 = None
    if not has_write_event(g2):
      g2 = None
  else:
    g1 = None
    g2 = None

  # Split split graph 2
  components = nx.weakly_connected_components(graph2)  # Only consider first graph of the cluster

  if len(components) == 2:
    # Only interesting if the graph has two separate branches
    r1 = nx.DiGraph(graph2.subgraph(components[0]))
    r2 = nx.DiGraph(graph2.subgraph(components[1]))

    # Only consider "write branches"
    if not has_write_event(r1):
      r1 = None
    if not has_write_event(r2):
      r2 = None
  else:
    r1 = None
    r2 = None

  # Find isomorphic parts
  iso = False
  if g1 and r1 and nx.is_isomorphic(g1, r1, node_match=node_match, edge_match=edge_match):
    iso = True
  elif g1 and r2 and nx.is_isomorphic(g1, r2, node_match=node_match, edge_match=edge_match):
    iso = True
  elif g2 and r1 and nx.is_isomorphic(g2, r1, node_match=node_match, edge_match=edge_match):
    iso = True
  elif g2 and r2 and nx.is_isomorphic(g2, r2, node_match=node_match, edge_match=edge_match):
    iso = True

  return iso


def node_match(n1, n2):
  # it returns True if two nodes have the same event type
  return type(n1['event']) == type(n2['event'])


def edge_match(e1, e2):
  # it returns True if two edges have the same relation
  return e1['rel'] == e2['rel']
