from __future__ import print_function
import csv
import re
import sys
import types
import time
import math
#parse args
import argparse
import copy
import os

import util
import flags
import jobs
import cluster
import log
import lp

import pandas as pd
import numpy as np

#parse input arguments
flags.DEFINE_string('trace_file', 'tf_job.csv',
                '''Provide TF job trace file (*.csv, *.txt).
                    *.csv file, use \',\' as delimiter; *.txt file, user \' \' as deliminter.
                    Default file is tf_job.csv ''')
flags.DEFINE_string('log_path', 'result-' + time.strftime("%Y%m%d-%H-%M-%S", time.localtime()),
                '''Simulation output folder, including cluster/node/gpu usage trace, pending job_queue info.
                Default folder is result-[time]''')
flags.DEFINE_string('scheme', 'yarn',
                '''
                Job placement scheme:
                0.count, just resource counting, without assignment (which gpu, which cpu)
                1.yarn, ms yarn
                2.random
                3.crandom (consolidate + random)
                4.greedy
                5.balance
                6.cbalance (consolidate + balance)
                Default is yarn''')
flags.DEFINE_string('schedule', 'fifo',
                '''
                Job schedule scheme:
                1.fifo
                2.fjf, fit job first( in fifo order)
                3.sjf, smallest job first
                4.lpjf, longest pending job first
                5.shortest, shortest-remaining-time job first
                6.shortest-gpu, shortest-remaining-gputime job first
                7.dlas, discretized las
                8.dlas-gpu, dlas using gpu time
                Default is fifo''')
flags.DEFINE_integer('num_switch', 1,
                '''Part of cluster spec: the number of switches in this cluster, default is 1''')
flags.DEFINE_integer('num_node_p_switch', 32,
                '''Part of cluster spec: the number of nodes under a single switch, default is 32''')
flags.DEFINE_integer('num_gpu_p_node', 8,
                '''Part of cluster spec: the number of gpus on each node, default is 8''')
flags.DEFINE_integer('num_cpu_p_node', 64,
                '''Part of cluster spec: the number of cpus on each node, default is 64''')
flags.DEFINE_integer('mem_p_node', 256,
                '''Part of cluster spec: memory capacity on each node, default is 128''')
flags.DEFINE_string('cluster_spec', None,
                '''Part of cluster spec: cluster infra spec file,
                this file will overwrite the specs from num_switch, num_node_p_switch, and num_gpu_p_node
                Spec format:
                    num_switch,num_node_p_switch,num_gpu_p_node
                    int,int,int''')

flags.DEFINE_boolean('print', False,
                '''Enable print out information, default is False''')
flags.DEFINE_boolean('flush_stdout', True,
                '''Flush stdout, default is True''')
flags.DEFINE_version('0.1')

flags.DEFINE_boolean('fss', False, "Run cluster with FSS")

FLAGS = flags.FLAGS

#prepare JOBS list
JOBS = jobs.JOBS

#get host info
CLUSTER = cluster.CLUSTER

#get LOG object
LOG = log.LOG


def parse_job_file(trace_file):
    #check trace_file is *.csv
    fd = open(trace_file, 'r')
    deli = ','
    if ((trace_file.find('.csv') == (len(trace_file) - 4))):
        deli = ','
    elif ((trace_file.find('.txt') == (len(trace_file) - 4))):
        deli = ' '

    reader = csv.DictReader(fd, delimiter = deli)
    ''' Add job from job trace file'''
    keys = reader.fieldnames
    util.print_fn('--------------------------------- Read TF jobs from: %s ---------------------------------' % trace_file)
    util.print_fn('    we get the following fields:\n        %s' % keys)
    job_idx = 0
    for row in reader:
        #add job into JOBS
        JOBS.add_job(row)
        # JOBS.read_job_info(job_idx, 'num_gpu')
        job_idx += 1

    assert job_idx == len(JOBS.job_list)
    assert JOBS.num_job == len(JOBS.job_list)
    # JOBS.print_all_job_size_info()
    JOBS.sort_all_jobs()
    # print(lp.prepare_job_info(JOBS.job_list[0]))
    util.print_fn('---------------------------------- Get %d TF jobs in total ----------------------------------' % job_idx)
    # JOBS.read_all_jobs()
    fd.close()

