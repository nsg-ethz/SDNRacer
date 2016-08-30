#!/usr/bin/env python

"""
Runs reduce.py for all traces in the sim_files list.

Note: Has to be called from sdnracer folder.
"""


import os
import subprocess

sim_files = ['results/floodlight_loadbalancer-StarTopology4-steps200/hb.json',
             'results/floodlight_loadbalancer-StarTopology4-steps400/hb.json',
             'results/floodlight_loadbalancer-StarTopology4-steps600/hb.json',
             'results/floodlight_loadbalancer-StarTopology4-steps800/hb.json',
             'results/floodlight_loadbalancer_fixed-StarTopology4-steps200/hb.json',
             'results/floodlight_loadbalancer_fixed-StarTopology4-steps400/hb.json',
             'results/floodlight_loadbalancer_fixed-StarTopology4-steps600/hb.json',
             'results/floodlight_loadbalancer_fixed-StarTopology4-steps800/hb.json',
             'results/floodlight_learningswitch-BinaryLeafTreeTopology2-steps200/hb.json',
             'results/floodlight_learningswitch-BinaryLeafTreeTopology2-steps400/hb.json',
             'results/floodlight_learningswitch-BinaryLeafTreeTopology2-steps600/hb.json',
             'results/floodlight_learningswitch-BinaryLeafTreeTopology2-steps800/hb.json',
             'results/pox_eel_learningswitch-BinaryLeafTreeTopology2-steps200/hb.json',
             'results/pox_eel_learningswitch-BinaryLeafTreeTopology2-steps400/hb.json',
             'results/pox_eel_learningswitch-BinaryLeafTreeTopology2-steps600/hb.json',
             'results/pox_eel_learningswitch-BinaryLeafTreeTopology2-steps800/hb.json']

# Check if all files exist
all_exist = True
for f in sim_files:
  if not os.path.exists(f):
    print "%s does not exist" % f
    all_exist = False

if not all_exist:
  raise RuntimeError("Not all files exist. Modify list and start again.")
else:
  print "All files exist."

# Process all files
for f in sim_files:
  print "Run %s" % f
  subprocess.check_call(["./sts/happensbefore/reduce/reduce.py", f])

