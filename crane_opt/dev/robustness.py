"""
================================================================================
robustness.py
================================================================================
NSGA-II 결과 강건성 검증 (보완 작업 [4])
--------------------------------------------------------------------------------
유전 알고리즘은 확률적 — seed 에 따라 Pareto front 가 달라질 수 있음.
"이 결과가 진짜 최적인가" 답하려면 다음 분석이 필요:

  ① 여러 seed 로 반복 실행 → Pareto front 가 일관되게 수렴하는지
  ② 각 seed 의 hypervolume 지표 분포 → 알고리즘 자체의 강건성
  ③ Pareto front 의 영역별 안정성 (knee 부근 vs 양 극단)

학술 출처:
  - Hypervolume: Zitzler & Thiele (1999), IEEE Trans. Evol. Comput.
  - 다중 seed 검증: Bartz-Beielstein et al. (2020), Evolutionary Computation
"""

import numpy as np
import matplotlib.pyplot as plt
from pymoo.indicators.hv import HV
from optimizer import run_optimization, MODEL_LIST

plt.rcParams['axes.unicode_minus'] = False


def run_multiple_seeds(n_seeds: int = 10,
                         pop_size: int = 80,
                         n_gen: int = 40,
                         seed_start: int = 0):
    """N개 seed 로 NSGA-II 반복 실행. 각각의 Pareto front 수집."""
    results = []
    print(f"NSGA-II 반복 실행: {n_seeds} seeds, pop={pop_size}, gen={n_gen}")
    print(f"{'seed':>6} {'n_pareto':>10} {'F1 범위':>20} {'F2 범위':>20}")
    print("-" * 70)

    for s in range(seed_start, seed_start + n_seeds):
        result, _ = run_optimization(
            pop_size=pop_size, n_gen=n_gen, seed=s, verbose=False
        )
        if result.F is None or len(result.F) == 0:
            print(f"{s:>6}  ❌ feasible 해 없음")
            continue

        F = result.F
        X = result.X
        results.append({
            "seed": s,
            "F": F,
            "X": X,
            "n_pareto": len(F),
            "F1_min": F[:, 0].min(),
            "F1_max": F[:, 0].max(),
            "F2_min": F[:, 1].min(),
            "F2_max": F[:, 1].max(),
        })
        print(f"{s:>6} {len(F):>10} "
              f"[{F[:,0].min():>6.1f}, {F[:,0].max():>6.1f}]  "
              f"[{F[:,1].min():>6.1f}, {F[:,1].max():>6.1f}]")
    return results


def compute_hypervolume_indicators(results, ref_point=None):
    """각 seed의 Pareto front 에 대한 hypervolume 지표 계산."""
    # 모든 F 합쳐서 reference point 결정 (전체 worst 보다 약간 큰 점)
    all_F = np.vstack([r["F"] for r in results])
    if ref_point is None:
        ref_point = np.array([
            all_F[:, 0].max() * 1.1,
            all_F[:, 1].max() * 1.05,
        ])

    hv_calc = HV(ref_point=ref_point)
    for r in results:
        r["hv"] = hv_calc(r["F"])
    return ref_point


def analyze_solution_consistency(results, knee_focus: bool = True):
    """
    각 seed 의 'knee point' (균형해) 좌표 분포 분석.
    knee 가 안정적이면 → 시스템 강건 결론 도출 가능.
    """
    knees = []
    for r in results:
        F = r["F"]
        X = r["X"]
        if len(F) < 2:
            continue

        # F1·F2 정규화 후 원점에서 가장 가까운 점이 knee
        f1n = (F[:, 0] - F[:, 0].min()) / (F[:, 0].max() - F[:, 0].min() + 1e-9)
        f2n = (F[:, 1] - F[:, 1].min()) / (F[:, 1].max() - F[:, 1].min() + 1e-9)
        idx_knee = int(np.argmin(f1n**2 + f2n**2))

        x, y, m_idx, jib, mast = X[idx_knee]
        knees.append({
            "seed": r["seed"],
            "x": x, "y": y,
            "model_idx": int(m_idx),
            "model": MODEL_LIST[int(m_idx)],
            "jib": jib,
            "mast": mast,
            "F1": F[idx_knee, 0],
            "F2": F[idx_knee, 1],
        })
    return knees


