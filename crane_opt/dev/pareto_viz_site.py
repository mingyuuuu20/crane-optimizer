"""
================================================================================
pareto_viz_site.py
================================================================================
범용 Pareto front 시각화 — 임의 SiteData 와 결과 dict 를 받아 그림
--------------------------------------------------------------------------------

기능 1: 단일 부지 Pareto + 대표 3개 위치 + 부지 다이어그램 (2-panel)
기능 2: 여러 부지 Pareto front 한 장 비교 (overlay)
기능 3: 여러 부지 grid 시각화 (각 부지별 panel)

CLI:
    python pareto_viz_site.py --site sites/gongdeok_256_42.json
    python pareto_viz_site.py --compare         # 4개 부지 한 장
    python pareto_viz_site.py --grid            # 4개 부지 grid
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon as MplPolygon, Circle

# 한글 폰트 — Windows 환경 우선
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


MODEL_NAMES = ["Potain_MDT_178", "Potain_MR_160C", "Liebherr_280_HC_L"]
MODEL_SHORT = {
    "Potain_MDT_178":    "MDT 178 (T)",
    "Potain_MR_160C":    "MR 160C (러핑소)",
    "Liebherr_280_HC_L": "280 HC-L (러핑대)",
}
MODEL_COLOR_BY_IDX = {0: "#D32F2F", 1: "#1976D2", 2: "#388E3C"}
MODEL_LABEL_BY_IDX = {
    0: "Potain MDT 178 (T형)",
    1: "Potain MR 160C (러핑소)",
    2: "Liebherr 280 HC-L (러핑대)",
}


# -----------------------------------------------------------------------------
# 헬퍼: 결과 dict (run_all_sites 출력) → 필요한 array 회복
# -----------------------------------------------------------------------------
def _result_to_arrays(r):
    F = np.array(r["_F"]) if "_F" in r else None
    X = np.array(r["_X"]) if "_X" in r else None
    return F, X


def _find_knee_idx(F_sorted):
    if len(F_sorted) < 2:
        return 0
    f1 = F_sorted[:, 0]; f2 = F_sorted[:, 1]
    f1n = (f1 - f1.min()) / (f1.max() - f1.min() + 1e-9)
    f2n = (f2 - f2.min()) / (f2.max() - f2.min() + 1e-9)
    return int(np.argmin(f1n**2 + f2n**2))


# -----------------------------------------------------------------------------
# 부지 다이어그램 overlay
# -----------------------------------------------------------------------------
def _draw_site_overlay(ax, site):
    """부지·인접건물·도로·계획건물·양중점을 ax 에 그린다."""
    for key, r in site.ROADS.items():
        color = "#EEEEEE" if r["occupation_allowed"] else "#F8D7DA"
        coords = list(r["polygon"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor=color,
                                  edgecolor="#999", linewidth=0.5, zorder=2))
    for key, b in site.ADJACENT_BUILDINGS.items():
        coords = list(b["footprint"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#888",
                                  edgecolor="black", linewidth=1,
                                  alpha=0.5, zorder=3))
        c = b["footprint"].centroid
        ax.text(c.x, c.y, f"{key}\n{b['floors']}F",
                ha="center", va="center", fontsize=7,
                color="white", fontweight="bold")
    site_xy = list(site.SITE.exterior.coords)
    ax.add_patch(MplPolygon(site_xy, facecolor="#FFF3CD",
                              edgecolor="red", linewidth=2.5, zorder=5))
    pb_xy = list(site.PLANNED_BUILDING.exterior.coords)
    ax.add_patch(MplPolygon(pb_xy, facecolor="#1976D2",
                              edgecolor="#0D47A1", linewidth=1.5,
                              alpha=0.4, zorder=6))
    for p in site.LIFT_POINTS:
        ax.scatter(p[0], p[1], s=40, c="#FFEB3B",
                    edgecolors="black", linewidths=0.5, zorder=8)


# -----------------------------------------------------------------------------
# 기능 1: 단일 부지 — Pareto + 위치 (2-panel)
# -----------------------------------------------------------------------------
def plot_single_site(site, F, X, out_path=None, title_suffix=""):
    if F is None or len(F) == 0:
        print(f"  {site.metadata.get('display_name')}: feasible 0개 — skip")
        return None

    order = np.argsort(F[:, 0])
    F_sorted = F[order]; X_sorted = X[order]
    idx_safety = 0
    idx_eff = len(F_sorted) - 1
    idx_knee = _find_knee_idx(F_sorted)

    reps = {
        "safety":     (idx_safety, "안전 최우선",  "#D32F2F"),
        "balanced":   (idx_knee,   "균형 (Knee)",  "#1976D2"),
        "efficiency": (idx_eff,    "효율 최우선",  "#388E3C"),
    }

    fig = plt.figure(figsize=(18, 8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.2])

    # (1) Pareto 산점도
    ax1 = fig.add_subplot(gs[0])
    for m_idx, color in MODEL_COLOR_BY_IDX.items():
        mask = np.array([int(X[i, 2]) == m_idx for i in range(len(X))])
        if mask.sum() > 0:
            ax1.scatter(F[mask, 0], F[mask, 1],
                         c=color, s=60, alpha=0.6,
                         label=f"{MODEL_LABEL_BY_IDX[m_idx]} (n={mask.sum()})",
                         edgecolors="black", linewidths=0.4)
    ax1.plot(F_sorted[:, 0], F_sorted[:, 1], "k--",
              linewidth=0.6, alpha=0.4)
    for key, (idx, label, c) in reps.items():
        f1, f2 = F_sorted[idx]
        ax1.scatter(f1, f2, s=300, marker="*", c=c,
                     edgecolors="black", linewidths=1.8, zorder=10)
        ax1.annotate(f"{label}\nF1={f1:.0f}, F2={f2:.1f}h",
                      (f1, f2), xytext=(12, 12),
                      textcoords="offset points",
                      fontsize=9, fontweight="bold",
                      bbox=dict(boxstyle="round,pad=0.3",
                                facecolor=c, alpha=0.25, edgecolor=c))
    ax1.set_xlabel("F1 — 제3자 안전 지수 (낮을수록 안전)", fontsize=10)
    ax1.set_ylabel("F2 — 양중 사이클 시간 (h, 낮을수록 빠름)", fontsize=10)
    ax1.set_title(f"Pareto Front · {len(F)}개 비지배해", fontsize=11, fontweight="bold")
    ax1.legend(loc="best", fontsize=8, framealpha=0.95)
    ax1.grid(alpha=0.3)

    # (2) 부지 + 대표 위치
    ax2 = fig.add_subplot(gs[1])
    _draw_site_overlay(ax2, site)
    for key, (idx, label, color) in reps.items():
        x, y, m_idx, jib, mast = X_sorted[idx]
        ax2.scatter(x, y, s=380, marker="*", c=color,
                     edgecolors="black", linewidths=2, zorder=20)
        circle = Circle((x, y), jib, fill=False,
                         edgecolor=color, linewidth=2, linestyle="--",
                         alpha=0.7, zorder=15)
        ax2.add_patch(circle)
        ax2.annotate(f"{label}\n({x:+.1f},{y:+.1f}) jib={jib:.0f}m",
                      (x, y), xytext=(10, -22),
                      textcoords="offset points",
                      fontsize=8, fontweight="bold",
                      bbox=dict(boxstyle="round,pad=0.25",
                                facecolor="white", edgecolor=color, alpha=0.95))
    sb = site.SEARCH_BOUNDS
    ax2.set_xlim(sb["x_range"][0] - 6, sb["x_range"][1] + 6)
    ax2.set_ylim(sb["y_range"][0] - 4, sb["y_range"][1] + 4)
    ax2.set_aspect("equal")
    ax2.grid(alpha=0.3)
    ax2.set_xlabel("X (m, 동측+)", fontsize=10)
    ax2.set_ylabel("Y (m, 북측+)", fontsize=10)
    ax2.set_title("부지 + 크레인 위치 (점선 = 작업 반경)",
                   fontsize=11, fontweight="bold")

    plt.suptitle(
        f"{site.metadata.get('display_name', 'Site')}{title_suffix}\n"
        f"다목적 NSGA-II 최적화 결과",
        fontsize=13, fontweight="bold", y=1.02,
    )
    plt.tight_layout()

    if out_path is None:
        sid = site.metadata.get("site_id", "site")
        out_path = f"results/pareto_{sid}.png"
    Path(os.path.dirname(out_path)).mkdir(exist_ok=True)
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  → {out_path}")
    return out_path


# -----------------------------------------------------------------------------
# 기능 2: 여러 부지 Pareto front 한 장 비교 (overlay)
# -----------------------------------------------------------------------------
def plot_pareto_overlay(results, out_path="results/pareto_overlay.png"):
    """여러 부지의 Pareto front 를 한 그래프에 겹쳐 보여준다.

    F1·F2 단위가 부지마다 다르므로 정규화 옵션도 추가.
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    colors = ["#D32F2F", "#1976D2", "#388E3C", "#F57C00", "#7B1FA2"]

    # (1) 원본 단위
    ax = axes[0]
    for i, r in enumerate(results):
        if not r.get("feasible"):
            ax.text(0.5, 0.95 - i*0.05,
                     f"  ✗ {r['site_name']}: infeasible",
                     transform=ax.transAxes, fontsize=9,
                     color="red", ha="left")
            continue
        F, X = _result_to_arrays(r)
        order = np.argsort(F[:, 0])
        F_s = F[order]
        ax.scatter(F[:, 0], F[:, 1], s=30, c=colors[i % len(colors)],
                    alpha=0.5, edgecolors="black", linewidths=0.3,
                    label=r["site_name"])
        ax.plot(F_s[:, 0], F_s[:, 1], color=colors[i % len(colors)],
                 linewidth=1.5, alpha=0.7)
        knee_i = _find_knee_idx(F_s)
        ax.scatter(F_s[knee_i, 0], F_s[knee_i, 1], s=250, marker="*",
                    c=colors[i % len(colors)], edgecolors="black",
                    linewidths=1.5, zorder=10)
    ax.set_xlabel("F1 — 제3자 안전 지수", fontsize=11)
    ax.set_ylabel("F2 — 양중 사이클 시간 (h)", fontsize=11)
    ax.set_title("Pareto Front 비교 (원본 단위)\n★ = knee point",
                  fontsize=12, fontweight="bold")
    ax.legend(loc="best", fontsize=9, framealpha=0.95)
    ax.grid(alpha=0.3)

    # (2) 정규화 — 각 부지 내부에서 F1·F2 [0,1] 로 스케일
    ax = axes[1]
    for i, r in enumerate(results):
        if not r.get("feasible"):
            continue
        F, _ = _result_to_arrays(r)
        order = np.argsort(F[:, 0])
        F_s = F[order]
        if F_s[:, 0].max() == F_s[:, 0].min():
            f1n = np.zeros_like(F_s[:, 0])
        else:
            f1n = (F_s[:, 0] - F_s[:, 0].min()) / (F_s[:, 0].max() - F_s[:, 0].min())
        if F_s[:, 1].max() == F_s[:, 1].min():
            f2n = np.zeros_like(F_s[:, 1])
        else:
            f2n = (F_s[:, 1] - F_s[:, 1].min()) / (F_s[:, 1].max() - F_s[:, 1].min())
        ax.plot(f1n, f2n, "-o", color=colors[i % len(colors)], markersize=6,
                 linewidth=2, alpha=0.8, label=r["site_name"],
                 markeredgecolor="black", markeredgewidth=0.5)
    ax.set_xlabel("F1 정규화 (0=가장 안전, 1=가장 위험)", fontsize=11)
    ax.set_ylabel("F2 정규화 (0=가장 빠름, 1=가장 느림)", fontsize=11)
    ax.set_title("Pareto Front 정규화 비교\n(형상 패턴 비교용)",
                  fontsize=12, fontweight="bold")
    ax.legend(loc="best", fontsize=9, framealpha=0.95)
    ax.grid(alpha=0.3)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)

    plt.suptitle("부지 간 Pareto Front 비교 — 다목적 NSGA-II 결과",
                  fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    Path(os.path.dirname(out_path)).mkdir(exist_ok=True)
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"→ Overlay 저장: {out_path}")
    return out_path


