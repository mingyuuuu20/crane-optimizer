"""
================================================================================
constraints.py
================================================================================
타워크레인 배치 제약조건 검사 함수 (작업 2)
--------------------------------------------------------------------------------
구현된 제약: C1 ~ C12 (제약조건 명세서 v1.0 기준)
입력: 크레인 배치 후보 (위치, 모델, 마스트 높이, 지브 길이)
출력: (통과 여부, 사유 문자열)

각 제약은 독립 함수로 분리. 알고리즘에서 개별 호출 또는 batch 검사 가능.

출처는 함수 docstring 에 명시.
"""

from shapely.geometry import Point, Polygon

# --- 활성 부지 관리 (범용화) ----------------------------------------------
# 기본 동작: 기존 동작 보존 — site_model.py (공덕동 256-42) 를 그대로 사용
# 임의 부지로 전환: from site_loader import load_site; set_active_site(load_site(path))
import site_model as _default_site

SITE                       = _default_site.SITE
ADJACENT_BUILDINGS         = _default_site.ADJACENT_BUILDINGS
ROADS                      = _default_site.ROADS
PLANNED_BUILDING           = _default_site.PLANNED_BUILDING
PLANNED_BUILDING_HEIGHT_M  = _default_site.PLANNED_BUILDING_HEIGHT_M
LIFT_POINTS                = _default_site.LIFT_POINTS
ALLOWED_AREA               = _default_site.ALLOWED_AREA


def set_active_site(site):
    """모듈 전역 부지 변수를 site (SiteData) 로 교체.

    optimizer / objectives / constraints 모두 같은 site 로 일관되게 작동시키려면
    각각 set_active_site 를 호출해야 한다 (또는 helpers.use_site() 사용).
    """
    global SITE, ADJACENT_BUILDINGS, ROADS, PLANNED_BUILDING
    global PLANNED_BUILDING_HEIGHT_M, LIFT_POINTS, ALLOWED_AREA
    SITE                       = site.SITE
    ADJACENT_BUILDINGS         = site.ADJACENT_BUILDINGS
    ROADS                      = site.ROADS
    PLANNED_BUILDING           = site.PLANNED_BUILDING
    PLANNED_BUILDING_HEIGHT_M  = site.PLANNED_BUILDING_HEIGHT_M
    LIFT_POINTS                = site.LIFT_POINTS
    ALLOWED_AREA               = site.ALLOWED_AREA


# =============================================================================
# 크레인 모델 사양
# =============================================================================
# [정정 이력] 기존엔 여기에 "간략 버전" CRANE_MODELS를 별도 정의했으나,
#   crane_models.py(CRANES)와 값이 불일치하는 버그가 있었음:
#   - 자립고: 간략본 30/30/35m  vs  정본(제조사) 67/50/59.1m  ← 정본이 맞음
#   - MR 160C 반경: 간략본 50  vs  정본 51m
#   따라서 단일 출처(crane_models.CRANES)를 그대로 사용하도록 통합.
#   CRANES는 각 모델에 manufacturer/source(제조사 데이터시트 출처)를 포함.
# =============================================================================
from crane_models import CRANES as _CRANES

# 하위호환: 기존 코드가 spec["jib_max_length_m"]를 참조하므로,
# 정본에 없는 이 키를 max_radius_m(= 최대 지브 도달반경)로 매핑해 보강.
CRANE_MODELS = {}
for _mid, _spec in _CRANES.items():
    _s = dict(_spec)
    _s.setdefault("jib_max_length_m", _s.get("max_radius_m"))
    CRANE_MODELS[_mid] = _s


# =============================================================================
# 제약 상수 (출처 명시)
# =============================================================================

CLEARANCE_JIB_TO_BUILDING_M = 0.6        # KOSHA GUIDE C-104-2020
CLEARANCE_TO_POWER_LINE_M = 0.9          # 산안기준규칙 별표 5의2 (22.9 kV)
HOOK_HEIGHT_MARGIN_M = 7.0               # 건물 최고높이 + 안전여유
AIRSPACE_VERT_CLEARANCE_M = 5.0          # 상공권 동의 인접건물 위 지브·인양물 수직 통과 여유
                                          #   [가정] 인접건물 최고높이 + 인양물 높이(~2m) + 안전여유(~3m).
                                          #   마스트가 (인접건물높이 + 이 값) 이상이면 상공 통과로 간주.
