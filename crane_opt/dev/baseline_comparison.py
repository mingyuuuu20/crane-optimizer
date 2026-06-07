"""
================================================================================
baseline_comparison.py
================================================================================
검증 α-1: Random Search vs NSGA-II 성능 비교
--------------------------------------------------------------------------------
"우리 NSGA-II 가 무작위 탐색보다 얼마나 좋은가?" 정량 검증

방법:
  - 같은 부지에서 Random Search 1000회 vs NSGA-II 100회
  - 각각 best F1, F2, Pareto 크기 비교
  - "X% cost reduction" / "Y배 빠른 수렴" 정량 결론

Abdelmegid et al. (2015) 의 검증 패턴: "20% cost reduction 대비 educated guess"

산출물:
  - results/baseline_comparison.csv: 표
  - results/baseline_comparison.png: 시각화
"""
import time
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

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


def run_random_search(site, n_samples=1000, seed=42, target_model_idx=None):
    """Random Search baseline.

    부지 검색 범위 내에서 무작위로 n_samples 개 후보 생성.
    각 후보 평가 후 feasible 한 것만 Pareto 추출.
    """
    use_site(site)
    from constraints import continuous_constraints
    from objectives import compute_F1, compute_F2
    from optimizer import get_search_bounds, MODEL_LIST

    bounds = get_search_bounds()
    x_lo, x_hi = bounds["x_range"]
    y_lo, y_hi = bounds["y_range"]
    jib_lo, jib_hi = bounds["jib_range"]
    mast_lo, mast_hi = bounds["mast_range"]

    rng = np.random.default_rng(seed)
    feasible_F = []
    feasible_X = []
    total_evaluated = 0
    n_feasible = 0

    t0 = time.time()
    for _ in range(n_samples):
        x = float(rng.uniform(x_lo, x_hi))
        y = float(rng.uniform(y_lo, y_hi))
        m_idx = (int(rng.integers(0, 3)) if target_model_idx is None
                  else int(target_model_idx))
        jib = float(rng.uniform(jib_lo, jib_hi))
        mast = float(rng.uniform(mast_lo, mast_hi))
        model = MODEL_LIST[m_idx]

        try:
            g = continuous_constraints((x, y), model, mast, jib)
            cv = max(max(g), 0.0)
            total_evaluated += 1
            if cv > 1e-6:
                continue
            f1 = compute_F1((x, y), model, jib)["F1"]
            # BUGFIX: NSGA-II(optimizer.py)는 F2_calendar_hours(가동률 η 적용)를 쓰는데
            # 여기선 F2_hours(η 미적용)를 써서 Random이 1/η=1.61배 빠르게 잘못 평가됨.
            # → 동일 단위(calendar_hours)로 맞춰 공정 비교.
            f2 = compute_F2((x, y), model)["F2_calendar_hours"]
            feasible_F.append([f1, f2])
            feasible_X.append([x, y, m_idx, jib, mast])
            n_feasible += 1
        except Exception:
            continue

    elapsed = time.time() - t0
    F = np.array(feasible_F) if feasible_F else np.empty((0, 2))
    X = np.array(feasible_X) if feasible_X else np.empty((0, 5))

    # Pareto 추출
    pareto_mask = compute_pareto_mask(F)
    F_pareto = F[pareto_mask] if len(F) > 0 else F
    X_pareto = X[pareto_mask] if len(X) > 0 else X

    return {
        "method": "Random Search",
        "n_samples": n_samples,
        "n_feasible": n_feasible,
        "feasible_rate": n_feasible / n_samples if n_samples > 0 else 0,
        "F_all": F,
        "X_all": X,
        "F_pareto": F_pareto,
        "X_pareto": X_pareto,
        "n_pareto": len(F_pareto),
        "elapsed_s": elapsed,
        "evals": total_evaluated,
    }


