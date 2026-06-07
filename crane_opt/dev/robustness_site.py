"""
================================================================================
robustness_site.py
================================================================================
범용 강건성 검증 — 임의 부지에 대해 multi-seed NSGA-II 강건성 측정
--------------------------------------------------------------------------------

평가 지표:
  - Hypervolume CV: 10개 seed의 HV 변동계수
  - Pareto 크기 CV
  - Knee point 공간 분산 (x, y, model, F1, F2)
  - Cluster coverage: y < y_split 영역 (부지내) 도달률
    (mode collapse 검출 — dual-branch 의 핵심 기능)

CLI:
    python robustness_site.py sites/gongdeok_256_42.json
    python robustness_site.py --all  # 모든 부지 비교
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon

# 한글
import matplotlib.font_manager as fm
def _setup_font():
    for c in ["Malgun Gothic", "NanumGothic", "AppleGothic",
               "Noto Sans CJK KR", "DejaVu Sans"]:
        if c in {f.name for f in fm.fontManager.ttflist}:
            plt.rcParams["font.family"] = c
            return
_setup_font()
plt.rcParams["axes.unicode_minus"] = False

from site_loader import load_site, list_sites
from site_helpers import use_site


MODEL_NAMES = ["Potain_MDT_178", "Potain_MR_160C", "Liebherr_280_HC_L"]


# =============================================================================
# Multi-seed run
# =============================================================================
def run_multiple_seeds(site, n_seeds=10, pop_size=60, n_gen=30,
                         seed_start=0):
    """한 부지에서 n_seeds 회 NSGA-II 반복."""
    use_site(site)
    from optimizer import run_dual_branch_optimization

    results = []
    for s in range(seed_start, seed_start + n_seeds):
        t0 = time.time()
        r = run_dual_branch_optimization(
            pop_size=pop_size, n_gen=n_gen, seed=s, verbose=False
        )
        elapsed = time.time() - t0
        if r.F is None or len(r.F) == 0:
            print(f"  seed={s}: feasible 0개 (skip)")
            continue
        results.append({
            "seed": s,
            "F": r.F.copy(),
            "X": r.X.copy(),
            "n_pareto": len(r.F),
            "elapsed_s": elapsed,
        })
        print(f"  seed={s}: Pareto {len(r.F)}개 ({elapsed:.1f}s)")
    return results


# =============================================================================
# Hypervolume 계산
# =============================================================================
def compute_hypervolume(results):
    """모든 결과를 합쳐 reference point 잡고 각 결과의 HV 계산."""
    if not results:
        return [], None
    all_F = np.vstack([r["F"] for r in results])
    ref = np.array([all_F[:, 0].max() * 1.05, all_F[:, 1].max() * 1.05])
    # pymoo Hypervolume
    from pymoo.indicators.hv import Hypervolume
    hv_calc = Hypervolume(ref_point=ref)
    hvs = []
    for r in results:
        r["hv"] = float(hv_calc(r["F"]))
        hvs.append(r["hv"])
    return hvs, ref


def find_knees(results):
    """각 seed 결과에서 knee point 추출."""
    knees = []
    for r in results:
        F, X = r["F"], r["X"]
        order = np.argsort(F[:, 0])
        F_s = F[order]; X_s = X[order]
        f1n = (F_s[:, 0] - F_s[:, 0].min()) / (np.ptp(F_s[:, 0]) + 1e-9)
        f2n = (F_s[:, 1] - F_s[:, 1].min()) / (np.ptp(F_s[:, 1]) + 1e-9)
        ki = int(np.argmin(f1n**2 + f2n**2))
        x, y, m_idx, jib, mast = X_s[ki]
        knees.append({
            "seed": r["seed"],
            "x": float(x), "y": float(y),
            "model": MODEL_NAMES[int(m_idx)],
            "jib": float(jib), "mast": float(mast),
            "F1": float(F_s[ki, 0]), "F2": float(F_s[ki, 1]),
        })
    return knees


def compute_cluster_coverage(results, y_split=None):
    """y < y_split 군집(부지내) 도달률.

    dual-branch 의 'Inside' 군집을 매번 찾는지 측정.
    """
    if not results:
        return 0.0
    if y_split is None:
        # 자동: 활성 부지의 검색범위 75% 지점
        import optimizer as _opt
        y_lo, y_hi = _opt._SEARCH_Y_RANGE
        y_split = y_lo + 0.75 * (y_hi - y_lo)

    coverage = []
    for r in results:
        ys = r["X"][:, 1]
        n_inside = (ys < y_split).sum()
        coverage.append(1.0 if n_inside > 0 else 0.0)
    return float(np.mean(coverage))


# =============================================================================
# 단일 부지 강건성 분석
# =============================================================================
def analyze_site_robustness(site, n_seeds=10, pop_size=60, n_gen=30,
                              out_dir="results"):
    print(f"\n{'='*78}")
    print(f"강건성 검증: {site.metadata.get('display_name')}")
    print(f"  {n_seeds}개 seed, pop={pop_size}, n_gen={n_gen}")
    print(f"{'='*78}")

    results = run_multiple_seeds(site, n_seeds, pop_size, n_gen)

    if not results:
        print("  ❌ 모든 seed feasible 0개 — 부지 자체가 infeasible")
        return None

    hvs, ref = compute_hypervolume(results)
    knees = find_knees(results)
    coverage = compute_cluster_coverage(results)

    # 통계
    hv_arr = np.array(hvs)
    hv_cv = float(hv_arr.std() / max(hv_arr.mean(), 1e-9))
    n_pareto = np.array([r["n_pareto"] for r in results])
    np_cv = float(n_pareto.std() / max(n_pareto.mean(), 1e-9))
    knee_x = np.array([k["x"] for k in knees])
    knee_y = np.array([k["y"] for k in knees])
    knee_F1 = np.array([k["F1"] for k in knees])

    summary = {
        "site_id": site.metadata.get("site_id"),
        "site_name": site.metadata.get("display_name"),
        "n_seeds_ran": n_seeds,
        "n_seeds_feasible": len(results),
        "hv_mean": float(hv_arr.mean()),
        "hv_std": float(hv_arr.std()),
        "hv_cv": hv_cv,
        "pareto_size_mean": float(n_pareto.mean()),
        "pareto_size_cv": np_cv,
        "knee_x_std": float(knee_x.std()),
        "knee_y_std": float(knee_y.std()),
        "knee_F1_cv": float(knee_F1.std() / max(knee_F1.mean(), 1e-9)),
        "cluster_coverage": coverage,
        "models_used": list(set(k["model"] for k in knees)),
        "reference_point": ref.tolist() if ref is not None else None,
    }

    # 콘솔 출력
    print(f"\n  [Hypervolume 통계]")
    print(f"    평균 HV: {hv_arr.mean():.1f}, 표준편차: {hv_arr.std():.1f}, "
          f"CV: {hv_cv:.3f}")
    if hv_cv < 0.05:
        print(f"    → ✅ 매우 강건 (CV < 0.05)")
    elif hv_cv < 0.10:
        print(f"    → ✅ 강건 (CV < 0.10)")
    elif hv_cv < 0.20:
        print(f"    → ⚠️  보통 (CV < 0.20)")
    else:
        print(f"    → ❌ 취약 (CV ≥ 0.20)")

    print(f"\n  [Knee 위치 분산]")
    print(f"    x 표준편차: {knee_x.std():.2f}m")
    print(f"    y 표준편차: {knee_y.std():.2f}m")
    print(f"    F1 CV: {summary['knee_F1_cv']:.3f}")
    print(f"    모델 다양성: {summary['models_used']}")

    print(f"\n  [군집 커버리지]")
    print(f"    Inside 군집 도달률: {coverage*100:.0f}%")
    if coverage >= 0.9:
        print(f"    → ✅ dual-branch 가 두 영역 모두 탐색")
    else:
        print(f"    → ⚠️  Inside 군집 도달 부족 (mode collapse 가능성)")

    # 시각화
    out_dir_p = Path(out_dir); out_dir_p.mkdir(exist_ok=True)
    fig_path = out_dir_p / f"robustness_{summary['site_id']}.png"
    draw_robustness_figure(site, results, knees, summary, str(fig_path))

    # JSON 저장
    json_path = out_dir_p / f"robustness_{summary['site_id']}.json"
    summary_save = {**summary, "knees": knees,
                     "hv_values": [r["hv"] for r in results],
                     "n_paretos": n_pareto.tolist()}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_save, f, ensure_ascii=False, indent=2)
    print(f"\n  → {fig_path}")
    print(f"  → {json_path}")
    return summary


def draw_robustness_figure(site, results, knees, summary, out_path):
    """2-panel figure: Pareto 중첩 + knee 위치 분산."""
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    # (1) Pareto front 중첩
    ax = axes[0]
    colors = plt.cm.viridis(np.linspace(0, 1, len(results)))
    for i, r in enumerate(results):
        F = r["F"]
        order = np.argsort(F[:, 0])
        ax.plot(F[order, 0], F[order, 1], "-o", color=colors[i],
                 markersize=4, linewidth=1.2, alpha=0.6,
                 label=f"seed={r['seed']}")
    ax.set_xlabel("F1 — 제3자 안전위험", fontsize=11)
    ax.set_ylabel("F2 — 양중 사이클 (h)", fontsize=11)
    ax.set_title(f"{len(results)}개 seed Pareto 중첩\nHV CV = {summary['hv_cv']:.3f}",
                  fontsize=12, fontweight="bold")
    ax.legend(loc="best", fontsize=7, ncol=2, framealpha=0.9)
    ax.grid(alpha=0.3)

    # (2) Knee 위치 분포 + 부지 overlay
    ax = axes[1]
    for key, r in site.ROADS.items():
        coords = list(r["polygon"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#EEE",
                                  edgecolor="#999", linewidth=0.5, zorder=2))
    for key, b in site.ADJACENT_BUILDINGS.items():
        coords = list(b["footprint"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#888", alpha=0.5,
                                  edgecolor="black", zorder=3))
    ax.add_patch(MplPolygon(list(site.SITE.exterior.coords),
                              facecolor="#FFF3CD", edgecolor="red",
                              linewidth=2.5, zorder=5))
    ax.add_patch(MplPolygon(list(site.PLANNED_BUILDING.exterior.coords),
                              facecolor="#1976D2", alpha=0.4,
                              edgecolor="#0D47A1", zorder=6))

    # 모델별 색
    model_color = {"Potain_MDT_178": "#D32F2F",
                    "Potain_MR_160C": "#1976D2",
                    "Liebherr_280_HC_L": "#388E3C"}
    for k in knees:
        c = model_color.get(k["model"], "gray")
        ax.scatter(k["x"], k["y"], s=300, marker="*", c=c,
                    edgecolors="black", linewidths=1.5, zorder=20, alpha=0.85)
        ax.annotate(f"s={k['seed']}", (k["x"], k["y"]),
                     xytext=(8, 8), textcoords="offset points",
                     fontsize=7)
    sb = site.SEARCH_BOUNDS
    ax.set_xlim(sb["x_range"][0] - 5, sb["x_range"][1] + 5)
    ax.set_ylim(sb["y_range"][0] - 4, sb["y_range"][1] + 4)
    ax.set_aspect("equal")
    ax.set_xlabel("X (m)", fontsize=11)
    ax.set_ylabel("Y (m)", fontsize=11)
    ax.set_title(f"Knee 위치 분포 ({len(knees)}개 seed)\n"
                  f"x σ={summary['knee_x_std']:.1f}m, y σ={summary['knee_y_std']:.1f}m, "
                  f"coverage={summary['cluster_coverage']*100:.0f}%",
                  fontsize=12, fontweight="bold")
    ax.grid(alpha=0.3)

    plt.suptitle(
        f"{site.metadata.get('display_name')} — NSGA-II 강건성 검증",
        fontsize=14, fontweight="bold", y=1.02
    )
    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()


# =============================================================================
# 다중 부지 비교
# =============================================================================
def compare_all_sites_robustness(n_seeds=10, pop_size=60, n_gen=30,
                                     out_dir="results"):
    """모든 부지에 대해 강건성 분석 + 통합 표."""
    site_files = list_sites("sites")
    summaries = []
    for sf in site_files:
        site = load_site(sf)
        s = analyze_site_robustness(site, n_seeds, pop_size, n_gen, out_dir)
        if s is not None:
            summaries.append(s)
        else:
            # infeasible 부지
            summaries.append({
                "site_id": site.metadata.get("site_id"),
                "site_name": site.metadata.get("display_name"),
                "n_seeds_feasible": 0,
                "hv_cv": None, "pareto_size_cv": None,
                "knee_F1_cv": None, "cluster_coverage": None,
                "note": "INFEASIBLE",
            })

    # 통합 CSV
    import pandas as pd
    df = pd.DataFrame(summaries)
    csv_path = Path(out_dir) / "robustness_summary.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"\n{'='*78}")
    print(f"  ▼ 부지 강건성 비교")
    print(f"{'='*78}")
    cols = ["site_id", "n_seeds_feasible", "hv_cv", "pareto_size_cv",
             "knee_F1_cv", "cluster_coverage"]
    avail = [c for c in cols if c in df.columns]
    print(df[avail].to_string(index=False))
    print(f"\n→ {csv_path}")
    return summaries


# =============================================================================
# CLI
# =============================================================================
def main():
    p = argparse.ArgumentParser()
    p.add_argument("site", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--n-seeds", type=int, default=10)
    p.add_argument("--pop", type=int, default=60)
    p.add_argument("--gen", type=int, default=30)
    p.add_argument("--out-dir", default="results")
    args = p.parse_args()

    if args.all:
        compare_all_sites_robustness(args.n_seeds, args.pop, args.gen,
                                       args.out_dir)
    elif args.site:
        site = load_site(args.site)
        analyze_site_robustness(site, args.n_seeds, args.pop, args.gen,
                                  args.out_dir)
    else:
        print("usage: robustness_site.py <site.json> | --all")


if __name__ == "__main__":
    main()
