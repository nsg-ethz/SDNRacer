from config.experiment_config_lib import ControllerConfig
from sts.topology import StarTopology
from sts.topology import BufferedPatchPanel
from sts.topology import MeshTopology
from sts.topology import GridTopology
from sts.topology import BinaryLeafTreeTopology
from sts.controller_manager import UserSpaceControllerPatchPanel
from sts.control_flow.fuzzer import Fuzzer
from sts.input_traces.input_logger import InputLogger
from sts.simulation_state import SimulationConfig
from sts.happensbefore.hb_logger import HappensBeforeLogger


# Use POX EEL (fixed) as our controller

start_cmd = (" ./pox.py --verbose openflow.of_01 --address=__address__ --port=__port__  openflow.discovery forwarding.l2_multi")

#start_cmd = '''echo "no-op"'''
#controllers = [ControllerConfig(start_cmd, cwd="pox/", address="192.168.56.1", port=6633, controller_type='dummy')]
controllers = [ControllerConfig(start_cmd, cwd="/home/roman/sdnracer/pox/", port=6633)]

#################################
# Topologies used in PLDI paper #
#################################

# Uncomment exactly one of the topologies below to use it..

############
# "Single" #
# ############
# num = 2
# topology_class = StarTopology #
# topology_params = "num_hosts=%d" % num

#############
# "Single4" #
#############
# num = 4
# topology_class = StarTopology #
# topology_params = "num_hosts=%d" % num

############
# "Linear" #
############
#num = 2
#topology_class = MeshTopology
#topology_params = "num_switches=%d" % num

############
# "BinTree" #
############
num = 2
topology_class = BinaryLeafTreeTopology
topology_params = "num_levels=%d" % num

# Increase this value to get longer traces
steps = 600

# This folder will be placed in the root STS directory
# To see the exact parameters used for each trace, refer to the "orig_config.py" in each trace directory.
# This file will be copied to the results_dir, along with the results themselves.

results_dir = "results/pox_eel_l2_multi_fixed-%s%d-steps%s" % (topology_class.__name__, num, steps)

apps = None

# include all defaults
simulation_config = SimulationConfig(controller_configs=controllers,
                                     topology_class=topology_class,
                                     topology_params=topology_params,
                                     patch_panel_class=BufferedPatchPanel,
                                     controller_patch_panel_class=UserSpaceControllerPatchPanel,
                                     dataplane_trace=None,
                                     snapshot_service=None,
                                     multiplex_sockets=False,
                                     violation_persistence_threshold=None,
                                     kill_controllers_on_exit=True,
                                     interpose_on_controllers=False,
                                     ignore_interposition=False,
                                     hb_logger_class=HappensBeforeLogger,
                                     hb_logger_params=results_dir,
                                     apps=apps)

# Manual, interactive mode
# control_flow = Interactive(simulation_config, input_logger=InputLogger())

control_flow = Fuzzer(simulation_config,
                      input_logger=InputLogger(),
                      initialization_rounds=100,
                      send_all_to_all=False,
                      check_interval=10,
                      delay=0.1,
                      halt_on_violation=True,
                      send_init_packets=False,
                      steps=steps,
#                       invariant_check_name="check_everything",
                      invariant_check_name="InvariantChecker.check_liveness",
                      apps=apps)
