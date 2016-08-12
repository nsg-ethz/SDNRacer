import argparse
import os
import shutil
import json

import matplotlib.pyplot as plt


class Evaluation:
  def __init__(self, eval_folder):
    # Check if eval file exists
    assert os.path.exists(eval_folder), 'Folder %s does not exist' % eval_folder

    self.eval_folder = eval_folder

    self.eval_dicts = []
    for folder in os.listdir(eval_folder):
      print folder
      eval_file = os.path.join(eval_folder, *[folder, 'reduce', 'eval.json'])
      try:
        with open(eval_file, 'r') as f:
          self.eval_dicts.append(json.load(f))
          self.eval_dicts[-1]['trace_info'] = folder

      except IOError:
        print "Could not load file: %s" % eval_file
        continue

    # Prepare directory for results
    self.evaldir = os.path.join(os.path.dirname(self.eval_folder), 'evaluation')
    if os.path.exists(self.evaldir):
      shutil.rmtree(self.evaldir)
    os.makedirs(self.evaldir)

  def run(self):
    # Evaluate score functions
    # Generate boxplot
    fig = plt.figure()
    plt.hold(True)

    num_colums = 2
    num_rows = (len(self.eval_dicts) + 1) / 2

    for ind, eval_dict in enumerate(self.eval_dicts):
      row = ind / 2
      col = ind % 2
      # Calculate the percentage each function adds to each score
      percentage = {'iso': [],
                    'write': [],
                    'dataplane': [],
                    'pingpong': [],
                    'single': [],
                    'return': []}

      for i in xrange(0, len(eval_dict)):
        if eval_dict['total'][i] !=0:
          percentage['iso'].append(eval_dict['iso'][i] / eval_dict['total'][i])
          percentage['write'].append(eval_dict['write'][i] / eval_dict['total'][i])
          percentage['dataplane'].append(eval_dict['dataplane'][i] / eval_dict['total'][i])
          percentage['pingpong'].append(eval_dict['pingpong'][i] / eval_dict['total'][i])
          percentage['single'].append(eval_dict['single'][i] / eval_dict['total'][i])
          percentage['return'].append(eval_dict['return'][i] / eval_dict['total'][i])

      values = []
      labels = []
      for k, v in percentage.iteritems():
        values.append(v)
        labels.append(k)

      ax = plt.subplot2grid((num_rows, num_colums), (row, col))
      ax.set_title(eval_dict['trace_info'], fontsize=5)
      ax.boxplot(values, labels=labels)
      ax.set_ylim([0, 1])
      plt.xticks(rotation=40)

    plt.tight_layout()
    fig.savefig(os.path.join(self.evaldir, 'socre_functions_percentage.pdf'))

    # Create timing graph
    fig = plt.figure()
    plt.hold(True)

    t_total = []
    t_init = []
    t_subg = []
    t_prep = []
    t_clust = []
    t_rank = []
    labels = []
    x_values = range(0, len(self.eval_dicts))
    for eval_dict in self.eval_dicts:
      if 't_toatl' in eval_dict:
        t_total.append(eval_dict['t_toatl'])
      else:
        t_total.append(eval_dict['t_total'])

      t_init.append(eval_dict['t_init'])
      t_subg.append(eval_dict['t_subg'])
      t_prep.append(eval_dict['t_prep'])
      t_clust.append(eval_dict['t_clust'])
      t_rank.append(eval_dict['t_rank'])
      labels.append(eval_dict['trace_info'])

    plt.plot(x_values, t_total, 'ro')
    plt.xticks(x_values, labels, rotation=40)

    plt.tight_layout()
    fig.savefig(os.path.join(self.evaldir, 'timing_information.pdf'))

if __name__ == '__main__':
  # First call hb_graph.py and provide the same parameters
  # From hb_graph.py
  empty_delta = 1000000
  parser = argparse.ArgumentParser()
  parser.add_argument('eval_folder', help='Path to evaluation file produced by reduce.py (normally eval.json)')

  args = parser.parse_args()

  evaluation = Evaluation(args.eval_folder)
  evaluation.run()


