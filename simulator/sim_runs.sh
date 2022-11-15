#!/bin/bash
placement=("count")
#schedule=("fifo" "fjf" "sjf" "shortest" "shortest-gpu" "dlas" "dlas-gpu")
#schedule=("dlas" "dlas-gpu" "dlas-gpu-100" "dlas-gpu-8" "dlas-gpu-4" "dlas-gpu-2" "dlas-gpu-1" "dlas-gpu-05")
schedule=("dlas-gpu")
#schedule=("shortest-gpu")
#schedule=("dlas" "dlas-gpu")
#schedule=("dlas-gpu-05")
#schedule=("dlas-gpu-1" "dlas-gpu-2" "dlas-gpu-4" "dlas-gpu-8" "dlas-gpu-10" "dlas-gpu-100" "dlas-gpu-1000")
#schedule=("fifo")
#jobs=("breakit")
jobs=("60")
#setups=("n1g4")
setups=("n32g4")


for setup in ${setups[@]};do
    cluster_spec="cluster_specs/${setup}.csv"
    for job in ${jobs[@]};do
        job_file="job_files/${job}_job.csv"
        log_folder="log_files/${setup}j${job}"
        mkdir ${log_folder}
        for p in ${placement[@]};do
            for s in ${schedule[@]};do
                log_name="${log_folder}/${s}-${p}"
                cmd="python run_sim.py --cluster_spec=${cluster_spec} --print --scheme=${p} --trace_file=${job_file} --schedule=${s} --log_path=${log_name}"
                echo ${cmd}
                python run_sim.py --cluster_spec=${cluster_spec} --print --scheme=${p} --trace_file=${job_file} --schedule=${s} --log_path=${log_name}
            done
        done
        cmd="analyze.py --job_file={$job_file} --log_file={$log_name}"
        echo ${cmd}
        python analyze.py --job_file=$job_file --log_file=$log_name
    done
done