def parse_cluster_spec():
    if FLAGS.cluster_spec:
        print(FLAGS.cluster_spec)
        spec_file = FLAGS.cluster_spec
        fd = open(spec_file, 'r')
        deli = ','
        if ((spec_file.find('.csv') == (len(spec_file) - 4))):
            deli = ','
        elif ((spec_file.find('.txt') == (len(spec_file) - 4))):
            deli = ' '
        reader = csv.DictReader(fd, delimiter = deli)
        keys = reader.fieldnames
        util.print_fn(keys)
        if 'num_switch' not in keys:
            return
        if 'num_node_p_switch' not in keys:
            return
        if 'num_gpu_p_node' not in keys:
            return
        if 'num_cpu_p_node' not in keys:
            return
        if 'mem_p_node' not in keys:
            return

        ''' there should be only one line remaining'''
        assert reader.line_num == 1

        ''' get cluster spec '''
        for row in reader:
            # util.print_fn('num_switch %s' % row['num_switch'])
            FLAGS.num_switch = int(row['num_switch'])
            FLAGS.num_node_p_switch = int(row['num_node_p_switch'])
            FLAGS.num_gpu_p_node = int(row['num_gpu_p_node'])
            FLAGS.num_cpu_p_node = int(row['num_cpu_p_node'])
            FLAGS.mem_p_node = int(row['mem_p_node'])
        fd.close()

    util.print_fn("num_switch: %d" % FLAGS.num_switch)
    util.print_fn("num_node_p_switch: %d" % FLAGS.num_node_p_switch)
    util.print_fn("num_gpu_p_node: %d" % FLAGS.num_gpu_p_node)
    util.print_fn("num_cpu_p_node: %d" % FLAGS.num_cpu_p_node)
    util.print_fn("mem_p_node: %d" % FLAGS.mem_p_node)

    '''init infra'''
    CLUSTER.init_infra()
    # util.print_fn(lp.prepare_cluster_info())
    util.print_fn('--------------------------------- End of cluster spec ---------------------------------')
    return


'''
Allocate job resource
'''
def try_get_job_res(job):
    '''
    select placement scheme
    '''
    if FLAGS.scheme == 'yarn':
        ret = CLUSTER.ms_yarn_placement(job)
    elif FLAGS.scheme == 'balance':
        ret = lp.placement(job)
        # ret = lp.min_new_job(job)
    elif FLAGS.scheme == 'random':
        ret = CLUSTER.random_placement(job)
    elif FLAGS.scheme == 'crandom':
        ret = CLUSTER.consolidate_random_placement(job)
    elif FLAGS.scheme == 'greedy':
        ret = CLUSTER.greedy_placement(job)
    elif FLAGS.scheme == 'gandiva':
        ret = CLUSTER.gandiva_placement(job)
    elif FLAGS.scheme == 'count':
        ret = CLUSTER.none_placement(job)
    else:
        ret = CLUSTER.ms_yarn_placement(job)
    if ret == True:
        # job['status'] = 'RUNNING'
        pass
    return ret