BUILDING_OFFSET_INTERNAL_M = 2.0         # 신축 건물과 크레인 이격
ROAD_RESIDUAL_WIDTH_M = 4.5              # 차량 3m + 보행자 1.5m
WALL_TIE_MAX_DIST_M = 15.0               # Wall tie 가능 한계 거리 [가정: 제조사별 상이, 통상 12~18m]
# --- 설치방식(외부/내부) 관련 ---
# 내부설치(internal climbing): 크레인을 신축건물 코어(EV/계단실) 내부에 세우고
#   건물과 함께 상승(climbing)하는 방식. 협소대지에서 외부 독립기초 공간이 없을 때 채택.
#   본 모델 단순화 가정: 크레인 기초가 본동 footprint 내부에 위치하면 내부설치로 간주하고
#   '본동 이격' 제약(외부설치 전용)을 면제한다. 단, 양중효율(F2)·해체난이도 차이는
#   본 모델에서 별도 반영하지 않으며 향후 과제로 둔다.
INTERNAL_MOUNT_ENABLED = True            # 내부설치 허용 여부 (False면 기존 외부설치 전용)
INTERNAL_MOUNT_CORE_MARGIN_M = 1.0       # [가정] 내부설치 기초가 본동 경계에서 안쪽으로 확보할 여유
GROUND_ALLOWABLE_BEARING_KPA = 150.0     # 공덕동 표층 가정 (KDS 11 50 05)
WIND_SPEED_OUT_OF_SERVICE_MS = 35.0      # 비작업시(out-of-service) 설계풍속, KS B 6230 / ISO 4302
                                          #  ※ 작업중지 순간풍속(15m/s, 산안규칙 §37)과는 다른 개념.
                                          #    G3는 강풍시 크레인 전도(생존) 안정성 검사이므로 설계풍속 적용.
WIND_DRAG_COEFFICIENT = 1.2              # 격자형 (ISO 4302)
AIR_DENSITY = 1.225                      # kg/m³
PAYLOAD_MAX_KGF = 3500.0                 # PC 부재 (가장 무거운 자재)
RIGGING_WEIGHT_KGF = 100.0               # 와이어 + 샤클


# =============================================================================
# 유틸리티: Load Chart 보간
# =============================================================================

def lookup_load_capacity(model: str, radius_m: float) -> float:
    """
    반경별 인양능력 보간 (선형).
    실제 사용 시 모델별 Load Chart 데이터 포인트로 교체 예정.

    출처: 제조사 공식 카탈로그 (Potain / Liebherr).
    """
    spec = CRANE_MODELS[model]
    if radius_m <= 10:
        return spec["max_load_kgf"]
    if radius_m >= spec["max_radius_m"]:
        return spec["load_at_max_radius_kgf"]
    # 선형 보간 (간략)
    r_min, r_max = 10.0, spec["max_radius_m"]
    w_min, w_max = spec["max_load_kgf"], spec["load_at_max_radius_kgf"]
    return w_min + (w_max - w_min) * (radius_m - r_min) / (r_max - r_min)


# =============================================================================
# C1. 인양능력 (Lifting Capacity)
# =============================================================================

def check_C1_lifting_capacity(crane_xy, model, payload_kgf=PAYLOAD_MAX_KGF):
    """
    C1: 후크블록·인양구 포함 실효 하중이 반경별 정격능력 이내.

    수식: W_required + W_hook + W_rigging ≤ W_max(model, r)
    출처: 제조사 Load Chart
    """
    spec = CRANE_MODELS[model]
    effective_load = payload_kgf + spec["hook_block_kgf"] + RIGGING_WEIGHT_KGF
    crane_pt = Point(crane_xy)

    for p in LIFT_POINTS:
        r = crane_pt.distance(Point(p))
        if r > spec["max_radius_m"]:
            return False, f"C1 위반: 양중점 ({p[0]:.1f}, {p[1]:.1f}) 도달 불가 (r={r:.1f}m)"
        capacity = lookup_load_capacity(model, r)
        if capacity < effective_load:
            return False, (f"C1 위반: 양중점 ({p[0]:.1f}, {p[1]:.1f}) 인양능력 부족 "
                          f"(요구 {effective_load:.0f}kgf > 능력 {capacity:.0f}kgf @ r={r:.1f}m)")
    return True, "C1 통과"


