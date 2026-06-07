"""
================================================================================
objectives.py
================================================================================
타워크레인 배치 다목적 최적화 — 목적함수 F1·F2 (작업 4)
--------------------------------------------------------------------------------
F1: 제3자 안전 지수 최소화 (Third-Party Safety Risk Index)
F2: 양중 사이클 타임 최소화 (Lifting Cycle Time)

수학적 정식화 출처:
  - F1 구조 (Risk = Likelihood × Consequence): ISO 31000:2018
  - F1 취약성 가중치 카테고리: KOSHA KRAS 위험성평가 + CIRIA C703
  - F2 시간 계산: 제조사 카탈로그 운동 속도 사양

설계 원칙:
  - 두 함수 모두 "낮을수록 좋음" (minimization)
  - 결정변수: (crane_x, crane_y, model_id, jib_length, mast_height)
  - 알고리즘은 두 값을 동시 최소화하려 함 → trade-off → Pareto front
"""

import math
from typing import Tuple, Dict
from shapely.geometry import Point

# --- 활성 부지 관리 ---------------------------------------------------------
import site_model as _default_site

SITE                        = _default_site.SITE
ADJACENT_BUILDINGS          = _default_site.ADJACENT_BUILDINGS
ROADS                       = _default_site.ROADS
PLANNED_BUILDING            = _default_site.PLANNED_BUILDING
PLANNED_BUILDING_HEIGHT_M   = _default_site.PLANNED_BUILDING_HEIGHT_M
LIFT_POINTS                 = _default_site.LIFT_POINTS
MATERIAL_YARD               = _default_site.MATERIAL_YARD
BUILDING_GRID_POINTS        = _default_site.BUILDING_GRID_POINTS
LIFT_POINT_MATERIAL_PROFILE = _default_site.LIFT_POINT_MATERIAL_PROFILE
MATERIAL_WEIGHTS            = _default_site.MATERIAL_WEIGHTS
MATERIAL_HANDLING_TIME      = _default_site.MATERIAL_HANDLING_TIME


def set_active_site(site):
    """모듈 전역 부지 변수를 SiteData 로 교체 (constraints.set_active_site와 짝)."""
    global SITE, ADJACENT_BUILDINGS, ROADS, PLANNED_BUILDING
    global PLANNED_BUILDING_HEIGHT_M, LIFT_POINTS, MATERIAL_YARD
    global BUILDING_GRID_POINTS, LIFT_POINT_MATERIAL_PROFILE
    global MATERIAL_WEIGHTS, MATERIAL_HANDLING_TIME
    SITE                        = site.SITE
    ADJACENT_BUILDINGS          = site.ADJACENT_BUILDINGS
    ROADS                       = site.ROADS
    PLANNED_BUILDING            = site.PLANNED_BUILDING
    PLANNED_BUILDING_HEIGHT_M   = site.PLANNED_BUILDING_HEIGHT_M
    LIFT_POINTS                 = site.LIFT_POINTS
    MATERIAL_YARD               = site.MATERIAL_YARD
    BUILDING_GRID_POINTS        = site.BUILDING_GRID_POINTS
    LIFT_POINT_MATERIAL_PROFILE = site.LIFT_POINT_MATERIAL_PROFILE
    MATERIAL_WEIGHTS            = site.MATERIAL_WEIGHTS
    MATERIAL_HANDLING_TIME      = site.MATERIAL_HANDLING_TIME


from crane_models import CRANES


# =============================================================================
# F1 관련 — 취약성 가중치 (Vulnerability Weights)
# =============================================================================
# (KOSHA 통계 출처 등은 동일, 위에 정의)

VULNERABILITY_WEIGHTS = {
    "own_site":              0.5,
    "planned_building":      0.5,
    "adjacent_residential":  3.0,
    "road":                  5.0,
    "empty":                 0.5,
}


# =============================================================================
# F2 관련 — 시공 시나리오 (자재별 + 위치별)
# =============================================================================
# 양중점·자재별 cycle 수 = LIFT_POINT_MATERIAL_PROFILE 에서 가져옴
# 자재별 중량 = MATERIAL_WEIGHTS
# 자재별 결박·해제 시간 = MATERIAL_HANDLING_TIME

HOOK_OPERATING_HEIGHT_M = PLANNED_BUILDING_HEIGHT_M + 7   # 39m
LIFT_POINT_DELIVERY_HEIGHT_M = 27                          # 9층 바닥

