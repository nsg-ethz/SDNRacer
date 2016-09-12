#!/usr/bin/env bash

./sts/happensbefore/reduce/reduce.py results/floodlight_loadbalancer-StarTopology4-steps200/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_loadbalancer-StarTopology4-steps400/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_loadbalancer-StarTopology4-steps600/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_loadbalancer-StarTopology4-steps800/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_loadbalancer_fixed-StarTopology4-steps200/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_loadbalancer_fixed-StarTopology4-steps400/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_loadbalancer_fixed-StarTopology4-steps600/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_loadbalancer_fixed-StarTopology4-steps800/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_learningswitch-BinaryLeafTreeTopology2-steps200/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_learningswitch-BinaryLeafTreeTopology2-steps400/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_learningswitch-BinaryLeafTreeTopology2-steps600/hb.json &&
./sts/happensbefore/reduce/reduce.py results/floodlight_learningswitch-BinaryLeafTreeTopology2-steps800/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_learningswitch-BinaryLeafTreeTopology2-steps200/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_learningswitch-BinaryLeafTreeTopology2-steps400/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_learningswitch-BinaryLeafTreeTopology2-steps600/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_learningswitch-BinaryLeafTreeTopology2-steps800/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_l2_multi-StarTopology4-steps200/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_l2_multi-StarTopology4-steps400/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_l2_multi-StarTopology4-steps600/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_l2_multi-StarTopology4-steps800/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_l2_multi_fixed-StarTopology4-steps200/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_l2_multi_fixed-StarTopology4-steps400/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_l2_multi_fixed-StarTopology4-steps600/hb.json &&
./sts/happensbefore/reduce/reduce.py results/pox_eel_l2_multi_fixed-StarTopology4-steps800/hb.json &&

echo "FINISHED"

