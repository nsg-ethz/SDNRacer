#!/usr/bin/env python

import sys
import os
import ConfigParser
import logging.config

sys.path.append(os.path.join(os.path.dirname(__file__), "./.."))

from hb_graph import *
from preprocessor import *
from cluster import *
from subgraph import *

# create logger
logging.config.fileConfig(os.path.dirname(__file__) + '/logging.conf', disable_existing_loggers=False)
logger = logging.getLogger(__name__)


class Reduce:
  def __init__(self, hb_graph, trace_file):
    print ""
    print ""
    print "########################################################################"
    print ""

    logger.info("Init... ")
    # Create separate results directory
    self.resultdir = os.path.join(os.path.dirname(trace_file), 'reduce')
    if not os.path.exists(self.resultdir):
      os.makedirs(self.resultdir)

    # Parse config
    config = ConfigParser.RawConfigParser()
    config.read(os.path.dirname(__file__) + '/config.ini')

    # Create Clustering object if not disabled
    if not config.getboolean('general', 'no_cluster'):
      if config.has_section('cluster'):
        clusterargs = dict(config.items('cluster'))
      else:
        clusterargs = {}

      self.cluster = Cluster(self.resultdir, **clusterargs)
    else:
      self.cluster = None

    # Create Preprocessor Object if not disabled
    if not config.getboolean('general', 'no_preprocess'):
      if config.has_section('preprocessor'):
        prepargs = dict(config.items('preprocessor'))
      else:
        prepargs = {}

      self.preprocessor = Preprocessor(**prepargs)
    else:
      self.preprocessor = None

    # graph data
    self.hb_graph = hb_graph


  def run(self):
    # get subgraphs
    self.subgraphs = get_subgraphs(self.hb_graph, self.resultdir)
    logger.info("Number of subgraphs: %d" % len(self.subgraphs))

    # Preprocessing
    if self.preprocessor:
      logger.info("Start preprocessing...")
      self.subgraphs = self.preprocessor.run(self.subgraphs)
      logger.info("Finished preprocessing")

    # Clustering
    if self.cluster:
      logger.info("Start clustering...")
      self.cluster.run(self.subgraphs)
      logger.info("Finished clustering")

    # Results




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

  m = Main(args.trace_file, print_pkt=args.print_pkt,
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
