import logging.config
import itertools

logger = logging.getLogger(__name__)


class Cluster:
  _ids = itertools.count(0)

  def __init__(self, graphs=[]):
    self.id = Cluster._ids.next()   # Add cluster id to each group
    self.representative = None      # representative graph of the group
    self.graphs = []                # List of all graphs in the groups
    self.write_ids = []             # List of all ids of write-race-events
    self.properties = {             # Properties for "relation functions"
        'pingpong': 0,              # Percentage of graphs containing a controller-switch-pingpong
        'single': 0,                # Percentage of races origin from a single send event
        'return': 0,                # Percentage of races on the return path (contain HbHostHandle and HbHostSend)
        'write': 0                  # Percentage of graphs containing a common write event with another graph
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
    # Single Send
    single = [g for g in self.graphs if len(g.graph['roots']) == 1]
    self.properties['single'] = len(single) / float(len(self.graphs))

    # Return path
    ret = [g for g in self.graphs if len(g.graph['hosthandles']) > 0]
    self.properties['return'] = len(ret) / float(len(self.graphs))

    # Common write events
    common = 0
    # count each graph that has a write_race_id in common with another one
    for graph in self.graphs:
      for write_id in graph.graph['write_ids']:
        if self.write_ids.count(write_id) > 1:
          common += 1
          # Cont each graph only once! -> break
          break
    self.properties['write'] = common / float(len(self.graphs))

    # Pingpong
    self.properties['pingpong'] = len([g for g in self.graphs if g.graph['pingpong']]) / float(len(self.graphs))

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