# 사고 확률 (per cycle) — 자재 무게에 비례 조정
# 출처 정당화는 위 docstring 동일
INCIDENT_PROBABILITY_PER_CYCLE = 1e-4   # baseline (갱폼 3톤 기준)

# 자재 무게별 사고 확률 가중치 (heavier → higher risk)
MATERIAL_RISK_FACTOR = {
    "gangform":  1.00,
    "rebar":     0.50,    # 가벼움
    "concrete":  0.70,
    "pc_part":   1.30,    # 무겁고 부피 큼
    "finishing": 0.20,    # 매우 가벼움
}

UTILIZATION_FACTOR = 0.62


# =============================================================================
# F1: 제3자 안전 지수 (자재별 가중)
# =============================================================================

def compute_F1(crane_xy: Tuple[float, float],
               model_id: str,
               jib_length_m: float,
               total_cycles: int = None) -> Dict:
    """
    제3자 안전 지수 F1 계산 (자재별 risk factor 반영).

    수식:
        F1 = Σ_material (N_material × P_base × R_material) × Σ V_z × A_overlap

    Args:
        crane_xy: 크레인 위치 (x, y) in meters
        model_id: 크레인 모델 ID
        jib_length_m: 지브 길이 (작업 반경)
        total_cycles: deprecated, 자동 계산

    Returns:
        dict with breakdown by zone + total F1
    """
    # 자재별 가중 cycles 합산
    weighted_cycles = 0
    raw_cycles = 0
    for idx, profile in LIFT_POINT_MATERIAL_PROFILE.items():
        for material, n in profile.items():
            risk_factor = MATERIAL_RISK_FACTOR.get(material, 1.0)
            weighted_cycles += n * risk_factor
            raw_cycles += n

    swept = Point(crane_xy).buffer(jib_length_m)

    # 카운터지브 영역 (T형은 별도 swept area)
    spec = CRANES[model_id]
    if spec["type"] == "hammerhead":
        counter_swept = Point(crane_xy).buffer(spec["counter_jib_length_m"])
        total_swept = swept.union(counter_swept)
    else:
        total_swept = swept

    breakdown = {}

    # 자기 부지
    overlap_site = total_swept.intersection(SITE).area
    breakdown["own_site"] = {
        "vulnerability": VULNERABILITY_WEIGHTS["own_site"],
        "area_m2": overlap_site,
        "risk_contribution": VULNERABILITY_WEIGHTS["own_site"] * overlap_site,
    }

    # 도로 (보행자·차량)
    road_total = 0
    for road_key, road in ROADS.items():
        overlap = total_swept.intersection(road["polygon"]).area
        road_total += overlap
    breakdown["road"] = {
        "vulnerability": VULNERABILITY_WEIGHTS["road"],
        "area_m2": road_total,
        "risk_contribution": VULNERABILITY_WEIGHTS["road"] * road_total,
    }

    # 인접 건물
    adj_total = 0
    for direction, bldg in ADJACENT_BUILDINGS.items():
        overlap = total_swept.intersection(bldg["footprint"]).area
        adj_total += overlap
    breakdown["adjacent_residential"] = {
        "vulnerability": VULNERABILITY_WEIGHTS["adjacent_residential"],
        "area_m2": adj_total,
        "risk_contribution": VULNERABILITY_WEIGHTS["adjacent_residential"] * adj_total,
    }

    # 그 외 (빈 영역) — 가중치 낮음
    total_swept_area = total_swept.area
    covered_area = overlap_site + road_total + adj_total
    empty_area = max(0, total_swept_area - covered_area)
    breakdown["empty"] = {
        "vulnerability": VULNERABILITY_WEIGHTS["empty"],
        "area_m2": empty_area,
        "risk_contribution": VULNERABILITY_WEIGHTS["empty"] * empty_area,
    }

    weighted_area_sum = sum(b["risk_contribution"] for b in breakdown.values())
    F1_value = weighted_cycles * INCIDENT_PROBABILITY_PER_CYCLE * weighted_area_sum

    return {
        "F1": F1_value,
        "weighted_area_sum": weighted_area_sum,
        "raw_cycles": raw_cycles,
        "weighted_cycles": weighted_cycles,
        "breakdown": breakdown,
    }


# =============================================================================
# F2: 양중 사이클 타임
# =============================================================================