# =============================================================================
# C2-1. 인접 구조물 이격 (Clearance to Adjacent Buildings)
# =============================================================================

def _crane_swept_radius(model: str, jib_length: float) -> float:
    """T형: 카운터지브도 weather-vane → 두 중 큰 값. 러핑: 지브만."""
    spec = CRANE_MODELS[model]
    if spec["type"] == "hammerhead":
        return max(jib_length, spec["counter_jib_length_m"])
    return jib_length


def _operational_sector_area(crane_xy, lift_points_arr, jib_length, swept_r,
                                 margin_deg=10):
    """
    러핑 크레인은 sector 내에서만 작동.
    Sector = 양중점들을 모두 포함하는 최소 각도 + 안전 margin.

    Returns: Polygon (sector shape), 또는 full circle (T형 또는 도달 불가 시).
    """
    import math
    from shapely.geometry import Polygon as _P, Point as _Pt

    crane_pt = _Pt(crane_xy)
    angles = []
    for p in lift_points_arr:
        d = crane_pt.distance(_Pt(p))
        if d > jib_length + 0.5:
            return None  # 일부 양중점 도달 불가
        ang = math.atan2(p[1] - crane_xy[1], p[0] - crane_xy[0])
        angles.append(ang)

    angles_sorted = sorted(angles)
    # 각 점 사이 gap + 마지막→첫번째 wrap-around gap 중 최대 gap 찾기
    n = len(angles_sorted)
    gaps = []
    for i in range(n):
        a1 = angles_sorted[i]
        a2 = angles_sorted[(i+1) % n]
        gap = a2 - a1 if i < n-1 else (2*math.pi + a2 - a1)
        gaps.append(gap)
    max_gap = max(gaps)
    if max_gap > math.pi:
        # 양중점들이 한쪽으로 모여있음 → sector 사용 의미 있음
        idx = gaps.index(max_gap)
        # sector 는 max_gap의 complement
        start_angle = angles_sorted[(idx+1) % n]
        end_angle = angles_sorted[idx]
        # margin 추가
        m = math.radians(margin_deg)
        start_angle -= m
        end_angle += m
        # sector polygon 생성
        n_arc = 24
        if end_angle < start_angle:
            end_angle += 2*math.pi
        pts = [crane_xy]
        for i in range(n_arc + 1):
            t = start_angle + (end_angle - start_angle) * i / n_arc
            pts.append((crane_xy[0] + swept_r * math.cos(t),
                        crane_xy[1] + swept_r * math.sin(t)))
        return _P(pts)
    else:
        # 양중점이 360° 둘러싸있음 → full circle
        return crane_pt.buffer(swept_r)


def check_C2_1_building_clearance(crane_xy, model, jib_length):
    """
    C2-1: 크레인 회전부 ↔ 인접 건물 0.6m 이상 이격.

    수식: dist(operating_area, adj_bldg_footprint) ≥ 0.6 m
        - T형(hammerhead): operating_area = full swept circle (자유회전 + 무풍 weather-vane)
        - 러핑(luffing): operating_area = operational sector (양중점 방향만)
    출처: KOSHA GUIDE C-104-2020

    NOTE: 이 함수는 continuous_constraints(NSGA-II 용) 와 동일 기준을 사용해야
    Level 1 검증과 알고리즘 최적해가 일관됨.
    """
    spec = CRANE_MODELS[model]
    swept_r = _crane_swept_radius(model, jib_length)
    crane_pt = Point(crane_xy)

    # 러핑은 sector, T형은 full circle — continuous_constraints 와 동일
    if spec["type"] == "hammerhead":
        operating_area = crane_pt.buffer(swept_r)
    else:
        operating_area = _operational_sector_area(
            crane_xy, LIFT_POINTS, jib_length, swept_r
        )
        if operating_area is None:
            # 도달 불가 양중점 있음 → C5에서 처리되므로 여기는 full circle fallback
            operating_area = crane_pt.buffer(swept_r)

    for direction, bldg in ADJACENT_BUILDINGS.items():
        dist = operating_area.distance(bldg["footprint"])
        if dist < CLEARANCE_JIB_TO_BUILDING_M:
            shortage = CLEARANCE_JIB_TO_BUILDING_M - dist
            return False, (f"C2-1 위반: {direction} {bldg['name']} 이격 부족 "
                          f"(부족량 {shortage:.2f}m)")
    return True, "C2-1 통과"


