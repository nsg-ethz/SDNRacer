#!/usr/bin/env bash

#####################################
# Clustering Only
############################################
# Multiprocessing variables and functions
m_jobs=3         # Maximum number of jobs
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


# Process the following number of steps
steps[0]="1000"
#steps[1]="400"
#steps[2]="600"
#steps[3]="800"
#steps[4]="1000"


# Check if file parameter is submitted and points to a file
if [[ -z $1 ]] ; then
    echo "Missing parameter: Path to simulation.log file" >&2
    exit 1
else
    if [[ ! -d $1 ]] ; then
        echo "Dir not found: ${1}"
    fi
fi
res_dir=$1

traces=""
for s in "${steps[@]}" ; do
    for folder in $res_dir/*/ ;do
        if [[ $folder = *"evaluation"* ]] ; then
            echo "Skip ${folder}"
            continue

        # Process only one stepsize in this iteration
        elif [[ $folder != *"$s"* ]] ; then
            continue

        elif [[ $folder != *"loadbalancer-Binary"* ]] ; then
            continue

        elif [[ $folder != *""* ]] ; then
            continue

        else
            echo "$(date +"%D %T"): Cluster ${folder}"

            red="${folder%/*}/${folder##*/}_red.txt"
            ./sts/happensbefore/reduce/reduce.py "${folder}/hb.json" >> $red 2>&1 &
            jobs="$jobs $!"
            n_jobs=$(($n_jobs + 1))

            while [ $n_jobs -ge $m_jobs ]; do
                check_jobs
                sleep 1
            done
        fi
    done
done

wait

echo "FINISHED"