def _angle_diff_rad(p1: Tuple[float, float], p2: Tuple[float, float],
                     center: Tuple[float, float]) -> float:
    """두 점이 중심에서 이루는 각도 차 (radian)."""
    a1 = math.atan2(p1[1] - center[1], p1[0] - center[0])
    a2 = math.atan2(p2[1] - center[1], p2[0] - center[0])
    d = abs(a1 - a2)
    return min(d, 2*math.pi - d)


def _radial_change(p1: Tuple[float, float], p2: Tuple[float, float],
                    center: Tuple[float, float]) -> float:
    """두 점의 반경 차이 (m)."""
    r1 = math.hypot(p1[0] - center[0], p1[1] - center[1])
    r2 = math.hypot(p2[0] - center[0], p2[1] - center[1])
    return abs(r2 - r1)


def compute_single_cycle_time(crane_xy: Tuple[float, float],
                                lift_point: Tuple[float, float],
                                model_id: str,
                                material: str = "gangform") -> Dict:
    """
    야적장 → 양중점 → 야적장 한 사이클의 총 시간 (초).
    자재 종류에 따라 결박·해제 시간, 호이스트 속도 영향 받음.
    """
    spec = CRANES[model_id]
    yard = MATERIAL_YARD

    # 각도·반경 변화 (크레인 기준)
    delta_theta_rad = _angle_diff_rad(yard, lift_point, crane_xy)
    delta_r = _radial_change(yard, lift_point, crane_xy)

    # 자재 중량에 따른 호이스트 속도 보정
    # 무거우면 full speed, 가벼우면 max speed
    material_weight = MATERIAL_WEIGHTS.get(material, 3000)
    weight_ratio = material_weight / spec["max_load_kgf"]
    # 보정 속도: weight_ratio가 1에 가까우면 full speed, 0에 가까우면 max speed
    v_hoist_loaded = (spec["hoist_speed_at_full_mpm"] +
                      (spec["hoist_speed_max_mpm"] - spec["hoist_speed_at_full_mpm"])
                      * (1 - weight_ratio)) / 60  # m/s
    v_hoist_empty = spec["hoist_speed_max_mpm"] / 60       # m/s

    # 선회·반경 속도
    omega_slew = spec["slewing_speed_rpm"] * 2 * math.pi / 60  # rad/s
    if spec["type"] == "hammerhead":
        v_radial = spec["trolley_speed_mpm"] / 60
    else:
        v_radial = spec.get("luffing_speed_mpm", 40) / 60

    # 자재별 결박·해제 시간
    handling = MATERIAL_HANDLING_TIME.get(material,
                                            {"attach": 30, "release": 20})
    t_attach = handling["attach"]
    t_release = handling["release"]

    # 호이스트 + 수평 이동
    t_hoist_up_loaded = HOOK_OPERATING_HEIGHT_M / v_hoist_loaded
    t_hoist_down_loaded = (HOOK_OPERATING_HEIGHT_M - LIFT_POINT_DELIVERY_HEIGHT_M) / v_hoist_loaded
    t_hoist_up_empty = (HOOK_OPERATING_HEIGHT_M - LIFT_POINT_DELIVERY_HEIGHT_M) / v_hoist_empty
    t_hoist_down_empty = HOOK_OPERATING_HEIGHT_M / v_hoist_empty

    t_slew = delta_theta_rad / omega_slew if omega_slew > 0 else 0
    t_radial = delta_r / v_radial if v_radial > 0 else 0
    t_horizontal_loaded = max(t_slew, t_radial)
    t_horizontal_empty = t_horizontal_loaded * 0.75

    t_one_cycle = (
        t_attach +
        t_hoist_up_loaded +
        t_horizontal_loaded +
        t_hoist_down_loaded +
        t_release +
        t_hoist_up_empty +
        t_horizontal_empty +
        t_hoist_down_empty
    )

    return {
        "total_sec": t_one_cycle,
        "material": material,
        "delta_theta_deg": math.degrees(delta_theta_rad),
        "delta_r_m": delta_r,
    }


