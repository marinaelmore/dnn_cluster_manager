GPU cluster simulator
===
1. What Did We Modify:
    1. ``run_sim.py``: The main function script of this simulator
    2. ``analyze.py``: Added and analysis file
    3. ``*_job.csv``: Job trace file that was modified to add the lying field. Jobs have the following necessary fields: ``job_id,num_gpu,submit_time,iterations,model_name,duration,interval,liar``
    4. ``log.py``: Log function for the simulator, we modified to provide more robust logging
    5. ``nxxgxx.csv`` and ``cluster_spec.csv``:  Cluster spec file, including the fields: ``num_switch,num_node_p_switch,num_gpu_p_node,num_cpu_p_node,mem_p_node``


2. Before the execution, what's needed?
    1. Infrastructure details
    Define the hierarchy and resource capacity of the infrastructure in ``cluster_spec.csv``. For example, we have a cluster with 4 racks (switches). Under each rack (switch), there are 32 nodes. And each node has 128 CPU cores, 256 GB memory, and 8 GPUs. Then ``cluster_spec.csv`` will look like this:
        ```csv
        num_switch,num_node_p_switch,num_gpu_p_node,num_cpu_p_node,mem_p_node
        4,32,8,128,256
        ```
    2. Job trace
    The job trace to simulate. For each job, the simulator needs the following information:
       * ``job_id``: for tracking
       * ``num_gpu``: gpu requirement
       * ``submit_time``: when the job is submitted. The simulator is event-based and discrete-time. Therefore, the time value starts from ``0``, and in second-scale.
       * ``iterations``: the number of iterations to training. For the scheduling schemes in Tiresias, they are not relying on this information.
       * ``model_name``: what's the model in that job. This is used to estimate the CPU and GPU memory usage, and tensor size (in MB, only consider the large tensors).
       * ``duration``: how long this job will run. This information is used to generate job completion event by the simulator.
       * ``interval``: job submission interval from this job to the next job

3. How to run the simulator?

    In terminal, run
    ```bash
        ./sim_runs.sh
    ```
    This executes the following command with the required options:
    ```bash
    python3 run_sim.py --cluster_spec=n32g4.csv --print --scheme=yarn --trace_file=480_job.csv --schedule=dlas --log_path=test_1
    ```
    The following options are necessary and set within the shell file:
    * ``--cluster_spec``: infrastructure spec file
    * ``--trace_file``: job trace
    * ``--scheme``: **placement scheme**
    * ``--schedule``: **scheduler**

4. What are the placement and scheduling algorithms provided?

    Our project modifies the DLAS (discretized LAS GPU Time Based) algorithm proposed by Tiresias.

    *Scheduling*
    * ``fifo`` : We use FIFO as baseline
    * ``dlas-gpu``: discretized LAS (gpu-time-based)

5. What's the output?
    1. ``cluster.csv``: cluster-level resource utilization info at each event point
    2. ``jobs.csv``: the job execution information
    3. ``cpu.csv``, ``gpu.csv``, ``memory.csv``, ``network.csv``: those are the utilization details of each resource unit at event points. However, those logs are not accurate under some combinations of placement and scheduler. When ``count`` is chosen, those files are not generated.

    The output logs are defined in ``log.py``

    We pass the output to ``analyze.py`` that provides simple Pandas analytics on top of the CSV file for added insights.