def one_queue_fifo_sim_jobs():
    '''
    run jobs in fifo order;
    new jobs are added to the end of the pending queue
    '''
    while (len(JOBS.job_events) + len(JOBS.pending_jobs))> 0:
        if len(JOBS.job_events) == 0:
            util.print_fn("This cluster is not large enough to run the job")
            break

        event = JOBS.job_events[0]
        event_time = event['time']
        # util.print_fn('--------------------------------- Handle event[time %d]------------------------------------' % event_time)
        #for ending jobs, release gpu
        has_ejob = False
        for e_job in event['end_jobs']:
            #remove from migratable jobs, if it's there
            # JOBS.remote_migratable(e_job)

            #job completes
            CLUSTER.release_job_res(e_job)
            # CLUSTER.release_gpus(e_job)
            LOG.job_complete(e_job, event_time)
            has_ejob = True


        #for new-start jobs, try to start
        for s_job in event['start_jobs']:
            #add into pending list
            JOBS.move_to_pending(s_job)


        if CLUSTER.check_free_gpu() > 0:
            #for pending jobs, try to start
            new_start_list = list()
            for p_job in JOBS.pending_jobs:
                # ret = CLUSTER.alloc_gpus(p_job)
                ret = try_get_job_res(p_job)
                if ret == True:
                    ''' if remove_from_pending, then will miss the next p_job in the list '''
                    new_start_list.append(p_job)
                else:
                    break
            for ns_job in new_start_list:
                JOBS.remove_from_pending(ns_job, event_time)
                JOBS.add_job_end_event(ns_job)
                util.print_fn('----job[%d] starts from pending' % ns_job['job_idx'])


        #remove time_event
        JOBS.job_events.pop(0)
        JOBS.job_events.sort(key = lambda e:e.__getitem__('time'))

        LOG.checkpoint(event_time)


def append_fss_to_job():
    users_file = LOG.users_file

    df = pd.read_csv(users_file)
    user_ids = df['user_id']

    for i in range(0, len(JOBS.job_events)):

        for r in range(0,len(JOBS.job_events[i]['start_jobs'])):
            job_user_id = JOBS.job_events[i]['start_jobs'][r]['user_id']
            if job_user_id in user_ids:
                JOBS.job_events[i]['start_jobs'][r]['fss'] = df.loc[df['user_id'] == job_user_id]['fss'].item()
            else:
                JOBS.job_events[i]['start_jobs'][r]['fss'] = 0
    return df

