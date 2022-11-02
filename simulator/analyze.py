import pandas as pd
import argparse
from os.path import exists

parser = argparse.ArgumentParser()
parser.add_argument("-lf", "--log_file", help="Log File")
parser.add_argument("-jf", "--job_file", help="Job File")
args = parser.parse_args()

def read_into_pandas(args):
    if 'log_file' in args and args.log_file:
        file_path = "%s/job.csv" %args.log_file
        print( "Log File %s" %file_path)

        if exists(file_path):
            print("File exists")
            df = pd.read_csv(file_path)
            print(df)
        else:
            print("DN exist")


def analyze_job_file(args):
    read_into_pandas(args)

if __name__ == '__main__':
    analyze_job_file(args)
