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
    self.paper_file = os.path.join(self.evaldir, 'paper.csv')

    # Rename dictionary (change names for table)
    self.r_dict = {'BinaryLeafTreeTopology': 'BinTree',
                   'StarTopology': 'Single',
                   'MeshTopology': 'Linear',
                   'circuitpusher': 'CircuitPusher',
                   'firewall': 'Adm. Ctrl.',
                   'loadbalancer': 'LoadBalancer',
                   'forwarding': 'Forwarding',
                   'l2_multi': 'Forwarding',
                   'learningswitch': 'LearningSwitch',
                   '_fixed': ' Fx'}

    # Expected simulations number of steps
    self.exp_steps = [200, 400, 600, 800, 1000]

  def run(self):
    print "Write Output"
    # Fetch data
    self.fetch_data()
    if self.sim_log is not None:
      self.fetch_simulation_time()

    # Write eval file
    with open(self.file, 'w') as f:
      f.write("App,Topology,Controller,Steps,iter,# Events,# Races,# Isomorphic Clusters,# Final Clusters,"
              "Total Time,Hb_Graph,Preprocess hb_graph,Subgraphs,Init Clusters,Distance Matrix,Clustering\n")
      # Clustering information
      for app in sorted(self.eval_dicts.keys()):
        if app not in self.median:
          self.median[app] = {}
        for topology in sorted(self.eval_dicts[app].keys()):
          if topology not in self.median[app]:
            self.median[app][topology] = {}
          for controller in sorted(self.eval_dicts[app][topology].keys()):
            if controller not in self.median[app][topology]:
              self.median[app][topology][controller] = {}
            for steps in sorted(self.eval_dicts[app][topology][controller].keys()):
              if steps not in self.median[app][topology][controller]:
                self.median[app][topology][controller][steps] = {'n_events': [],
                                                                 'n_graphs': [],
                                                                 'n_iso': [],
                                                                 'n_iso_timeout': [],
                                                                 'n_iso_total': [],
                                                                 'n_final': [],
                                                                 'n_gpc': [],           # Number of graphs per clusters
                                                                 't_t': [],
                                                                 't_hb': [],
                                                                 't_sim': [],
                                                                 'num': 0}

              for i, data in sorted(self.eval_dicts[app][topology][controller][steps].iteritems()):
                # Add data for median
                self.median[app][topology][controller][steps]['num'] += 1
                self.median[app][topology][controller][steps]['n_events'].append(int(data['info']['Number of events']))
                self.median[app][topology][controller][steps]['n_graphs'].append(data['info']['Number of graphs'])
                self.median[app][topology][controller][steps]['n_iso'].append(
                    data['clustering']['info']['Number of clusters after iso'])
                self.median[app][topology][controller][steps]['n_iso_timeout'].append(
                    data['clustering']['iso init timeout'])
                self.median[app][topology][controller][steps]['n_iso_total'].append(
                    data['clustering']['iso init total'])
                self.median[app][topology][controller][steps]['n_final'].append(data['info']['Number of clusters'])
                self.median[app][topology][controller][steps]['t_t'].append(data['time']['total'])
                self.median[app][topology][controller][steps]['t_hb'].append(data['time']['hb_graph'])
                if data['sim_time'] is not None:
                  self.median[app][topology][controller][steps]['t_sim'].append(data['sim_time'])

                clust_num = 0
                while True:
                  c_str = 'Cluster %d' % clust_num
                  if c_str in data:
                    self.median[app][topology][controller][steps]['n_gpc'].append(data[c_str]['Number of graphs'])
                  else:
                    break
                  clust_num += 1

                # Generate output
                line = ""
                line += "%s," % app
                line += "%s," % topology
                line += "%s," % controller
                line += "%s," % steps
                line += "%s," % i
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
      f.write(",,,,,SDNRacer,,,BigBug,,,,Clusters,,,Timing,,,,,\n")
      f.write("App,Topology,Controller,Steps,,Events,Races,,Isomorphic Clusters,Timeouts,"
              "Final Clusters,,Mean,s.d.,,Total,STS,SDNRacer,BigBug\n")
      for app in sorted(self.median.keys()):
        for topology in sorted(self.median[app].keys()):
          for controller in sorted(self.median[app][topology].keys()):
            for steps in self.exp_steps:
              # Trace Info
              line = ""
              line += "%s," % app
              line += "%s," % topology
              line += "%s," % controller
              line += "%s,," % steps

              if steps in self.median[app][topology][controller]:
                data = self.median[app][topology][controller][steps]
                # SDNRacer Info
                line += "%d," % round(np.median(data['n_events']))
                line += "%d,," % round(np.median(data['n_graphs']))
                # BigBug Info
                line += "%.2f (%.2f %%)," % (round(np.median(data['n_iso']), 2),
                                             round(float(np.median(data['n_iso'])) /
                                             float(np.median(data['n_graphs'])) * 100, 2))
                if np.median(data['n_iso_total']) == 0:
                  assert np.median(data['n_iso_timeout']) == 0, 'More timeouts than total'
                  line += "0 (0.00 %),"
                else:
                  line += "%d (%.2f %%)," % (round(np.median(data['n_iso_timeout'])),
                                             round(float(np.median(data['n_iso_timeout'])) /
                                             float(np.median(data['n_iso_total'])) * 100, 2))
                line += "%d (%.2f %%),," % (round(np.median(data['n_final'])),
                                            round(float(np.median(data['n_final'])) /
                                            float(np.median(data['n_graphs'])) * 100, 2))
                # Graphs per Cluster
                line += "%.2f," % round(np.median(data['n_gpc']), 2)
                line += "%.2f,," % round(np.std(data['n_gpc']), 2)

                # Timing Info
                tot = float(np.median(data['t_t']))
                sdnracer = float(np.median(data['t_hb']))
                bigbug = tot - sdnracer
                if data['t_sim']:
                  sim = float(np.median(data['t_sim']))
                  tot += sim

                  line += "%.3f s," % round(tot, 3)
                  line += "%.3f s," % round(sim, 3)
                else:
                  line += "N/A,N/A,"

                line += "%.3f s," % round(sdnracer, 3)
                line += "%.3f s" % round(bigbug, 3)

                line += "\n"
              else:
                # Fill line with N/A if no data is available
                line += "N/A,N/A,,N/A,N/A,N/A,,N/A,N/A,,N/A,N/A,N/A,N/A\n"

              f.write(line)

  def fetch_data(self):
    print "Fetch Data"
    for folder in os.listdir(self.eval_folder):
      # Skip files
      if os.path.isfile(os.path.join(self.eval_folder, folder)):
        continue
      # Skip evaluation folder
      if folder == 'evaluation':
        continue

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

      app, topology, controller, steps, iteration = self.get_settings(trace_info)

      if app not in self.eval_dicts:
        self.eval_dicts[app] = {}
      if topology not in self.eval_dicts[app]:
        self.eval_dicts[app][topology] = {}
      if controller not in self.eval_dicts[app][topology]:
        self.eval_dicts[app][topology][controller] = {}
      if steps not in self.eval_dicts[app][topology][controller]:
        self.eval_dicts[app][topology][controller][steps] = {}
      self.eval_dicts[app][topology][controller][steps][iteration] = data
      self.eval_dicts[app][topology][controller][steps][iteration]['sim_time'] = None

  def fetch_simulation_time(self):
    print "Fetch simulation times"
    with open(self.sim_log, 'r') as f:
      for line in f:
        l = line.split(" ")
        # Only consider successful simulations
        if l[1] == 'failed':
          print "Failed simulation: %s" % line
          continue
        trace_info = l[0].split("/")[-1]

        app, topology, controller, steps, iteration = self.get_settings(trace_info)

        try:
          self.eval_dicts[app][topology][controller][steps][iteration]['sim_time'] = float(l[2])
        except KeyError:
          # print "Not in eval dicts: %s" % line
          pass

  def rename(self, s):
    for k, v in self.r_dict.iteritems():
      s = s.replace(k, v)
    return s

  def get_settings(self, trace_string):
    settings = trace_string.split('-')
    controller = self.rename(settings[0])
    # Separate controller and module
    if controller.startswith('floodlight'):
      app = controller.replace('floodlight_', '')
      if app.endswith(' Fx'):
        app = app[:-3]
        controller = "Floodlight Fx"
      else:
        controller = 'Floodlight'
    elif controller.startswith('pox_eel'):
      app = controller.replace('pox_eel_', '')
      if app.endswith(' Fx'):
        app = app[:-3]
        controller = "POX EEL Fx"
      else:
        controller = 'POX EEL'
    else:
      raise RuntimeError("Unknown controller string %s" % controller)
    topology = self.rename(settings[1])
    steps = int(re.search(r'\d+$', settings[2]).group())
    iteration = settings[3]

    return app, topology, controller, steps, iteration


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