def dlas_sim_jobs(gputime=False, solve_starvation=0, fss=FLAGS.fss):
    '''
    Job's executed time -- priority queue
    Q0:[0, 30min)
    Q1:[30min,1h)
    Q2:[1h, 2h)
    Q3:[2h, 00)

    in each queue, jobs are scheduled in fit-first with FIFO

    '''
    end_events = list()
    next_job_jump = sys.maxsize

    if fss:
        fss_df = append_fss_to_job()
        # queue 0 is the pending queue, start assigning at queue 1
        queue_1 = float(fss_df['fss'].quantile(q=0.3))
        queue_2 = float(fss_df['fss'].quantile(q=0.8))

    # While
    while (len(JOBS.job_events) + len(JOBS.runnable_jobs))> 0:
        if (len(JOBS.job_events) + len(end_events)) == 0:
            util.print_fn("This cluster is not large enough to run the job")
            break

        start_event = None
        start_time = sys.maxsize
        if len(JOBS.job_events) > 0:
            start_event = JOBS.job_events[0]
            start_time = start_event['time']
        end_event = None
        end_time = sys.maxsize
        if len(end_events) > 0:
            end_event = end_events[0]
            end_time = end_event['time']

        event_time = sys.maxsize
        event = dict()
        event['time'] = sys.maxsize
        if end_time < start_time:
            event_time = end_time
            event = end_event
        elif end_time > start_time:
            event_time = start_time
            event = start_event
        elif end_time == start_time and end_time != sys.maxsize:
            event_time = start_time
            event = start_event
            event['end_jobs'] = end_events[0]['end_jobs']

        assert event_time == event['time']

        #decide if job_jump first or (start/end) first
        if event_time > next_job_jump:
            event_time = next_job_jump
            event = dict()

        # util.print_fn('--------------------------------- Handle event[time %d]------------------------------------' % event_time)
        #for ending jobs, release gpu
        if 'end_jobs' in event:
            for e_job in event['end_jobs']:
                CLUSTER.release_job_res(e_job)
                LOG.job_complete(e_job, event_time)
                # util.print_fn('---- job[%d] is completed' % e_job['job_idx'])
                JOBS.runnable_jobs.remove(e_job)
                JOBS.queues[e_job['q_id']].remove(e_job)

        #for new jobs, append to runnable jobs with pending status
        # Jobs already sorted when they get here
        if 'start_jobs' in event:
            for s_job in event['start_jobs']:
                JOBS.move_to_runnable(s_job)
                s_job['q_id'] = 0 #any new start job should be in Q0
                JOBS.queues[0].append(s_job)
                util.print_fn('---- job[%d] is added' % s_job['job_idx'])
            #pop start event
            JOBS.job_events.pop(0)


        #update executed_time
        for rjob in JOBS.runnable_jobs:
            if 'RUNNING' == rjob['status']:
                tmp = int(event_time - rjob['last_check_time'])
                rjob['total_executed_time'] = int(rjob['total_executed_time'] + tmp)
                rjob['executed_time'] = int(rjob['executed_time'] + tmp) # decide job priority queue
                rjob['last_check_time'] = event_time

                # Get Job GPU Time, If Runtime > G=J_GT then bad
                j_gt = 0
                if gputime:
                    j_gt = int(rjob['executed_time'] * rjob['num_gpu'])
                else:
                    j_gt = int(rjob['executed_time'])

                cur_qid = rjob['q_id']
                # To Do - find a way to type cast as bool on read
                liar = True if rjob['liar']=="True" else False

                if fss:
                    fair_share_score = float(rjob['fss'])

                    #Check FSS against quantile
                    if fair_share_score <= queue_1:
                        rjob['q_id'] = 0
                    if fair_share_score > queue_1 and fair_share_score <= queue_2:
                        rjob['q_id'] = 1
                    if fair_share_score > queue_2:
                        rjob['q_id'] = 2

                    print("job %d assigned to Q%d" % (rjob['job_idx'], rjob['q_id']))

                elif not liar:
                    if ((j_gt >= JOBS.queue_limit[cur_qid])):
                        # current queue
                        if cur_qid < int(JOBS.num_queue - 1):#not for the last queue
                            rjob['q_id'] = int(cur_qid + 1)
                            print("job %d demote to Q%d" % (rjob['job_idx'], rjob['q_id']))
                #If job is lying, do not demote to later queue
                elif liar:
                    print("job %d is lying - keep in Queue 0" % (rjob['job_idx']))
                    rjob['q_id'] = 0

                # Add to queue
                JOBS.queues[rjob['q_id']].append(rjob)
                JOBS.queues[cur_qid].remove(rjob)


            # For jobs that are in queue 0
            elif 'PENDING' == rjob['status']:
                tmp = int(event_time - rjob['last_check_time'])
                rjob['last_check_time'] = event_time
                rjob['pending_time'] = int(rjob['pending_time'] + tmp) #this is the total pending_time
                if rjob['executed_time'] > 0: # if not started yet, job is always in Q0 and no need to push_back
                    rjob['last_pending_time'] = int(rjob['last_pending_time'] + tmp) #this is the total pending_time
                #Q0 job no need to push_back, and must be a runned
                if solve_starvation > 0 and rjob['q_id'] > 0 and rjob['total_executed_time'] > 0 and rjob['executed_time'] > 0:
                    if rjob['last_pending_time'] >= int(rjob['executed_time'] * solve_starvation):
                        rjob['executed_time'] = 0
                        rjob['last_pending_time'] = 0
                        JOBS.queues[0].append(rjob)
                        JOBS.queues[rjob['q_id']].remove(rjob)
                        rjob['q_id'] = 0
                        rjob['promote'] = int(rjob['promote'] + 1)

            elif 'END' == rjob['status']: # won't happen
                JOBS.runnable_jobs.remove(rjob)
                # util.print_fn('---- job[%d] completed' % rjob['job_idx'])
                pass


        ''' schedule jobs in each queue '''
        # This breaks when jobs lie!

        #empty_cluster resource
        CLUSTER.empty_infra()
        run_jobs = list()
        preempt_jobs = list()

        for queue in JOBS.queues:

            # Do lying jobs first, because they're lying!
            queue.sort(key = lambda e : (e.__getitem__('liar')=="True"), reverse=True)

            for job in queue:
                if CLUSTER.free_gpu >= job['num_gpu']:
                    #should run
                    if job['status'] == 'PENDING':
                        #not running
                        run_jobs.append(job)
                    CLUSTER.free_gpu = int(CLUSTER.free_gpu - job['num_gpu'])
                else:
                    #should NOT run
                    if job['status'] == 'RUNNING':
                        #running
                        preempt_jobs.append(job)
                    continue

        for job in preempt_jobs:
            job['status'] = 'PENDING'
            job['preempt'] = int(job['preempt'] + 1)
        for job in run_jobs:
            job['status'] = 'RUNNING'
            job['resume'] = int(job['resume'] + 1)
            if job['start_time'] == sys.maxsize:
                job['start_time'] = event_time


        #sort based on the job start time
        for queue in JOBS.queues:
            pending_job = list()
            for job in queue:
                if job['status'] == 'PENDING':
                    pending_job.append(job)
            for job in pending_job:
                queue.remove(job)
            queue.extend(pending_job)

        #update end events and sort, and get the most recent one
        del end_events[:]

        min_end_time = sys.maxsize
        tmp_end_event = dict()
        for rjob in JOBS.runnable_jobs:
            if 'RUNNING' == rjob['status']:
                remaining_time = rjob['duration'] - rjob['total_executed_time']
                end_time = int(event_time + remaining_time)
                if end_time < min_end_time:
                    tmp_end_event['time'] = end_time
                    tmp_end_event['end_jobs'] = list()
                    tmp_end_event['end_jobs'].append(rjob)
                    min_end_time = end_time
                elif min_end_time == end_time:
                    tmp_end_event['end_jobs'].append(rjob)
        if min_end_time < sys.maxsize:
            end_events.append(tmp_end_event)

        # what's the closest queue_jump (demotion, and promotion) among all the jobs
        next_job_jump = sys.maxsize
        for rjob in JOBS.runnable_jobs:
            if 'RUNNING' == rjob['status']:
                qid = rjob['q_id']
                if qid < int(JOBS.num_queue - 1):
                    if gputime:
                        jump_time = int(math.ceil((JOBS.queue_limit[qid] - rjob['executed_time'])/rjob['num_gpu']) + event_time)
                    else:
                        jump_time = int(JOBS.queue_limit[qid] - rjob['executed_time'] + event_time)
                    if jump_time < next_job_jump:
                        next_job_jump = jump_time

            elif 'PENDING' == rjob['status']: # when pending job will be push back to Q0
                if solve_starvation > 0 and rjob['q_id'] > 0 and rjob['total_executed_time'] and rjob['executed_time'] > 0:
                    diff_time = int(rjob['executed_time'] * solve_starvation - rjob['last_pending_time'])
                    if diff_time > 0:
                        jump_time = int(diff_time + event_time)
                        if jump_time < next_job_jump:
                            next_job_jump = jump_time



        LOG.checkpoint(event_time)