def compute_pareto_mask(F):
    """간단한 Pareto 추출 (낮을수록 좋음)."""
    if len(F) == 0:
        return np.array([], dtype=bool)
    n = len(F)
    mask = np.ones(n, dtype=bool)
    for i in range(n):
        for j in range(n):
            if i == j: continue
            # j dominates i?
            if (F[j] <= F[i]).all() and (F[j] < F[i]).any():
                mask[i] = False
                break
    return mask


def run_nsga2(site, pop_size=80, n_gen=30, seed=42):
    """우리 NSGA-II dual-branch."""
    use_site(site)
    from optimizer import run_dual_branch_optimization

    t0 = time.time()
    r = run_dual_branch_optimization(
        pop_size=pop_size, n_gen=n_gen, seed=seed, verbose=False
    )
    elapsed = time.time() - t0

    if r.F is None or len(r.F) == 0:
        return {
            "method": "NSGA-II",
            "n_samples": pop_size * n_gen,
            "n_pareto": 0,
            "F_pareto": np.empty((0, 2)),
            "X_pareto": np.empty((0, 5)),
            "elapsed_s": elapsed,
        }

    return {
        "method": "NSGA-II",
        "n_samples": pop_size * n_gen,
        "n_pareto": len(r.F),
        "F_pareto": r.F,
        "X_pareto": r.X,
        "elapsed_s": elapsed,
    }


def hypervolume(F, ref_point):
    """간단한 2D HV 계산."""
    if len(F) == 0:
        return 0.0
    from pymoo.indicators.hv import Hypervolume
    hv = Hypervolume(ref_point=ref_point)
    return float(hv(F))


