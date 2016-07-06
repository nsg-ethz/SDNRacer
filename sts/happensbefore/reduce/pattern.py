import hb_events


class Pattern:
  """
  The class pattern defines an interface to find patterns in a graph. At the moment, only patternsn with a single start
  and end node are supportet.
  """

  def __init__(self, events=[], edges=[], label=''):
    """
    The following fields have to be defined for each subclass:

    events:     List of all event types in the pattern. The start of the pattern has to be the first element and the
                end has to be the last element of the list. At the moment, only one event of the same type is supported.

    edges:      List of all edges in the pattern. The edges are represented in tuples of the
                form [<src>, <dst>, <rel>] (see example below), where src and dst are indices of the event list and
                <rel> is the relation between the events.

    Examples:
      Assume a pattern consiting of a HbPacketHandle, HbMessageSend and HbMessageHandle. The HbPacketHandle is connected
      by a 'mid' edge with HbMessageSend and by a 'pid' edge with the HbMessageHandle and the HbMessageSend event is
      connected with the HbPacketHandle with a 'mid' edge.
      The following variables represent this pattern:
      events     =  [HbPacketHandle, HbMessageSend, HbMessageHandle]
      edges      =  [(0, 1,'mid'),(0, 2,'pid'),(1,2,'mid)]
    """
    self.events = events
    self.edges = edges
    self.label = label

  def find_pattern(self, graph):
    """
    Find start and enpoint of a pattern in the given graph, starting at "start_node"
    """
    # List to store patterns
    found_patterns = []
    # Put all root nodes on the stack
    stack = [x for x in graph.nodes() if not graph.predecessors(x)]
    visited = []
    while stack:
      curr_node = stack.pop()
      # Only visit each node once
      if curr_node in visited:
        continue
      else:
        visited.append(curr_node)

      if isinstance(graph.node[curr_node]['event'], self.events[0]):
        # found an event which could be the start of the pattern -> check_pattern
        p = self.check_pattern(graph, curr_node)
        if p:
          found_patterns.append(p)

      # continue with the successors
      stack.extend(graph.successors(curr_node))

    if found_patterns:
      return self.substitute(graph, found_patterns)
    else:
      return graph

  def check_pattern(self, graph, node):
    """
    Subclasses need to implement this function. The function checks if node is the starting node of the pattern.
    It returns a list of all node ids which are part of the pattern or None if the node is not the starting point of the
    pattern.
    """
    event_node_ids = [None] * len(self.events)

    # Node has to be the first event of the pattern
    if not isinstance(graph.node[node]['event'], self.events[0]):
      return None

    stack = [node]
    while stack:
      curr_node = stack.pop()

      # If we already visited this node it has to be in event_node_ids and we can skip it
      if curr_node in event_node_ids:
        continue
      # check if the current node event is in the pattern
      for ind, event in enumerate(self.events):
        event_index = None
        if isinstance(graph.node[curr_node]['event'], event):
          event_index = ind
          break

      # if the event is not in the patter -> not this pattern
      if event_index is None or event_node_ids[event_index] is not None:
        return None
      else:
        event_node_ids[event_index] = curr_node

      # the current node event is not the last in this pattern we add it's successors to the stack
      if not event_index == len(self.events) - 1:
        stack.extend(graph.successors(curr_node))

    # Now we have to check if we found all events
    for ids in event_node_ids:
      if ids is None:
        return None

    # At this point, all events are checked, Now check the edges
    for src_ind, dst_ind, rel in self.edges:
      if not (graph.has_edge(event_node_ids[src_ind], event_node_ids[dst_ind]) and
              graph.edge[event_node_ids[src_ind]][event_node_ids[dst_ind]]['rel'] == rel):
        return None

    # if not returned until now we found this pattern
    return event_node_ids

  def substitute(self, graph, found_patterns):
    """
    Substitues a pattern through a single node.
    Args:
      graph: graph
      found_patterns: list of found patterns

    Returns:
      new graph
    """
    g = graph.copy()

    for p in found_patterns:
      # get the dpid for the label
      dpid = g.node[p[0]]['event'].dpid

      # Get all incomming edges (tuple of predecessor node id and edge attributes)
      in_edges = []
      for predecessor in g.predecessors(p[0]):
        in_edges.append([predecessor, g[predecessor][p[0]]])

      # Get all outgoing edges (tuple of successor node id and edge attributes)
      out_edges = []
      for successor in g. successors(p[-1]):
        out_edges.append([successor, g[p[-1]][successor]])

      # remove all nodes
      g.remove_nodes_from(p)

      # add the substitute node (use the same node id as the first event of the pattern had)
      g.add_node(p[0])

      g.node[p[0]]['event'] = None
      g.node[p[0]]['event_ids'] = p
      g.node[p[0]]['label'] = "%s \\n %s\\n DPID: %d" % (self.label, p[0], dpid)
      g.node[p[0]]['color'] = 'green'

      # add the in- and out-edges with the same attributes as before
      for e in in_edges:
        g.add_edge(e[0], p[0], e[1])

      for e in out_edges:
        g.add_edge(p[0], e[0], e[1])

    return g


class ControllerHandle(Pattern):
  """
  A controller handle consists of a HbPacketHandle event, followed by HbMessageSend, HbControllerHandle,
  HbControllerSend and HbMessageHandle. Additionally, the HbPacketHandle and HbMessageHandle are connected
  with a pid edge.
  """

  def __init__(self):
    label = 'ControllerHandle'
    events = [hb_events.HbPacketHandle,
              hb_events.HbMessageSend,
              hb_events.HbControllerHandle,
              hb_events.HbControllerSend,
              hb_events.HbMessageHandle,
              hb_events.HbPacketSend]

    edges = [(0, 1, 'mid'),
             (0, 4, 'pid'),
             (1, 2, 'mid'),
             (2, 3, 'mid'),
             (3, 4, 'mid'),
             (4, 5, 'pid')]

    Pattern.__init__(self, events, edges, label)


class SwitchTraversal(Pattern):
  """
  A Switch Traversal consists of a simple HbPacketHandle and a HbPacketSend. It happens, when there is already a
  matching rule in the switch.
  """

  def __init__(self):
    label = 'SwitchTraversal'
    events = [hb_events.HbPacketHandle,
              hb_events.HbPacketSend]

    edges = [(0, 1, 'pid')]

    Pattern.__init__(self, events, edges, label)


