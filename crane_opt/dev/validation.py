"""
================================================================================
validation.py
================================================================================
검증 체계 (Validation Framework) — 보완작업 C
--------------------------------------------------------------------------------
Level 1: 코드 적합성 자동 검증 (Compliance Check)
  → 제안된 해가 모든 법규·기준 제약을 만족하는지 자동 점검
  → 결정론적, 가장 강력한 검증

Level 2: 케이스 벤치마크 (별도, 지도교수 협조 필요)

Level 3: 민감도 분석 (Sensitivity Analysis)
  → 입력 파라미터 변동에 대한 출력 강건성 평가
  → Monte Carlo + One-at-a-time 방식 둘 다 지원

검증 산출물:
  - validation_report.txt: 상세 점검 결과
  - sensitivity_results.csv: 민감도 분석 표
"""

import numpy as np
from typing import Dict, List, Tuple
from constraints import evaluate_crane_placement, CRANE_MODELS
from objectives import (
    compute_F1, compute_F2, evaluate_objectives,
    VULNERABILITY_WEIGHTS, INCIDENT_PROBABILITY_PER_CYCLE,
    UTILIZATION_FACTOR,
)
import objectives as obj_module


# =============================================================================
# Level 1: 코드 적합성 검증
# =============================================================================

def level1_compliance_check(crane_xy: Tuple[float, float],
                             model_id: str,
                             mast_height_m: float,
                             jib_length_m: float,
                             verbose: bool = True) -> Dict:
    """
    Level 1 검증: 12개 제약조건 자동 점검.

    Returns:
        dict with overall pass/fail + per-constraint details
    """
    all_pass, results = evaluate_crane_placement(
        crane_xy, model_id, mast_height_m, jib_length_m
    )

    passed = [k for k, v in results.items() if v[0]]
    failed = [k for k, v in results.items() if not v[0]]

    summary = {
        "candidate": {
            "position": crane_xy,
            "model": model_id,
            "mast_height_m": mast_height_m,
            "jib_length_m": jib_length_m,
        },
        "overall_pass": all_pass,
        "n_passed": len(passed),
        "n_failed": len(failed),
        "passed_constraints": passed,
        "failed_constraints": failed,
        "detailed_results": {k: {"passed": v[0], "message": v[1]}
                             for k, v in results.items()},
    }

    if verbose:
        print(f"\n{'='*70}")
        print(f"Level 1 Compliance Check")
        print(f"{'='*70}")
        print(f"후보: pos={crane_xy}, model={model_id}, "
              f"mast={mast_height_m}m, jib={jib_length_m}m")
        print(f"결과: {'✅ 모두 통과' if all_pass else '❌ 실패'} "
              f"({len(passed)}/{len(results)} 통과)")
        for k, (ok, msg) in results.items():
            mark = "✅" if ok else "❌"
            print(f"  {mark} [{k}] {msg}")

    return summary


# =============================================================================
# Level 3: 민감도 분석 (One-at-a-time)
# =============================================================================

def sensitivity_F1_weights(crane_xy: Tuple[float, float],
                            model_id: str,
                            jib_length_m: float,
                            variation: float = 0.5) -> Dict:
    """
    F1 가중치를 ±variation% 변동시켰을 때 F1 값 변화 측정.

    Args:
        variation: 변동 비율 (0.5 = ±50%)

    Returns:
        dict with sensitivity by weight category
    """
    # 원본 보존
    original_weights = VULNERABILITY_WEIGHTS.copy()
    f1_baseline = compute_F1(crane_xy, model_id, jib_length_m)["F1"]

    results = {"baseline_F1": f1_baseline, "perturbations": {}}

    for category in original_weights:
        # 원래 값
        orig_val = original_weights[category]

        # +variation%
        obj_module.VULNERABILITY_WEIGHTS[category] = orig_val * (1 + variation)
        f1_high = compute_F1(crane_xy, model_id, jib_length_m)["F1"]

        # -variation%
        obj_module.VULNERABILITY_WEIGHTS[category] = orig_val * (1 - variation)
        f1_low = compute_F1(crane_xy, model_id, jib_length_m)["F1"]

        # 복원
        obj_module.VULNERABILITY_WEIGHTS[category] = orig_val

        rel_change_high = (f1_high - f1_baseline) / f1_baseline * 100
        rel_change_low = (f1_low - f1_baseline) / f1_baseline * 100

        results["perturbations"][category] = {
            "weight_baseline": orig_val,
            "F1_baseline": f1_baseline,
            "F1_high": f1_high,
            "F1_low": f1_low,
            "rel_change_high_pct": rel_change_high,
            "rel_change_low_pct": rel_change_low,
            "sensitivity_index": (abs(rel_change_high) + abs(rel_change_low)) / 2,
        }

    return results


