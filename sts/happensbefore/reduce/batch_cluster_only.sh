#!/usr/bin/env bash

#####################################
# Clustering Only
############################################
# Multiprocessing variables and functions
m_jobs=4         # Maximum number of jobs
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

# Check if file parameter is submitted and points to a file
if [[ -z $1 ]] ; then
    echo "Missing parameter: Path to simulation.log file" >&2
    exit 1
else
    if [[ ! -f $1 ]] ; then
        echo "File not found: ${1}"
    fi
fi
sim_file=$1

# Read line by line to find all traces
traces=""
while read -r line ; do
    l=($line)
    if [ ! ${#l[@]} -eq 3 ] ; then
        echo "Line not in correct format: ${l}" >&2
        continue
    fi
    if [ ! "${l[1]}" == "successful" ] ; then
        echo "${l[0]} was not successfull"
        continue
    else
        traces="$traces ${l[0]}"
    fi
done < "${sim_file}"

# Start clustering for all remaining traces
for trace in $traces
do
    # Cluster trace (parallel)
    echo "$(date +"%D %T"): Cluster ${trace}"
    red="${trace%/*}/${trace##*/}_red.txt"
    ./sts/happensbefore/reduce/reduce.py "${trace}/hb.json" >> $red 2>&1 &
    jobs="$jobs $!"
    n_jobs=$(($n_jobs + 1))

    while [ $n_jobs -ge $m_jobs ]; do
        check_jobs
        sleep 1
    done
done

wait

echo "FINISHED"

