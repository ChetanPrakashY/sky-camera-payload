"""Simulate a calibration set and a short night-sky observation, written the way the payload stores
data: raw 16-bit little-endian frames (12 bits used) plus one JSON line of metadata per frame.

    python simulate.py OUTDIR
"""
import json
import pathlib
import sys
import numpy as np
from camera import Sensor, star_field, add_streak, PLATE_SCALE, W, H

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data")
for d in ("darks", "flats", "ptc", "science"):
    (out / d).mkdir(parents=True, exist_ok=True)
sensor = Sensor(seed=1)
rng = np.random.default_rng(2)
T_EXP = 0.2
meta = []

def save(sub, name, img, **info):
    img.astype("<u2").tofile(out / sub / f"{name}.raw")
    meta.append(dict(file=f"{sub}/{name}.raw", width=W, height=H, **info))

for i in range(16):                                            # darks: lens cap on, same exposure as science
    save("darks", f"dark_{i:02d}", sensor.expose(np.zeros((H, W)), T_EXP), t_exp=T_EXP, kind="dark")
for i in range(16):                                            # flats: evenly lit diffuser, ~40% of full well
    save("flats", f"flat_{i:02d}", sensor.expose(np.full((H, W), 7000.0), T_EXP), t_exp=T_EXP, kind="flat")
for level in np.geomspace(200, 30000, 30):                    # photon-transfer pairs at increasing light
    for k in (0, 1):
        save("ptc", f"ptc_{level:07.0f}_{k}", sensor.expose(np.full((H, W), level), T_EXP), t_exp=T_EXP,
             kind="ptc", level_e_s=float(level))
for t in (0.05, 0.1, 0.2, 0.4, 0.8):                            # dark current: darks at several exposure times
    save("darks", f"darkramp_{t:.2f}", sensor.expose(np.zeros((H, W)), t), t_exp=t, kind="darkramp")

truth = []
t0 = 1_700_000_000.0                                            # GNSS-disciplined time of the first frame (s)
for i in range(6):
    scene, stars = star_field(np.random.default_rng(100 + i))
    items = list(stars)
    if i in (1, 3, 4):                                         # a satellite crosses in three of six frames
        # a LEO satellite near zenith moves ~0.8 deg/s; in 0.2 s that is ~0.16 deg = ~90 px at this plate scale
        length = 0.8 * 3600 * T_EXP / PLATE_SCALE
        items.append(add_streak(scene, rng.uniform(150, 350), rng.uniform(150, 350), rng.uniform(0, 180), length, 4e5))
    ts = t0 + 2.0 * i + 1e-6 * rng.integers(0, 2000)            # frames every 2 s, trigger jitter below 2 ms
    save("science", f"sci_{i:03d}", sensor.expose(scene, T_EXP), t_exp=T_EXP, kind="science", time_gps=ts, index=i)
    truth.append(dict(frame=i, objects=items))

with open(out / "frames.jsonl", "w") as f:
    for m in meta:
        f.write(json.dumps(m) + "\n")
(out / "truth.json").write_text(json.dumps(truth, indent=1))
print(f"plate scale {PLATE_SCALE:.2f} arcsec/px, field {W*PLATE_SCALE/60:.1f} arcmin; "
      f"{len(meta)} frames written to {out}/ (simulated data)")
