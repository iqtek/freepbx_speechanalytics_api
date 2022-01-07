#!/bin/sh

source ./venv/bin/activate
#uvicorn server:app --reload --port 5005  --host 127.0.0.1
uvicorn server:app --port 5005  --host 127.0.0.1 --workers 10
