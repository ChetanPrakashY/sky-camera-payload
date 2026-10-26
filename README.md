# sky-camera-payload

A small imaging payload that photographs star fields, detects the streaks satellites leave as they cross
the field, and sends a compact list of detections to the ground. This repository has the payload software
and the full engineering documentation for it.

**The camera is simulated.** No hardware has been built yet. A sensor model with realistic noise, dark current
and pixel defects stands in for the camera, so every result below shows that the software and the method
work, not how a particular camera performs. The documents say which values are assumptions (marked TBC).

## Payload software (`payload/`)

| Step | Code | What it does |
|---|---|---|
| Simulate | `sim/camera.py`, `sim/simulate.py` | IMX477-like sensor (1.55 um pixels, 12-bit) behind a 50 mm lens; star fields, satellite streaks, calibration frames |
| Calibrate | `calib/masters.py` | master dark, normalised flat, bad-pixel mask |
| Characterise | `calib/characterize.py` | gain, read noise, dark current, saturation by the EMVA 1288 photon-transfer method |
| Process on board | `onboard/procframe.c` | dark/flat/bad-pixel correction, background estimate, source extraction, streak detection from second moments, telemetry packet with CRC-16 (C11, no dependencies) |
| Decode on the ground | `ground/parse_tm.py` | finds packets by sync marker, rejects bad CRCs, writes CSV |
| Evaluate | `ground/evaluate.py` | compares detections with the simulator's truth |
| Budgets | `budgets.py` | power and data budgets, also as a spreadsheet with live formulas |

```bash
cd payload
./run_trial.sh trial_data                     # whole chain, a few seconds
python3 -m unittest discover -s tests -v      # C vs numpy, CRC, detection performance
```

Results of the simulated trial: the calibration recovers the simulated gain (0.903 vs 0.900 e-/DN), read
noise (3.09 vs 3.00 e-) and dark current (1.98 vs 2.00 e-/s); 99% of stars above 2000 e- are found with a
centroid error of 0.18 px; all three satellite streaks are found with direction errors under 0.3 degrees.
One streak merged with a bright star, which biased its centre; that is written up as a risk with a fix.

## Documentation (`docs/`)

Controlled documents for the payload, written as Markdown in `docs/src/` and built into Word files by
`docs/build_docs.py`. Numbers in the documents are filled in from the trial and budget outputs, so they always
match the software.

| Document | Word | Read online |
|---|---|---|
| Preliminary design review data package | [SKY-PDR-001.docx](docs/out/SKY-PDR-001.docx) | [SKY-PDR-001.md](docs/out/SKY-PDR-001.md) |
| Interface control document | [SKY-ICD-001.docx](docs/out/SKY-ICD-001.docx) | [SKY-ICD-001.md](docs/out/SKY-ICD-001.md) |
| Ground trial plan and procedure | [SKY-TP-001.docx](docs/out/SKY-TP-001.docx) | [SKY-TP-001.md](docs/out/SKY-TP-001.md) |
| On-board software user manual | [SKY-UM-001.docx](docs/out/SKY-UM-001.docx) | [SKY-UM-001.md](docs/out/SKY-UM-001.md) |
| Simulated trial report | [SKY-TR-001.docx](docs/out/SKY-TR-001.docx) | [SKY-TR-001.md](docs/out/SKY-TR-001.md) |

Also: the block diagram and a PERT-based Gantt chart (`docs/figures/`), and the budget spreadsheet
(`docs/budgets/budgets.xlsx`).

```bash
cd payload && ./run_trial.sh trial_data && python3 budgets.py ../docs/budgets
cd ../docs && python3 figures/make_figures.py && python3 build_docs.py     # needs python-docx
```