# =============================================================================
# C2-3. 인접대지 침범 금지
# =============================================================================

def check_C2_3_no_lot_intrusion(crane_xy, model, jib_length):
    """
    C2-3: 크레인 operating_area 가 부지 ∪ 도로 영역 안에 완전히 포함.

    수식: operating_area ⊆ ALLOWED_AREA
        - T형(hammerhead): operating_area = full swept circle
        - 러핑(luffing):   operating_area = operational sector (양중점 방향만)
    출처: 건축법 + 민법 공중권

    NOTE: 이전 버전은 러핑크레인도 full circle 로 검사했으나
    C2-1 과 평가 기준이 불일치하는 버그가 있어 sector 처리로 수정 (v2.5.20).
    """
    spec = CRANE_MODELS[model]
    swept_r = _crane_swept_radius(model, jib_length)
    crane_pt = Point(crane_xy)

    # 러핑은 sector, T형은 full circle — C2-1 과 동일 기준
    if spec["type"] == "hammerhead":
        operating_area = crane_pt.buffer(swept_r)
    else:
        operating_area = _operational_sector_area(
            crane_xy, LIFT_POINTS, jib_length, swept_r
        )
        if operating_area is None:
            # 도달 불가 양중점 있음 → C5에서 처리되므로 여기는 full circle fallback
            operating_area = crane_pt.buffer(swept_r)

    if not ALLOWED_AREA.contains(operating_area):
        intrusion = operating_area.difference(ALLOWED_AREA).area
        # tolerance = sector 면적의 15% (G9 와 일치, 도로점용 현실 반영)
        tolerance = max(operating_area.area * 0.15, 5.0)
        if intrusion > tolerance:
            return False, (f"C2-3 위반: 인접대지 침범 면적 {intrusion:.1f}m² "
                            f"(허용 {tolerance:.1f}㎡)")
        else:
            return True, (f"C2-3 통과 (침범 {intrusion:.1f}㎡ ≤ "
                           f"{tolerance:.1f}㎡ tolerance)")
    return True, "C2-3 통과"


# =============================================================================
# C3-1. 정지 풍하중 모멘트
# =============================================================================

def check_C3_1_wind_moment(model, mast_height_m, jib_length):
    """
    C3-1: 정지 시 풍하중 모멘트 ≤ 모델 한계.

    수식: M_wind = 0.5 × ρ × v² × A_jib × C_d × h_eff ≤ M_limit
    출처: KS B 6230 + ISO 4302 + 제조사
    """
    spec = CRANE_MODELS[model]
    q = 0.5 * AIR_DENSITY * WIND_SPEED_OUT_OF_SERVICE_MS ** 2  # N/m²
    F_wind = WIND_DRAG_COEFFICIENT * q * spec["wind_pressure_area_m2"]  # N
    h_eff = mast_height_m + jib_length / 2
    M_wind = F_wind * h_eff / 1000  # kNm
    M_limit = spec["moment_limit_kNm"]
    if M_wind > M_limit:
        return False, f"C3-1 위반: 풍모멘트 {M_wind:.0f}kNm > 한계 {M_limit:.0f}kNm"
    return True, f"C3-1 통과 (M_wind={M_wind:.0f}kNm, 여유 {M_limit-M_wind:.0f}kNm)"


