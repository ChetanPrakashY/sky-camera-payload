"""Compare decoded detections with the simulator's truth: completeness by brightness, centroid error,
false detections, and streak angle and length.

    python evaluate.py DATADIR PACKETS     # prints a report, writes DATADIR/evaluation.json
"""
import json
import math
import pathlib
import sys
import numpy as np
from parse_tm import packets

data = pathlib.Path(sys.argv[1])
truth = {t["frame"]: t["objects"] for t in json.loads((data / "truth.json").read_text())}
T_EXP = 0.2
found = {h["frame"]: d for h, d in packets(open(sys.argv[2], "rb").read())}

star_rows, cen_err, false_pos, streaks = [], [], 0, []
for f, objs in truth.items():
    dets = found.get(f, [])
    used = set()
    for o in sorted(objs, key=lambda o: -o["flux_e_s"]):
        if o["kind"] == "star":
            near = [(math.hypot(d["x"] - o["x"], d["y"] - o["y"]), k) for k, d in enumerate(dets) if k not in used and not d["streak"]]
            dist, k = min(near, default=(99, None))
            hit = dist < 1.5
            star_rows.append((o["flux_e_s"] * T_EXP, hit))
            if hit:
                used.add(k); cen_err.append(dist)
        else:
            # a streak counts as found if a streak detection lies on the true line with the right direction;
            # a bright star touching the streak merges into it and shifts the centre along the line
            a = math.radians(o["angle_deg"])
            best = None
            for k, d in enumerate(dets):
                if not d["streak"]:
                    continue
                dang = (d["angle_deg"] - o["angle_deg"] + 90) % 180 - 90
                perp = abs(-(d["x"] - o["x"]) * math.sin(a) + (d["y"] - o["y"]) * math.cos(a))
                if abs(dang) < 3 and perp < 3:
                    best = (k, d, dang, math.hypot(d["x"] - o["x"], d["y"] - o["y"]))
            if best:
                k, d, dang, dist = best
                used.add(k)
                streaks.append(dict(frame=f, pos_err=dist, angle_err=dang, length=d["length_px"],
                                    true_length=o["length_px"], blended=dist > 3))
            else:
                streaks.append(dict(frame=f, missed=True))
    false_pos += len(dets) - len(used)

e = np.array([r[0] for r in star_rows]); hit = np.array([r[1] for r in star_rows])
print("Star detection (simulated frames)")
for lo, hi in [(200, 600), (600, 2000), (2000, 20000)]:
    m = (e >= lo) & (e < hi)
    print(f"  {lo:5d}-{hi:5d} e- per star: {hit[m].sum():3d} of {m.sum():3d} found ({100*hit[m].mean():.0f} %)")
print(f"  centroid error: rms {np.sqrt(np.mean(np.square(cen_err))):.3f} px = {np.sqrt(np.mean(np.square(cen_err)))*6.39:.2f} arcsec")
print(f"  false detections: {false_pos} in {len(truth)} frames")
print("Streaks")
for s in streaks:
    if s.get("missed"):
        print(f"  frame {s['frame']}: MISSED")
    else:
        print(f"  frame {s['frame']}: position error {s['pos_err']:.2f} px, angle error {s['angle_err']:+.2f} deg, "
              f"length {s['length']:.1f} px (true {s['true_length']:.1f})"
              + ("  <- blended with a star: centre and length biased" if s["blended"] else ""))
bins = [dict(lo=lo, hi=hi, found=int(hit[(e >= lo) & (e < hi)].sum()), total=int(((e >= lo) & (e < hi)).sum()))
        for lo, hi in [(200, 600), (600, 2000), (2000, 20000)]]
for b in bins:
    b["pct"] = round(100 * b["found"] / b["total"])
summary = dict(bins=bins, streaks=streaks, frames=len(truth), completeness_bright=float(hit[e >= 2000].mean()), centroid_rms_px=float(np.sqrt(np.mean(np.square(cen_err)))),
               false_detections=int(false_pos), streaks_found=sum(not s.get("missed") for s in streaks), streaks_total=len(streaks),
               max_streak_angle_err_deg=float(max(abs(s["angle_err"]) for s in streaks if not s.get("missed"))))
(data / "evaluation.json").write_text(json.dumps(summary, indent=1))
