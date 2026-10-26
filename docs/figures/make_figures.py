"""Figures for the design documents: the payload block diagram and the project Gantt chart (PERT
three-point estimates, critical path in red)."""
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = pathlib.Path(__file__).resolve().parent


def block_diagram():
    fig, ax = plt.subplots(figsize=(9, 4.6)); ax.set_xlim(0, 100); ax.set_ylim(0, 55); ax.axis("off")
    boxes = {  # name: (x, y, w, h, label)
        "lens": (2, 33, 14, 9, "Lens\n50 mm f/1.8"), "cam": (22, 33, 16, 9, "Camera\nIMX477 sensor"),
        "obc": (46, 30, 20, 15, "On-board computer\nLinux, procframe,\nSD card storage"),
        "gnss": (46, 8, 14, 9, "GNSS receiver\n(PPS output)"), "imu": (64, 8, 10, 9, "IMU"),
        "radio": (74, 33, 13, 9, "Telemetry\nradio"), "gs": (90, 33, 9, 9, "Ground\nstation"),
        "pwr": (14, 8, 22, 9, "Battery 2S Li-ion\nbuck 5 V, LDO 3.3 V"), "htr": (2, 8, 10, 9, "Camera\nheater"),
    }
    for k, (x, y, w, h, lab) in boxes.items():
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4", fc="#EEF2F7" if k != "gs" else "#F4F4F4", ec="#33475B"))
        ax.text(x + w / 2, y + h / 2, lab, ha="center", va="center", fontsize=7.5)
    def arrow(x1, y1, x2, y2, lab, dy=1.2):
        ax.annotate("", (x2, y2), (x1, y1), arrowprops=dict(arrowstyle="->", color="#33475B", lw=1))
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, lab, ha="center", fontsize=6.5, color="#33475B")
    arrow(16.4, 37.5, 21.6, 37.5, "light")
    arrow(38.4, 37.5, 45.6, 37.5, "MIPI CSI-2")
    arrow(66.4, 37.5, 73.6, 37.5, "UART")
    arrow(87.4, 37.5, 89.6, 37.5, "RF", dy=1.5)
    arrow(53, 17.4, 53, 29.6, "UART + PPS", dy=0)
    arrow(69, 17.4, 62, 29.6, "I2C", dy=0)
    arrow(30, 17.4, 45.6, 30.5, "5 V / 3.3 V to all units", dy=-4)
    arrow(13.6, 12.5, 12.4, 12.5, "", dy=0)
    ax.text(13, 15.5, "7.4 V", ha="center", fontsize=6.5, color="#33475B")
    ax.text(50, 52, "Sky-camera payload: functional block diagram", ha="center", fontsize=10, weight="bold")
    fig.tight_layout(); fig.savefig(HERE / "block_diagram.png", dpi=160)


TASKS = {  # task: ((optimistic, most likely, pessimistic) working days, predecessors)
    "Requirements + SRR": ((3, 5, 8), []),
    "Optics and camera selection": ((3, 5, 10), ["Requirements + SRR"]),
    "On-board software v1": ((8, 12, 20), ["Requirements + SRR"]),
    "Power and thermal design": ((4, 6, 10), ["Optics and camera selection"]),
    "PDR": ((2, 3, 5), ["Optics and camera selection", "On-board software v1", "Power and thermal design"]),
    "Build and integrate": ((8, 10, 16), ["PDR"]),
    "Bench calibration": ((3, 4, 7), ["Build and integrate"]),
    "Ground night-sky trial": ((2, 3, 8), ["Bench calibration"]),
    "Trial report": ((2, 3, 5), ["Ground night-sky trial"]),
}


def gantt():
    te = {k: (o + 4 * m + p) / 6 for k, ((o, m, p), _) in TASKS.items()}
    es, ef = {}, {}
    for k, (_, pre) in TASKS.items():
        es[k] = max((ef[p] for p in pre), default=0.0); ef[k] = es[k] + te[k]
    end = max(ef.values()); ls = {}
    for k in reversed(list(TASKS)):
        succ = [s for s, (_, pre) in TASKS.items() if k in pre]
        ls[k] = min((ls[s] for s in succ), default=end) - te[k]
    crit = [k for k in TASKS if abs(ls[k] - es[k]) < 1e-9]
    sd = sum(((p - o) / 6) ** 2 for k, ((o, m, p), _) in TASKS.items() if k in crit) ** 0.5
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for i, k in enumerate(TASKS):
        ax.barh(i, te[k], left=es[k], color="#C0392B" if k in crit else "#7F8C8D")
        if ls[k] > es[k]:
            ax.barh(i, ls[k] - es[k], left=ef[k], color="none", edgecolor="#7F8C8D", hatch="//", lw=0.5)
    ax.set_yticks(range(len(TASKS)), list(TASKS), fontsize=8); ax.invert_yaxis()
    ax.set_xlabel("working days from start")
    ax.set_title(f"Schedule: {end:.0f} days expected, sigma {sd:.0f} days. Red: critical path. Hatched: slack.", fontsize=9)
    fig.tight_layout(); fig.savefig(HERE / "gantt.png", dpi=160)
    return dict(end=round(end, 1), sigma=round(sd, 1), critical=crit,
                rows=[dict(task=k, o=v[0][0], m=v[0][1], p=v[0][2], te=round(te[k], 1), start=round(es[k], 1),
                           slack=round(ls[k] - es[k], 1)) for k, v in TASKS.items()])


if __name__ == "__main__":
    import json
    block_diagram()
    (HERE / "schedule.json").write_text(json.dumps(gantt(), indent=1))
    print("block_diagram.png, gantt.png, schedule.json")
