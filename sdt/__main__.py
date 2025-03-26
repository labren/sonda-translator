import argparse
from read_raw import readRaw


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', type=lambda s: s.lower(), help='Nome da estação', default='')
    args = parser.parse_args()
    print(args)