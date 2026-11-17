#!/bin/sh
# Start the unattended Phase III runner in the background, keeping the Mac awake while it runs.
cd "$(dirname "$0")"
mkdir -p phase3
if pgrep -f "run_phase3.py" >/dev/null; then echo "already running"; exit 0; fi
nohup caffeinate -ims .venv/bin/python run_phase3.py >> phase3/stdout.log 2>&1 &
sleep 2; pgrep -fl "run_phase3.py" && tail -3 phase3/run.log
