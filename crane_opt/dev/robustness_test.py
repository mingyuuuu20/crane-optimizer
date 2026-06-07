"""
================================================================================
robustness_test.py
================================================================================
NSGA-II 결과 강건성 검증 (작업 [4])
--------------------------------------------------------------------------------
유전 알고리즘은 확률적이므로 seed 에 따라 결과가 다를 수 있다.
"우리가 찾은 Pareto front 가 진짜 최적인가" 를 정량 평가.

평가 지표:
  1. Hypervolume (HV) — Pareto front 가 얼마나 넓은 영역을 dominate 하는가
     높을수록 좋음. seed 간 분산이 작아야 알고리즘 강건.
  2. Pareto front 크기 일관성
  3. Knee point 위치 일관성

산출물:
  - robustness_results.csv: seed × HV, n_solutions, knee_xy
  - robustness_summary.png: HV 분포, knee 위치 산점도
"""

import numpy as np
import time
import matplotlib.pyplot as plt
import pandas as pd
from pymoo.indicators.hv import Hypervolume

from optimizer import run_optimization, MODEL_LIST


def find_knee_point(F_sorted):
    """정규화 후 (0,0) 기준 가까운 점."""
    if len(F_sorted) < 2:
        return 0
    f1_norm = (F_sorted[:, 0] - F_sorted[:, 0].min()) / (F_sorted[:, 0].max() - F_sorted[:, 0].min() + 1e-9)
    f2_norm = (F_sorted[:, 1] - F_sorted[:, 1].min()) / (F_sorted[:, 1].max() - F_sorted[:, 1].min() + 1e-9)
    return int(np.argmin(f1_norm**2 + f2_norm**2))


def run_robustness_test(seeds=(42, 7, 13, 21, 33, 55, 77, 99, 123, 256),
                          pop_size=80, n_gen=40):
    """여러 seed 로 NSGA-II 실행 + 결과 비교."""

    print(f"\n{'='*80}")
    print(f"NSGA-II 강건성 검증 — {len(seeds)}개 seed")
    print(f"{'='*80}")

    results = []
    all_F = []
    all_X = []

    for seed in seeds:
        t0 = time.time()
        result, _ = run_optimization(pop_size=pop_size, n_gen=n_gen,
                                       seed=seed, verbose=False)
        elapsed = time.time() - t0

        if result.F is None or len(result.F) == 0:
            print(f"  seed={seed:>3}: ❌ feasible 해 없음")
            results.append({"seed": seed, "n_solutions": 0,
                            "HV": np.nan, "elapsed": elapsed,
                            "knee_x": np.nan, "knee_y": np.nan,
                            "knee_F1": np.nan, "knee_F2": np.nan,
                            "min_F1": np.nan, "min_F2": np.nan})
            continue

        F = result.F; X = result.X
        order = np.argsort(F[:, 0])
        F_sorted = F[order]
        X_sorted = X[order]

        # Hypervolume 계산 — 참조점은 모든 seed 의 nadir + margin
        # (일단 임시 reference point 로 계산, 나중에 통합 후 재계산)
        ref_pt = np.array([800.0, 200.0])   # F1, F2 의 worst-case 추정
        hv_indicator = Hypervolume(ref_point=ref_pt)
        hv_value = hv_indicator(F_sorted)

        # Knee point
        knee_idx = find_knee_point(F_sorted)
        knee_x, knee_y, _, knee_jib, _ = X_sorted[knee_idx]
        knee_F1, knee_F2 = F_sorted[knee_idx]

        results.append({
            "seed": seed,
            "n_solutions": len(F),
            "HV": hv_value,
            "elapsed": elapsed,
            "knee_x": knee_x,
            "knee_y": knee_y,
            "knee_F1": knee_F1,
            "knee_F2": knee_F2,
            "knee_jib": knee_jib,
            "min_F1": F_sorted[0, 0],
            "min_F2": F_sorted[-1, 1],
        })
        all_F.append(F_sorted)
        all_X.append(X_sorted)

        print(f"  seed={seed:>3}: n={len(F):>3}, HV={hv_value:>10.1f}, "
              f"knee=({knee_x:>+6.2f},{knee_y:>+6.2f}), "
              f"F1∈[{F_sorted[0,0]:.1f}, {F_sorted[-1,0]:.1f}], "
              f"{elapsed:.1f}s")

    df = pd.DataFrame(results)

    print(f"\n{'='*80}")
    print("강건성 통계")
    print(f"{'='*80}")
    valid = df.dropna()
    if len(valid) == 0:
        print("모든 seed 실패")
        return df, all_F, all_X

    # HV 통계
    print(f"\n[Hypervolume]")
    print(f"  평균 = {valid['HV'].mean():.1f}")
    print(f"  표준편차 = {valid['HV'].std():.1f}")
    print(f"  변동계수(CV) = {valid['HV'].std()/valid['HV'].mean():.3f}")
    print(f"  범위 = [{valid['HV'].min():.1f}, {valid['HV'].max():.1f}]")

    print(f"\n[Pareto front 크기]")
    print(f"  평균 = {valid['n_solutions'].mean():.1f}")
    print(f"  범위 = [{valid['n_solutions'].min()}, {valid['n_solutions'].max()}]")

    print(f"\n[Knee point 위치]")
    print(f"  x 평균 = {valid['knee_x'].mean():+.2f} ± {valid['knee_x'].std():.2f}")
    print(f"  y 평균 = {valid['knee_y'].mean():+.2f} ± {valid['knee_y'].std():.2f}")
    print(f"  F1 평균 = {valid['knee_F1'].mean():.1f} ± {valid['knee_F1'].std():.1f}")
    print(f"  F2 평균 = {valid['knee_F2'].mean():.1f} ± {valid['knee_F2'].std():.1f}")

    print(f"\n[해 안정성 판정]")
    cv_hv = valid['HV'].std() / valid['HV'].mean()
    cv_knee_pos = (valid['knee_x'].std() + valid['knee_y'].std()) / 2
    if cv_hv < 0.05 and cv_knee_pos < 2.0:
        print(f"  ✅ 매우 강건 (HV CV={cv_hv:.3f}, knee 표준편차={cv_knee_pos:.2f}m)")
    elif cv_hv < 0.15 and cv_knee_pos < 5.0:
        print(f"  🟢 강건 (HV CV={cv_hv:.3f}, knee 표준편차={cv_knee_pos:.2f}m)")
    else:
        print(f"  ⚠️ 불안정 (HV CV={cv_hv:.3f}, knee 표준편차={cv_knee_pos:.2f}m) — n_gen 증가 권장")

    return df, all_F, all_X