def sim_job_events():
    '''
    Simulate job start/end, and gpu allocation
    pick one event from sorted job_event list
    1.ending jobs
    2.check the pending job list, for potential job placements
    3.start jobs
    4.logging
    '''
    while (len(JOBS.job_events) + len(JOBS.pending_jobs))> 0:
        if len(JOBS.job_events) == 0:
            util.print_fn("This cluster is not large enough to run the job")
            break
        event = JOBS.job_events[0]
        event_time = event['time']
        # util.print_fn('--------------------------------- Handle event[time %d]------------------------------------' % event_time)
        #for ending jobs, release gpu
        for e_job in event['end_jobs']:
            #remove from migratable jobs, if it's there
            # JOBS.remote_migratable(e_job)

            #job completes
            CLUSTER.release_job_res(e_job)
            # CLUSTER.release_gpus(e_job)
            LOG.job_complete(e_job, event_time)

        #for pending jobs, try to start
        for p_job in JOBS.pending_jobs:
            # ret = CLUSTER.alloc_gpus(p_job)
            ret = try_get_job_res(p_job)
            if ret == True:
                #if job is migratable, add into migratable job list
                # JOBS.add_migratable(p_job)
                JOBS.remove_from_pending(p_job, event_time)
                JOBS.add_job_end_event(p_job)
                util.print_fn('----job[%d] starts from pending' % p_job['job_idx'])
                # JOBS.read_job_info(p_job['job_idx'])
            else:
                # pending_jobs are sorted, if one is not able to be placement, then the rest are not necessary to consider
                break

        #for new-start jobs, try to start
        for s_job in event['start_jobs']:
            ret = try_get_job_res(s_job)
            # ret = CLUSTER.alloc_gpus(s_job)
            if ret == False:
                #allocation failed, add into pending jobs
                JOBS.move_to_pending(s_job)
                util.print_fn('----job[%d] move to pending' % s_job['job_idx'])
            else:
                #if job is migratable, add into migratable job list
                # JOBS.add_migratable(s_job)
                JOBS.add_job_end_event(s_job)
                util.print_fn('----job[%d] starts' % s_job['job_idx'])
                # JOBS.read_job_info(s_job['job_idx'])

        #sort pending jobs based on the num_gpu
        JOBS.pending_jobs.sort(key = lambda e:e.__getitem__('num_gpu'))

        #remove time_event
        JOBS.job_events.pop(0)
        JOBS.job_events.sort(key = lambda e:e.__getitem__('time'))
        # JOBS.print_job_events()

        LOG.checkpoint(event_time)

    pass


