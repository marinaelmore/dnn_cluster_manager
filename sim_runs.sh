#!/bin/bash
placement=("count")
#schedule=("fifo")
schedule=("dlas-gpu")
#schedule=("dlas-gpu-05")
jobs=("20")
#jobs=("60")
#jobs=("breakit")
setups=("n1g4")
#setups=("n32g4")


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
                python run_sim.py --cluster_spec=${cluster_spec} --print --scheme=${p} --trace_file=${job_file} --schedule=${s} --log_path=${log_name} --fss=True
            done
        done
        cmd="analyze.py --job_file={$job_file} --log_file={$log_name}"
        echo ${cmd}
        python analyze.py --job_file=$job_file --log_file=$log_name
    done
done
