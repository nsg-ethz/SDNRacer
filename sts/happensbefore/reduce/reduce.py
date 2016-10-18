#!/usr/bin/env python

import sys
import os
import time
import shutil
import ConfigParser
import logging.config
import argparse
import json
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "./.."))
import hb_graph


class Reduce:
  def __init__(self, hb_graph, trace_file, thbgraph):
    tstart = time.clock()

    print ""
    print "########################################################################"
    print "#############################  CLUSTERING  #############################"
    print "########################################################################"
    print "Trace File: %s" % trace_file

    # Create separate results directory
    self.resultdir = os.path.join(os.path.dirname(trace_file), 'reduce')
    if not os.path.exists(self.resultdir):
      os.makedirs(self.resultdir)
    else:
      shutil.rmtree(self.resultdir)
      os.makedirs(self.resultdir)

    # Configure logger
    logdir = os.path.join(os.path.dirname(self.resultdir), 'log')
    if not os.path.exists(logdir):
      os.makedirs(logdir)
    logging.config.fileConfig(os.path.dirname(__file__) + '/logging.conf',
                              defaults={'logfilename': "%s/reduce.log" % logdir}, disable_existing_loggers=False)
    self.logger = logging.getLogger(__name__)

    # Import modules, this has to be done after the logger configuration because of the dynamic logging file path
    import preprocessor
    import clustering
    import subgraph
    import cluster_algorithm

    # Store copy of hb_graph and the harmful races
    self.hb_graph = hb_graph.g.copy()
    self.races = hb_graph.race_detector.races_harmful
    # Exit if there are no races in the trace
    if len(self.races) == 0:
      self.logger.info("There are no races in the trace.")
      sys.exit(0)

    # Parse config
    config = ConfigParser.RawConfigParser()
    config.read(os.path.dirname(__file__) + '/config.ini')

    # Initialize Class Preprocessor
    c_args = dict(config.items('preprocessor'))
    self.preprocessor = preprocessor.Preprocessor(self.hb_graph, self.races, **c_args)

    # Initialize Class Subgraph
    c_args = dict(config.items('subgraph'))
    self.subgraph = subgraph.Subgraph(self.hb_graph, self.races, self.resultdir, **c_args)

    # Initialize Class Clustering
    c_args = dict(config.items('clustering'))
    self.clustering = clustering.Clustering(self.resultdir, **c_args)

    # Initialize clustering algorithm
    c_args = dict(config.items('cluster_algorithm'))
    self.algorithm = cluster_algorithm.ClusterAlgorithm(self.resultdir, **c_args)

    # Eval dict
    self.eval = {'info': {},
                 'time': {}}
    self.eval['time']['Init'] = time.clock() - tstart
    self.eval['time']['hb_graph'] = thbgraph
    self.eval['info']['Number of events'] = len(hb_graph.g)
    return

  def run(self):
    tstart = time.clock()
    # Preprocessing
    self.logger.info("Preprocessing hb_graph")
    self.preprocessor.run()

    self.logger.info("Building subgraphs")
    # Building Subgraphs
    graphs = self.subgraph.run()

    # Clustering
    self.logger.info("Cluster graphs")
    self.clustering.run(graphs, self.algorithm)

    # Ranking
    tr = time.clock()
    for cluster in self.clustering.clusters:
      cluster.get_representative()
    self.eval['time']['ranking'] = time.clock() - tr

    # Store data for evaluation
    self.eval['time']['run'] = time.clock() - tstart
    self.eval['time']['total'] = self.eval['time']['hb_graph'] + self.eval['time']['Init'] + self.eval['time']['run']
    self.eval['preprocessor'] = self.preprocessor.eval
    self.eval['subgraph'] = self.subgraph.eval
    self.eval['clustering'] = self.clustering.eval

    self.eval['info']['Number of graphs'] = len(self.subgraph.subgraphs)
    self.eval['info']['Number of clusters'] = len(self.clustering.clusters)
    self.eval['info']['Remaining Graphs'] = len(self.clustering.remaining)

    for ind, cluster in enumerate(self.clustering.clusters):
      self.eval['Cluster %d' % ind] = {}
      self.eval['Cluster %d' % ind]['Number of graphs'] = len(cluster.graphs)
      self.eval['Cluster %d' % ind]['Properties'] = cluster.properties

    self.eval['graphs'] = []
    for graph in self.subgraph.subgraphs:
      # replace the race from the dictionary with just the event ids (race object not serializable)
      graph.graph['race'] = (graph.graph['race'].i_event.eid, graph.graph['race'].i_event.eid)
      self.eval['graphs'].append(graph.graph)

    with open(os.path.join(self.resultdir, 'eval.json'), 'w') as outfile:
      json.dump(self.eval, outfile)

    # Export clusters
    self.clustering.export_clusters()

    # Generate Info String
    # General Information
    s = ''
    s += "General Information\n"
    s += "\t%30s - %s\n" % ("Number of events", self.eval['info']['Number of events'])
    s += "\t%30s - %s\n" % ("Number of races", self.eval['info']['Number of graphs'])
    s += "\t%30s - %s\n" % ("Initialized clusters (iso)", self.eval['clustering']['info']['Number of clusters after iso'])
    s += "\t%30s - %s\n" % ("Final number of clusters", self.eval['info']['Number of clusters'])

    if self.eval['clustering']['iso init total']:
      s += "\t%30s - %s of %s (%f %%)\n" % \
           ("Iso init timeouts", self.eval['clustering']['iso init timeout'],
            self.eval['clustering']['iso init total'],
            float(self.eval['clustering']['iso init timeout']) / float(self.eval['clustering']['iso init total']))
    else:
      s += "\t%30s - %s\n" % ("Iso init timeouts", "N/A")

    # Cluster information
    for cluster in self.clustering.clusters:
      s += "\n%s" % cluster

    # Write time information
    # summary timing
    s += "Timing:\n"
    for k, v in self.eval['time'].iteritems():
      s += "%30s - %10.3f\n" % (k, v)

    # summary preprocessor
    s += "Timing preprocessor:\n"
    for k, v in self.eval['preprocessor']['time'].iteritems():
      s += "%30s - %10.3f\n" % (k, v)

    # summary subgraph
    s += "Timing subgraph:\n"
    for k, v in self.eval['subgraph']['time'].iteritems():
      s += "%30s - %10.3f\n" % (k, v)

    # summary clustering
    s += "Timing clustering:\n"
    for k, v in self.eval['clustering']['time'].iteritems():
      s += "%30s - %10.3f\n" % (k, v)

    # Write info file
    with open(os.path.join(self.resultdir, 'info.txt'), 'w') as outfile:
      outfile.write(s)

    # Print info 
    self.logger.info("\n" + s)

    return


