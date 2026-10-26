"""Build the calibration products the on-board software loads: master dark, normalised master flat and a
bad-pixel mask. Medians of 16 frames reject outliers; the mask marks hot pixels (from the dark) and dead
or weak pixels (from the flat).

    python masters.py DATADIR      # writes DATADIR/calib/{dark.f32, flat.f32, badpix.u8}
"""
import json
import pathlib
import sys
import numpy as np

data = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data")
meta = [json.loads(l) for l in open(data / "frames.jsonl")]
W, H = meta[0]["width"], meta[0]["height"]

def load(m):
    return np.fromfile(data / m["file"], dtype="<u2").reshape(H, W).astype(np.float32)

darks = np.stack([load(m) for m in meta if m["kind"] == "dark"])
flats = np.stack([load(m) for m in meta if m["kind"] == "flat"])
dark = np.median(darks, axis=0)
flat = np.median(flats, axis=0) - dark
flat /= np.median(flat)

med, mad = np.median(dark), np.median(np.abs(dark - np.median(dark)))
hot = dark > med + 10 * 1.4826 * mad            # 1.4826 MAD = one Gaussian sigma
dead = flat < 0.5
bad = (hot | dead).astype(np.uint8)

out = data / "calib"
out.mkdir(exist_ok=True)
dark.astype("<f4").tofile(out / "dark.f32")
flat.astype("<f4").tofile(out / "flat.f32")
bad.tofile(out / "badpix.u8")
print(f"master dark median {med:.1f} DN; flat range {flat[~(hot|dead)].min():.3f}-{flat[~(hot|dead)].max():.3f}; "
      f"bad pixels: {hot.sum()} hot, {dead.sum()} dead")