def compare_site(site_path, n_random=1000, pop_size=80, n_gen=30, seed=42):
    """단일 부지에서 두 알고리즘 비교."""
    site = load_site(site_path)
    print(f"\n{'='*78}")
    print(f"▶ {site.metadata.get('display_name')}")
    print(f"{'='*78}")

    # 1) Random Search
    print(f"  [Random Search] n={n_random}회...")
    rnd = run_random_search(site, n_samples=n_random, seed=seed)
    print(f"    feasible {rnd['n_feasible']}/{rnd['n_samples']} "
          f"({rnd['feasible_rate']*100:.1f}%), "
          f"Pareto {rnd['n_pareto']}개, {rnd['elapsed_s']:.1f}s")

    # 2) NSGA-II
    print(f"  [NSGA-II dual-branch] pop={pop_size} gen={n_gen}...")
    nsga = run_nsga2(site, pop_size, n_gen, seed)
    print(f"    Pareto {nsga['n_pareto']}개, {nsga['elapsed_s']:.1f}s")

    # 3) 공통 reference point: 고정 이론 최악값 (전 부지 동일)
    #    BUGFIX: 기존 percentile(95)*1.10 방식은 데이터 분포에 휘둘려
    #    점이 front에 모인 좋은 알고리즘(NSGA-II)일수록 HV가 작아 보이는 역설 발생.
    #    HV의 올바른 해석("더 넓은 영역 지배 = 우월")을 위해 ref를 분포와 무관하게 고정.
    #    F1: 협소대지 제3자위험 상한 추정, F2: 가동률 적용 양중시간 상한 추정.
    REF_POINT_FIXED = np.array([2000.0, 250.0])
    ref = REF_POINT_FIXED.copy()
    # 안전장치: 어떤 해라도 ref보다 나쁜(큰) 값이면 그 점이 HV에서 누락되므로,
    # 실제 관측 최댓값 + 마진이 고정 ref를 넘으면 ref를 끌어올려 모든 점을 포괄.
    _allF = [a for a in (rnd["F_pareto"], nsga["F_pareto"]) if len(a) > 0]
    if _allF:
        _cat = np.vstack(_allF)
        ref[0] = max(ref[0], float(_cat[:, 0].max()) * 1.05)
        ref[1] = max(ref[1], float(_cat[:, 1].max()) * 1.05)

    hv_rnd = hypervolume(rnd["F_pareto"], ref)
    hv_nsga = hypervolume(nsga["F_pareto"], ref)

    # 3.5) 지배 관계 (HV보다 직관적·공정한 우월성 지표)
    def _dominates(a, b):  # a가 b를 지배 (최소화)
        return bool(np.all(a <= b) and np.any(a < b))
    Rf, Nf = rnd["F_pareto"], nsga["F_pareto"]
    rnd_dominated = sum(1 for rp in Rf if any(_dominates(np_, rp) for np_ in Nf)) if len(Rf) and len(Nf) else 0
    nsga_dominated = sum(1 for np_ in Nf if any(_dominates(rp, np_) for rp in Rf)) if len(Rf) and len(Nf) else 0
    rnd_dom_rate = (rnd_dominated / len(Rf) * 100) if len(Rf) else None
    nsga_dom_rate = (nsga_dominated / len(Nf) * 100) if len(Nf) else None

    # 4) 통계
    print(f"\n  📊 비교 결과:")
    print(f"    Hypervolume:")
    print(f"      Random: {hv_rnd:>12,.1f}")
    print(f"      NSGA-II:{hv_nsga:>12,.1f}")
    if hv_rnd > 0:
        print(f"      개선:   {(hv_nsga/hv_rnd - 1)*100:+.1f}%")

    print(f"\n    Pareto 크기:")
    print(f"      Random: {rnd['n_pareto']}")
    print(f"      NSGA-II:{nsga['n_pareto']}")

    print(f"\n    🎯 지배 관계 (핵심 지표):")
    print(f"      Random Pareto 중 NSGA-II에 지배당함: {rnd_dominated}/{len(Rf)}"
          + (f" ({rnd_dom_rate:.0f}%)" if rnd_dom_rate is not None else ""))
    print(f"      NSGA-II Pareto 중 Random에 지배당함: {nsga_dominated}/{len(Nf)}"
          + (f" ({nsga_dom_rate:.0f}%)" if nsga_dom_rate is not None else ""))

    print(f"\n    수렴 속도:")
    print(f"      Random: {rnd['elapsed_s']:.1f}s / {rnd['n_samples']} eval")
    print(f"      NSGA-II:{nsga['elapsed_s']:.1f}s / {nsga['n_samples']} eval")

    # 5) Best F1, F2 비교
    if rnd["n_pareto"] > 0 and nsga["n_pareto"] > 0:
        print(f"\n    Best F1 (안전):")
        rnd_best_f1 = rnd["F_pareto"][:, 0].min()
        nsga_best_f1 = nsga["F_pareto"][:, 0].min()
        print(f"      Random: {rnd_best_f1:.1f}")
        print(f"      NSGA-II:{nsga_best_f1:.1f}")
        print(f"      개선:   {(1 - nsga_best_f1/rnd_best_f1)*100:+.1f}%")

        print(f"\n    Best F2 (시간):")
        rnd_best_f2 = rnd["F_pareto"][:, 1].min()
        nsga_best_f2 = nsga["F_pareto"][:, 1].min()
        print(f"      Random: {rnd_best_f2:.1f}h")
        print(f"      NSGA-II:{nsga_best_f2:.1f}h")
        print(f"      개선:   {(1 - nsga_best_f2/rnd_best_f2)*100:+.1f}%")

    return {
        "site_id": site.metadata.get("site_id"),
        "site_name": site.metadata.get("display_name"),
        "random": rnd,
        "nsga": nsga,
        "hv_random": hv_rnd,
        "hv_nsga": hv_nsga,
        "hv_improvement_pct": (hv_nsga/hv_rnd - 1) * 100 if hv_rnd > 0 else None,
        "ref_point": ref.tolist(),
        "rnd_dominated": rnd_dominated,
        "nsga_dominated": nsga_dominated,
        "rnd_dom_rate": rnd_dom_rate,
        "nsga_dom_rate": nsga_dom_rate,
    }


