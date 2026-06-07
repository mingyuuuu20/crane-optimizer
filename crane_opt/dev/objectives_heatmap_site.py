"""
================================================================================
objectives_heatmap_site.py
================================================================================
범용 F1/F2 히트맵 — 임의 부지에 대한 목적함수 landscape 시각화
--------------------------------------------------------------------------------
원본 objectives_heatmap.py 의 범용 버전.

용도:
  1. NSGA-II 알고리즘이 들어가기 전 "최적해가 어디 근처일까" 직관 확보
  2. F1·F2 최소 위치가 다름 (trade-off 존재) 시각화 → Pareto 의 정당성
  3. 부지별 landscape 비교 → 알고리즘 일반성 검증

CLI:
    python objectives_heatmap_site.py sites/gongdeok_256_42.json
    python objectives_heatmap_site.py --all      # 모든 부지 grid
    python objectives_heatmap_site.py --model Liebherr_280_HC_L --jib 35
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import Point

# 한글 폰트
import matplotlib.font_manager as fm
def _setup_font():
    cands = ["Malgun Gothic", "NanumGothic", "AppleGothic",
              "Noto Sans CJK KR", "DejaVu Sans"]
    avail = {f.name for f in fm.fontManager.ttflist}
    for c in cands:
        if c in avail:
            plt.rcParams["font.family"] = c
            return c
    return "DejaVu Sans"
_setup_font()
plt.rcParams["axes.unicode_minus"] = False

from site_loader import load_site, list_sites
from site_helpers import use_site


# =============================================================================
# 격자 평가
# =============================================================================
def evaluate_grid(site, model_id="Potain_MR_160C", jib_length=27.0,
                    grid_res=1.5):
    """주어진 부지에 대해 격자별 F1/F2 평가.

    부지/도로 영역 (ALLOWED_AREA) 안에서만 평가.
    """
    # use_site 이후 호출되는 import (활성 site 반영)
    use_site(site)
    from objectives import compute_F1, compute_F2

    sb = site.SEARCH_BOUNDS
    xs = np.arange(sb["x_range"][0], sb["x_range"][1] + grid_res, grid_res)
    ys = np.arange(sb["y_range"][0], sb["y_range"][1] + grid_res, grid_res)

    F1_grid = np.full((len(ys), len(xs)), np.nan)
    F2_grid = np.full((len(ys), len(xs)), np.nan)

    n_evaluated = 0
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            pt = Point(x, y)
            base_circle = pt.buffer(2.5)
            if not site.ALLOWED_AREA.contains(base_circle):
                continue
            try:
                f1 = compute_F1((x, y), model_id, jib_length)
                f2 = compute_F2((x, y), model_id)
                F1_grid[j, i] = f1["F1"]
                F2_grid[j, i] = f2["F2_hours"]
                n_evaluated += 1
            except Exception:
                continue

    return {
        "xs": xs, "ys": ys,
        "F1": F1_grid, "F2": F2_grid,
        "n_evaluated": n_evaluated,
        "model": model_id, "jib_length": jib_length,
    }


# =============================================================================
# 부지 overlay
# =============================================================================
def add_overlay(ax, site):
    """부지·건물·도로 외곽선."""
    # 도로
    for key, r in site.ROADS.items():
        coords = list(r["polygon"].exterior.coords)
        color = "#EEE" if r["occupation_allowed"] else "#F8D7DA"
        ax.add_patch(MplPolygon(coords, facecolor=color, alpha=0.5,
                                  edgecolor="#999", linewidth=0.5, zorder=2))
    # 인접 건물
    for key, b in site.ADJACENT_BUILDINGS.items():
        coords = list(b["footprint"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="gray", alpha=0.5,
                                  edgecolor="black", linewidth=0.8, zorder=5))
        c = b["footprint"].centroid
        ax.text(c.x, c.y, f"{key}\n{b['floors']}F",
                ha="center", va="center", fontsize=6, color="black", zorder=6)
    # 부지
    ax.add_patch(MplPolygon(list(site.SITE.exterior.coords),
                              facecolor="none", edgecolor="red",
                              linewidth=2.5, zorder=10))
    # 신축
    ax.add_patch(MplPolygon(list(site.PLANNED_BUILDING.exterior.coords),
                              facecolor="none", edgecolor="blue",
                              linewidth=1.5, linestyle="--", zorder=10))


# =============================================================================
# 단일 부지 figure
# =============================================================================
def draw_single_site(site, out_path, model_id="Potain_MR_160C",
                       jib_length=27.0, grid_res=1.5):
    """단일 부지 F1·F2 히트맵 (2 panel)."""
    print(f"  격자 평가 중: {site.metadata.get('display_name')}")
    g = evaluate_grid(site, model_id, jib_length, grid_res)
    if g["n_evaluated"] == 0:
        print(f"  ⚠️ 격자에 valid 점 0개 — skip")
        return None
    print(f"    평가 격자: {g['n_evaluated']}개 / 전체 {len(g['xs'])*len(g['ys'])}")

    fig, axes = plt.subplots(1, 2, figsize=(20, 9))

    # F1 히트맵
    ax = axes[0]
    add_overlay(ax, site)
    F1m = np.ma.masked_invalid(g["F1"])
    mesh = ax.pcolormesh(g["xs"], g["ys"], F1m, cmap="RdYlGn_r",
                          shading="nearest", alpha=0.75, zorder=3)
    cb = plt.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("F1 (제3자 안전위험, 낮을수록 안전)", fontsize=10)
    # 최솟값 위치 표시
    if not np.all(np.isnan(g["F1"])):
        j_min, i_min = np.unravel_index(np.nanargmin(g["F1"]), g["F1"].shape)
        x_opt, y_opt = g["xs"][i_min], g["ys"][j_min]
        ax.plot(x_opt, y_opt, "k*", markersize=22, zorder=20,
                 markeredgecolor="white", markeredgewidth=1.5)
        ax.annotate(f"Min F1\n({x_opt:.1f}, {y_opt:.1f})\n"
                     f"F1={g['F1'][j_min, i_min]:.0f}",
                     xy=(x_opt, y_opt), xytext=(10, 10),
                     textcoords="offset points", fontsize=10,
                     fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.4", facecolor="yellow",
                               edgecolor="black", alpha=0.95), zorder=21)
    sb = site.SEARCH_BOUNDS
    ax.set_xlim(sb["x_range"][0] - 3, sb["x_range"][1] + 3)
    ax.set_ylim(sb["y_range"][0] - 3, sb["y_range"][1] + 3)
    ax.set_xlabel("X (m, 동측+)", fontsize=11)
    ax.set_ylabel("Y (m, 북측+)", fontsize=11)
    ax.set_title(f"F1: 제3자 안전위험 지수\n({model_id}, jib={jib_length}m)",
                  fontsize=12, fontweight="bold")
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)

    # F2 히트맵
    ax = axes[1]
    add_overlay(ax, site)
    F2m = np.ma.masked_invalid(g["F2"])
    mesh2 = ax.pcolormesh(g["xs"], g["ys"], F2m, cmap="RdYlGn_r",
                           shading="nearest", alpha=0.75, zorder=3)
    cb2 = plt.colorbar(mesh2, ax=ax, fraction=0.046, pad=0.04)
    cb2.set_label("F2 (양중 사이클 시간, h, 낮을수록 빠름)", fontsize=10)
    if not np.all(np.isnan(g["F2"])):
        j_min, i_min = np.unravel_index(np.nanargmin(g["F2"]), g["F2"].shape)
        x_opt, y_opt = g["xs"][i_min], g["ys"][j_min]
        ax.plot(x_opt, y_opt, "k*", markersize=22, zorder=20,
                 markeredgecolor="white", markeredgewidth=1.5)
        ax.annotate(f"Min F2\n({x_opt:.1f}, {y_opt:.1f})\n"
                     f"F2={g['F2'][j_min, i_min]:.1f}h",
                     xy=(x_opt, y_opt), xytext=(10, 10),
                     textcoords="offset points", fontsize=10,
                     fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.4", facecolor="cyan",
                               edgecolor="black", alpha=0.95), zorder=21)
    ax.set_xlim(sb["x_range"][0] - 3, sb["x_range"][1] + 3)
    ax.set_ylim(sb["y_range"][0] - 3, sb["y_range"][1] + 3)
    ax.set_xlabel("X (m, 동측+)", fontsize=11)
    ax.set_ylabel("Y (m, 북측+)", fontsize=11)
    ax.set_title(f"F2: 양중 사이클 시간\n({model_id}, jib={jib_length}m)",
                  fontsize=12, fontweight="bold")
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)

    # 분석 정보
    if not np.all(np.isnan(g["F1"])) and not np.all(np.isnan(g["F2"])):
        j1, i1 = np.unravel_index(np.nanargmin(g["F1"]), g["F1"].shape)
        j2, i2 = np.unravel_index(np.nanargmin(g["F2"]), g["F2"].shape)
        dist = ((g["xs"][i1] - g["xs"][i2])**2 +
                 (g["ys"][j1] - g["ys"][j2])**2) ** 0.5
        tradeoff_msg = (
            f"F1 최소 ({g['xs'][i1]:.1f},{g['ys'][j1]:.1f}) ↔ "
            f"F2 최소 ({g['xs'][i2]:.1f},{g['ys'][j2]:.1f}) — "
            f"거리 {dist:.1f}m → Trade-off 존재 → Pareto 최적화 의미 있음 ✅"
        )
    else:
        tradeoff_msg = ""

    plt.suptitle(
        f"{site.metadata.get('display_name', 'Site')} — 목적함수 Landscape\n"
        f"{tradeoff_msg}",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  → {out_path}")
    return g


# =============================================================================
# 모든 부지 grid (4 부지를 4x2 grid 로 한 figure)
# =============================================================================
def draw_all_sites_grid(out_path="results/heatmap_all_sites.png",
                          model_id="Potain_MR_160C", jib_length=27.0,
                          grid_res=1.5):
    """모든 부지를 한 figure 에 4행 (각 row 는 F1·F2)."""
    site_files = list_sites("sites")
    n = len(site_files)
    fig, axes = plt.subplots(n, 2, figsize=(16, 7 * n))
    if n == 1:
        axes = np.array([axes])

    for i, sf in enumerate(site_files):
        site = load_site(sf)
        print(f"\n[{i+1}/{n}] {site.metadata.get('display_name')}")
        g = evaluate_grid(site, model_id, jib_length, grid_res)

        for col, (key, label) in enumerate([("F1", "F1 안전위험"),
                                              ("F2", "F2 시간(h)")]):
            ax = axes[i, col]
            add_overlay(ax, site)
            if g["n_evaluated"] == 0:
                ax.text(0.5, 0.5, "ALL POINTS INFEASIBLE\n(no valid placement)",
                         ha="center", va="center", fontsize=11,
                         transform=ax.transAxes,
                         bbox=dict(boxstyle="round,pad=0.5",
                                    facecolor="#FFE0E0",
                                    edgecolor="red"))
            else:
                arr = np.ma.masked_invalid(g[key])
                if arr.count() > 0:
                    mesh = ax.pcolormesh(g["xs"], g["ys"], arr,
                                          cmap="RdYlGn_r",
                                          shading="nearest",
                                          alpha=0.75, zorder=3)
                    plt.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
                    j_min, i_min = np.unravel_index(
                        np.nanargmin(g[key]), g[key].shape)
                    ax.plot(g["xs"][i_min], g["ys"][j_min], "k*",
                             markersize=18, zorder=20,
                             markeredgecolor="white", markeredgewidth=1.2)
            sb = site.SEARCH_BOUNDS
            ax.set_xlim(sb["x_range"][0] - 3, sb["x_range"][1] + 3)
            ax.set_ylim(sb["y_range"][0] - 3, sb["y_range"][1] + 3)
            ax.set_aspect("equal")
            ax.grid(alpha=0.2)
            ax.set_title(f"{site.metadata.get('display_name', '?')[:30]}\n"
                          f"{label}",
                          fontsize=10, fontweight="bold")
            ax.set_xlabel("X (m)", fontsize=9)
            if col == 0:
                ax.set_ylabel("Y (m)", fontsize=9)

    plt.suptitle(
        f"목적함수 Landscape — 4 부지 비교 (model={model_id}, jib={jib_length}m)\n"
        "★ = 최소값 위치 · 좌측 F1(안전위험) · 우측 F2(시간)",
        fontsize=14, fontweight="bold", y=1.0,
    )
    plt.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"\n→ Grid: {out_path}")
    return out_path


# =============================================================================
# CLI
# =============================================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("site", nargs="?", help="부지 JSON 경로")
    p.add_argument("--all", action="store_true",
                    help="모든 부지 한 grid figure")
    p.add_argument("--model", default="Potain_MR_160C",
                    help="크레인 모델 (Potain_MR_160C, Potain_MDT_178, "
                         "Liebherr_280_HC_L)")
    p.add_argument("--jib", type=float, default=27.0,
                    help="지브 길이 (m)")
    p.add_argument("--grid-res", type=float, default=1.5)
    p.add_argument("--out-dir", default="results")
    args = p.parse_args()

    if args.all:
        out = Path(args.out_dir) / "heatmap_all_sites.png"
        draw_all_sites_grid(str(out), args.model, args.jib, args.grid_res)
        # 개별 figure 도
        for sf in list_sites("sites"):
            site = load_site(sf)
            sid = site.metadata.get("site_id")
            out = Path(args.out_dir) / f"heatmap_{sid}.png"
            draw_single_site(site, str(out), args.model, args.jib,
                              args.grid_res)
    elif args.site:
        site = load_site(args.site)
        sid = site.metadata.get("site_id")
        out = Path(args.out_dir) / f"heatmap_{sid}.png"
        draw_single_site(site, str(out), args.model, args.jib, args.grid_res)
    else:
        print("usage: objectives_heatmap_site.py <site.json> | --all")


if __name__ == "__main__":
    main()
