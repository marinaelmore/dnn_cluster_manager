import pandas
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("-jf", "--job_file", help="Job File")

args = parser.parse_args()

print( "Job File {}".format(args.job_file))
