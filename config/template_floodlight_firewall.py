from config.experiment_config_lib import ControllerConfig
from sts.topology import StarTopology, BufferedPatchPanel, MeshTopology, GridTopology, BinaryLeafTreeTopology
from sts.controller_manager import UserSpaceControllerPatchPanel
from sts.control_flow.fuzzer import Fuzzer
from sts.control_flow.interactive import Interactive
from sts.input_traces.input_logger import InputLogger
from sts.simulation_state import SimulationConfig
from sts.happensbefore.hb_logger import HappensBeforeLogger
from config.application_events import AppFloodlightFirewall

start_cmd = ('''java -ea -Dlogback.configurationFile=./src/main/resources/logback-trace.xml -jar '''
             '''./target/floodlight.jar '''
              '''-cf ./src/main/resources/trace_firewall.properties''')
  
controllers = [ControllerConfig(start_cmd, cwd='../floodlight', address="127.0.0.1", port=6633)]

# Uncomment this if you are running Floodlight separately, e.g. for debugging in Eclipse. There must be a controller listening on port 6633.
# start_cmd = '''echo "no-op"'''
# controllers = [ControllerConfig(start_cmd, cwd='../floodlight', address="127.0.0.1", port=6633, controller_type='dummy')]

############################################
topology_class=#
steps=#
results_dir=#
############################################

if topology_class == StarTopology:
  num = 4
  topology_params = "num_hosts=%d" % num
elif topology_class == MeshTopology:
  num = 2
  topology_params = "num_switches=%d" % num
elif topology_class == BinaryLeafTreeTopology:
  num = 2
  topology_params = "num_levels=%d" % num
else:
  raise RuntimeError("Unknown Topology.")


apps = [AppFloodlightFirewall('firewall', cwd='./', controller='localhost:8080')]

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
                      initialization_rounds=20,
                      send_all_to_all=False,
                      check_interval=10,
                      delay=0.1,
                      halt_on_violation=True,
                      send_init_packets=False,
                      steps=steps, # if no circuits are installed, increase this number.
#                       invariant_check_name="check_everything",
                      invariant_check_name="InvariantChecker.check_liveness",
                      apps=apps)