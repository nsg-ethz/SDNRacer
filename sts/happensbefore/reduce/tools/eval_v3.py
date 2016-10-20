import argparse
import os
import json
import re

import numpy as np
import matplotlib.pyplot as plt

class Evaluation:
  def __init__(self, eval_folder):

    print "Init"
    # Check if eval file exists
    assert os.path.exists(eval_folder), 'Folder %s does not exist' % eval_folder

    print eval_folder
    self.eval_folder = os.path.abspath(eval_folder)
    print self.eval_folder

    # Fetch data and store them based on controller and topology
    self.eval_dicts = {}
    self.num_traces = 0
    for folder in os.listdir(eval_folder):
      # Skip files
      if os.path.isfile(os.path.join(eval_folder, folder)):
        continue
      # Skip evaluation folder
      if folder == 'evaluation':
        continue

      print "Load trace %s" % folder
      # Try to read eval file
      eval_file = os.path.join(eval_folder, *[folder, 'reduce', 'eval.json'])
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
      self.num_traces += 1

    # Get number of different controllers/topology pairs
    self.num_cont_topo = 0
    self.num_sim = 0
    for controller in self.eval_dicts.keys():
      for topology in self.eval_dicts[controller].keys():
        self.num_cont_topo += 1
        self.num_sim += len(self.eval_dicts[controller][topology].keys())

    # average
    self.avg = {}

    # Prepare directory for results
    self.evaldir = os.path.join(self.eval_folder, 'evaluation')
    if not os.path.exists(self.evaldir):
      os.makedirs(self.evaldir)

    # Prepare evaluation Text File
    self.file = os.path.join(self.evaldir, 'eval.csv')

  def run(self):
    # Write eval file
    print "Write eval.csv file"
    print "Path %s" % self.file
    with open(self.file, 'w') as f:
      # Clustering information
      for controller in sorted(self.eval_dicts.keys()):
        if controller not in self.avg:
          self.avg[controller] = {}
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
          if topology not in self.avg[controller]:
            self.avg[controller][topology] = {}
          for steps in sorted(self.eval_dicts[controller][topology].keys()):
            if steps not in self.avg[controller][topology]:
              self.avg[controller][topology][steps] = {'controller_str': controller_str,
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
                                                       'num': 0}

            for i, data in sorted(self.eval_dicts[controller][topology][steps].iteritems()):
              # Add data for average
              self.avg[controller][topology][steps]['num'] += 1
              self.avg[controller][topology][steps]['n_events'].append(int(data['info']['Number of events']))
              self.avg[controller][topology][steps]['n_graphs'].append(data['info']['Number of graphs'])
              self.avg[controller][topology][steps]['n_iso'].append(data['clustering']['info']['Number of clusters after iso'])
              self.avg[controller][topology][steps]['n_iso_timeout'].append(data['clustering']['iso init timeout'])
              self.avg[controller][topology][steps]['n_iso_total'].append(data['clustering']['iso init total'])
              self.avg[controller][topology][steps]['n_final'].append(data['info']['Number of clusters'])
              self.avg[controller][topology][steps]['t_t'].append(data['time']['total'])
              self.avg[controller][topology][steps]['t_hb'].append(data['time']['hb_graph'])

      # Average
      f.write(
        "Controller,App,Topology,Steps,Number,# Events,# Races,# Isomorphic Clusters,# Final Clusters,"
        "Total Time,Hb_Graph\n")
      for controller in sorted(self.avg.keys()):
        for topology in sorted(self.avg[controller].keys()):
          for steps, data in sorted(self.avg[controller][topology].iteritems()):
            line = ""
            line += "%s," % data['controller_str']
            line += "%s," % data['app']
            line += "%s," % data['topology']
            line += "%s," % data['steps']
            line += "%s," % data['num']
            line += "%.3f," % np.median(data['n_events'])
            line += "%.3f," % np.median(data['n_graphs'])
            line += "%.3f (%.6f %%)," % (np.median(data['n_iso']),
                                         np.median(data['n_iso']) / float(np.median(data['n_graphs'])) * 100)
            line += "%.3f (%.6f %%)," % (np.median(data['n_iso_timeout']),
                                         np.median(data['n_iso_timeout']) / float(np.median(data['n_iso_total'])) * 100)
            line += "%.3f (%.6f %%)," % (np.median(data['n_final']),
                                         np.median(data['n_final']) / float(np.median(data['n_graphs'])) * 100)
            line += "%.3f s," % np.median(data['t_t'])
            line += "%.3f s\n" % np.median(data['t_hb'])
            f.write(line)


if __name__ == '__main__':
  # First call hb_graph.py and provide the same parameters
  # From hb_graph.py
  empty_delta = 1000000
  parser = argparse.ArgumentParser()
  parser.add_argument('eval_folder', help='Path to evaluation file produced by reduce.py (normally eval.json)')

  args = parser.parse_args()

  evaluation = Evaluation(args.eval_folder)
  evaluation.run()


