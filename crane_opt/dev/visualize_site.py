"""
================================================================================
visualize_site.py
================================================================================
범용 부지 다이어그램 생성기 — 임의 SiteData 를 받아 도면을 그린다.
--------------------------------------------------------------------------------
visualize.py (공덕동 전용) 의 범용 버전.

CLI 사용:
    python visualize_site.py sites/synthetic_a_rectangular.json
    python visualize_site.py sites/gongdeok_256_42.json --out gongdeok.png
    python visualize_site.py --all     # sites/ 모든 부지 일괄 생성
"""
import argparse
import os
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon as MplPolygon

from site_loader import load_site, list_sites

# 한글 폰트 — Linux/Mac 에 Malgun Gothic 없을 수 있으니 fallback
import matplotlib.font_manager as fm
def _setup_font():
    candidates = ["Malgun Gothic", "NanumGothic", "AppleGothic",
                   "Noto Sans CJK KR", "DejaVu Sans"]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            plt.rcParams["font.family"] = c
            return c
    plt.rcParams["font.family"] = "DejaVu Sans"
    return "DejaVu Sans"

_setup_font()
plt.rcParams["axes.unicode_minus"] = False


def shapely_to_mpl(polygon, **kwargs):
    xy = list(polygon.exterior.coords)
    return MplPolygon(xy, **kwargs)


def height_to_color(h):
    norm = min(h / 60.0, 1.0)
    return (0.4 + 0.4*(1-norm), 0.4 + 0.3*(1-norm), 0.4 + 0.2*(1-norm))


def draw_site(site, out_path=None, figsize=(13, 13), ax=None):
    """SiteData 객체 → matplotlib 다이어그램."""
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(1, 1, figsize=figsize)

    # 검색 범위 (자동 zoom)
    sb = site.SEARCH_BOUNDS
    xlim = (sb["x_range"][0] - 8, sb["x_range"][1] + 8)
    ylim = (sb["y_range"][0] - 6, sb["y_range"][1] + 6)

    # --- Roads ---
    for key, road in site.ROADS.items():
        color = "#E8E8E8" if road["occupation_allowed"] else "#F8D7DA"
        edge = "#999" if road["occupation_allowed"] else "#C00"
        ax.add_patch(shapely_to_mpl(
            road["polygon"], facecolor=color,
            edgecolor=edge, linewidth=0.8, zorder=1
        ))
        cx, cy = road["polygon"].centroid.x, road["polygon"].centroid.y
        label = f"도로\n{road['width_m']}m"
        if not road["occupation_allowed"]:
            label += "\n(점용불가)"
        ax.text(cx, cy, label, ha="center", va="center",
                fontsize=8, color="#555", style="italic", zorder=2)

    # --- Adjacent buildings ---
    for key, b in site.ADJACENT_BUILDINGS.items():
        ax.add_patch(shapely_to_mpl(
            b["footprint"],
            facecolor=height_to_color(b["height_m"]),
            edgecolor="#333", linewidth=1.0, alpha=0.85, zorder=3
        ))
        cx, cy = b["footprint"].centroid.x, b["footprint"].centroid.y
        ax.text(cx, cy, f"{key}\n{b['floors']}F\n{b['height_m']:.0f}m",
                ha="center", va="center", fontsize=9,
                fontweight="bold", color="white", zorder=4)

    # --- Site ---
    ax.add_patch(shapely_to_mpl(
        site.SITE, facecolor="#FFF3CD",
        edgecolor="#D32F2F", linewidth=3.0, zorder=5
    ))
    sc = site.SITE.centroid
    site_label = (f"{site.metadata.get('display_name', 'Site')}\n"
                   f"{site.SITE_AREA_OFFICIAL_M2:.0f}㎡")
    ax.text(sc.x, sc.y + (sb["y_range"][1] - sb["y_range"][0]) * 0.12,
            site_label, ha="center", va="center", fontsize=10,
            fontweight="bold", color="#D32F2F", zorder=10)

    # --- Planned building ---
    ax.add_patch(shapely_to_mpl(
        site.PLANNED_BUILDING, facecolor="#1976D2",
        edgecolor="#0D47A1", linewidth=1.5, alpha=0.5, zorder=6
    ))
    pc = site.PLANNED_BUILDING.centroid
    ax.text(pc.x, pc.y,
            f"신축\n{site.PLANNED_BUILDING_FLOORS}F/{site.PLANNED_BUILDING_HEIGHT_M:.0f}m\n"
            f"{site.PLANNED_BUILDING.area:.0f}㎡",
            ha="center", va="center", fontsize=9,
            fontweight="bold", color="white", zorder=11)

    # --- Lift points ---
    n_lp = len(site.LIFT_POINTS)
    for i, p in enumerate(site.LIFT_POINTS, 1):
        is_yard = (i == n_lp)
        marker = "s" if is_yard else "o"
        color = "#FF5722" if is_yard else "#FFEB3B"
        ax.scatter(p[0], p[1], s=80, c=color, marker=marker,
                   edgecolors="black", linewidths=1.2, zorder=12)

    # --- Origin + grid ---
    ax.axhline(y=0, color="gray", linewidth=0.3, linestyle=":")
    ax.axvline(x=0, color="gray", linewidth=0.3, linestyle=":")
    ax.plot(0, 0, "k+", markersize=10, zorder=20)

    # --- Scale ---
    ax.set_xlim(xlim); ax.set_ylim(ylim)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.set_xlabel("X (m, 동측+)", fontsize=9)
    ax.set_ylabel("Y (m, 북측+)", fontsize=9)

    n_adj = len(site.ADJACENT_BUILDINGS)
    n_road = len(site.ROADS)
    title = (f"{site.metadata.get('display_name', '부지')}\n"
              f"부지 {site.SITE.area:.0f}㎡ · "
              f"신축 {site.PLANNED_BUILDING_FLOORS}층 · "
              f"인접 {n_adj}동 · 도로 {n_road}개")
    ax.set_title(title, fontsize=11, fontweight="bold", pad=12)

    # --- Compass ---
    cx_n = xlim[1] - 4
    cy_n = ylim[1] - 4
    ax.annotate("N", (cx_n, cy_n), fontsize=12, fontweight="bold",
                ha="center", color="darkred")
    ax.annotate("", xy=(cx_n, cy_n - 1.5), xytext=(cx_n, cy_n - 4.5),
                arrowprops=dict(arrowstyle="->", color="darkred", lw=2))

    if standalone:
        if out_path is None:
            site_id = site.metadata.get("site_id", "site")
            out_path = f"site_diagram_{site_id}.png"
        plt.tight_layout()
        plt.savefig(out_path, dpi=130, bbox_inches="tight")
        plt.close()
        print(f"  → {out_path}")
        return out_path


