"""Tests for the payload pipeline. Runs the whole simulated trial once (about half a minute).

    python -m unittest discover -s tests -v
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ground"))
from parse_tm import crc16_ccitt, packets  # noqa: E402


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.d = pathlib.Path(cls.tmp.name) / "trial"
        subprocess.run([str(ROOT / "run_trial.sh"), str(cls.d)], check=True, capture_output=True)
        subprocess.run(["make", "-s", "-C", str(ROOT / "onboard"), "procframe-check"], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_c_correction_matches_numpy(self):
        d, w = self.d, 512
        raw_file = d / "science" / "sci_002.raw"
        subprocess.run([str(ROOT / "onboard" / "procframe-check"), str(d / "calib"), str(raw_file), "512", "512", "2",
                        "0", str(d / "t.bin"), "--corrected", str(d / "c.f32")], check=True, capture_output=True)
        raw = np.fromfile(raw_file, "<u2").reshape(w, w).astype(np.float32)
        dark = np.fromfile(d / "calib" / "dark.f32", "<f4").reshape(w, w)
        flat = np.fromfile(d / "calib" / "flat.f32", "<f4").reshape(w, w)
        bad = np.fromfile(d / "calib" / "badpix.u8", np.uint8).reshape(w, w).astype(bool)
        ref = (raw - dark) / flat
        out = ref.copy()
        for y, x in zip(*np.nonzero(bad)):
            v = [ref[yy, xx] for yy in range(max(0, y - 1), min(w, y + 2)) for xx in range(max(0, x - 1), min(w, x + 2))
                 if (yy, xx) != (y, x) and not bad[yy, xx]]
            out[y, x] = np.median(v)
        c = np.fromfile(d / "c.f32", "<f4").reshape(w, w)
        self.assertLess(np.abs(c - out).max(), 1e-3)

    def test_crc_check_value_and_corruption(self):
        self.assertEqual(crc16_ccitt(b"123456789"), 0x29B1)
        blob = bytearray((self.d / "telemetry.bin").read_bytes())
        self.assertEqual(len(list(packets(bytes(blob)))), 6)
        blob[30] ^= 0x01                                   # one flipped bit inside the first packet
        self.assertEqual(len(list(packets(bytes(blob)))), 5)

    def test_detection_performance(self):
        s = json.loads((self.d / "evaluation.json").read_text())
        self.assertGreaterEqual(s["completeness_bright"], 0.95)
        self.assertLess(s["centroid_rms_px"], 0.3)
        self.assertEqual(s["streaks_found"], s["streaks_total"])
        self.assertLess(s["max_streak_angle_err_deg"], 1.0)


if __name__ == "__main__":
    unittest.main()