def draw_comparison_figure(comparisons, out_path):
    """4 부지 비교 시각화."""
    n_feasible_sites = sum(1 for c in comparisons
                             if c["random"]["n_pareto"] > 0 or c["nsga"]["n_pareto"] > 0)
    if n_feasible_sites == 0:
        return

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    axes = axes.flatten()

    for ax, c in zip(axes, comparisons):
        rnd_F = c["random"]["F_pareto"]
        nsga_F = c["nsga"]["F_pareto"]

        # Random Search 전체 (회색)
        rnd_F_all = c["random"]["F_all"]
        if len(rnd_F_all) > 0:
            ax.scatter(rnd_F_all[:, 0], rnd_F_all[:, 1],
                        c="lightgray", s=10, alpha=0.4, label=f"Random samples")

        if len(rnd_F) > 0:
            ax.scatter(rnd_F[:, 0], rnd_F[:, 1], c="orange", s=50,
                        edgecolors="black", linewidths=0.5,
                        label=f"Random Pareto ({len(rnd_F)})")
            order = np.argsort(rnd_F[:, 0])
            ax.plot(rnd_F[order, 0], rnd_F[order, 1], "--",
                     color="orange", alpha=0.7, linewidth=1.5)

        if len(nsga_F) > 0:
            ax.scatter(nsga_F[:, 0], nsga_F[:, 1], c="#1976D2", s=60,
                        edgecolors="black", linewidths=0.5,
                        label=f"NSGA-II Pareto ({len(nsga_F)})")
            order = np.argsort(nsga_F[:, 0])
            ax.plot(nsga_F[order, 0], nsga_F[order, 1], "-",
                     color="#1976D2", linewidth=1.8)

        title = c["site_name"]
        if c["hv_improvement_pct"] is not None:
            title += f"\nHV 개선 {c['hv_improvement_pct']:+.1f}%"
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xlabel("F1 — 제3자 안전위험", fontsize=10)
        ax.set_ylabel("F2 — 양중 사이클 (h)", fontsize=10)
        ax.legend(loc="best", fontsize=8)
        ax.grid(alpha=0.3)

    plt.suptitle("Random Search vs NSGA-II — 4 부지 비교",
                  fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close()


def main():
    print(f"\n{'#'*78}")
    print(f"# 검증 α-1: Random Search vs NSGA-II Baseline 비교")
    print(f"#"*78)

    sites = list_sites("sites")
    comparisons = []
    for sf in sites:
        c = compare_site(sf, n_random=1000, pop_size=80, n_gen=30, seed=42)
        comparisons.append(c)

    # CSV 저장
    import pandas as pd
    rows = []
    for c in comparisons:
        rows.append({
            "site_id": c["site_id"],
            "site_name": c["site_name"],
            "Random_feasible_rate_%":
                100 * c["random"]["n_feasible"] / c["random"]["n_samples"],
            "Random_pareto_n":  c["random"]["n_pareto"],
            "Random_time_s":    round(c["random"]["elapsed_s"], 1),
            "Random_HV":        round(c["hv_random"], 1),
            "NSGAII_pareto_n":  c["nsga"]["n_pareto"],
            "NSGAII_time_s":    round(c["nsga"]["elapsed_s"], 1),
            "NSGAII_HV":        round(c["hv_nsga"], 1),
            "HV_improvement_%": (round(c["hv_improvement_pct"], 1)
                                  if c["hv_improvement_pct"] is not None
                                  else None),
            "Random_dominated_by_NSGA": f"{c['rnd_dominated']}/{c['random']['n_pareto']}",
            "NSGA_dominated_by_Random": f"{c['nsga_dominated']}/{c['nsga']['n_pareto']}",
        })
    df = pd.DataFrame(rows)
    csv_path = Path("results") / "baseline_comparison.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n→ {csv_path}")
    print(df.to_string(index=False))

    # 시각화
    fig_path = Path("results") / "baseline_comparison.png"
    draw_comparison_figure(comparisons, str(fig_path))
    print(f"→ {fig_path}")


if __name__ == "__main__":
    main()