def sim_gpu_demands():
    '''
    Simulate job start/end, and gpu demands
    pick one event from sorted job_event list
    1.ending jobs
    2.check the pending job list, for potential job placements
    3.start jobs
    4.logging
    '''
    while (len(JOBS.job_events) + len(JOBS.pending_jobs))> 0:
        if len(JOBS.job_events) == 0:
            util.print_fn("This cluster is not large enough to run the job")
            break
        event = JOBS.job_events[0]
        event_time = event['time']
        # util.print_fn('--------------------------------- Handle event[time %d]------------------------------------' % event_time)
        #for ending jobs, release gpu
        for e_job in event['end_jobs']:
            #remove from migratable jobs, if it's there
            # JOBS.remote_migratable(e_job)

            # CLUSTER.release_job_res(e_job)
            # LOG.job_complete(e_job, event_time)
            JOBS.delete_gpu_job(e_job)

        #for new-start jobs, try to start
        for s_job in event['start_jobs']:
            #if job is migratable, add into migratable job list
            # JOBS.add_migratable(s_job)
            s_job['end_time'] = s_job['submit_time'] + s_job['duration']
            JOBS.add_job_end_event(s_job)
            util.print_fn('----job[%d] starts' % s_job['job_idx'])
            # JOBS.read_job_info(s_job['job_idx'])
            JOBS.add_gpu_job(s_job)



        #sort pending jobs based on the num_gpu
        # JOBS.pending_jobs.sort(key = lambda e:e.__getitem__('num_gpu'))

        #remove time_event
        JOBS.job_events.pop(0)
        JOBS.job_events.sort(key = lambda e:e.__getitem__('time'))
        # JOBS.print_job_events()

        # LOG.checkpoint(event_time)
        LOG.checkpoint_gpu_demands(event_time)