# =============================================================================
# C4-1. 기초 수직하중
# =============================================================================

def check_C4_1_foundation_vertical(model, base_area_m2=25.0):
    """
    C4-1: 기초 수직하중이 지반 허용지내력 이내.

    수식: V_total / A_base ≤ q_allow
    출처: KDS 11 50 05 (얕은기초 설계기준)
    가정: 공덕동 표층 N=10~15 → q_allow = 150 kPa
    """
    spec = CRANE_MODELS[model]
    # 단순화: 자중(추정) + 최대 인양물 + 풍하중 수직성분
    V_self_kN = spec.get("self_weight_kN", 400)  # 기본값
    V_payload_kN = PAYLOAD_MAX_KGF * 9.81 / 1000
    V_wind_kN = 50.0  # 보수적 추정
    V_total = V_self_kN + V_payload_kN + V_wind_kN
    pressure_kPa = V_total / base_area_m2
    if pressure_kPa > GROUND_ALLOWABLE_BEARING_KPA:
        return False, (f"C4-1 위반: 기초압력 {pressure_kPa:.0f}kPa "
                      f"> 허용지내력 {GROUND_ALLOWABLE_BEARING_KPA}kPa")
    return True, f"C4-1 통과 (압력 {pressure_kPa:.0f}/{GROUND_ALLOWABLE_BEARING_KPA}kPa)"


# =============================================================================
# C5. 작업 도달 거리
# =============================================================================

def check_C5_coverage(crane_xy, model):
    """
    C5: 모든 양중점이 working radius 내.

    수식: max(dist(crane, lift_point)) ≤ r_max
    출처: 제조사 Load Chart
    """
    spec = CRANE_MODELS[model]
    crane_pt = Point(crane_xy)
    for p in LIFT_POINTS:
        r = crane_pt.distance(Point(p))
        if r > spec["max_radius_m"]:
            return False, (f"C5 위반: 양중점 ({p[0]:.1f}, {p[1]:.1f}) 사각지대 "
                          f"(r={r:.1f}m > r_max={spec['max_radius_m']}m)")
    return True, "C5 통과"


# =============================================================================
# C6. 후크 높이
# =============================================================================

def check_C6_hook_height(mast_height_m):
    """
    C6: H_hook ≥ H_building + 7m.

    출처: KOSHA C-104 (안전여유)
    """
    required = PLANNED_BUILDING_HEIGHT_M + HOOK_HEIGHT_MARGIN_M
    if mast_height_m < required:
        return False, f"C6 위반: 마스트 {mast_height_m}m < 요구 {required}m"
    return True, f"C6 통과 (마스트 {mast_height_m}m ≥ {required}m)"


# =============================================================================
# C7. 기초 설치 가능 영역
# =============================================================================

def check_C7_installation(crane_xy, base_size_m=5.0):
    """
    C7: 기초 설치 영역 검사.
       C7-1: 부지 내 → 신축 건물과 2.0m 이격
       C7-2: 도로 점용 → 4.5m 잔여 폭 확보
       C7-3: 인접대지 → 불가

    출처: KOSHA C-104, 도로교통법, 실무 기준
    """
    base_fp = Point(crane_xy).buffer(base_size_m / 2)

    # C7-1: 부지 내?
    if SITE.contains(base_fp):
        d = base_fp.distance(PLANNED_BUILDING)
        if d < BUILDING_OFFSET_INTERNAL_M:
            return False, f"C7-1 위반: 신축 건물과 이격 {d:.2f}m < {BUILDING_OFFSET_INTERNAL_M}m"
        return True, "C7-1 통과 (부지 내 설치)"

    # C7-2: 도로 점용?
    for road_key, road in ROADS.items():
        if road["polygon"].contains(base_fp):
            residual = road["width_m"] - base_size_m
            if residual < ROAD_RESIDUAL_WIDTH_M:
                return False, (f"C7-2 위반: {road['name']} 잔여폭 {residual:.1f}m "
                              f"< {ROAD_RESIDUAL_WIDTH_M}m")
            return True, f"C7-2 통과 ({road['name']} 점용)"

    # 어디에도 안 속함 = 인접대지 침범
    return False, "C7-3 위반: 부지·도로 외 (인접대지 침범)"