def compute_F2(crane_xy: Tuple[float, float], model_id: str) -> Dict:
    """
    F2: 모든 양중점 × 자재에 대한 총 사이클 타임 (초).

    수식:
        F2_nominal = Σ_(point, material) N(point, material) × T_cycle(point, material)
        F2_calendar = F2_nominal / UTILIZATION_FACTOR

    자재별·위치별 cycle 수를 LIFT_POINT_MATERIAL_PROFILE 에서 가져와 합산.
    """
    total_time = 0.0
    per_point = {}
    per_material = {m: 0.0 for m in MATERIAL_WEIGHTS}

    for idx, profile in LIFT_POINT_MATERIAL_PROFILE.items():
        p = BUILDING_GRID_POINTS[idx]
        point_contribution = 0.0
        point_cycles = 0
        for material, n in profile.items():
            if n == 0:
                continue
            cycle_info = compute_single_cycle_time(crane_xy, p, model_id, material)
            contribution = n * cycle_info["total_sec"]
            point_contribution += contribution
            point_cycles += n
            per_material[material] += contribution
        total_time += point_contribution
        per_point[f"P{idx+1}"] = {
            "cycles": point_cycles,
            "total_sec": point_contribution,
            "position": p,
        }

    # 가동률 적용
    calendar_time = total_time / UTILIZATION_FACTOR

    return {
        "F2_sec": total_time,
        "F2_hours": total_time / 3600,
        "F2_days_at_8h": total_time / 3600 / 8,
        "F2_calendar_sec": calendar_time,
        "F2_calendar_hours": calendar_time / 3600,
        "F2_calendar_days_at_8h": calendar_time / 3600 / 8,
        "utilization_factor": UTILIZATION_FACTOR,
        "per_point": per_point,
        "per_material_hours": {m: t/3600 for m, t in per_material.items()},
    }


# =============================================================================
# 통합 평가
# =============================================================================

def evaluate_objectives(crane_xy: Tuple[float, float],
                          model_id: str,
                          jib_length_m: float) -> Dict:
    """주어진 배치에 대한 F1·F2 동시 계산."""
    f1 = compute_F1(crane_xy, model_id, jib_length_m)
    f2 = compute_F2(crane_xy, model_id)
    return {"F1": f1, "F2": f2}


# =============================================================================
# 자체 테스트
# =============================================================================

if __name__ == "__main__":
    print("=" * 78)
    print("F1 / F2 목적함수 자체 테스트")
    print("=" * 78)

    test_cases = [
        ("부지 중앙 + MR 160C + 짧은 지브",   (0, 0),    "Potain_MR_160C",    25),
        ("부지 중앙 + MR 160C + 긴 지브",     (0, 0),    "Potain_MR_160C",    50),
        ("부지 동남 + MR 160C",               (8, -5),   "Potain_MR_160C",    25),
        ("부지 북서 + MR 160C",               (-8, 5),   "Potain_MR_160C",    25),
        ("부지 중앙 + MDT 178 (T형)",         (0, 0),    "Potain_MDT_178",    25),
        ("부지 중앙 + 280 HC-L (대형)",       (0, 0),    "Liebherr_280_HC_L", 25),
    ]

    print(f"\n{'케이스':<40} {'F1':>10} {'F2(hours)':>12} {'F2(days@8h)':>12}")
    print("-" * 78)
    for name, xy, mid, jib in test_cases:
        r = evaluate_objectives(xy, mid, jib)
        F1 = r["F1"]["F1"]
        F2_h = r["F2"]["F2_hours"]
        F2_d = r["F2"]["F2_days_at_8h"]
        print(f"{name:<40} {F1:>10.3f} {F2_h:>12.1f} {F2_d:>12.1f}")

    # 상세 breakdown 한 케이스
    print("\n" + "=" * 78)
    print("상세 분석 — 부지 중앙 + MR 160C + 25m 지브")
    print("=" * 78)
    r = evaluate_objectives((0, 0), "Potain_MR_160C", 25)

    print("\n[F1 영역별 기여도]")
    for zone, b in r["F1"]["breakdown"].items():
        print(f"  {zone:<25} V={b['vulnerability']:>4.1f}  "
              f"Area={b['area_m2']:>7.1f}m²  "
              f"Risk={b['risk_contribution']:>8.2f}")
    print(f"  {'─'*60}")
    print(f"  Weighted area sum: {r['F1']['weighted_area_sum']:.2f}")
    print(f"  Total cycles: {r['F1']['total_cycles']}")
    print(f"  F1 = {r['F1']['F1']:.4f}")

    print("\n[F2 양중점별 기여도]")
    for pid, p in r["F2"]["per_point"].items():
        print(f"  {pid}: {p['cycles']}cycles × {p['single_cycle_sec']:.1f}s "
              f"= {p['total_sec']/3600:.1f}h")
    print(f"  {'─'*60}")
    print(f"  F2 = {r['F2']['F2_hours']:.1f}h = {r['F2']['F2_days_at_8h']:.1f} working days @8h/day")