def sensitivity_incident_probability(crane_xy: Tuple[float, float],
                                       model_id: str,
                                       jib_length_m: float) -> Dict:
    """
    사고 확률을 [1e-5, 1e-3] 범위에서 변동시켰을 때 F1 변화.
    """
    original_p = obj_module.INCIDENT_PROBABILITY_PER_CYCLE
    test_values = [1e-5, 5e-5, 1e-4, 5e-4, 1e-3]

    results = []
    for p in test_values:
        obj_module.INCIDENT_PROBABILITY_PER_CYCLE = p
        f1 = compute_F1(crane_xy, model_id, jib_length_m)["F1"]
        results.append({"P_incident": p, "F1": f1})

    obj_module.INCIDENT_PROBABILITY_PER_CYCLE = original_p

    return {"results": results, "baseline": original_p}


def sensitivity_utilization(crane_xy: Tuple[float, float],
                             model_id: str) -> Dict:
    """
    가동률 0.4 ~ 0.85 범위 변동.
    """
    original_u = obj_module.UTILIZATION_FACTOR
    test_values = [0.40, 0.50, 0.62, 0.70, 0.85]

    results = []
    for u in test_values:
        obj_module.UTILIZATION_FACTOR = u
        f2 = compute_F2(crane_xy, model_id)
        results.append({
            "utilization": u,
            "F2_calendar_days": f2["F2_calendar_days_at_8h"],
        })

    obj_module.UTILIZATION_FACTOR = original_u

    return {"results": results, "baseline": original_u}


# =============================================================================
# Level 3: 민감도 분석 (Monte Carlo, simple)
# =============================================================================

def monte_carlo_sensitivity(crane_xy: Tuple[float, float],
                              model_id: str,
                              jib_length_m: float,
                              n_trials: int = 200,
                              seed: int = 42) -> Dict:
    """
    모든 핵심 파라미터를 동시에 ±20% 변동시킨 Monte Carlo.

    출력: F1·F2 분포의 평균, 표준편차, 5/95 백분위.
    이게 좁으면 모델이 robust, 넓으면 fragile.
    """
    rng = np.random.default_rng(seed)

    F1_samples = []
    F2_samples = []

    original_weights = obj_module.VULNERABILITY_WEIGHTS.copy()
    original_p = obj_module.INCIDENT_PROBABILITY_PER_CYCLE
    original_u = obj_module.UTILIZATION_FACTOR

    for _ in range(n_trials):
        # 가중치 ±20%
        for cat, val in original_weights.items():
            obj_module.VULNERABILITY_WEIGHTS[cat] = val * rng.uniform(0.8, 1.2)
        # 사고확률 ±50% (log 정규에 가까운 변동)
        obj_module.INCIDENT_PROBABILITY_PER_CYCLE = original_p * np.exp(rng.normal(0, 0.5))
        # 가동률 ±10%
        obj_module.UTILIZATION_FACTOR = np.clip(original_u + rng.normal(0, 0.1), 0.3, 0.9)

        try:
            f1 = compute_F1(crane_xy, model_id, jib_length_m)["F1"]
            f2 = compute_F2(crane_xy, model_id)["F2_calendar_days_at_8h"]
            F1_samples.append(f1)
            F2_samples.append(f2)
        except Exception:
            continue

    # 복원
    obj_module.VULNERABILITY_WEIGHTS = original_weights
    obj_module.INCIDENT_PROBABILITY_PER_CYCLE = original_p
    obj_module.UTILIZATION_FACTOR = original_u

    F1_arr = np.array(F1_samples)
    F2_arr = np.array(F2_samples)

    return {
        "n_trials": len(F1_samples),
        "F1": {
            "mean": float(np.mean(F1_arr)),
            "std": float(np.std(F1_arr)),
            "p5": float(np.percentile(F1_arr, 5)),
            "p95": float(np.percentile(F1_arr, 95)),
            "cv": float(np.std(F1_arr) / np.mean(F1_arr)),  # 변동계수
        },
        "F2_days": {
            "mean": float(np.mean(F2_arr)),
            "std": float(np.std(F2_arr)),
            "p5": float(np.percentile(F2_arr, 5)),
            "p95": float(np.percentile(F2_arr, 95)),
            "cv": float(np.std(F2_arr) / np.mean(F2_arr)),
        },
    }


