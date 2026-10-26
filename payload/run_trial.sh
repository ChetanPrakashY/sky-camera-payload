#!/usr/bin/env bash
# End-to-end run on simulated data: simulate -> calibrate -> on-board processing -> ground decode -> evaluate.
#   ./run_trial.sh [OUTDIR]
set -euo pipefail
cd "$(dirname "$0")"
D=${1:-trial_data}
rm -rf "$D"
python3 sim/simulate.py "$D"
python3 calib/masters.py "$D"
python3 calib/characterize.py "$D"
make -s -C onboard procframe
python3 - "$D" <<'PY'
import json, subprocess, sys, pathlib
d = pathlib.Path(sys.argv[1])
for m in map(json.loads, open(d / "frames.jsonl")):
    if m["kind"] == "science":
        subprocess.run(["onboard/procframe", str(d / "calib"), str(d / m["file"]), str(m["width"]), str(m["height"]),
                        str(m["index"]), f"{m['time_gps']:.6f}", str(d / "telemetry.bin")], check=True)
PY
python3 ground/parse_tm.py "$D/telemetry.bin"
python3 ground/evaluate.py "$D" "$D/telemetry.bin"
