#!/usr/bin/env bash

#####################################
# Simulate and clustering

# Variables
# Number of iterations for each configuration
iter=5

# Controller & Module
controller[0]="floodlight_loadbalancer"
controller[1]="floodlight_loadbalancer_fixed"
controller[2]="floodlight_learningswitch"
controller[3]="pox_eel_learningswitch"
controller[4]="pox_eel_l2_multi"
controller[5]="pox_eel_l2_multi_fixed"
controller[6]="floodlight_circuitpusher"
controller[7]="floodlight_forwarding"
controller[8]="floodlight_firewall"

# Topologies
topology[0]="StarTopology"
topology[1]="MeshTopology"
topology[2]="BinaryLeafTreeTopology"

# Steps
steps[0]="200"
steps[1]="400"
steps[2]="600"
steps[3]="800"
steps[4]="1000"

############################################
exp_num=0
traces=""
t_stamp="$(date +%s)" # Use timestamp as folder name
# Use first argument as result folder if it's given and check for it's existance.
if [[ -z $1 ]] ; then
    res_dir=results_batch/${t_stamp}
else
    if [[ -d $1 ]] ; then
        res_dir=$1
    else
        echo "Verzeichniss existiert nicht" >&2
        exit 1
    fi
fi

batch_log="${res_dir}/simulation.log"

i=0
while [[ $i -lt $iter ]];
do
    echo "Iteration ${i}"
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
                # continue iteration number if there are already some in the folder
                res_path="${res_dir}/${c}-${t}-${s}-${i}"
                if [ -d $res_path ] ; then
                    continue
                fi

                sed "s,topology_class=#,topology_class=$t," <"$template" >"$temp_config"
                sed -i "s,steps=#,steps=${s}," "$temp_config"
                sed -i "s,results_dir=#,results_dir=\"${res_path}\"," "$temp_config"

                # Runn simulation (sequentailly)
                echo "$(date +"%D %T"): Simulate ${res_path}"
                sim="${res_path%/*}/${res_path##*/}_sim.txt"
                mkdir -p $res_path
                # if the simulation was successfull, run the clustering, but only if there are less than m_jobs running
                # Else run it later
                t_start=$SECONDS
                if ./simulator.py -L 'logging.cfg' -c "$temp_config" >> $sim 2>&1 ; then
                    # Write log
                    tm=$(($SECONDS - $t_start))
                    echo "${res_path} successful ${tm}" >> $batch_log
                else
                    tm=$(($SECONDS - $t_start))
                    echo "${res_path} failed ${tm}" >> $batch_log
                    # remove simulation folder if there is one
                    if [[ -d $res_path ]] ; then
                        rm -R $res_path
                    fi
                fi
                # Remove the config file
                rm $temp_config
            done
        done
    done
    i=$(($i+1))
done

echo "$(date +"%D %T"): FINISHED"

