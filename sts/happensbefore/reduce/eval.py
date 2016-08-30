import argparse
import os
import shutil
import json
import re

import numpy as np
import matplotlib.pyplot as plt

# Parameters
ts = 6  # Titlesize
fs = 6  # Fontsize


class Evaluation:
  def __init__(self, eval_folder):

    print "Init"
    # Check if eval file exists
    assert os.path.exists(eval_folder), 'Folder %s does not exist' % eval_folder

    self.eval_folder = eval_folder

    # Fetch data and store them based on controller and topology
    self.eval_dicts = {}
    self.num_traces = 0
    for folder in os.listdir(eval_folder):
      print "Load trace %s" % folder
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
      if controller not in self.eval_dicts:
        self.eval_dicts[controller] = {}
      if topology not in self.eval_dicts[controller]:
        self.eval_dicts[controller][topology] = {}

      self.eval_dicts[controller][topology][steps] = data
      self.num_traces += 1

    # Get number of different controllers/topology pairs
    self.num_cont_topo = 0
    self.num_sim = 0
    for controller in self.eval_dicts.keys():
      for topology in self.eval_dicts[controller].keys():
        self.num_cont_topo += 1
        self.num_sim += len(self.eval_dicts[controller][topology].keys())

    # Prepare directory for results
    self.evaldir = os.path.join(os.path.dirname(self.eval_folder), 'evaluation')
    if os.path.exists(self.evaldir):
      shutil.rmtree(self.evaldir)
    os.makedirs(self.evaldir)

    # Prepare evaluation Text File
    self.file = os.path.join(self.evaldir, 'eval.txt')

  def run(self):
    print "Evaluate Score functions"
    # Evaluate score functions
    # Generate boxplot
    fig = plt.figure()
    plt.hold(True)

    num = 0
    for controller in sorted(self.eval_dicts.keys()):
      for topology in sorted(self.eval_dicts[controller].keys()):
        n = len(self.eval_dicts[controller][topology].keys())
        ind = np.arange(n)

        width = 0.25

        pingpong = []
        single = []
        return_path = []
        labels = []

        plot_graph = False
        for steps, data in sorted(self.eval_dicts[controller][topology].iteritems()):
          if 'graph' not in data:
            continue
          else:
            plot_graph = True

          print "\t Generate graph for %s, %s, %s steps" % (controller, topology, steps)
          # Calculate the percentage of the properties in each graph
          pingpong.append(len([x for x in data['graphs'] if x['pingpong']]) / len(data['graphs']) * 100)
          single.append(len([x for x in data['graphs'] if x['single']]) / len(data['graphs']) * 100)
          return_path.append(len([x for x in data['graphs'] if x['return']]) / len(data['graphs']) * 100)
          labels.append(str(steps))

        if not plot_graph:
          continue

        # Plot
        ax = plt.subplot2grid((self.num_cont_topo, 1), (num, 0))
        bar1 = plt.bar(ind, pingpong, width, color='b')
        bar2 = plt.bar(ind + width, single, width, color='g')
        bar3 = plt.bar(ind + (2 * width), return_path, width, color='r')

        ax.set_title("%s, %s" % (controller, topology), fontsize=fs)
        ax.set_ylabel('Percentage of graph property')
        ax.set_xticks(ind + 1.5 * width)
        ax.set_xticklabels(labels)

        ax.legend((bar1, bar2, bar3), ('pingpong', 'single send', 'return path'))

        num += 1

    plt.tight_layout()
    fig.savefig(os.path.join(self.evaldir, 'graph_properties.pdf'))

    # Create timing graph for each controller and module
    print "Evaluate timing information"
    fig = plt.figure()
    plt.hold(True)

    # One subplot for each controller and topology
    num = 0
    for controller in self.eval_dicts.keys():
      for topology in self.eval_dicts[controller].keys():
        print "\tCalculate graph for %s, %s" % (controller, topology)
        ax = plt.subplot2grid((self.num_cont_topo, 1), (num, 0))
        ax.set_title("%s, %s" % (controller, topology), fontsize=fs)
        t_total = []
        t_hb_graph = []
        x_values = []
        for steps, data in sorted(self.eval_dicts[controller][topology].iteritems()):
          x_values.append(steps)
          t_total.append(data['time']['total'])
          t_hb_graph.append(data['time']['hb_graph'])

        alpha = 0.5
        plt.fill_between(x_values, t_hb_graph, [0] * len(t_hb_graph), facecolor='r', alpha=alpha)
        plt.fill_between(x_values, t_total, t_hb_graph, facecolor='b', alpha=alpha)

        plt.plot(x_values, t_hb_graph, label='HbGraph', c='r')
        plt.plot(x_values, t_total, label='Total', c='b')

        ax.legend(loc='upper left', prop={'size': 6})

        ax.set_ylabel('Time [s]')
        ax.set_xlabel('Number of Steps')
        ax.set_xticks(x_values)

        num += 1

    plt.tight_layout()
    fig.savefig(os.path.join(self.evaldir, 'timing_information.pdf'))

    # Write some other infos to the eval file
    with open(self.file, 'w') as f:
      title = "| %26s | %25s | %5s | %8s | %11s | %10s [s] |\n" % \
              ('Controller', 'Topology', 'Steps', 'NumRaces', 'NumClusters', 'TotTime')
      sep_line = "-" * len(title) + "\n"
      f.write(title)
      for controller in sorted(self.eval_dicts.keys()):
        f.write(sep_line)
        for topology in sorted(self.eval_dicts[controller].keys()):
          for steps, data in sorted(self.eval_dicts[controller][topology].iteritems()):
            num_races = data['info']['Number of graphs']
            num_clusters = data['info']['Number of clusters']
            t_total = data['time']['total']

            line = "| %26s | %25s | %5d | %8d | %11d | %14.3f |\n" % \
                   (controller, topology, steps, num_races, num_clusters, t_total)
            f.write(line)

      f.write(sep_line)


if __name__ == '__main__':
  # First call hb_graph.py and provide the same parameters
  # From hb_graph.py
  empty_delta = 1000000
  parser = argparse.ArgumentParser()
  parser.add_argument('eval_folder', help='Path to evaluation file produced by reduce.py (normally eval.json)')

  args = parser.parse_args()

  evaluation = Evaluation(args.eval_folder)
  evaluation.run()


