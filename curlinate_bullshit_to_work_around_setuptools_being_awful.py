#!/usr/bin/env python3

# This script is a complete piece of bullshit that should not exist
# and is an affront to reasonable packaging. See setup.py for more
# details on the nonsense that I was forced to do just so that the Go
# binary can be installed to $PATH by the Python package.

import os
import sys


def main():
    os.execl(os.path.split(__file__)[0] + "/curlinate", "curlinate", *sys.argv[1:])
