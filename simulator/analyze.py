import pandas as pd
import argparse
from os.path import exists

parser = argparse.ArgumentParser()
parser.add_argument("-lf", "--log_file", help="Log File")
parser.add_argument("-jf", "--job_file", help="Job File")
args = parser.parse_args()

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

    print(df)
    
    # Total Run Time
    start_time = df.iloc[0]['time']
    end_time = df.iloc[len(df)-1]['time']
    print("*** Total Run Time: %s" %(end_time-start_time))

if __name__ == '__main__':
    analyze_job_file()
