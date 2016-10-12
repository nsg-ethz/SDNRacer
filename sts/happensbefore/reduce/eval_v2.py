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

    # Prepare directory for results
    self.evaldir = os.path.join(self.eval_folder, 'evaluation')
    if os.path.exists(self.evaldir):
      shutil.rmtree(self.evaldir)
    os.makedirs(self.evaldir)

    # Prepare evaluation Text File
    self.file = os.path.join(self.evaldir, 'eval.txt')

  def run(self):
    # Write eval file
    print "Write eval.txt file"
    print "Path %s" % self.file
    with open(self.file, 'w') as f:
      # Clustering information
      for controller in sorted(self.eval_dicts.keys()):
        for topology in sorted(self.eval_dicts[controller].keys()):
          controller_str = ""
          for s in controller.split("_"):
            controller_str += ("%s " % s.capitalize())
          f.write("%s%s\n" % (controller_str, topology))
          f.write("Steps\tIteration\t# Events\t# Races\t# Isomorphic Clusters\t# Final Clusters\t"
                  "Cluster 0\tCluster 1\tCluster 2\tCluster 3\tTotal Time\tHb_Graph\tPreprocess hb_graph\t"
                  "Subgraphs\tInit Clusters (iso)\tDistance Matrix\tClustering\n")
          for steps in sorted(self.eval_dicts[controller][topology].keys()):
            for i, data in sorted(self.eval_dicts[controller][topology][steps].iteritems()):
              line = "%s\t" % str(steps)  # Number of steps
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

if __name__ == '__main__':
  # First call hb_graph.py and provide the same parameters
  # From hb_graph.py
  empty_delta = 1000000
  parser = argparse.ArgumentParser()
  parser.add_argument('eval_folder', help='Path to evaluation file produced by reduce.py (normally eval.json)')

  args = parser.parse_args()

  evaluation = Evaluation(args.eval_folder)
  evaluation.run()


