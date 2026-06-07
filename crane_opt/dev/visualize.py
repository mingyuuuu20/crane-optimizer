"""
================================================================================
visualize.py
================================================================================
부지·인접건물·도로 시각화 — 데이터 모델 검증용
출력: site_diagram.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon as MplPolygon
import numpy as np
from site_model import (
    SITE, ADJACENT_BUILDINGS, ROADS, PLANNED_BUILDING,
    PLANNED_BUILDING_HEIGHT_M, LIFT_POINTS, ALLOWED_AREA,
    SITE_AREA_OFFICIAL_M2,
)

# 한글 폰트 설정 (사용 환경에 맞게)
plt.rcParams['font.family'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def shapely_to_mpl(polygon, **kwargs):
    """Shapely Polygon → matplotlib patch."""
    xy = list(polygon.exterior.coords)
    return MplPolygon(xy, **kwargs)


def height_to_color(h):
    """건물 높이를 색으로 매핑 (낮음=옅음, 높음=짙음)."""
    norm = min(h / 60.0, 1.0)
    return (0.4 + 0.4*(1-norm), 0.4 + 0.3*(1-norm), 0.4 + 0.2*(1-norm))


def main():
    fig, ax = plt.subplots(1, 1, figsize=(13, 13))

    # --- Roads ---
    for key, road in ROADS.items():
        patch = shapely_to_mpl(road["polygon"],
                                facecolor="#E8E8E8",
                                edgecolor="#999999",
                                linewidth=0.8, zorder=1)
        ax.add_patch(patch)
        cx, cy = road["polygon"].centroid.x, road["polygon"].centroid.y
        ax.text(cx, cy, f"Road\n{road['width_m']}m",
                ha="center", va="center", fontsize=8, color="#555555",
                style="italic", zorder=2)

    # --- Adjacent buildings ---
    for direction, b in ADJACENT_BUILDINGS.items():
        patch = shapely_to_mpl(b["footprint"],
                                facecolor=height_to_color(b["height_m"]),
                                edgecolor="#333333",
                                linewidth=1.0,
                                alpha=0.85, zorder=3)
        ax.add_patch(patch)
        cx, cy = b["footprint"].centroid.x, b["footprint"].centroid.y
        ax.text(cx, cy, f"{direction}\n{b['floors']}F\n{b['height_m']:.0f}m",
                ha="center", va="center", fontsize=9,
                fontweight="bold", color="white", zorder=4)

    # --- Site (Lot 256-42) ---
    site_patch = shapely_to_mpl(SITE,
                                 facecolor="#FFF3CD",
                                 edgecolor="#D32F2F",
                                 linewidth=3.0, zorder=5)
    ax.add_patch(site_patch)
    sc = SITE.centroid
    ax.text(sc.x, sc.y - 8, f"LOT 256-42\n{SITE_AREA_OFFICIAL_M2} m²\nQuasi-residential",
            ha="center", va="center", fontsize=11,
            fontweight="bold", color="#D32F2F", zorder=10)

    # --- Planned building ---
    pb_patch = shapely_to_mpl(PLANNED_BUILDING,
                               facecolor="#1976D2",
                               edgecolor="#0D47A1",
                               linewidth=1.5,
                               alpha=0.5, zorder=6)
    ax.add_patch(pb_patch)
    pc = PLANNED_BUILDING.centroid
    ax.text(pc.x, pc.y, f"Planned\n9F / 32m\n280 m²",
            ha="center", va="center", fontsize=10,
            fontweight="bold", color="white", zorder=11)

    # --- Lift points ---
    for i, p in enumerate(LIFT_POINTS, 1):
        marker = "o" if i < len(LIFT_POINTS) else "s"  # 마지막은 야적장 (square)
        color = "#FFEB3B" if i < len(LIFT_POINTS) else "#FF5722"
        ax.scatter(p[0], p[1], s=140, c=color, marker=marker,
                   edgecolors="black", linewidths=1.5, zorder=12)
        ax.annotate(f"P{i}" if i < len(LIFT_POINTS) else "Yard",
                    (p[0], p[1]), xytext=(7, 7),
                    textcoords="offset points",
                    fontsize=9, fontweight="bold", zorder=13)

    # --- Coordinate axes ---
    ax.axhline(y=0, color="gray", linewidth=0.3, linestyle=":")
    ax.axvline(x=0, color="gray", linewidth=0.3, linestyle=":")
    ax.plot(0, 0, "k+", markersize=12, zorder=20)
    ax.text(1, 1, "(0,0) origin\n= site centroid", fontsize=7,
            color="gray", zorder=20)

    # --- Scale ---
    ax.set_xlim(-45, 45)
    ax.set_ylim(-40, 40)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.set_xlabel("X (East, m)", fontsize=10)
    ax.set_ylabel("Y (North, m)", fontsize=10)
    ax.set_title(
        "Gongdeok-dong 256-42 — Capstone Site Geometric Model\n"
        "Site 550.6m² (irregular), Planned 9F building, 6 adjacent buildings, 3 roads",
        fontsize=12, fontweight="bold", pad=15
    )

    # --- Legend ---
    legend_items = [
        mpatches.Patch(facecolor="#FFF3CD", edgecolor="#D32F2F",
                       linewidth=2, label="Lot 256-42 (site)"),
        mpatches.Patch(facecolor="#1976D2", edgecolor="#0D47A1",
                       alpha=0.5, label="Planned building (9F, 32m)"),
        mpatches.Patch(facecolor="#888888", edgecolor="#333333",
                       label="Adjacent buildings (color=height)"),
        mpatches.Patch(facecolor="#E8E8E8", edgecolor="#999999",
                       label="Roads"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#FFEB3B",
                    markeredgecolor="black", markersize=10,
                    label="Lift points (building)"),
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="#FF5722",
                    markeredgecolor="black", markersize=10,
                    label="Material yard"),
    ]
    ax.legend(handles=legend_items, loc="upper left",
              fontsize=9, framealpha=0.95)

    # --- Compass ---
    ax.annotate("N", (38, 35), fontsize=14, fontweight="bold",
                ha="center", color="darkred")
    ax.annotate("", xy=(38, 33), xytext=(38, 28),
                arrowprops=dict(arrowstyle="->", color="darkred", lw=2))

    plt.tight_layout()
    out_path = "/home/claude/crane_opt/site_diagram.png"
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    print(f"저장 완료: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
