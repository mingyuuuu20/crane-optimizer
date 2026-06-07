"""
================================================================================
infeasibility_analyzer.py
================================================================================
실행불가 부지(infeasible site) 정량 분석기
--------------------------------------------------------------------------------
NSGA-II 가 feasible 해를 못 찾을 때, "그냥 결과 없음" 으로 끝내지 않고
다음을 정량 보고한다:

  - 어느 제약이 가장 자주 위반되는가? (제약별 위반 빈도)
  - 최소 위반 후보는? (가장 가까운 quasi-feasible)
  - 어느 부분을 완화하면 feasible 되는가? (sensitivity)

이것은 학술적 가치 있는 결과:
    "도로점용 불가 + 6m 이격 의무 + 9층 시공" 조건의 협소대지는
    합법적 단일 크레인 시공이 사실상 불가능함을 정량 입증.
"""
import numpy as np
from itertools import product

from constraints import continuous_constraints

CONSTRAINT_NAMES = [
    "C1  인양능력 (자재 무게 ≤ 능력)",
    "C2  인접건물 0.6m 이격",
    "C3  인접건물 본체 침범",
    "C4  풍하중 모멘트 한계",
    "C5  도달거리 (양중점 사각 없음)",
    "C6  후크 높이 (건물 + 5m 여유)",
    "C7  설치 영역 (부지 ∪ 점용가능도로)",
    "C8  Wall tie 가능성",
    "C9  인접대지 공중 침범 (operating area)",
]


def grid_scan_min_violation(model_list=None,
                              x_step=1.5, y_step=1.5,
                              jib_options=(20, 25, 30, 35, 40, 45, 50),
                              mast_options=(35, 45, 55, 65, 75)):
    """grid 스캔으로 각 모델별 최소 위반 후보를 탐색.

    Returns dict:
        per_model: {model: {min_viol, best_xy, best_jib, best_mast, G}}
        per_constraint_freq: {C_idx: violations_count}
    """
    # 활성 site 의 검색 경계 사용
    import optimizer as _opt
    x_lo, x_hi = _opt._SEARCH_X_RANGE
    y_lo, y_hi = _opt._SEARCH_Y_RANGE

    if model_list is None:
        model_list = ["Potain_MR_160C", "Liebherr_280_HC_L", "Potain_MDT_178"]

    xs = np.arange(x_lo, x_hi + 0.001, x_step)
    ys = np.arange(y_lo, y_hi + 0.001, y_step)

    per_model = {}
    per_constraint_freq = np.zeros(len(CONSTRAINT_NAMES), dtype=int)
    quasi_feasible = []   # 위반 ≤ 0.5 후보

    for model in model_list:
        best = (float("inf"), None, None)
        for x in xs:
            for y in ys:
                for jib in jib_options:
                    for mast in mast_options:
                        try:
                            g = continuous_constraints((x, y), model, mast, jib)
                        except Exception:
                            continue
                        viol = float(max(max(g), 0.0))
                        if viol < best[0]:
                            best = (viol, (x, y, jib, mast), g)
                        # 제약별 위반 빈도
                        for i, v in enumerate(g):
                            if v > 0.01:
                                per_constraint_freq[i] += 1
                        if viol < 0.5:
                            quasi_feasible.append({
                                "model": model,
                                "x": float(x), "y": float(y),
                                "jib": float(jib), "mast": float(mast),
                                "violation": viol,
                            })
        per_model[model] = {
            "min_violation": float(best[0]),
            "xy": tuple(map(float, best[1][:2])) if best[1] else None,
            "jib_m": float(best[1][2]) if best[1] else None,
            "mast_m": float(best[1][3]) if best[1] else None,
            "G": [float(v) for v in best[2]] if best[2] is not None else None,
            "primary_violation": (
                CONSTRAINT_NAMES[int(np.argmax(best[2]))]
                if best[2] is not None else None
            ),
        }

    return {
        "per_model": per_model,
        "per_constraint_freq": per_constraint_freq.tolist(),
        "quasi_feasible_count": len(quasi_feasible),
        "quasi_feasible_examples": quasi_feasible[:10],
    }


def analyze_and_report(label="infeasible site"):
    """현재 활성 부지를 분석하고 사람이 읽을 수 있는 리포트 출력."""
    print(f"\n{'='*78}")
    print(f"  실행불가성 분석: {label}")
    print(f"{'='*78}")

    res = grid_scan_min_violation()

    # 1) 모델별 최소 위반
    print(f"\n[모델별 최소 위반 후보]")
    for model, info in res["per_model"].items():
        if info["min_violation"] == 0.0:
            print(f"  ✅ {model}: feasible 후보 발견! "
                  f"위치 {info['xy']}, jib {info['jib_m']}m, mast {info['mast_m']}m")
        else:
            print(f"  ❌ {model}: 최소 위반 {info['min_violation']:.2f}")
            print(f"      위치 {info['xy']}, jib {info['jib_m']}m, mast {info['mast_m']}m")
            print(f"      주요 제약: {info['primary_violation']}")
            print(f"      G = {[round(v,2) for v in info['G']]}")

    # 2) 제약별 위반 빈도
    print(f"\n[제약별 위반 빈도 (grid 전수조사)]")
    total = sum(res["per_constraint_freq"])
    if total > 0:
        for i, freq in enumerate(res["per_constraint_freq"]):
            pct = 100 * freq / total
            bar = "█" * int(pct / 3)
            print(f"  {CONSTRAINT_NAMES[i]:<32} : {freq:>6}회 ({pct:5.1f}%) {bar}")

    # 3) quasi-feasible 후보
    n_qf = res["quasi_feasible_count"]
    if n_qf > 0:
        print(f"\n[quasi-feasible (위반 ≤ 0.5)]: {n_qf}개 발견")
        for ex in res["quasi_feasible_examples"][:5]:
            print(f"  {ex['model'][:18]:<18} ({ex['x']:+.1f},{ex['y']:+.1f}) "
                  f"jib={ex['jib']:.0f} mast={ex['mast']:.0f}  viol={ex['violation']:.2f}")
        print(f"\n  → 제약을 약간만 완화하면 시공 가능 (예: 도로점용 허가 또는 이격 거리 0.4m 완화)")
    else:
        print(f"\n[quasi-feasible]: 없음 — 단일 크레인 시공 불가능 부지")
        print(f"  → 권장: 이동식 크레인 병용, 부분 시공, 또는 도로점용 허가 필요")

    return res


if __name__ == "__main__":
    import sys
    from site_loader import load_site
    from site_helpers import use_site

    site_path = sys.argv[1] if len(sys.argv) > 1 else "sites/synthetic_c_enclosed.json"
    site = load_site(site_path)
    use_site(site)
    analyze_and_report(label=site.metadata.get("display_name", site_path))
