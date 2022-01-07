#!/bin/bash

yum install screen
yum install python36 python36-pip python36-venv

python3.6 -m venv venv
source ./venv/bin/activate
pip3 install --upgrade pip
pip3 install -r ./requirements.txt