def draw_all(sites_dir="sites", out_dir="results"):
    """sites/ 내 모든 부지에 대한 다이어그램을 results/ 에 저장."""
    Path(out_dir).mkdir(exist_ok=True)
    site_files = list_sites(sites_dir)
    paths = []
    for sf in site_files:
        site = load_site(sf)
        site_id = site.metadata.get("site_id", Path(sf).stem)
        out = Path(out_dir) / f"diagram_{site_id}.png"
        draw_site(site, str(out))
        paths.append(str(out))
    return paths


def draw_grid(sites_dir="sites", out_path="results/all_sites_grid.png",
               ncols=2):
    """전체 부지를 2×2 grid 로 한 장에 모아 비교 시각화."""
    Path(os.path.dirname(out_path)).mkdir(exist_ok=True)
    site_files = list_sites(sites_dir)
    n = len(site_files)
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(7 * ncols, 7 * nrows))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]
    for i, sf in enumerate(site_files):
        site = load_site(sf)
        draw_site(site, ax=axes[i])
    for j in range(n, len(axes)):
        axes[j].axis("off")
    plt.suptitle("협소대지 타워크레인 배치 — 부지 비교 (4개 케이스)",
                  fontsize=14, fontweight="bold", y=1.0)
    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"→ Grid 저장: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("site", nargs="?", help="단일 부지 JSON 경로")
    parser.add_argument("--out", default=None, help="출력 PNG 경로")
    parser.add_argument("--all", action="store_true",
                         help="sites/ 모든 부지 일괄 생성")
    parser.add_argument("--grid", action="store_true",
                         help="2x2 비교 그리드 한 장 생성")
    args = parser.parse_args()

    if args.grid:
        draw_grid()
    elif args.all:
        draw_all()
    elif args.site:
        site = load_site(args.site)
        draw_site(site, args.out)
    else:
        # 기본: grid + 개별
        draw_all()
        draw_grid()