def plot_robustness(df, all_F, all_X, save_path):
    """결과 시각화."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))

    # (1) Pareto fronts 모두 겹쳐 그리기
    ax = axes[0, 0]
    cmap = plt.cm.tab10
    for i, F in enumerate(all_F):
        ax.scatter(F[:, 0], F[:, 1], s=15, alpha=0.55,
                    color=cmap(i % 10), label=f"seed={df['seed'].iloc[i]}")
    ax.set_xlabel("F1 (Safety Risk)")
    ax.set_ylabel("F2 (Cycle hours)")
    ax.set_title(f"All Pareto Fronts ({len(all_F)} seeds)")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3)

    # (2) HV 분포
    ax = axes[0, 1]
    valid = df.dropna()
    ax.bar(valid['seed'].astype(str), valid['HV'],
            color="#1976D2", alpha=0.7, edgecolor="black")
    ax.axhline(valid['HV'].mean(), color="red", linestyle="--",
                label=f"평균 {valid['HV'].mean():.0f}")
    ax.set_xlabel("Seed")
    ax.set_ylabel("Hypervolume")
    ax.set_title(f"HV consistency (CV={valid['HV'].std()/valid['HV'].mean():.3f})")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")

    # (3) Knee point 위치 산점도 (xy 분포)
    ax = axes[1, 0]
    ax.scatter(valid['knee_x'], valid['knee_y'], s=120,
                c=valid['seed'], cmap="tab10", edgecolors="black",
                linewidths=1, alpha=0.85)
    for _, row in valid.iterrows():
        ax.annotate(f"s={int(row['seed'])}",
                     (row['knee_x'], row['knee_y']),
                     xytext=(7, 7), textcoords="offset points",
                     fontsize=8)
    # 평균 점
    ax.scatter(valid['knee_x'].mean(), valid['knee_y'].mean(),
                s=400, marker="*", c="red",
                edgecolors="black", linewidths=2,
                label=f"평균 ({valid['knee_x'].mean():+.1f}, {valid['knee_y'].mean():+.1f})")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Knee point location consistency")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_aspect("equal")

    # (4) Knee point F1, F2 분포
    ax = axes[1, 1]
    ax.scatter(valid['knee_F1'], valid['knee_F2'], s=120,
                c=valid['seed'], cmap="tab10",
                edgecolors="black", linewidths=1, alpha=0.85)
    ax.scatter(valid['knee_F1'].mean(), valid['knee_F2'].mean(),
                s=400, marker="*", c="red",
                edgecolors="black", linewidths=2,
                label=f"평균 ({valid['knee_F1'].mean():.0f}, {valid['knee_F2'].mean():.1f})")
    for _, row in valid.iterrows():
        ax.annotate(f"s={int(row['seed'])}",
                     (row['knee_F1'], row['knee_F2']),
                     xytext=(7, 7), textcoords="offset points",
                     fontsize=8)
    ax.set_xlabel("F1 at knee")
    ax.set_ylabel("F2 at knee (h)")
    ax.set_title("Knee point objective values")
    ax.legend()
    ax.grid(alpha=0.3)

    plt.suptitle("NSGA-II Robustness Test — Multiple Seeds",
                  fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(save_path, dpi=130, bbox_inches="tight")
    print(f"\n시각화 저장: {save_path}")


if __name__ == "__main__":
    df, all_F, all_X = run_robustness_test()
    df.to_csv("/home/claude/crane_opt/robustness_results.csv", index=False)
    print(f"\n표 저장: /home/claude/crane_opt/robustness_results.csv")
    plot_robustness(df, all_F, all_X, "/home/claude/crane_opt/robustness_summary.png")