def auto_int(x):
  return int(x, 0)


if __name__ == '__main__':
  # First call hb_graph.py and provide the same parameters
  # From hb_graph.py
  empty_delta = 1000000
  parser = argparse.ArgumentParser()
  parser.add_argument('trace_file',
                      help='Trace file produced by the instrumented sts, usually "hb.json"')

  parser.add_argument('--no-hbt', dest='no_hbt', action='store_true', default=False,
                      help="Don't add HB edges based on time")
  parser.add_argument('--time-delta', dest='delta', default=2, type=int,
                      help="delta time (in secs) for adding HB edges based on time")
  parser.add_argument('--pkt', dest='print_pkt', action='store_true', default=False,
                      help="Print packet headers in the produced dot files")
  parser.add_argument('--rw_delta', dest='rw_delta', default=2, type=int,
                      help="delta time (in secs) for adding HB edges based on time")
  parser.add_argument('--ww_delta', dest='ww_delta', default=2, type=int,
                      help="delta time (in secs) for adding HB edges based on time")
  parser.add_argument('--filter_rw', dest='filter_rw', action='store_true', default=False,
                      help="Filter Read/Write operations with HB relations")
  parser.add_argument('--ignore-ethertypes', dest='ignore_ethertypes', nargs='*',
                      type=auto_int, default=0,
                      help='Ether types to ignore from the graph')
  parser.add_argument('--no-race', dest='no_race', action='store_true', default=False,
                      help="Don't add edge between racing events in the visualized graph")
  parser.add_argument('--alt-barr', dest='alt_barr', action='store_true', default=False,
                      help="Use alternative barrier rules for purely reactive controllers")
  parser.add_argument('-v', dest='verbose', action='store_true', default=False,
                      help="Print all commute and harmful races")
  parser.add_argument('--ignore-first', dest='ignore_first', action='store_true',
                      default=False, help="Ignore the first race for per-packet consistency check")
  parser.add_argument('--disable-path-cache', dest='disable_path_cache', action='store_true',
                      default=False, help="Disable using all_pairs_shortest_path_length() preprocessing.")
  parser.add_argument('--data-deps', dest='data_deps', action='store_true',
                      default=False, help="Use shadow tables for adding data dependency edges between reads/writes.")
  parser.add_argument('--no-dot-files', dest='no_dot_files', action='store_true',
                      default=False, help="Do not write any .dot files to the disk.")
  parser.add_argument('--verify-and-minimize-only', dest='verify_and_minimize_only', action='store_true',
                      default=False, help="Verify the input trace, then write out a minimized version.")
  parser.add_argument('--is-minimized', dest='is_minimized', action='store_true',
                      default=False, help="Process a minimized trace.")

  args = parser.parse_args()
  if not args.no_hbt:
    if args.delta == empty_delta:
      assert args.rw_delta == args.ww_delta
    else:
      args.rw_delta = args.ww_delta = args.delta
  tstart = time.clock()
  m = hb_graph.Main(args.trace_file, print_pkt=args.print_pkt,
                    add_hb_time=not args.no_hbt, rw_delta=args.rw_delta, ww_delta=args.ww_delta,
                    filter_rw=args.filter_rw, ignore_ethertypes=args.ignore_ethertypes,
                    no_race=args.no_race, alt_barr=args.alt_barr, verbose=args.verbose,
                    ignore_first=args.ignore_first, disable_path_cache=args.disable_path_cache,
                    data_deps=args.data_deps, no_dot_files=args.no_dot_files,
                    verify_and_minimize_only=args.verify_and_minimize_only,
                    is_minimized=args.is_minimized)
  m.run()
  thbgraph = time.clock() - tstart
  r = Reduce(m.graph, args.trace_file, thbgraph)
  r.run()



