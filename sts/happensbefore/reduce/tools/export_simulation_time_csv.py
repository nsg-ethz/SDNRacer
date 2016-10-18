import argparse
import os


class Evaluation:
  """
  This script reads the simulation log and export the time in a csv.
  """
  def __init__(self, sim_file):

    print "Init"
    # Check if simulation log file exists
    assert os.path.exists(sim_file), 'File %s does not exist' % eval_folder

    self.sim_file = os.path.abspath(sim_file)
    self.csv_file = os.path.join(os.path.dirname(self.sim_file), "sim_time.csv")

  def run(self):
    # Write eval file
    print "Run"
    with open(self.csv_file, 'w') as csv:
      csv.write("controller, app, topology, steps, sim_time\n")
      with open(self.sim_file) as sim:
        for line in sim:
          l = line.split(" ")
          if len(l) != 3:
            print "Line not in correct format: %s" % line
            continue
          #assert len(l) == 3, "Line not in correct format: %s" % line

          # Second element is either successfull or failed -> only consider successfull simulations
          if l[1] == "failed":
            continue

          # First elemement is folder/controller_app-topology-steps-iteration -> extract experiment info
          exp_str = l[0].split("/")[-1]
          controller, topology, steps, iter = exp_str.split("-")
          # separate controller and app
          if controller.startswith('floodlight'):
            app = controller.replace('floodlight_', '')
            controller = 'Floodlight'
          elif controller.startswith('pox_eel'):
            app = controller.replace('pox_eel_', '')
            controller = 'POX EEL'
          else:
            raise RuntimeError("Unknown controller string %s" % controller)

          # Last element is the time
          tm = l[2]

          # Write csv line
          csv.write("%s, %s, %s, %s, %s\n" % (controller, app, topology, steps, tm))

    print "Finished"


if __name__ == '__main__':
  # First call hb_graph.py and provide the same parameters
  # From hb_graph.py
  empty_delta = 1000000
  parser = argparse.ArgumentParser()
  parser.add_argument('sim_log', help='Path to the simulation log file produced by batch_simulate_only.sh')

  args = parser.parse_args()

  evaluation = Evaluation(args.sim_log)
  evaluation.run()