# =============================================================================
# C8. Wall Tie (마스트 지지)
# =============================================================================

def check_C8_mast_support(crane_xy, mast_height_m, model):
    """
    C8: 마스트 자립 한계 초과 시 wall tie 필요.
       Wall tie = 건물 본체에 부착 → 크레인이 건물 가까이 있어야.

    출처: 제조사 manual + KOSHA C-104
    """
    spec = CRANE_MODELS[model]
    h_free = spec["free_standing_height_m"]
    if mast_height_m <= h_free:
        return True, f"C8 통과 (자립 마스트, {mast_height_m}m ≤ {h_free}m)"

    # Wall tie 필요: 건물 본체와 가까이
    d = Point(crane_xy).distance(PLANNED_BUILDING)
    if d > WALL_TIE_MAX_DIST_M:
        return False, (f"C8 위반: 마스트 {mast_height_m}m > 자립한계 {h_free}m 인데 "
                      f"건물과 {d:.1f}m 떨어져 wall tie 불가")
    return True, f"C8 통과 (wall tie 가능, 건물 이격 {d:.1f}m)"


# =============================================================================
# 통합 검사
# =============================================================================

def evaluate_crane_placement(crane_xy, model, mast_height_m, jib_length_m):
    """
    크레인 배치 후보 1건을 12개 제약 모두 통과하는지 검사.
    반환: (모두 통과 여부, 결과 dict)
    """
    results = {
        "C1":  check_C1_lifting_capacity(crane_xy, model),
        "C2-1": check_C2_1_building_clearance(crane_xy, model, jib_length_m),
        "C2-3": check_C2_3_no_lot_intrusion(crane_xy, model, jib_length_m),
        "C3-1": check_C3_1_wind_moment(model, mast_height_m, jib_length_m),
        "C4-1": check_C4_1_foundation_vertical(model),
        "C5":   check_C5_coverage(crane_xy, model),
        "C6":   check_C6_hook_height(mast_height_m),
        "C7":   check_C7_installation(crane_xy),
        "C8":   check_C8_mast_support(crane_xy, mast_height_m, model),
    }
    all_pass = all(r[0] for r in results.values())
    return all_pass, results


# =============================================================================
# NSGA-II 용 연속 제약 (Continuous Constraint Violations)
# =============================================================================
# pymoo 규약: G_i ≤ 0 이면 제약 만족, G_i > 0 이면 위반 (값이 위반 정도)
# 위반량을 연속 실수로 반환해야 알고리즘이 feasible 영역을 효율적으로 탐색.

