"""
F1 / F2 히트맵 생성 — 크레인 위치별 목적함수 값 시각화.
NSGA-II 알고리즘이 들어가기 전 "최적해가 어디 근처일까" 직관 확보용.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import Point

from site_model import (
    SITE, ADJACENT_BUILDINGS, ROADS, PLANNED_BUILDING, ALLOWED_AREA
)
from objectives import compute_F1, compute_F2

plt.rcParams['axes.unicode_minus'] = False

# 모델 선택 (가장 적합 후보)
MODEL_ID = "Potain_MR_160C"
JIB_LENGTH = 30.0  # 30m 지브로 시작

# 격자 정의 — 부지 + 도로 영역에서만 평가
GRID_RES = 1.5  # 격자 간격 (m)
xs = np.arange(-25, 25, GRID_RES)
ys = np.arange(-20, 20, GRID_RES)

F1_grid = np.full((len(ys), len(xs)), np.nan)
F2_grid = np.full((len(ys), len(xs)), np.nan)

print(f"Evaluating {len(xs)} × {len(ys)} = {len(xs)*len(ys)} grid points...")
print(f"Model: {MODEL_ID}, Jib length: {JIB_LENGTH}m")

# 허용 설치 영역(부지 ∪ 도로) 내에서만 평가
for j, y in enumerate(ys):
    for i, x in enumerate(xs):
        pt = Point(x, y)
        # 기초 크기(직경 5m) 가 ALLOWED_AREA 안에 들어가야 설치 가능
        base_circle = pt.buffer(2.5)
        if not ALLOWED_AREA.contains(base_circle):
            continue
        try:
            f1 = compute_F1((x, y), MODEL_ID, JIB_LENGTH)
            f2 = compute_F2((x, y), MODEL_ID)
            F1_grid[j, i] = f1["F1"]
            F2_grid[j, i] = f2["F2_hours"]
        except Exception:
            continue

# === Visualization ===
fig, axes = plt.subplots(1, 2, figsize=(20, 9))

def add_overlay(ax):
    """부지·건물·도로 외곽선 그리기."""
    # 부지
    site_xy = list(SITE.exterior.coords)
    ax.add_patch(MplPolygon(site_xy, facecolor="none",
                             edgecolor="red", linewidth=2.5, zorder=10))
    # 신축 건물
    pb_xy = list(PLANNED_BUILDING.exterior.coords)
    ax.add_patch(MplPolygon(pb_xy, facecolor="none",
                             edgecolor="blue", linewidth=1.5,
                             linestyle="--", zorder=10))
    # 인접 건물
    for direction, b in ADJACENT_BUILDINGS.items():
        coords = list(b["footprint"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="gray", alpha=0.3,
                                 edgecolor="black", linewidth=0.8, zorder=5))
        c = b["footprint"].centroid
        ax.text(c.x, c.y, f"{direction}\n{b['floors']}F", ha="center", va="center",
                fontsize=7, color="black")
    # 도로
    for road in ROADS.values():
        coords = list(road["polygon"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#EEE", alpha=0.5,
                                 edgecolor="#999", linewidth=0.5, zorder=2))

# --- F1 heatmap ---
ax = axes[0]
add_overlay(ax)

# F1 컨투어
F1_masked = np.ma.masked_invalid(F1_grid)
mesh = ax.pcolormesh(xs, ys, F1_masked, cmap="RdYlGn_r",
                      shading="nearest", alpha=0.75, zorder=3,
                      vmin=np.nanmin(F1_grid), vmax=np.nanmax(F1_grid))
cb = plt.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
cb.set_label("F1 (Risk Index, lower = safer)", fontsize=10)

# 최솟값 위치 표시
if np.any(~np.isnan(F1_grid)):
    j_min, i_min = np.unravel_index(np.nanargmin(F1_grid), F1_grid.shape)
    x_opt, y_opt = xs[i_min], ys[j_min]
    ax.plot(x_opt, y_opt, "k*", markersize=20, zorder=20,
             markeredgecolor="white", markeredgewidth=1.5)
    ax.annotate(f"Min F1\n({x_opt:.1f}, {y_opt:.1f})\nF1={F1_grid[j_min, i_min]:.0f}",
                xy=(x_opt, y_opt), xytext=(10, 10),
                textcoords="offset points",
                fontsize=10, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="yellow",
                          edgecolor="black", alpha=0.95),
                zorder=21)

ax.set_xlabel("X (East, m)", fontsize=11)
ax.set_ylabel("Y (North, m)", fontsize=11)
ax.set_title(f"F1: Third-Party Safety Risk\n({MODEL_ID}, jib={JIB_LENGTH}m)",
             fontsize=12, fontweight="bold")
ax.set_aspect("equal")
ax.set_xlim(-30, 30)
ax.set_ylim(-25, 25)
ax.grid(alpha=0.2)

# --- F2 heatmap ---
ax = axes[1]
add_overlay(ax)

F2_masked = np.ma.masked_invalid(F2_grid)
mesh2 = ax.pcolormesh(xs, ys, F2_masked, cmap="RdYlGn_r",
                       shading="nearest", alpha=0.75, zorder=3,
                       vmin=np.nanmin(F2_grid), vmax=np.nanmax(F2_grid))
cb2 = plt.colorbar(mesh2, ax=ax, fraction=0.046, pad=0.04)
cb2.set_label("F2 (Cycle time, hours, lower = faster)", fontsize=10)

if np.any(~np.isnan(F2_grid)):
    j_min, i_min = np.unravel_index(np.nanargmin(F2_grid), F2_grid.shape)
    x_opt, y_opt = xs[i_min], ys[j_min]
    ax.plot(x_opt, y_opt, "k*", markersize=20, zorder=20,
             markeredgecolor="white", markeredgewidth=1.5)
    ax.annotate(f"Min F2\n({x_opt:.1f}, {y_opt:.1f})\nF2={F2_grid[j_min, i_min]:.1f}h",
                xy=(x_opt, y_opt), xytext=(10, 10),
                textcoords="offset points",
                fontsize=10, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="cyan",
                          edgecolor="black", alpha=0.95),
                zorder=21)

ax.set_xlabel("X (East, m)", fontsize=11)
ax.set_ylabel("Y (North, m)", fontsize=11)
ax.set_title(f"F2: Lifting Cycle Time\n({MODEL_ID}, jib={JIB_LENGTH}m)",
             fontsize=12, fontweight="bold")
ax.set_aspect("equal")
ax.set_xlim(-30, 30)
ax.set_ylim(-25, 25)
ax.grid(alpha=0.2)

plt.suptitle(
    "Objective Function Landscape — Gongdeok-dong 256-42\n"
    "Lower is better for both. Notice: F1 and F2 minimums are at DIFFERENT locations → trade-off → Pareto needed.",
    fontsize=13, fontweight="bold"
)
plt.tight_layout()

out_path = "/home/claude/crane_opt/objectives_heatmap.png"
plt.savefig(out_path, dpi=130, bbox_inches="tight")
print(f"저장: {out_path}")

# 분석 출력
print("\n=== 분석 ===")
print(f"F1 범위: {np.nanmin(F1_grid):.0f} ~ {np.nanmax(F1_grid):.0f}")
print(f"F2 범위: {np.nanmin(F2_grid):.1f}h ~ {np.nanmax(F2_grid):.1f}h")
if np.any(~np.isnan(F1_grid)) and np.any(~np.isnan(F2_grid)):
    j1, i1 = np.unravel_index(np.nanargmin(F1_grid), F1_grid.shape)
    j2, i2 = np.unravel_index(np.nanargmin(F2_grid), F2_grid.shape)
    print(f"F1 최소 위치: ({xs[i1]:.1f}, {ys[j1]:.1f})")
    print(f"F2 최소 위치: ({xs[i2]:.1f}, {ys[j2]:.1f})")
    if (i1, j1) != (i2, j2):
        print("→ F1·F2 최소 위치가 다름 → trade-off 존재 → Pareto 최적화 의미 있음 ✅")
