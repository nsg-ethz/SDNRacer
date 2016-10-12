#!/usr/bin/env bash

# Variables
# Number of iterations for each configuration
iter=1

# Controller & Module
controller[0]="floodlight_loadbalancer"
controller[1]="floodlight_loadbalancer_fixed"
controller[2]="floodlight_learningswitch"
controller[3]="pox_eel_learningswitch"
controller[4]="pox_eel_l2_multi"
controller[5]="pox_eel_l2_multi_fixed"

# Topologies
topology[0]="StarTopology"
topology[1]="MeshTopology"
topology[2]="BinaryLeafTreeTopology"

# Steps
steps[0]="200"
#steps[1]="400"
#steps[2]="600"
#steps[3]="800"

############################################
# Multiprocessing variables and functions
m_jobs=2         # Maximum number of jobs
jobs=""          # process ids
n_jobs=0         # Number of processes

function update_jobs {
    old_jobs=$jobs
    jobs=""
    n_jobs=0
    for job in $old_jobs
    do
        if [ -d /proc/$job ] ; then
            jobs="$jobs $job"
            n_jobs=$(($n_jobs+1))
         fi
    done
}

function check_jobs {
    for job in $jobs
    do
        if [ ! -d /proc/$job ] ; then
            update_jobs
            break
        fi
    done
}
############################################

exp_num=0
traces=""
t_stamp="$(date +%s)" # Use timestamp as folder name

for i in $(seq 1 $iter);
do
    for c in "${controller[@]}"
    do
        for t in "${topology[@]}"
        do
            for s in "${steps[@]}"
            do
                exp_num=$(($exp_num+1))
                # Edit config file
                template="config/template_${c}.py"
                temp_config="config/conf_${t_stamp}_${exp_num}.py"
                res_path="results_batch/${t_stamp}/${c}-${t}-${s}-${i}"

                sed "s,topology_class=#,topology_class=$t," <"$template" >"$temp_config"
                sed -i "s,steps=#,steps=${s}," "$temp_config"
                sed -i "s,results_dir=#,results_dir=\"${res_path}\"," "$temp_config"

                # Runn simulation (sequentailly)
                echo "$(date +"%D %T"): Simulate ${res_path}"
                sim="${res_path%/*}/${res_path##*/}_sim.txt"
                mkdir -p $res_path
                # if the simulation was successfull, run the clustering, but only if there are less than m_jobs running
                # Else run it later
                if ./simulator.py -L 'logging.cfg' -c "$temp_config" >> $sim 2>&1 ; then
                    check_jobs
                    if [ $n_jobs -ge $m_jobs ]; then
                        traces="$traces $res_path"
                    else
                        # Cluster trace (parallel)
                        echo "$(date +"%D %T"): Cluster ${res_path}"
                        red="${res_path%/*}/${res_path##*/}_red.txt"
                        ./sts/happensbefore/reduce/reduce.py "${res_path}/hb.json" >> $red 2>&1 &
                        jobs="$jobs $!"
                        n_jobs=$(($n_jobs+1))
                    fi
                fi
                # Remove the config file
                rm $temp_config
            done
        done
    done
done

# Start clustering for all remaining traces
for trace in $traces
do
    # Cluster trace (parallel)
    echo "$(date +"%D %T"): Cluster ${trace}"
    red="${trace%/*}/${trace##*/}_red.txt"
    ./sts/happensbefore/reduce/reduce.py "${trace}/hb.json" >> $red 2>&1 &
    jobs="$jobs $!"
    n_jobs=$(($n_jobs+1))

    while [ $n_jobs -ge $m_jobs ]; do
        check_jobs
        sleep 1
    done
done

wait

echo "FINISHED"

