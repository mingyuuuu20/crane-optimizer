"""
Load Chart 비교 시각화 — 세 모델의 반경별 인양능력 곡선.
"""

import matplotlib.pyplot as plt
import numpy as np
from crane_models import CRANES, get_capacity

plt.rcParams['axes.unicode_minus'] = False

fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# 색상 매핑
colors = {
    "Potain_MDT_178":    "#D32F2F",
    "Potain_MR_160C":    "#1976D2",
    "Liebherr_280_HC_L": "#388E3C",
}
labels = {
    "Potain_MDT_178":    "Potain MDT 178 (T-type, Hammerhead)",
    "Potain_MR_160C":    "Potain MR 160C (Luffing, Small)",
    "Liebherr_280_HC_L": "Liebherr 280 HC-L 16/28 (Luffing, Large)",
}

# ===== Plot 1: Load chart (선형) =====
ax = axes[0]
for mid, spec in CRANES.items():
    rs = [pt[0] for pt in spec["load_chart"]]
    ws = [pt[1]/1000 for pt in spec["load_chart"]]
    ax.plot(rs, ws, "o-", color=colors[mid], label=labels[mid],
             linewidth=2, markersize=5)

# 갱폼 3.4t (페이로드 + 후크블록 + 리깅) 기준선
ax.axhline(y=3.4, color="black", linestyle="--", linewidth=1.5,
            label="Required: 3.4 t (3.0t payload + hook + rigging)")
ax.fill_between([0, 70], 0, 3.4, alpha=0.05, color="red")

ax.set_xlabel("Working radius (m)", fontsize=11)
ax.set_ylabel("Lifting capacity (tonne)", fontsize=11)
ax.set_title("Load Chart Comparison — Linear Scale",
              fontsize=12, fontweight="bold")
ax.grid(True, alpha=0.3)
ax.legend(loc="upper right", fontsize=9, framealpha=0.95)
ax.set_xlim(0, 65)
ax.set_ylim(0, 30)

# ===== Plot 2: Load chart (로그 스케일) =====
ax = axes[1]
for mid, spec in CRANES.items():
    rs = [pt[0] for pt in spec["load_chart"]]
    ws = [pt[1]/1000 for pt in spec["load_chart"]]
    ax.plot(rs, ws, "o-", color=colors[mid], label=labels[mid],
             linewidth=2, markersize=5)

ax.axhline(y=3.4, color="black", linestyle="--", linewidth=1.5,
            label="Required: 3.4 t")
ax.set_xlabel("Working radius (m)", fontsize=11)
ax.set_ylabel("Lifting capacity (tonne, log)", fontsize=11)
ax.set_title("Load Chart Comparison — Log Scale (focused on small loads)",
              fontsize=12, fontweight="bold")
ax.set_yscale("log")
ax.grid(True, alpha=0.3, which="both")
ax.legend(loc="upper right", fontsize=9, framealpha=0.95)
ax.set_xlim(0, 65)
ax.set_ylim(1, 30)

plt.suptitle(
    "Tower Crane Load Charts — Gongdeok-dong Capstone Project\n"
    "Source: Manitowoc/Potain Data Sheet, LECTURA Specs, Liebherr Brochure",
    fontsize=13, fontweight="bold"
)
plt.tight_layout()
out = "/home/claude/crane_opt/load_charts.png"
plt.savefig(out, dpi=140, bbox_inches="tight")
print(f"저장: {out}")
