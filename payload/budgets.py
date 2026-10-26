"""Power and data budgets for the payload, written as a spreadsheet and as tables for the design document.
Component numbers are assumptions marked TBC (to be confirmed from datasheets and bench measurements).

    python budgets.py OUTDIR      # writes OUTDIR/budgets.xlsx and OUTDIR/budgets.json
"""
import json
import pathlib
import sys
from openpyxl import Workbook
from openpyxl.styles import Font

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
out.mkdir(parents=True, exist_ok=True)
V_BAT, ETA_BUCK, MARGIN, FLIGHT_H = 7.4, 0.90, 0.20, 4.0

LOADS = [  # name, rail V, power when on (W), duty cycle, source
    ("Camera module (IMX477)", 5.0, 1.0, 1.0, "TBC: bench measurement"),
    ("On-board computer", 5.0, 5.0, 1.0, "TBC: bench measurement under processing load"),
    ("GNSS receiver", 3.3, 0.15, 1.0, "TBC: datasheet"),
    ("IMU", 3.3, 0.05, 1.0, "TBC: datasheet"),
    ("Telemetry radio (transmitting)", 5.0, 1.0, 0.10, "TBC: datasheet; 10% transmit duty"),
    ("Camera heater", V_BAT, 3.0, 0.40, "TBC: thermal analysis"),
]
rows, p5, p33, pbat = [], 0.0, 0.0, 0.0
for name, v, p, duty, src in LOADS:
    avg = p * duty
    rows.append(dict(load=name, rail_v=v, on_w=p, duty=duty, avg_w=round(avg, 3), source=src))
    if v == 5.0: p5 += avg
    elif v == 3.3: p33 += avg
    else: pbat += avg
p33_in = p33 / (3.3 / 5.0)                                   # 3.3 V from 5 V through an LDO
p5_total = p5 + p33_in
p_battery = p5_total / ETA_BUCK + pbat
energy_wh = p_battery * FLIGHT_H * (1 + MARGIN)

FULL_W, FULL_H, FRAME_S = 4056, 3040, 2.0
frame_mb = FULL_W * FULL_H * 2 / 1e6                         # 12-bit pixels stored in 16 bits
stored_gb_per_h = frame_mb * 3600 / FRAME_S / 1e3
packet_b = 21 + 16 * 60                                      # header + CRC + ~60 sources (measured in the trial)
downlink_bps = packet_b * 8 / FRAME_S

summary = dict(rows=rows, p5_w=round(p5, 3), p33_w=round(p33, 3), ldo_loss_w=round(p33_in - p33, 3),
               buck_loss_w=round(p5_total / ETA_BUCK - p5_total, 3), battery_w=round(p_battery, 2),
               energy_wh=round(energy_wh, 1), capacity_mah=round(energy_wh / V_BAT * 1000),
               frame_mb=round(frame_mb, 2), stored_gb_per_h=round(stored_gb_per_h, 1),
               packet_bytes=packet_b, downlink_bps=round(downlink_bps), raw_downlink_mbps=round(frame_mb * 8 / FRAME_S, 1),
               assumptions=dict(battery_v=V_BAT, buck_efficiency=ETA_BUCK, margin=MARGIN, flight_h=FLIGHT_H, frame_period_s=FRAME_S))
(out / "budgets.json").write_text(json.dumps(summary, indent=1))

wb = Workbook(); ws = wb.active; ws.title = "Power"
ws.append(["Load", "Rail (V)", "On power (W)", "Duty", "Average (W)", "Source"])
for r in rows:
    ws.append([r["load"], r["rail_v"], r["on_w"], r["duty"], None, r["source"]])
n = len(rows) + 1
for i in range(2, n + 1):
    ws[f"E{i}"] = f"=C{i}*D{i}"                              # formulas, so the sheet stays live when edited
ws.append([]); ws.append(["Total average load", None, None, None, f"=SUM(E2:E{n})"])
ws.append(["Battery power incl. regulator losses", None, None, None, summary["battery_w"]])
ws.append([f"Energy for {FLIGHT_H:.0f} h incl. {MARGIN:.0%} margin (Wh)", None, None, None, summary["energy_wh"]])
for c in ws[1]: c.font = Font(bold=True)
ws.column_dimensions["A"].width = 44; ws.column_dimensions["F"].width = 44
ds = wb.create_sheet("Data")
ds.append(["Quantity", "Value", "Unit"])
for k, v, u in [("Full-frame size", summary["frame_mb"], "MB"), ("Frame period", FRAME_S, "s"),
                ("Raw data stored per hour", summary["stored_gb_per_h"], "GB"),
                ("Raw data rate if downlinked", summary["raw_downlink_mbps"], "Mbit/s"),
                ("Detection packet (60 sources)", packet_b, "bytes"), ("Detection downlink rate", summary["downlink_bps"], "bit/s")]:
    ds.append([k, v, u])
for c in ds[1]: c.font = Font(bold=True)
ds.column_dimensions["A"].width = 34
wb.save(out / "budgets.xlsx")
print(f"battery {summary['battery_w']} W, {summary['energy_wh']} Wh ({summary['capacity_mah']} mAh at {V_BAT} V); "
      f"raw {summary['stored_gb_per_h']} GB/h stored; detections {summary['downlink_bps']} bit/s vs raw {summary['raw_downlink_mbps']} Mbit/s")
