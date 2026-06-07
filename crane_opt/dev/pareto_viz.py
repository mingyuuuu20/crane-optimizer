"""
Pareto front 시각화 + 부지 상의 최적 후보 위치 표시.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Circle
from site_model import (
    SITE, ADJACENT_BUILDINGS, ROADS, PLANNED_BUILDING, LIFT_POINTS
)
from optimizer import MODEL_LIST

plt.rcParams['axes.unicode_minus'] = False

# Pareto 결과 로드
data = np.load("/home/claude/crane_opt/pareto_result.npz")
F = data["F"]
X = data["X"]

print(f"Pareto front 크기: {len(F)}")
print(f"F1 범위: {F[:,0].min():.1f} ~ {F[:,0].max():.1f}")
print(f"F2 범위: {F[:,1].min():.1f}h ~ {F[:,1].max():.1f}h")

# F1으로 정렬
order = np.argsort(F[:, 0])
F_sorted = F[order]
X_sorted = X[order]

# 3개 대표 해 선택: F1 최소 (안전 우선), F2 최소 (효율 우선), 중간 절충
idx_min_f1 = 0
idx_min_f2 = len(F_sorted) - 1
idx_balance = np.argmin(
    ((F_sorted[:, 0] - F_sorted[:, 0].min()) / (F_sorted[:, 0].max() - F_sorted[:, 0].min() + 1e-9))**2
    + ((F_sorted[:, 1] - F_sorted[:, 1].min()) / (F_sorted[:, 1].max() - F_sorted[:, 1].min() + 1e-9))**2
)

representatives = {
    "A_min_F1":   (idx_min_f1, "Safety-optimal (min F1)", "red"),
    "B_balance":  (idx_balance, "Balanced (knee)",        "blue"),
    "C_min_F2":   (idx_min_f2, "Efficiency-optimal (min F2)", "green"),
}

# ======================================================================
# Figure
# ======================================================================
fig = plt.figure(figsize=(20, 9))
gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.3])

# ------ (1) Pareto front (왼쪽) ------
ax1 = fig.add_subplot(gs[0])

# 모델별로 색 구분
model_colors = {0: "#D32F2F", 1: "#1976D2", 2: "#388E3C"}
model_labels = {0: "Potain MDT 178 (T)", 1: "Potain MR 160C (Lf)", 2: "Liebherr 280 HC-L (Lf)"}

for m_idx, color in model_colors.items():
    mask = np.array([int(X[i, 2]) == m_idx for i in range(len(X))])
    if mask.sum() > 0:
        ax1.scatter(F[mask, 0], F[mask, 1],
                     c=color, s=70, alpha=0.65, label=f"{model_labels[m_idx]} (n={mask.sum()})",
                     edgecolors="black", linewidths=0.5)

# Pareto 곡선 (전체 통합)
ax1.plot(F_sorted[:, 0], F_sorted[:, 1], "k--", linewidth=0.8, alpha=0.4)

# 대표 3개 강조
for key, (idx, label, c) in representatives.items():
    f1, f2 = F_sorted[idx]
    ax1.scatter(f1, f2, s=350, marker="*", c=c,
                 edgecolors="black", linewidths=2, zorder=10)
    ax1.annotate(f"{label}\nF1={f1:.0f}, F2={f2:.1f}h",
                  (f1, f2), xytext=(15, 15),
                  textcoords="offset points",
                  fontsize=10, fontweight="bold",
                  bbox=dict(boxstyle="round,pad=0.4",
                            facecolor=c, alpha=0.3, edgecolor=c))

ax1.set_xlabel("F1 — Third-Party Safety Risk Index  (lower = safer)",
                fontsize=11)
ax1.set_ylabel("F2 — Lifting Cycle Time (calendar hours, lower = faster)",
                fontsize=11)
ax1.set_title("Pareto Front — NSGA-II Result\n"
               f"{len(F)} non-dominated solutions, pop=80, n_gen=40",
               fontsize=12, fontweight="bold")
ax1.legend(loc="upper right", fontsize=9, framealpha=0.95)
ax1.grid(alpha=0.3)

# ------ (2) 부지 + 대표 3개 위치 (오른쪽) ------
ax2 = fig.add_subplot(gs[1])

# 부지 오버레이
def add_overlay(ax):
    for key, r in ROADS.items():
        coords = list(r["polygon"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#EEEEEE",
                                  edgecolor="#999999", linewidth=0.5, zorder=2))
    for direction, b in ADJACENT_BUILDINGS.items():
        coords = list(b["footprint"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#888",
                                  edgecolor="black", linewidth=1, alpha=0.5, zorder=3))
        c = b["footprint"].centroid
        ax.text(c.x, c.y, f"{direction}\n{b['floors']}F", ha="center", va="center",
                fontsize=8, color="white", fontweight="bold")
    site_xy = list(SITE.exterior.coords)
    ax.add_patch(MplPolygon(site_xy, facecolor="#FFF3CD",
                              edgecolor="red", linewidth=2.5, zorder=5))
    pb_xy = list(PLANNED_BUILDING.exterior.coords)
    ax.add_patch(MplPolygon(pb_xy, facecolor="#1976D2",
                              edgecolor="#0D47A1", linewidth=1.5, alpha=0.4, zorder=6))
    for p in LIFT_POINTS:
        ax.scatter(p[0], p[1], s=80, c="#FFEB3B",
                    edgecolors="black", linewidths=1, zorder=8)

add_overlay(ax2)

# 대표 3개 위치 표시
for key, (idx, label, color) in representatives.items():
    x, y, m_idx, jib, mast = X_sorted[idx]
    model = MODEL_LIST[int(m_idx)]

    # 크레인 위치
    ax2.scatter(x, y, s=400, marker="*", c=color,
                 edgecolors="black", linewidths=2, zorder=20)

    # Working radius circle
    circle = Circle((x, y), jib, fill=False,
                     edgecolor=color, linewidth=2, linestyle="--",
                     alpha=0.7, zorder=15)
    ax2.add_patch(circle)

    # 라벨
    ax2.annotate(f"{label}\n({x:.1f}, {y:.1f}) jib={jib:.1f}m",
                  (x, y), xytext=(10, -25),
                  textcoords="offset points",
                  fontsize=9, fontweight="bold",
                  bbox=dict(boxstyle="round,pad=0.3",
                            facecolor="white", edgecolor=color, alpha=0.95))

ax2.set_xlabel("X (East, m)", fontsize=11)
ax2.set_ylabel("Y (North, m)", fontsize=11)
ax2.set_title("Optimal Crane Locations — 3 Representative Solutions\n"
               "Dashed circles = working radius (jib length)",
               fontsize=12, fontweight="bold")
ax2.set_aspect("equal")
ax2.set_xlim(-40, 40)
ax2.set_ylim(-35, 35)
ax2.grid(alpha=0.3)
ax2.legend([
    plt.Line2D([0], [0], marker="*", color="red", markersize=15, linestyle="",
                markeredgecolor="black"),
    plt.Line2D([0], [0], marker="*", color="blue", markersize=15, linestyle="",
                markeredgecolor="black"),
    plt.Line2D([0], [0], marker="*", color="green", markersize=15, linestyle="",
                markeredgecolor="black"),
], ["Safety-optimal", "Balanced", "Efficiency-optimal"],
    loc="upper right", fontsize=9)

plt.suptitle(
    "Gongdeok-dong 256-42 — Multi-Objective Tower Crane Placement Optimization (NSGA-II)\n"
    "Pareto Front + Optimal Locations",
    fontsize=14, fontweight="bold"
)
plt.tight_layout()
out = "/home/claude/crane_opt/pareto_solution.png"
plt.savefig(out, dpi=140, bbox_inches="tight")
print(f"\n저장: {out}")

# 대표 해 상세 출력
print("\n" + "="*70)
print("대표 해 상세")
print("="*70)
for key, (idx, label, color) in representatives.items():
    x, y, m_idx, jib, mast = X_sorted[idx]
    f1, f2 = F_sorted[idx]
    model = MODEL_LIST[int(m_idx)]
    print(f"\n[{label}]")
    print(f"  위치: ({x:.2f}, {y:.2f}) m")
    print(f"  모델: {model}")
    print(f"  지브: {jib:.2f} m,  마스트: {mast:.2f} m")
    print(f"  F1 (안전): {f1:.2f}")
    print(f"  F2 (시간): {f2:.2f}h = {f2/8:.1f} 작업일")
