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
    for controller in self.eval_dicts.keys():
      self.num_cont_topo += len(self.eval_dicts[controller].keys())

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

    num_colums = 2
    num_rows = (self.num_traces + 1) / 2

    num = 0
    for controller in sorted(self.eval_dicts.keys()):
      for topology in sorted(self.eval_dicts[controller].keys()):
        for steps, data in sorted(self.eval_dicts[controller][topology].iteritems()):
          print "\t Generate graph for %s, %s, %s steps" % (controller, topology, steps)
          row = num / 2
          col = num % 2
          # Calculate the percentage each function adds to each score
          percentage = {'iso': [],
                        'write': [],
                        'dataplane': [],
                        'pingpong': [],
                        'single': [],
                        'return': []}

          for i in xrange(0, len(data['total'])):
            if data['total'][i] != 0:
              iso = data['iso'][i] / float(data['total'][i])
              write = data['write'][i] / float(data['total'][i])
              dataplane = data['dataplane'][i] / float(data['total'][i])
              pingpong = data['pingpong'][i] / float(data['total'][i])
              single = data['single'][i] / float(data['total'][i])
              ret = data['return'][i] / float(data['total'][i])
              total = iso + write + dataplane + pingpong + single + ret
              info = 'Total: %f \n' % total
              info += "Data['total']: %f \n" % data['total'][i]
              info += 'iso: %f' % iso
              info += 'write: %f' % write
              info += 'dataplane: %f' % dataplane
              info += 'pingpong: %f' % pingpong
              info += 'single: %f' % single
              info += 'ret: %f' % ret

              assert abs(total - 1) < 0.001, info

            else:
              iso = 0
              write = 0
              dataplane = 0
              pingpong = 0
              single = 0
              ret = 0

              assert data['iso'][i] == 0 and data['write'][i] == 0 and data['dataplane'][i] == 0 and \
                     data['pingpong'][i] == 0 and data['single'][i] == 0 and data['return'][i] == 0, \
                     'Total is 0 but not parts of the score are'

            percentage['iso'].append(iso)
            percentage['write'].append(write)
            percentage['dataplane'].append(dataplane)
            percentage['pingpong'].append(pingpong)
            percentage['single'].append(single)
            percentage['return'].append(ret)

          values = []
          labels = []
          for k, v in percentage.iteritems():
            values.append(v)
            labels.append(k)

          ax = plt.subplot2grid((num_rows, num_colums), (row, col))
          ax.set_title("%s, %s, %s steps" % (controller, topology, steps), fontsize=fs)
          ax.set_ylabel('Part of score', fontsize=fs)
          ax.boxplot(values, labels=labels)
          ax.set_ylim([0, 1])
          plt.yticks(fontsize=fs)
          plt.xticks(rotation=0, fontsize=fs)

          num += 1

    plt.tight_layout()
    fig.savefig(os.path.join(self.evaldir, 'score_functions_percentage.pdf'))

    # Create timing graph for each controller and module
    print "Evaluate timing information"
    fig = plt.figure()
    plt.hold(True)

    # One subplot for each controller and topology
    num = 0
    color = plt.cm.rainbow(np.linspace(0, 1, 7))
    for controller in self.eval_dicts.keys():
      for topology in self.eval_dicts[controller].keys():
        print "\tCalculate graph for %s, %s" % (controller, topology)
        ax = plt.subplot2grid((self.num_cont_topo, 1), (num, 0))
        ax.set_title("%s, %s" % (controller, topology), fontsize=fs)
        t_total = []
        t_init = []
        t_subg = []
        t_prep = []
        t_clust = []
        t_rank = []
        x_values = []
        for steps, data in sorted(self.eval_dicts[controller][topology].iteritems()):
          x_values.append(steps)
          if 't_toatl' in data:
            t_total.append(data['t_toatl'])
          else:
            t_total.append(data['t_total'])

          t_init.append(data['t_init'])
          t_subg.append(data['t_init'] + data['t_subg'])
          t_prep.append(data['t_init'] + data['t_subg'] + data['t_prep'])
          t_clust.append(data['t_init'] + data['t_subg'] + data['t_prep'] + data['t_clust'])
          t_rank.append(data['t_init'] + data['t_subg'] + data['t_prep'] + data['t_clust'] + data['t_rank'])

        alpha = 1.0
        plt.fill_between(x_values, t_init, [0] * len(t_init), facecolor=color[1], alpha=alpha)
        plt.fill_between(x_values, t_subg, t_init, facecolor=color[2], alpha=alpha)
        plt.fill_between(x_values, t_prep, t_subg, facecolor=color[3], alpha=alpha)
        plt.fill_between(x_values, t_clust, t_prep, facecolor=color[4], alpha=alpha)
        plt.fill_between(x_values, t_rank, t_clust, facecolor=color[5], alpha=alpha)

        plt.plot(x_values, t_init, label='Init', c=color[1])
        plt.plot(x_values, t_subg, label='Subgraph', c=color[2])
        plt.plot(x_values, t_prep, label='Preprocessing', c=color[3])
        plt.plot(x_values, t_clust, label='Iso Cluster', c=color[4])
        plt.plot(x_values, t_rank, label='Ranking', c=color[5])

        plt.plot(x_values, t_total, label='Total', lw=2, c='black')

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
            if 'num_races' in data:
              num_races = data['num_races']
            else:
              num_races = 0

            if 'num_clusters' in data:
              num_clusters = data['num_clusters']
            else:
              num_clusters = 0
            line = "| %26s | %25s | %5d | %8d | %11d | %14.3f |\n" % \
                   (controller, topology, steps, num_races, num_clusters, data['t_total'])
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


