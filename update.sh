#!/bin/bash

python3.7 -V > /dev/null 2>&1 || {
    echo >&2 "Python 3.7 doesn't seem to be installed.  Do you have a weird installation?"
    echo >&2 "If you have another python version up to 3.6+, use it to run run.py instead of this script."
    exit 1; }

python3.7 -m pip install --upgrade -r requirements.txt
