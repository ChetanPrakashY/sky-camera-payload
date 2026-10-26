"""Measure gain, read noise, dark current and full well from the calibration frames (the EMVA 1288
photon-transfer method), and compare with the values the simulator used.

    python characterize.py DATADIR      # prints a table and writes DATADIR/calib/ptc.png
"""
import json
import pathlib
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

data = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data")
meta = [json.loads(l) for l in open(data / "frames.jsonl")]
W, H = meta[0]["width"], meta[0]["height"]
load = lambda m: np.fromfile(data / m["file"], dtype="<u2").reshape(H, W).astype(float)
win = (slice(H // 4, 3 * H // 4), slice(W // 4, 3 * W // 4))       # central window: flat illumination

darks = [load(m)[win] for m in meta if m["kind"] == "dark"][:2]
dark_mean = 0.5 * (darks[0].mean() + darks[1].mean())
dark_var = 0.5 * np.var(darks[0] - darks[1])
levels = sorted({m["level_e_s"] for m in meta if m["kind"] == "ptc"})
mu, var = [], []
for lv in levels:
    a, b = [load(m)[win] for m in meta if m["kind"] == "ptc" and m["level_e_s"] == lv]
    mu.append(0.5 * (a.mean() + b.mean()) - dark_mean)
    var.append(0.5 * np.var(a - b) - dark_var)          # frame difference removes fixed-pattern noise
mu, var = np.array(mu), np.array(var)
sat = int(np.argmax(var))
lin = (mu < 0.6 * mu[sat]) & (mu > 0)
k_dn_per_e, _ = np.polyfit(mu[lin], var[lin], 1)
gain = 1 / k_dn_per_e
read_e = np.sqrt(dark_var) * gain

ramp = sorted((m["t_exp"], load(m)) for m in meta if m["kind"] == "darkramp")
good = np.fromfile(data / "calib" / "badpix.u8", dtype=np.uint8).reshape(H, W)[win] == 0
t = np.array([r[0] for r in ramp]); lvl = np.array([r[1][win][good].mean() for r in ramp])   # mean, not median: DN are integers
dark_rate = np.polyfit(t, lvl, 1)[0] * gain

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "sim"))
import camera  # noqa: E402  (only to compare with what the simulator used)
rows = [("gain (e-/DN)", gain, camera.GAIN_E_PER_DN), ("read noise (e-)", read_e, camera.READ_NOISE_E),
        ("dark current, typical pixel (e-/s)", dark_rate, camera.DARK_E_PER_S),
        ("saturation: variance peak vs hard clip", mu[sat] * gain, min(camera.FULL_WELL_E, (2 ** camera.BITS - 1 - camera.OFFSET_DN) * camera.GAIN_E_PER_DN))]
print(f"{'quantity':36} {'measured':>9} {'simulated':>9}")
for name, m, s in rows:
    print(f"{name:36} {m:9.2f} {s:9.2f}")
print("(the variance peaks below the hard clip because the brightest pixels in the window clip first;\n EMVA 1288 defines saturation capacity as the variance peak)")
print(f"dynamic range {mu[sat] * gain / read_e:.0f}:1 ({20*np.log10(mu[sat] * gain / read_e):.1f} dB)")

keys = ["gain_e_per_dn", "read_noise_e", "dark_e_per_s", "saturation_e"]
(data / "calib" / "characterization.json").write_text(json.dumps(
    {k: dict(measured=round(float(m), 3), simulated=round(float(s), 3)) for k, (_, m, s) in zip(keys, rows)}
    | {"dynamic_range_db": round(float(20 * np.log10(mu[sat] * gain / read_e)), 1),
       "dynamic_range": round(float(mu[sat] * gain / read_e))}, indent=1))

fig, ax = plt.subplots(figsize=(5, 3.2))
ax.loglog(mu * gain, var * gain ** 2, "o", ms=4, label="measured")
e = np.geomspace(mu[lin].min() * gain, mu[sat] * gain, 50)
ax.loglog(e, e, "--", lw=1, label="shot noise (variance = mean)")
ax.axvline(mu[sat] * gain, color="gray", lw=0.6)
ax.set(xlabel="signal (e-)", ylabel="temporal variance (e-$^2$)", title="Photon transfer curve (simulated sensor)")
ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(data / "calib" / "ptc.png", dpi=150)
