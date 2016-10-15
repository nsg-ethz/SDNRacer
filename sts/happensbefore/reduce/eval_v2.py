import argparse
import os
import shutil
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
    self.file = os.path.join(self.evaldir, 'eval.txt')

  def run(self):
    # Write eval file
    print "Write eval.txt file"
    print "Path %s" % self.file
    with open(self.file, 'w') as f:
      f.write("Controller\tApp\tTopology\tSteps\tIteration\t# Events\t# Races\t# Isomorphic Clusters\t# Final Clusters\t"
              "Cluster 0\tCluster 1\tCluster 2\tCluster 3\tTotal Time\tHb_Graph\tPreprocess hb_graph\t"
              "Subgraphs\tInit Clusters (iso)\tDistance Matrix\tClustering\n")
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
                                                       'n_events': 0,
                                                       'n_graphs': 0,
                                                       'n_iso': 0,
                                                       'n_final': 0,
                                                       't_t': 0,
                                                       't_hb': 0,
                                                       't_p': 0,
                                                       't_s': 0,
                                                       't_i': 0,
                                                       't_dm': 0,
                                                       't_c': 0,
                                                       'num': 0}

            for i, data in sorted(self.eval_dicts[controller][topology][steps].iteritems()):
              # Add data for average
              self.avg[controller][topology][steps]['num'] += 1
              self.avg[controller][topology][steps]['n_events'] += int(data['info']['Number of events'])
              self.avg[controller][topology][steps]['n_graphs'] += data['info']['Number of graphs']
              self.avg[controller][topology][steps]['n_iso'] += data['clustering']['info']['Number of clusters after iso']
              self.avg[controller][topology][steps]['n_final'] += data['info']['Number of clusters']
              self.avg[controller][topology][steps]['t_t'] += data['time']['total']
              self.avg[controller][topology][steps]['t_hb'] += data['time']['hb_graph']

              # Generate output
              line = ""
              line += "%s\t" % controller_str
              line += "%s\t" % app
              line += "%s\t" % topology
              line += "%s\t" % str(steps)
              line += "%s\t" % str(i)  # Iteration number
              line += "%s\t" % data['info']['Number of events']
              line += "%s\t" % data['info']['Number of graphs']
              line += "%s\t" % data['clustering']['info']['Number of clusters after iso']
              line += "%s\t" % data['info']['Number of clusters']
              for ind in xrange(0, 4):
                if 'Cluster %d' % ind in data:
                  line += "%s\t" % data['Cluster %d' % ind]['Number of graphs']
                else:
                  line += "-\t"
              line += "%.3f s\t" % data['time']['total']
              line += "%.3f s\t" % data['time']['hb_graph']
              line += "%.3f s\t" % data['preprocessor']['time']['Total']
              line += "%.3f s\t" % data['subgraph']['time']['Total']
              line += "%.3f s\t" % data['clustering']['time']['Initialize cluster']
              line += "%.3f s\t" % data['clustering']['time']['Calculate distance matrix']
              line += "%.3f s\t" % \
                      (data['clustering']['time']['Calculate clustering'] +
                       data['clustering']['time']['Assign new clusters'])
              line += "\n"
              f.write(line)

      # Average
      f.write("\n\n\Average\n")
      f.write(
        "Controller\tApp\tTopology\tSteps\tIterations\t# Events\t# Races\t# Isomorphic Clusters\t# Final Clusters\t"
        "Total Time\tHb_Graph\t\n")
      for controller in sorted(self.avg.keys()):
        for topology in sorted(self.avg[controller].keys()):
          for steps, data in sorted(self.avg[controller][topology].iteritems()):
            line = ""
            line += "%s\t" % data['controller_str']
            line += "%s\t" % data['app']
            line += "%s\t" % data['topology']
            line += "%s\t" % data['steps']
            line += "%s\t" % data['num']
            line += "%.3f\t" % (data['n_events'] / float(data['num']))
            line += "%.3f\t" % (data['n_graphs'] / float(data['num']))
            line += "%.3f\t" % (data['n_iso'] / float(data['num']))
            line += "%.3f\t" % (data['n_final'] / float(data['num']))
            line += "%.3f s\t" % (data['t_t'] / float(data['num']))
            line += "%.3f s\t" % (data['t_hb'] / float(data['num']))
            line += "\n"
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


