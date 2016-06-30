#!/usr/bin/env python

import sys
import os
import ConfigParser
import logging.config
import argparse
import time

import networkx as nx

sys.path.append(os.path.join(os.path.dirname(__file__), "./.."))
import hb_graph


class Reduce:
  def __init__(self, hb_graph, trace_file):
    print ""
    print ""
    print "########################################################################"
    print ""

    # Create separate results directory
    self.resultdir = os.path.join(os.path.dirname(trace_file), 'reduce')
    if not os.path.exists(self.resultdir):
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
    import cluster
    import subgraph

    # Parse config
    config = ConfigParser.RawConfigParser()
    config.read(os.path.dirname(__file__) + '/config.ini')

    # Create Clustering object if not disabled
    if not config.getboolean('general', 'no_cluster'):
      if config.has_section('cluster'):
        clusterargs = dict(config.items('cluster'))
      else:
        clusterargs = {}

      self.cluster = cluster.Cluster(self.resultdir, **clusterargs)
    else:
      self.cluster = None

    # Create Preprocessor Object if not disabled
    if not config.getboolean('general', 'no_preprocess'):
      if config.has_section('preprocessor'):
        prepargs = dict(config.items('preprocessor'))
      else:
        prepargs = {}

      self.preprocessor = preprocessor.Preprocessor(**prepargs)
    else:
      self.preprocessor = None

    # graph data
    self.hb_graph = hb_graph

    # get subgraphs
    if config.has_section('subgraph') and config.has_option('subgraph', 'preprocessing'):
      preprocessing = config.getboolean('subgraph', 'preprocessing')
    else:
      preprocessing = False

    ####################################################################################################################
    # Compare generating subgraphs with and without preprocessing (for testing reasons only)
    #
    # self.logger.debug("Compare building subgraphs with and without preprocessing")
    # self.logger.debug("Get subgraphs with preprocessing...")
    # tstart = time.time()
    # sub_preprocessing = subgraph.get_subgraphs(self.hb_graph, self.resultdir, preprocessing=True)
    # tprep = time.time() - tstart
    # self.logger.debug("Get subgraphs without preprocessing...")
    # tstart = time.time()
    # sub_no_preprocessing = subgraph.get_subgraphs(self.hb_graph, self.resultdir, preprocessing=False)
    # tnoprep = time.time() - tstart
    #
    # # verify that they generate the same subgraphs
    # def node_match(n1, n2):
    #   # it returns True if two nodes are the same
    #   return n1['label'] == n2['label']
    #
    # # first check if they have the same number of subgraphs
    # assert len(sub_preprocessing) == len(sub_no_preprocessing), 'Different number of subgraphs found!'
    #
    # for ind, sub in enumerate(sub_preprocessing):
    #   sub_equal = None
    #   for i, sub_no in enumerate(sub_no_preprocessing):
    #     # If the graphs are isomorphic...
    #     if nx.is_isomorphic(sub, sub_no, node_match=node_match):
    #       # and have the same nodes they are same
    #       if set(sub.nodes()) == set(sub_no.nodes()):
    #         # found same subgraph
    #         sub_equal = sub_no
    #         break
    #
    #   #assert sub_equal is not None, 'No equal graph found in sub_no_preprocessing'
    #   if sub_equal:
    #     sub_no_preprocessing.remove(sub_equal)
    #
    # assert len(sub_no_preprocessing) == 0, 'Sub_no_preprocessing not empty (Len: %s)' % len(sub_no_preprocessing)
    #
    # self.logger.debug("Building subgraphs with and without preprocessing lead to the same output :)")
    # self.logger.debug("Time with preprocessing: %f" % tprep)
    # self.logger.debug("Time without preprocessing: %f" % tnoprep)
    #
    # sys.exit(0)
    # END Compare
    ####################################################################################################################

    # Generating subgraphs
    self.subgraphs = subgraph.get_subgraphs(self.hb_graph, self.resultdir, preprocessing=preprocessing)
    self.logger.info("Number of subgraphs: %d" % len(self.subgraphs))

  def run(self):
    # Preprocessing
    if self.preprocessor:
      self.logger.info("Start preprocessing...")
      self.subgraphs = self.preprocessor.run(self.subgraphs)
      self.logger.info("Finished preprocessing")

    # Clustering
    if self.cluster:
      self.logger.info("Start clustering...")
      self.cluster.run(self.subgraphs)
      self.logger.info("Finished clustering")

    # Results


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

  m = hb_graph.Main(args.trace_file, print_pkt=args.print_pkt,
              add_hb_time=not args.no_hbt, rw_delta=args.rw_delta, ww_delta=args.ww_delta,
              filter_rw=args.filter_rw, ignore_ethertypes=args.ignore_ethertypes,
              no_race=args.no_race, alt_barr=args.alt_barr, verbose=args.verbose,
              ignore_first=args.ignore_first, disable_path_cache=args.disable_path_cache,
              data_deps=args.data_deps, no_dot_files=args.no_dot_files,
              verify_and_minimize_only=args.verify_and_minimize_only,
              is_minimized=args.is_minimized)
  m.run()

  r = Reduce(m.graph, args.trace_file)
  r.run()