def cal_r_gittins_index(job_data, a):
    '''
    a means attained-service to that job
    gittins_index = P/E
    r_gi = E/P
    '''
    ut_delta = JOBS.gittins_delta

    data = job_data['data']
    if a > (job_data['data'][-1] - 1):
        return 0.0
    else:
        idx = next(x[0] for x in enumerate(data) if x[1] > a)

    next_a = a + ut_delta
    if next_a > (job_data['data'][-1] - 1):
        idx_delta = job_data['num'] - 1
    else:
        idx_delta = next(x[0] for x in enumerate(data) if x[1] > next_a)
    # print(idx, idx_delta)

    p = round(((idx_delta - idx) * 1.0) / (job_data['num'] - idx), 5)

    e_sum = sum(data[idx : idx_delta]) + (ut_delta * (job_data['num'] - idx_delta))
    e = round(e_sum / (job_data['num'] - idx), 5)

    # rank of gittins index = 1/gi
    # r_gi = round(e / p, 4)
    r_gi = round(p * 1000000 / e, 4)

    # print(idx, idx_delta, p, e_sum, e, r_gi)
    return r_gi


def parse_job_dist():
    job_dist_file = os.path.join(os.getcwd(), 'yarn-gput1000.csv')
    fd = open(job_dist_file, 'r')
    reader = csv.DictReader(fd, delimiter = ',')
    durations = list()
    for row in reader:
        durations.append(int(row['duration']))
    fd.close()
    total_len = len(durations)
    durations.sort()
    print("  %s samples are learned" % total_len)

    job_dict = dict()
    job_dict['num'] = total_len
    job_dict['data'] = durations

    gi = list()
    for v in job_dict['data']:
        gi.append(cal_r_gittins_index(job_dict, int(v-1)))

    # print(gi)
    job_dict['data'].append(sys.maxsize)
    gi.append(0.0)
    job_dict['gittins'] = gi

    return job_dict


def main():

    if FLAGS.schedule == 'multi-dlas-gpu':
        if FLAGS.scheme != 'count':
            util.print_fn("In Main, multi-dlas-gpu without count")
            exit()
    ''' Parse input'''
    parse_job_file(FLAGS.trace_file)
    parse_cluster_spec()

    ''' prepare logging '''
    LOG.init_log()

    # lp.placement(JOBS.job_list[0])
    ''' Prepare jobs'''
    JOBS.prepare_job_start_events()

    # sim_job_events()
    if FLAGS.schedule == 'fifo':
        one_queue_fifo_sim_jobs()
    elif FLAGS.schedule == 'dlas':
        JOBS.job_dist_data = parse_job_dist()
        dlas_sim_jobs()
    elif FLAGS.schedule == 'dlas-gpu':
        dlas_sim_jobs(True)
    elif FLAGS.schedule == 'dlas-gpu-1':
        dlas_sim_jobs(True,1)
    elif FLAGS.schedule == 'dlas-gpu-2':
        dlas_sim_jobs(True,2)
    elif FLAGS.schedule == 'dlas-gpu-05':
        dlas_sim_jobs(True, 0.5)
    elif FLAGS.schedule == 'dlas-gpu-4':
        dlas_sim_jobs(True, 4)
    elif FLAGS.schedule == 'dlas-gpu-8':
        dlas_sim_jobs(True, 8)
    elif FLAGS.schedule == 'dlas-gpu-10':
        dlas_sim_jobs(True, 10)
    elif FLAGS.schedule == 'dlas-gpu-100':
        dlas_sim_jobs(True, 100)
    elif FLAGS.schedule == 'dlas-gpu-1000':
        dlas_sim_jobs(True, 1000)
    else:
        one_queue_fifo_sim_jobs()

if __name__ == '__main__':
    # print('Hello world %d' % 2)
    main()
