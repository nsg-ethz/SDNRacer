import argparse
import os
import shutil
import json
import re

import numpy as np
import matplotlib.pyplot as plt

class Evaluation:
  """
  This script is to export data from floodlight loadbalancer startopology to a csv for graph generation.
  """
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

      # Skip all except floodlight_loadbalancer-StarTopology
      if not folder.startswith("floodlight_loadbalancer-StarTopology"):
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

      if steps not in self.eval_dicts:
        self.eval_dicts[steps] = []
      self.eval_dicts[steps].append(data)

    self.evaldir = os.path.join(self.eval_folder, 'evaluation')
    if not os.path.exists(self.evaldir):
      os.makedirs(self.evaldir)

    # Prepare evaluation Text File
    self.file = os.path.join(self.evaldir, 'loadbalancer.csv')

  def run(self):
    # Write eval file
    with open(self.file, 'w') as f:
      f.write("steps, races, clusters\n")
      # Clustering information
      for steps, data_list in sorted(self.eval_dicts.iteritems()):
         for data in data_list:
            f.write("%d, %d, %d\n" % (steps, data['info']['Number of graphs'], data['info']['Number of clusters']))


if __name__ == '__main__':
  # First call hb_graph.py and provide the same parameters
  # From hb_graph.py
  empty_delta = 1000000
  parser = argparse.ArgumentParser()
  parser.add_argument('eval_folder', help='Path to evaluation file produced by reduce.py (normally eval.json)')

  args = parser.parse_args()

  evaluation = Evaluation(args.eval_folder)
  evaluation.run()