# -----------------------------------------------------------------------------
# 기능 3: 여러 부지 grid (각 부지별 단일 패널)
# -----------------------------------------------------------------------------
def plot_grid(results, sites_by_id, out_path="results/pareto_grid.png",
               ncols=2):
    """각 부지의 Pareto + 부지 위치를 grid 로 나란히."""
    n = len(results)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(9 * ncols, 8 * nrows))
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for i, r in enumerate(results):
        ax = axes[i]
        site = sites_by_id.get(r["site_id"])
        if site is None:
            ax.text(0.5, 0.5, f"Site '{r['site_id']}' not loaded",
                    transform=ax.transAxes, ha="center")
            continue

        if not r.get("feasible"):
            # infeasible: 부지 다이어그램 + 빨간 메시지
            _draw_site_overlay(ax, site)
            sb = site.SEARCH_BOUNDS
            ax.set_xlim(sb["x_range"][0] - 6, sb["x_range"][1] + 6)
            ax.set_ylim(sb["y_range"][0] - 4, sb["y_range"][1] + 4)
            ax.set_aspect("equal")
            note = r.get("note", "Infeasible")
            ax.text(0.5, 0.05, f"❌ {note}",
                     transform=ax.transAxes, fontsize=11,
                     ha="center", color="white", fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.4",
                               facecolor="#D32F2F", edgecolor="black"))
            ax.set_title(f"{r['site_name']} — 시공 곤란",
                          fontsize=11, fontweight="bold", color="#D32F2F")
            ax.grid(alpha=0.3)
            continue

        F, X = _result_to_arrays(r)
        order = np.argsort(F[:, 0])
        F_s = F[order]; X_s = X[order]
        idx_safety = 0
        idx_eff = len(F_s) - 1
        idx_knee = _find_knee_idx(F_s)

        # 부지 overlay
        _draw_site_overlay(ax, site)

        # 대표 3개
        reps = [
            (idx_safety, "S",  "#D32F2F"),
            (idx_knee,   "K",  "#1976D2"),
            (idx_eff,    "E",  "#388E3C"),
        ]
        for idx, label, color in reps:
            x, y, m_idx, jib, mast = X_s[idx]
            ax.scatter(x, y, s=350, marker="*", c=color,
                        edgecolors="black", linewidths=1.8, zorder=20)
            circle = Circle((x, y), jib, fill=False,
                             edgecolor=color, linewidth=1.5, linestyle="--",
                             alpha=0.6, zorder=15)
            ax.add_patch(circle)

        # Inset: F1·F2 Pareto 미니
        from mpl_toolkits.axes_grid1.inset_locator import inset_axes
        axin = inset_axes(ax, width="35%", height="35%", loc="upper right",
                           borderpad=1)
        for m_idx, color in MODEL_COLOR_BY_IDX.items():
            mask = np.array([int(X[k, 2]) == m_idx for k in range(len(X))])
            if mask.sum() > 0:
                axin.scatter(F[mask, 0], F[mask, 1], s=14,
                              c=color, alpha=0.6,
                              edgecolors="black", linewidths=0.2)
        axin.plot(F_s[:, 0], F_s[:, 1], "k--", linewidth=0.5, alpha=0.4)
        for idx, label, color in reps:
            axin.scatter(F_s[idx, 0], F_s[idx, 1], s=80, marker="*",
                          c=color, edgecolors="black", linewidths=1, zorder=10)
        axin.set_xlabel("F1", fontsize=8)
        axin.set_ylabel("F2", fontsize=8)
        axin.tick_params(labelsize=7)
        axin.set_title(f"Pareto n={len(F)}", fontsize=8)
        axin.grid(alpha=0.3)

        # 부지 limits
        sb = site.SEARCH_BOUNDS
        ax.set_xlim(sb["x_range"][0] - 6, sb["x_range"][1] + 6)
        ax.set_ylim(sb["y_range"][0] - 4, sb["y_range"][1] + 4)
        ax.set_aspect("equal")
        knee_model = MODEL_NAMES[int(X_s[idx_knee, 2])]
        ax.set_title(
            f"{r['site_name']}\n"
            f"Pareto {len(F)} · Knee: {MODEL_SHORT[knee_model]} "
            f"jib={X_s[idx_knee,3]:.0f}m",
            fontsize=11, fontweight="bold"
        )
        ax.grid(alpha=0.3)

    # 빈 패널 정리
    for j in range(n, len(axes)):
        axes[j].axis("off")

    plt.suptitle(
        "협소대지 타워크레인 배치 — 부지별 최적 결과 비교\n"
        "★S=안전 최우선, ★K=Knee, ★E=효율 최우선 · 점선=작업 반경",
        fontsize=14, fontweight="bold", y=1.0,
    )
    plt.tight_layout()
    Path(os.path.dirname(out_path)).mkdir(exist_ok=True)
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"→ Grid 저장: {out_path}")
    return out_path


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def _load_results_and_sites(results_path="results/site_comparison.json"):
    from site_loader import load_site, list_sites
    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    sites_by_id = {}
    for sf in list_sites():
        s = load_site(sf)
        sites_by_id[s.metadata.get("site_id")] = s
    return results, sites_by_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="단일 부지 JSON")
    parser.add_argument("--results",
                         default="results/site_comparison.json",
                         help="run_all_sites.py 결과 JSON")
    parser.add_argument("--overlay", action="store_true")
    parser.add_argument("--grid", action="store_true")
    parser.add_argument("--all", action="store_true",
                         help="overlay + grid + 부지별 단일")
    args = parser.parse_args()

    if args.site:
        # 단일 부지 — 그 자리에서 NSGA-II 실행 후 시각화
        from site_loader import load_site
        from site_helpers import use_site
        from optimizer import run_dual_branch_optimization
        site = load_site(args.site)
        use_site(site)
        r = run_dual_branch_optimization(pop_size=80, n_gen=40, seed=42,
                                            verbose=False)
        plot_single_site(site, r.F, r.X)
        return

    # results JSON 기반 (run_all_sites.py 실행 후)
    if not Path(args.results).exists():
        print(f"⚠️ {args.results} 없음. 먼저 'python run_all_sites.py' 실행.")
        return

    results, sites = _load_results_and_sites(args.results)

    if args.overlay:
        plot_pareto_overlay(results)
    if args.grid:
        plot_grid(results, sites)
    if args.all or (not args.overlay and not args.grid):
        plot_pareto_overlay(results)
        plot_grid(results, sites)
        # 부지별 단일
        for r in results:
            if not r.get("feasible"):
                continue
            site = sites.get(r["site_id"])
            if site is None: continue
            F, X = _result_to_arrays(r)
            plot_single_site(site, F, X)


if __name__ == "__main__":
    main()