# =============================================================================
# 통합 검증 리포트 생성
# =============================================================================

def generate_validation_report(crane_xy: Tuple[float, float],
                                 model_id: str,
                                 mast_height_m: float,
                                 jib_length_m: float,
                                 output_path: str = None) -> str:
    """
    통합 검증 리포트 (텍스트) 생성.
    """
    lines = []
    lines.append("=" * 78)
    lines.append("크레인 배치 검증 리포트 — Validation Report")
    lines.append("=" * 78)
    lines.append(f"\n검증 대상:")
    lines.append(f"  위치: ({crane_xy[0]:.1f}, {crane_xy[1]:.1f}) m")
    lines.append(f"  모델: {model_id}")
    lines.append(f"  마스트: {mast_height_m} m")
    lines.append(f"  지브: {jib_length_m} m")

    # Level 1
    lines.append(f"\n{'─'*78}")
    lines.append("LEVEL 1: 코드 적합성 검증 (Compliance Check)")
    lines.append(f"{'─'*78}")
    L1 = level1_compliance_check(crane_xy, model_id, mast_height_m,
                                    jib_length_m, verbose=False)
    lines.append(f"전체 결과: {'✅ 모두 통과' if L1['overall_pass'] else '❌ 위반 있음'}")
    lines.append(f"통과: {L1['n_passed']}, 실패: {L1['n_failed']}")
    for cid, info in L1['detailed_results'].items():
        mark = "✅" if info['passed'] else "❌"
        lines.append(f"  {mark} [{cid}] {info['message']}")

    # Objectives
    lines.append(f"\n{'─'*78}")
    lines.append("목적함수 값")
    lines.append(f"{'─'*78}")
    obj = evaluate_objectives(crane_xy, model_id, jib_length_m)
    lines.append(f"F1 (안전 지수): {obj['F1']['F1']:.2f}")
    lines.append(f"  - 영역별 기여:")
    for zone, b in obj['F1']['breakdown'].items():
        lines.append(f"    {zone:<25} V={b['vulnerability']:.1f}, "
                     f"A={b['area_m2']:.1f}m², R={b['risk_contribution']:.1f}")
    lines.append(f"\nF2 (사이클 타임):")
    lines.append(f"  - 명목: {obj['F2']['F2_hours']:.1f}h "
                 f"({obj['F2']['F2_days_at_8h']:.1f} working days @8h)")
    lines.append(f"  - 가동률 반영: {obj['F2']['F2_calendar_hours']:.1f}h "
                 f"({obj['F2']['F2_calendar_days_at_8h']:.1f} calendar days)")
    lines.append(f"  - 가동률: {obj['F2']['utilization_factor']:.2f}")

    # Level 3: One-at-a-time sensitivity
    lines.append(f"\n{'─'*78}")
    lines.append("LEVEL 3-A: F1 가중치 민감도 (±50%)")
    lines.append(f"{'─'*78}")
    sens_w = sensitivity_F1_weights(crane_xy, model_id, jib_length_m)
    lines.append(f"Baseline F1 = {sens_w['baseline_F1']:.2f}")
    lines.append(f"{'카테고리':<25} {'+50% F1':>10} {'-50% F1':>10} "
                 f"{'민감도지수':>12}")
    for cat, p in sens_w['perturbations'].items():
        lines.append(f"{cat:<25} {p['F1_high']:>10.1f} {p['F1_low']:>10.1f} "
                     f"{p['sensitivity_index']:>12.1f}%")

    # 가장 영향 큰 변수
    sorted_sens = sorted(sens_w['perturbations'].items(),
                          key=lambda x: -x[1]['sensitivity_index'])
    top = sorted_sens[0]
    lines.append(f"\n→ 가장 민감한 변수: {top[0]} (민감도 {top[1]['sensitivity_index']:.1f}%)")

    # Level 3-B: 사고 확률
    lines.append(f"\n{'─'*78}")
    lines.append("LEVEL 3-B: 사고 확률 변동 (1e-5 ~ 1e-3)")
    lines.append(f"{'─'*78}")
    sens_p = sensitivity_incident_probability(crane_xy, model_id, jib_length_m)
    lines.append(f"{'P_incident':>12} {'F1':>10}")
    for r in sens_p['results']:
        marker = " ← baseline" if r['P_incident'] == sens_p['baseline'] else ""
        lines.append(f"{r['P_incident']:>12.0e} {r['F1']:>10.2f}{marker}")
    lines.append("→ F1은 P에 선형 비례. 가중치 비율과 별개로 절대값 비교 시 주의.")

    # Level 3-C: 가동률
    lines.append(f"\n{'─'*78}")
    lines.append("LEVEL 3-C: 가동률 변동 (0.40 ~ 0.85)")
    lines.append(f"{'─'*78}")
    sens_u = sensitivity_utilization(crane_xy, model_id)
    lines.append(f"{'가동률':>10} {'F2 (실 시공일)':>16}")
    for r in sens_u['results']:
        marker = " ← baseline" if r['utilization'] == sens_u['baseline'] else ""
        lines.append(f"{r['utilization']:>10.2f} {r['F2_calendar_days']:>16.1f}{marker}")

    # Level 3-D: Monte Carlo
    lines.append(f"\n{'─'*78}")
    lines.append("LEVEL 3-D: Monte Carlo 종합 강건성 (n=200, 모든 변수 동시 변동)")
    lines.append(f"{'─'*78}")
    mc = monte_carlo_sensitivity(crane_xy, model_id, jib_length_m, n_trials=200)
    lines.append(f"시행 횟수: {mc['n_trials']}")
    lines.append(f"\nF1 분포:")
    lines.append(f"  평균 = {mc['F1']['mean']:.1f} ± {mc['F1']['std']:.1f}")
    lines.append(f"  90% 구간 = [{mc['F1']['p5']:.1f}, {mc['F1']['p95']:.1f}]")
    lines.append(f"  변동계수(CV) = {mc['F1']['cv']:.2f}")
    lines.append(f"\nF2 분포 (실 시공일):")
    lines.append(f"  평균 = {mc['F2_days']['mean']:.1f}일 ± {mc['F2_days']['std']:.1f}일")
    lines.append(f"  90% 구간 = [{mc['F2_days']['p5']:.1f}, {mc['F2_days']['p95']:.1f}]")
    lines.append(f"  변동계수(CV) = {mc['F2_days']['cv']:.2f}")

    # 강건성 평가
    lines.append("\n[강건성 평가]")
    if mc['F1']['cv'] < 0.3:
        lines.append("  F1: ✅ 강건 (CV < 0.3) - 절대값이 일관적")
    elif mc['F1']['cv'] < 0.6:
        lines.append("  F1: ⚠️ 보통 (0.3 ≤ CV < 0.6) - 가중치 추정에 주의")
    else:
        lines.append("  F1: ❌ 취약 (CV ≥ 0.6) - 절대값 신뢰성 낮음")
    if mc['F2_days']['cv'] < 0.2:
        lines.append("  F2: ✅ 강건")
    else:
        lines.append("  F2: ⚠️ 보통 이상")

    lines.append("\n" + "=" * 78)
    lines.append("리포트 끝")
    lines.append("=" * 78)

    report = "\n".join(lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"리포트 저장: {output_path}")

    return report


# =============================================================================
# 사용 예
# =============================================================================
if __name__ == "__main__":
    # 예시 후보: F1·F2 둘 다 적당한 절충 지점 추정
    report = generate_validation_report(
        crane_xy=(8, -5),
        model_id="Potain_MR_160C",
        mast_height_m=40,
        jib_length_m=30,
        output_path="/home/claude/crane_opt/validation_report.txt",
    )
    print(report)
