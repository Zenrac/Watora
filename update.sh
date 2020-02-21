#!/bin/bash

python3.6 -V > /dev/null 2>&1 || {
    echo >&2 "Python 3.6 doesn't seem to be installed.  Do you have a weird installation?"
    echo >&2 "If you have python 3.6, use it to run run.py instead of this script."
    exit 1; }

python3.6 -m pip install --upgrade -r requirements.txt
