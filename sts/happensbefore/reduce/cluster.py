import logging.config
import itertools
import sys

logger = logging.getLogger(__name__)


class Cluster:
  _ids = itertools.count(0)

  def __init__(self, graphs=[]):
    self.id = Cluster._ids.next()   # Add cluster id to each group
    self.representative = None      # representative graph of the group
    self.graphs = []                # List of all graphs in the groups
    self.write_ids = []             # List of all ids of write-race-events
    self.common_writes = 0          # Percentage of graphs containing a common write event with another graph

    self.properties = {             # Properties for "relation functions"
        'pingpong': 0,              # Percentage of graphs containing a controller-switch-pingpong
        'return': 0,                # Percentage of races on the return path (contain HbHostHandle and HbHostSend)
        'flowexpiry': 0,            # Percentage of graphs origin from flowexpiry
        'flood': 0,                 # Percentage of graphs containing a flooding action
        'num_roots': 0,             # Average number of root events
        'num_hostsends': 0,         # Average number of hostsend events
        'num_proactive': 0          # Average number of proactive race events
    }

    if graphs:
      self.add_graphs(graphs, update=True)

      if self.representative is None:
        self.representative = graphs[0]

  def get_write_ids(self):
    """
    Populate self.write_ids with the write-race-event-ids from all graphs.
    """
    self.write_ids = []
    for graph in self.graphs:
      self.write_ids.extend(graph.graph['write_ids'])

    return

  def get_properties(self):
    """ Calculates all properties. For a list of the properties see the init function."""

    # Return path
    self.properties['return'] = len([g for g in self.graphs if g.graph['return']]) / float(len(self.graphs))

    # Pingpong
    self.properties['pingpong'] = len([g for g in self.graphs if g.graph['pingpong']]) / float(len(self.graphs))

    # FlowExpiry
    self.properties['flowexpiry'] = len([g for g in self.graphs if g.graph['flowexpiry']]) / float(len(self.graphs))

    # Flooding
    self.properties['flood'] = len([g for g in self.graphs if g.graph['flood']]) / float(len(self.graphs))

    # Number of root events (average)
    self.properties['num_roots'] = sum([g.graph['num_roots'] for g in self.graphs]) / float(len(self.graphs))

    # Number of hostsend events (average)
    self.properties['num_hostsends'] = sum([g.graph['num_hostsends'] for g in self.graphs]) / float(len(self.graphs))

    # Proactive race event
    self.properties['num_proactive'] = sum([g.graph['num_proactive'] for g in self.graphs]) / float(len(self.graphs))

    return

  def add_graphs(self, graphs, update=False):
    """
    Adds the graphs from iterable graphs to the cluster and updates all variables.
    Args:
      graphs: Iterable of graphs to add
      update: Wether the properties and write_ids should be updated
    """
    # Add graphs
    self.graphs.extend(graphs)
    # If there is no representative graph yet -> set it to the first one in the list
    if self.representative is None:
      self.representative = graphs[0]

    # Update Properties and write_ids
    if update:
      self.update()
    return

  def update(self):
    """ Update write_ids and properties of the group."""
    # Update write ids
    self.get_write_ids()
    # Update properties
    self.get_properties()

    return

  def get_representative(self):
    """
    Sets representative graph based on the cluster properties.
    """
    # TODO Update this function to check the new features
    # Get graph  properties
    pingpong = True if self.properties['pingpong'] >= 0.5 else False
    ret = True if self.properties['return'] >= 0.5 else False
    flowexp = True if self.properties['flowexpiry'] >= 0.5 else False
    flood = True if self.properties['flood'] >= 0.5 else False

    # Get all graphs which satisfy this properties
    candidates = []
    for g in self.graphs:
      if (g.graph['pingpong'] == pingpong and
          g.graph['return'] == ret and
          g.graph['flowexpiry'] == flowexp and
          g.graph['flood'] == flood):
        candidates.append(g)

    # Get the graphs with the closest number of Proactive
    min_diff = sys.maxint
    new_candidates = []
    for c in candidates:
      diff = abs(g.graph['num_proactive'] - self.properties['num_proactive'])
      if diff < min_diff:
        new_candidates = [c]
      elif diff == min_diff:
        new_candidates.append(c)

    candidates = new_candidates

    # Get the graphs with the closest number of HostSends
    min_diff = sys.maxint
    new_candidates = []
    for c in candidates:
      diff = abs(g.graph['num_hostsends'] - self.properties['num_hostsends'])
      if diff < min_diff:
        new_candidates = [c]
      elif diff == min_diff:
        new_candidates.append(c)

    candidates = new_candidates

    # Get the graphs with the closest number of roots
    min_diff = sys.maxint
    new_candidates = []
    for c in candidates:
      diff = abs(g.graph['num_roots'] - self.properties['num_roots'])
      if diff < min_diff:
        new_candidates = [c]
      elif diff == min_diff:
        new_candidates.append(c)

    candidates = new_candidates

    # Take the graph with the smallest number of nodes
    candidates.sort(key=len)

    assert len(candidates) > 0, 'No graphs in candidate list'
    self.representative = candidates[0]

  def __str__(self):
      s = 'Cluster %s\n' % self.id
      s += "\t%-20s: %s\n" % ("Number of graphs", len(self.graphs))
      s += "\t%-20s:\n" % "Properties"
      for prop, value in self.properties.iteritems():
        s += "\t\t%-20s: %s\n" % (prop, value)
      s += "\t%-20s: %s\n" % ("Common writes", self.common_writes)

      return s