def main():
    print("=" * 78)
    print("NSGA-II 강건성 검증 (Multi-seed Robustness Analysis)")
    print("=" * 78)

    # 10개 seed 로 반복 (pop_size를 60으로 줄여서 시간 단축)
    # 검증 목적은 강건성 측정이므로 pop_size 차이는 본질 무관
    results = run_multiple_seeds(n_seeds=10, pop_size=60, n_gen=30, seed_start=0)
    if len(results) == 0:
        print("❌ 모든 seed 에서 feasible 해 없음")
        return

    # Hypervolume 계산
    ref = compute_hypervolume_indicators(results)
    print(f"\nReference point: F1={ref[0]:.1f}, F2={ref[1]:.1f}")
    print(f"\n{'seed':>6} {'n_pareto':>10} {'hypervolume':>14}")
    print("-" * 35)
    for r in results:
        print(f"{r['seed']:>6} {r['n_pareto']:>10} {r['hv']:>14.1f}")

    hv_values = [r["hv"] for r in results]
    n_pareto_values = [r["n_pareto"] for r in results]

    print(f"\n[Hypervolume 통계]")
    print(f"  평균 = {np.mean(hv_values):.1f}")
    print(f"  표준편차 = {np.std(hv_values):.1f}")
    print(f"  변동계수 CV = {np.std(hv_values)/np.mean(hv_values):.3f}")

    cv = np.std(hv_values) / np.mean(hv_values)
    if cv < 0.05:
        print("  → ✅ 매우 강건 (CV < 0.05)")
    elif cv < 0.10:
        print("  → ✅ 강건 (CV < 0.10)")
    elif cv < 0.20:
        print("  → ⚠️ 보통 (CV < 0.20)")
    else:
        print("  → ❌ 취약 (CV ≥ 0.20)")

    # Knee 일관성 분석
    knees = analyze_solution_consistency(results)
    print(f"\n[Knee point 일관성]")
    print(f"{'seed':>6} {'x':>7} {'y':>7} {'model':<22} {'jib':>6} {'F1':>9} {'F2':>9}")
    print("-" * 75)
    for k in knees:
        print(f"{k['seed']:>6} {k['x']:>7.2f} {k['y']:>7.2f} "
              f"{k['model']:<22} {k['jib']:>6.2f} "
              f"{k['F1']:>9.1f} {k['F2']:>9.1f}")

    xs = [k["x"] for k in knees]
    ys = [k["y"] for k in knees]
    f1s = [k["F1"] for k in knees]
    f2s = [k["F2"] for k in knees]
    model_counts = {}
    for k in knees:
        model_counts[k["model"]] = model_counts.get(k["model"], 0) + 1

    print(f"\n[Knee 위치 분포]")
    print(f"  x: 평균={np.mean(xs):.2f} ± {np.std(xs):.2f}")
    print(f"  y: 평균={np.mean(ys):.2f} ± {np.std(ys):.2f}")
    print(f"  F1: 평균={np.mean(f1s):.1f} ± {np.std(f1s):.1f}")
    print(f"  F2: 평균={np.mean(f2s):.1f} ± {np.std(f2s):.1f}")
    print(f"\n[Knee 모델 선택 분포]")
    for m, n in model_counts.items():
        pct = n / len(knees) * 100
        print(f"  {m}: {n}/{len(knees)} = {pct:.0f}%")

    # 시각화: 모든 Pareto front 겹쳐 그리기
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # (1) 모든 Pareto front
    ax = axes[0]
    cmap = plt.cm.tab10
    for i, r in enumerate(results):
        F = r["F"]
        order = np.argsort(F[:, 0])
        ax.plot(F[order, 0], F[order, 1], "o-",
                 color=cmap(i % 10), alpha=0.5, markersize=4,
                 linewidth=1, label=f"seed={r['seed']} (n={r['n_pareto']}, HV={r['hv']:.0f})")
    ax.set_xlabel("F1 — Third-Party Safety Risk")
    ax.set_ylabel("F2 — Cycle hours")
    ax.set_title(f"All {len(results)} Pareto fronts overlaid\n"
                  f"HV mean={np.mean(hv_values):.1f}, CV={cv:.3f}",
                  fontsize=11, fontweight="bold")
    ax.legend(fontsize=7, loc="upper right", ncol=2)
    ax.grid(alpha=0.3)

    # (2) Knee point 위치 분포
    ax = axes[1]
    from site_model import SITE, ADJACENT_BUILDINGS, ROADS, PLANNED_BUILDING
    from matplotlib.patches import Polygon as MplPolygon
    # 부지 오버레이
    for r in ROADS.values():
        coords = list(r["polygon"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#EEE",
                                  edgecolor="#999", linewidth=0.5, zorder=2))
    for direction, b in ADJACENT_BUILDINGS.items():
        coords = list(b["footprint"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#888",
                                  edgecolor="black", alpha=0.5, zorder=3))
    site_xy = list(SITE.exterior.coords)
    ax.add_patch(MplPolygon(site_xy, facecolor="#FFF3CD",
                              edgecolor="red", linewidth=2.5, zorder=5))
    pb_xy = list(PLANNED_BUILDING.exterior.coords)
    ax.add_patch(MplPolygon(pb_xy, facecolor="#1976D2",
                              edgecolor="#0D47A1", alpha=0.4, zorder=6))

    # Knee points
    for k in knees:
        ax.scatter(k["x"], k["y"], s=200, marker="*",
                    c=cmap(k["seed"] % 10),
                    edgecolors="black", linewidths=1.5, zorder=20,
                    label=f"seed={k['seed']}")
    # 평균
    ax.scatter(np.mean(xs), np.mean(ys), s=500, marker="X",
                c="red", edgecolors="black", linewidths=2,
                zorder=21, label=f"mean ({np.mean(xs):.1f}, {np.mean(ys):.1f})")
    ax.set_xlim(-30, 30)
    ax.set_ylim(-25, 25)
    ax.set_aspect("equal")
    ax.set_xlabel("X (East, m)")
    ax.set_ylabel("Y (North, m)")
    ax.set_title(f"Knee point locations across {len(knees)} seeds\n"
                  f"x: {np.mean(xs):.2f}±{np.std(xs):.2f}, "
                  f"y: {np.mean(ys):.2f}±{np.std(ys):.2f}",
                  fontsize=11, fontweight="bold")
    ax.legend(fontsize=7, loc="lower left", ncol=2)
    ax.grid(alpha=0.3)

    plt.suptitle(
        f"NSGA-II Robustness Analysis ({len(results)} seeds × pop=60 × gen=30)",
        fontsize=13, fontweight="bold"
    )
    plt.tight_layout()
    out = "/home/claude/crane_opt/robustness_analysis.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    print(f"\n저장: {out}")

    # JSON 저장 (재사용)
    import json
    summary = {
        "n_seeds": len(results),
        "pop_size": 60,
        "n_gen": 30,
        "hypervolume": {
            "mean": float(np.mean(hv_values)),
            "std": float(np.std(hv_values)),
            "cv": float(cv),
        },
        "knee_consistency": {
            "x_mean": float(np.mean(xs)), "x_std": float(np.std(xs)),
            "y_mean": float(np.mean(ys)), "y_std": float(np.std(ys)),
            "F1_mean": float(np.mean(f1s)), "F1_std": float(np.std(f1s)),
            "F2_mean": float(np.mean(f2s)), "F2_std": float(np.std(f2s)),
            "model_distribution": model_counts,
        },
        "per_seed": [
            {k: (float(v) if isinstance(v, (np.floating, float)) else v)
             for k, v in r.items() if k not in ["F", "X"]}
            for r in results
        ],
    }
    with open("/home/claude/crane_opt/robustness_summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("저장: /home/claude/crane_opt/robustness_summary.json")

    return results, knees


if __name__ == "__main__":
    main()
