import pandas as pd
import argparse
from os.path import exists
import log

parser = argparse.ArgumentParser()
parser.add_argument("-lf", "--log_file", help="Log File")
parser.add_argument("-jf", "--job_file", help="Job File")
args = parser.parse_args()

#Convert MS TO S
TIME_CONST = 1000000000

def read_into_pandas():
    if 'log_file' in args and args.log_file:
        file_path = "%s/job.csv" %args.log_file
        print( "Log File %s" %file_path)
    else:
        print("DN exist")
        exit(0)

    if exists(file_path):
        print("File exists")
    else:
        print("DN exist")
        exit(0)

    df = pd.read_csv(file_path)
    return df

def analyze_job_file():
    df = read_into_pandas()
    if df.empty:
        print("I should handle this error here and exit")
        exit(0)

    # Total Run Time
    start_time = df['start_time'].min()
    end_time = df['end_time'].max()
    total_run_time = end_time-start_time

    # Max Pending time
    pending_time = df['pending_time'].max()

    # Max JCT
    jct_time = df['JCT'].max()

    # Determining Fair Share Score
    df["actual_util"] = df.executed_time/(total_run_time*4)
    df["expected_util"] = df.duration/(total_run_time*4)
    df["delta_util"] = df.actual_util - df.expected_util

    # Average Util
    average_util = df['actual_util'].mean()
    sum_delta = df['delta_util'].sum()

    # Fair Share Score
    df['fss'] = (df.delta_util/sum_delta)*0.3+(df.actual_util/average_util)*0.7

    # Log User Behavior
    if 'log_file' in args and args.log_file:
        file_path = "%s/users.csv" %args.log_file
        df.to_csv(file_path,encoding='utf-8', index=False,columns=['user_id', 'fss'])

    print(df)
    print("*** Max JCT: %s" %(jct_time/TIME_CONST))
    print("*** Max Pending Time: %s" %(pending_time/TIME_CONST))
    print("\n*** Total Run Time: %s" %((end_time-start_time)/TIME_CONST))

if __name__ == '__main__':
    analyze_job_file()
