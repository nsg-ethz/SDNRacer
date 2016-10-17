#!/usr/bin/env bash


# Check if file parameter is submitted and points to a file
if [[ -z $1 ]] ; then
    echo "Missing parameter 1: Path to simulation.log file" >&2
    exit 1
else
    if [[ ! -d $1 ]] ; then
        echo "Dir not found: ${1}"
    fi
fi
res_dir=$1

if [[ -z $2 ]] ; then
    echo "Missing parameter 2: Number to shift the iteration number" >&2
    exit 1
fi

shift=$2


traces=""
for folder in $res_dir/*/ ;do
    if [[ $folder = *"evaluation"* ]] ; then
        echo "Skip ${folder}"
    else
        num=${folder##*-}
        num=${num%/}
        num=$(($num + $shift))
        new_folder="${folder%-*}-${num}"
        mv ${res_dir}/${folder} ${res_dir}/${new_folder}
    fi
done


echo "FINISHED"

