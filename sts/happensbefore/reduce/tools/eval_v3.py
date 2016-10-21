import argparse
import os
import json
import re

import numpy as np


class Evaluation:
  def __init__(self, eval_folder, sim_log=None):

    print "Init"
    # Check if eval file exists
    assert os.path.exists(eval_folder), 'Folder %s does not exist' % eval_folder
    self.eval_folder = os.path.abspath(eval_folder)

    if sim_log is not None:
      assert os.path.exists(sim_log), 'Simulation log %s does not exist' % sim_log
      self.sim_log = os.path.abspath(sim_log)
    else:
      self.sim_log = None

    # Data dict
    self.eval_dicts = {}
    # Median
    self.median = {}

    # Prepare directory for results
    self.evaldir = os.path.join(self.eval_folder, 'evaluation')
    if not os.path.exists(self.evaldir):
      os.makedirs(self.evaldir)

    # Prepare evaluation Text File
    self.file = os.path.join(self.evaldir, 'eval_all.csv')
    self.median_file = os.path.join(self.evaldir, 'eval_median.csv')

  def run(self):
    # Fetch data
    self.fetch_data()
    if self.sim_log is not None:
      self.fetch_simulation_time()

    # Write eval file
    print "Write eval.csv file"
    print "Path %s" % self.file

    with open(self.file, 'w') as f:
      f.write("Controller,App,Topology,Steps,iter,# Events,# Races,# Isomorphic Clusters,# Final Clusters,"
              "Total Time,Hb_Graph,Preprocess hb_graph,Subgraphs,Init Clusters,Distance Matrix,Clustering\n")
      # Clustering information
      for controller in sorted(self.eval_dicts.keys()):
        if controller not in self.median:
          self.median[controller] = {}
        # Separate controller and module
        if controller.startswith('floodlight'):
          app = controller.replace('floodlight_', '')
          controller_str = 'Floodlight'
        elif controller.startswith('pox_eel'):
          app = controller.replace('pox_eel_', '')
          controller_str = 'POX EEL'
        else:
          raise RuntimeError("Unknown controller string %s" % controller)

        for topology in sorted(self.eval_dicts[controller].keys()):
          if topology not in self.median[controller]:
            self.median[controller][topology] = {}
          for steps in sorted(self.eval_dicts[controller][topology].keys()):
            if steps not in self.median[controller][topology]:
              self.median[controller][topology][steps] = {'controller_str': controller_str,
                                                          'app': app,
                                                          'topology': topology,
                                                          'steps': steps,
                                                          'n_events': [],
                                                          'n_graphs': [],
                                                          'n_iso': [],
                                                          'n_iso_timeout': [],
                                                          'n_iso_total': [],
                                                          'n_final': [],
                                                          't_t': [],
                                                          't_hb': [],
                                                          't_p': [],
                                                          't_s': [],
                                                          't_i': [],
                                                          't_dm': [],
                                                          't_c': [],
                                                          't_sim': [],
                                                          'num': 0}

            for i, data in sorted(self.eval_dicts[controller][topology][steps].iteritems()):
              # Add data for median
              self.median[controller][topology][steps]['num'] += 1
              self.median[controller][topology][steps]['n_events'].append(int(data['info']['Number of events']))
              self.median[controller][topology][steps]['n_graphs'].append(data['info']['Number of graphs'])
              self.median[controller][topology][steps]['n_iso'].append(
                  data['clustering']['info']['Number of clusters after iso'])
              self.median[controller][topology][steps]['n_iso_timeout'].append(data['clustering']['iso init timeout'])
              self.median[controller][topology][steps]['n_iso_total'].append(data['clustering']['iso init total'])
              self.median[controller][topology][steps]['n_final'].append(data['info']['Number of clusters'])
              self.median[controller][topology][steps]['t_t'].append(data['time']['total'])
              self.median[controller][topology][steps]['t_hb'].append(data['time']['hb_graph'])
              if data['sim_time'] is not None:
                self.median[controller][topology][steps]['t_sim'].append(data['sim_time'])

              # Generate output
              line = ""
              line += "%s," % controller_str
              line += "%s," % app
              line += "%s," % topology
              line += "%s," % str(steps)
              line += "%s," % str(i)  # Iteration number
              line += "%s," % data['info']['Number of events']
              line += "%s," % data['info']['Number of graphs']
              line += "%s," % data['clustering']['info']['Number of clusters after iso']
              line += "%s," % data['info']['Number of clusters']
              line += "%.3f s," % data['time']['total']
              line += "%.3f s," % data['time']['hb_graph']
              line += "%.3f s," % data['preprocessor']['time']['Total']
              line += "%.3f s," % data['subgraph']['time']['Total']
              line += "%.3f s," % data['clustering']['time']['Initialize cluster']
              line += "%.3f s," % data['clustering']['time']['Calculate distance matrix']
              line += "%.3f s," % \
                      (data['clustering']['time']['Calculate clustering'] +
                       data['clustering']['time']['Assign new clusters'])
              if data['sim_time'] is not None:
                line += "%.3f s" % data['sim_time']
              else:
                line += "N/A"
              line += "\n"
              f.write(line)

    with open(self.median_file, 'w') as f:
      # Average
      f.write("Controller,App,Topology,Steps,Number,# Events,# Races,# Isomorphic Clusters,# Timeouts,"
              "# Final Clusters,Total Time,Hb_Graph,Sim Time\n")
      for controller in sorted(self.median.keys()):
        for topology in sorted(self.median[controller].keys()):
          for steps, data in sorted(self.median[controller][topology].iteritems()):
            line = ""
            line += "%s," % data['controller_str']
            line += "%s," % data['app']
            line += "%s," % data['topology']
            line += "%s," % data['steps']
            line += "%s," % data['num']
            line += "%.3f," % np.median(data['n_events'])
            line += "%.3f," % np.median(data['n_graphs'])
            line += "%d (%.3f %%)," % (int(np.median(data['n_iso'])),
                                       float(np.median(data['n_iso'])) /
                                       float(np.median(data['n_graphs'])) * 100)
            if np.median(data['n_iso_total']) == 0:
              assert np.median(data['n_iso_timeout']) == 0, 'More timeouts than total'
              line += "0 (0%%),"
            else:
              line += "%d (%.3f %%)," % (int(np.median(data['n_iso_timeout'])),
                                         float(np.median(data['n_iso_timeout'])) /
                                         float(np.median(data['n_iso_total'])) * 100)

            line += "%d (%.3f %%)," % (int(np.median(data['n_final'])),
                                       float(np.median(data['n_final'])) /
                                       float(np.median(data['n_graphs'])) * 100)
            line += "%.3f s," % np.median(data['t_t'])
            line += "%.3f s," % np.median(data['t_hb'])
            if data['t_sim']:
              line += "%f s" % np.median(data['t_sim'])
            else:
              line += "N/A"
            line += "\n"

            f.write(line)

  def fetch_data(self):
    for folder in os.listdir(self.eval_folder):
      # Skip files
      if os.path.isfile(os.path.join(self.eval_folder, folder)):
        continue
      # Skip evaluation folder
      if folder == 'evaluation':
        continue

      print "Load trace %s" % folder
      # Try to read eval file
      eval_file = os.path.join(self.eval_folder, *[folder, 'reduce', 'eval.json'])
      try:
        with open(eval_file, 'r') as f:
          data = json.load(f)
          trace_info = folder

      except IOError:
        print "Could not load file: %s" % eval_file
        continue

      except ValueError:
        print "Could not load file: %s" % eval_file
        continue

      settings = trace_info.split('-')
      controller = settings[0]
      topology = settings[1]
      steps = int(re.search(r'\d+$', settings[2]).group())
      iteration = settings[3]

      if controller not in self.eval_dicts:
        self.eval_dicts[controller] = {}
      if topology not in self.eval_dicts[controller]:
        self.eval_dicts[controller][topology] = {}
      if steps not in self.eval_dicts[controller][topology]:
        self.eval_dicts[controller][topology][steps] = {}
      self.eval_dicts[controller][topology][steps][iteration] = data
      self.eval_dicts[controller][topology][steps][iteration]['sim_time'] = None

  def fetch_simulation_time(self):
    with open(self.sim_log, 'r') as f:
      for line in f:
        l = line.split(" ")
        # Only consider successfull simulations
        if l[1] == 'failed':
          print "Failed simulation: %s" % line
          continue
        settings = (l[0].split("/")[-1]).split('-')
        controller = settings[0]
        topology = settings[1]
        steps = int(re.search(r'\d+$', settings[2]).group())
        iteration = settings[3]
        try:
          self.eval_dicts[controller][topology][steps][iteration]['sim_time'] = float(l[2])
        except KeyError:
          print "Not in eval dicts: %s" % line


if __name__ == '__main__':
  # First call hb_graph.py and provide the same parameters
  # From hb_graph.py
  empty_delta = 1000000
  parser = argparse.ArgumentParser()
  parser.add_argument('eval_folder', help='Path to evaluation file produced by reduce.py (normally eval.json)')
  parser.add_argument('sim_log', help='Path to the simulation log file (optional)', default=None)

  args = parser.parse_args()

  evaluation = Evaluation(args.eval_folder, args.sim_log)
  evaluation.run()


