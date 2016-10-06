#!/usr/bin/env bash

./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_learningswitch_200.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_learningswitch_400.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_learningswitch_600.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_learningswitch_800.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_loadbalancer_200.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_loadbalancer_400.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_loadbalancer_600.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_loadbalancer_800.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_loadbalancer_fixed_200.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_loadbalancer_fixed_400.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_loadbalancer_fixed_600.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_floodlight_loadbalancer_fixed_800.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_multi_forwarding_200.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_multi_forwarding_400.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_multi_forwarding_600.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_multi_forwarding_800.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_multi_fixed_forwarding_200.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_multi_fixed_forwarding_400.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_multi_fixed_forwarding_600.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_multi_fixed_forwarding_800.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_learning_200.py' &&
./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_learning_400.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_learning_600.py' &&
#./simulator.py -L 'logging.cfg' -c 'config/test_pox_eel_l2_learning_800.py' &&

echo "FINISHED"