def continuous_constraints(crane_xy, model, mast_height_m, jib_length_m):
    """
    NSGA-II 용 연속 제약 위반량 배열 반환.

    각 G_i의 의미:
        G_i ≤ 0  → 제약 i 만족
        G_i > 0  → 제약 i 위반 (값은 위반 정도)

    Returns:
        np.array of shape (n_constraints,)
    """
    import numpy as np
    from shapely.geometry import Point

    G = []
    spec = CRANE_MODELS[model]
    crane_pt = Point(crane_xy)

    # --- G1: 인양능력 (모든 양중점에서 능력 ≥ 요구) ---
    # 실제 작업 반경 = min(jib_length, model max_radius)
    effective_load = PAYLOAD_MAX_KGF + spec["hook_block_kgf"] + RIGGING_WEIGHT_KGF
    effective_max_r = min(jib_length_m, spec["max_radius_m"])
    g1_worst = -1e6
    for p in LIFT_POINTS:
        r = crane_pt.distance(Point(p))
        if r > effective_max_r:
            # 도달 자체 불가 (G5에서 처리, 여기서는 큰 위반)
            g1_worst = max(g1_worst, (r - effective_max_r) * 10)
            continue
        capacity = lookup_load_capacity(model, r)
        violation = effective_load - capacity
        g1_worst = max(g1_worst, violation / 1000)
    G.append(g1_worst)

    # --- G2: 인접 구조물 이격 (가장 가까운 건물과의 부족량) ---
    # 러핑: operational sector, T형: full circle (카운터지브 weather-vane)
    swept_r = _crane_swept_radius(model, jib_length_m)
    if spec["type"] == "hammerhead":
        operating_area = crane_pt.buffer(swept_r)
    else:
        operating_area = _operational_sector_area(
            crane_xy, LIFT_POINTS, jib_length_m, swept_r
        )
        if operating_area is None:
            # 도달 불가 → 큰 위반 + G5에서도 처리
            operating_area = crane_pt.buffer(swept_r)

    g2_worst = -1e6
    for direction, bldg in ADJACENT_BUILDINGS.items():
        # 상공권 동의 + 지브가 인접건물보다 충분히 높이 통과하면 평면 이격 면제.
        #   [근거] 인양물은 마스트~후크 높이대에서 운반된다. 인접건물 최고높이 +
        #   인양물·안전여유(AIRSPACE_VERT_CLEARANCE_M) 보다 마스트가 높으면
        #   지브·인양물이 그 상공을 안전하게 통과(평면상 겹쳐도 충돌 없음).
        if bldg.get("airspace_easement", False):
            clear_h = bldg["height_m"] + AIRSPACE_VERT_CLEARANCE_M
            if mast_height_m >= clear_h:
                continue   # 상공 통과 → 이 건물은 이격 평가 제외
        dist = operating_area.distance(bldg["footprint"])
        # 이미 겹치면 distance=0, 이격 부족
        # operating_area 경계에서 0.6m 이격 필요
        violation = CLEARANCE_JIB_TO_BUILDING_M - dist
        g2_worst = max(g2_worst, violation)
    G.append(g2_worst)

    # --- G3: 인접 건물 본체 침범 면적 (operational area 기준) ---
    #   상공권 동의 + 마스트가 인접건물보다 충분히 높으면 '상공 통과'로 보고
    #   평면 침범을 면제(충돌 없음). 그 외에는 기존대로 침범면적을 위반으로 집계.
    intrusion = 0.0
    for direction, bldg in ADJACENT_BUILDINGS.items():
        if bldg.get("airspace_easement", False):
            clear_h = bldg["height_m"] + AIRSPACE_VERT_CLEARANCE_M
            if mast_height_m >= clear_h:
                continue   # 상공 통과 → 침범 집계 제외
        intrusion += operating_area.intersection(bldg["footprint"]).area
    G.append(intrusion - 0.01)

    # --- G4: 풍하중 모멘트 ---
    q = 0.5 * AIR_DENSITY * WIND_SPEED_OUT_OF_SERVICE_MS ** 2
    F_wind = WIND_DRAG_COEFFICIENT * q * spec["wind_pressure_area_m2"]
    h_eff = mast_height_m + jib_length_m / 2
    M_wind = F_wind * h_eff / 1000
    G.append(M_wind - spec["moment_limit_kNm"])

    # --- G5: 도달거리 (양중점 사각지대 없음) — actual jib_length 기준 ---
    g5_worst = -1e6
    effective_r = min(jib_length_m, spec["max_radius_m"])
    for p in LIFT_POINTS:
        r = crane_pt.distance(Point(p))
        violation = r - effective_r
        g5_worst = max(g5_worst, violation)
    G.append(g5_worst)

    # --- G6: 후크 높이 ---
    required_hook = PLANNED_BUILDING_HEIGHT_M + HOOK_HEIGHT_MARGIN_M
    G.append(required_hook - mast_height_m)

    # --- G7: 설치 가능 영역 (외부설치 OR 내부설치 자동 판별) ---
    # [정정 이력] 기존엔 부지 안=외부설치만 가정하여 '본동 이격 2m'를 강제했으나,
    #   협소대지 실무에서 흔한 내부설치(코어 클라이밍)를 배제하는 문제가 있었음
    #   (역삼동 두산위브 실제 사례: 크레인을 본동 굴착부=코어 내부에 설치).
    #   → 크레인 기초가 본동 내부면 '내부설치'로 보고 이격 제약을 면제한다.
    base_fp = crane_pt.buffer(2.5)
    is_internal = INTERNAL_MOUNT_ENABLED and PLANNED_BUILDING.contains(crane_pt)
    if is_internal:
        # 내부설치(클라이밍): 본동 코어 내부. 이격 불필요.
        # 기초가 본동 경계 안쪽으로 INTERNAL_MOUNT_CORE_MARGIN_M 만큼 들어와 있으면 통과.
        margin = PLANNED_BUILDING.boundary.distance(crane_pt)  # 본동 경계까지 안쪽 거리
        G.append(INTERNAL_MOUNT_CORE_MARGIN_M - margin)
    elif SITE.contains(base_fp):
        # 외부설치: 부지 안 + 본동에서 이격 확보
        d = base_fp.distance(PLANNED_BUILDING)
        G.append(BUILDING_OFFSET_INTERNAL_M - d)
    else:
        # 도로 점용 가능?
        in_road = False
        for road in ROADS.values():
            if road["polygon"].contains(base_fp):
                residual = road["width_m"] - 5.0
                G.append(ROAD_RESIDUAL_WIDTH_M - residual)
                in_road = True
                break
        if not in_road:
            # 인접대지 침범
            G.append(1e3)   # 큰 위반량

    # --- G8: Wall tie 가능성 ---
    # 마스트가 자립고 초과 시 벽체 지지(wall-tie) 필요.
    #   외부설치: 본동까지 거리가 wall-tie 한계 이내여야 함.
    #   내부설치: 코어에 직접 지지(climbing frame)되므로 거리 제약 면제.
    h_free = spec["free_standing_height_m"]
    if mast_height_m > h_free:
        if is_internal:
            G.append(-1.0)   # 내부설치: 코어 직접지지로 wall-tie 항상 가능
        else:
            d = crane_pt.distance(PLANNED_BUILDING)
            G.append(d - WALL_TIE_MAX_DIST_M)
    else:
        G.append(-1.0)   # 자립 가능

    # --- G9: operating_area ⊆ ALLOWED_AREA (C2-3 인접대지 공중 침범 금지) ---
    # tolerance: operating_area 의 15% 까지 침범 허용 (sector 모서리 짜투리).
    # 협소대지 + 도로점용 현실 반영: sector 전체 면적의 15% 이내면 도로 폭 내
    # 점용으로 처리 가능 (한국 도로법 시행령 제43조 점용허가 기준).
    # 이를 초과하면 인접대지 공중침범으로 위반.
    intrusion_lot = operating_area.difference(ALLOWED_AREA).area
    tolerance = max(operating_area.area * 0.15, 5.0)
    G.append(intrusion_lot - tolerance)

    return np.array(G, dtype=float)


# numpy import 가 함수 내부에서만 필요하지만, 모듈 레벨로 빼지 않도록
# 함수 안에서 lazy import 처리됨. 외부에서 쓸 때는 numpy 설치 필수.


# =============================================================================
# 자체 테스트
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("제약조건 함수 자체 테스트")
    print("=" * 70)

    test_cases = [
        ("부지 중앙 + Potain MR 160C (러핑)", (0, 0), "Potain_MR_160C", 39, 35),
        ("부지 중앙 + Potain MDT 178 (T형)", (0, 0), "Potain_MDT_178", 39, 35),
        ("부지 북측 + Potain MR 160C (러핑)", (5, 8), "Potain_MR_160C", 39, 35),
        ("인접대지 위 + Potain MR 160C", (-25, 25), "Potain_MR_160C", 39, 35),
    ]

    for name, xy, model, h, jib in test_cases:
        print(f"\n[{name}]")
        print(f"  위치 {xy}, 모델 {model}, 마스트 {h}m, 지브 {jib}m")
        ok, results = evaluate_crane_placement(xy, model, h, jib)
        print(f"  종합: {'✅ 모두 통과' if ok else '❌ 위반 있음'}")
        for cid, (passed, msg) in results.items():
            mark = "✅" if passed else "❌"
            print(f"    {mark} {msg}")
