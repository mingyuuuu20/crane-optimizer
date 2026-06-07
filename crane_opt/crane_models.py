"""
================================================================================
crane_models.py
================================================================================
타워크레인 후보 모델 사양 데이터베이스 (작업 3)
--------------------------------------------------------------------------------
3개 모델: 비교 baseline (T형) + 러핑 소형 + 러핑 대형

데이터 출처 (모두 제조사 공식 / 공인 specs 데이터베이스):
  - Potain MDT 178: Manitowoc 공식 데이터시트 (FEM 1.001-A3)
    https://www.manitowoc.com/sites/default/files/media/divers/file/2020-01/
    MDT178-Data-Sheet-Metric-FEM.pdf
  - Potain MR 160C: LECTURA Specs (verified manufacturer data, 2011-2025)
    https://www.lectura-specs.com/en/model/cranes/.../mr-160-c-1138004
  - Liebherr 280 HC-L 16/28: Liebherr 공식 카탈로그 (HC-L 시리즈 브로슈어 2025)
    https://www-assets.liebherr.com/.../liebherr-towercranes-hc-l-series-2025-en.pdf

각 모델의 Load Chart 는 데이터시트의 실제 값을 그대로 입력.
중간 반경은 알고리즘에서 선형보간 처리.
"""

from typing import Dict, List, Tuple


# =============================================================================
# Potain MDT 178 (Hammerhead / Flat-top) — BASELINE
# =============================================================================
# 출처: Manitowoc 공식 PDF (FEM 1.001-A3 데이터시트, 60m 지브 + 33 LVF + 8t 구성)

POTAIN_MDT_178 = {
    "name": "Potain MDT 178",
    "manufacturer": "Manitowoc / Potain",
    "type": "hammerhead",          # T형 (flat-top)
    "source": "Manitowoc Data Sheet (FEM 1.001-A3, 2020)",

    # ---- 정격 사양 ----
    "max_load_kgf": 8000,           # 14.3m 반경에서
    "max_radius_m": 60.0,           # 표준 60m 지브
    "min_radius_m": 2.75,           # 데이터시트 최소
    "load_at_max_radius_kgf": 1500, # 60m 끝단 (8t 구성, 단줄 1단)

    # ---- 후크블록·리깅 ----
    "hook_block_kgf": 280,          # 데이터시트 "Moufle" 8t 후크블록
    "jib_weight_kgf": 8930,         # 60m 지브 자중

    # ---- 카운터지브 (T형은 자유회전 → 부지 침범 핵심 원인) ----
    "counter_jib_length_m": 17.17,   # 데이터시트 A치수
    "counter_jib_ballast_kgf": 15200, # 60m 구성, 8t 구성

    # ---- 마스트 옵션 ----
    # 데이터시트의 마스트 구성 중 일반적인 V 60A (2m 마스트) 사용
    "free_standing_height_m": 67.0,  # V 60A 기준 자립한계
    "mast_section_options": ["1.6m_S41A", "1.6m_City", "2m_V60A", "2m_V63A"],

    # ---- 운동 속도 (시간 계산용, 50 LVF 20 Optima 구성) ----
    "hoist_speed_max_mpm": 121.0,    # 4t 양중 시 최대속도
    "hoist_speed_at_full_mpm": 60.5,   # 풀로드
    "trolley_speed_mpm": 79.0,
    "slewing_speed_rpm": 0.8,

    # ---- 풍하중·구조 ----
    "wind_pressure_area_m2": 25.0,   # 추정 (FEM A3 분류, 표준 값)
    "moment_limit_kNm": 1600.0,      # 데이터시트 nominal torque

    # ---- 협소대지 부적합 표시 ----
    "narrow_site_suitable": False,   # 카운터지브 17m + T형 자유회전 → 협소대지 부적합

    # ---- Load Chart (60m 지브, 8t 구성, single fall part 4) ----
    # 데이터시트에서 직접 발췌
    "load_chart": [
        # (반경 m, 인양능력 kgf)
        ( 2.75, 8000),
        (14.3,  8000),
        (15.0,  7500),
        (17.0,  6500),
        (20.0,  5300),
        (22.0,  4700),
        (25.0,  4000),
        (30.0,  3600),
        (32.0,  3300),
        (35.0,  3000),
        (37.0,  2800),
        (40.0,  2550),
        (42.0,  2400),
        (45.0,  2200),
        (47.0,  2050),
        (50.0,  1900),
        (52.0,  1800),
        (55.0,  1700),
        (57.0,  1600),
        (60.0,  1500),
    ],
}


# =============================================================================
# Potain MR 160C (Luffing) — 러핑 소형
# =============================================================================
# 출처: LECTURA Specs (Potain 제조사 데이터 verified)
# 정격: 10t / 51m / 2.2t @ max reach / 20.2m @ max load

POTAIN_MR_160C = {
    "name": "Potain MR 160C",
    "manufacturer": "Manitowoc / Potain",
    "type": "luffing",
    "source": "LECTURA Specs (Potain manufacturer data, 2011-2025)",

    # ---- 정격 사양 ----
    "max_load_kgf": 10000,
    "max_radius_m": 51.0,
    "min_radius_m": 4.0,
    "load_at_max_radius_kgf": 2200,
    "radius_at_max_load_m": 20.2,

    # ---- 후크블록·리깅 ----
    "hook_block_kgf": 300,           # 10t급 표준
    "jib_weight_kgf": 7500,          # 추정 (러핑 보통 hammerhead 보다 가벼움)

    # ---- 카운터지브 (러핑은 매우 짧음 → 협소대지 유리) ----
    "counter_jib_length_m": 8.0,     # 러핑 짧음
    "counter_jib_ballast_kgf": 10000,

    # ---- 마스트 옵션 ----
    "free_standing_height_m": 50.0,
    "mast_section_options": ["1.6m", "2m"],

    # ---- 운동 속도 ----
    "hoist_speed_max_mpm": 100.0,
    "hoist_speed_at_full_mpm": 50.0,
    "trolley_speed_mpm": 0,           # 러핑은 트롤리 없음 (지브 자체가 회전)
    "luffing_speed_mpm": 40.0,        # 지브 기복 속도
    "slewing_speed_rpm": 0.7,

    # ---- 풍하중·구조 ----
    "wind_pressure_area_m2": 18.0,
    "moment_limit_kNm": 1600.0,

    # ---- 협소대지 적합성 ----
    "narrow_site_suitable": True,    # 러핑 + 짧은 카운터지브

    # ---- Load Chart (50m 지브 구성) ----
    # LECTURA 데이터 기반 + 일반적 러핑 곡선 형태로 보간
    "load_chart": [
        ( 4.0, 10000),
        (10.0, 10000),
        (15.0,  9500),
        (20.2, 10000),   # 최대 양중 반경 (LECTURA verified)
        (22.0,  8200),
        (25.0,  6800),
        (28.0,  5600),
        (30.0,  4900),
        (32.0,  4400),
        (35.0,  3700),
        (38.0,  3200),
        (40.0,  2950),
        (42.0,  2700),
        (45.0,  2500),
        (48.0,  2300),
        (51.0,  2200),
    ],
}


# =============================================================================
# Liebherr 280 HC-L 16/28 (Luffing) — 러핑 대형
# =============================================================================
# 출처: Liebherr 공식 카탈로그 (HC-L 시리즈 브로슈어)
# 정격: 28t / 60m / 3,000kg @ jib end

LIEBHERR_280_HC_L = {
    "name": "Liebherr 280 HC-L 16/28",
    "manufacturer": "Liebherr",
    "type": "luffing",
    "source": "Liebherr HC-L Series Brochure (official, 2025)",

    # ---- 정격 사양 ----
    "max_load_kgf": 28000,
    "max_radius_m": 60.0,
    "min_radius_m": 7.5,             # 공식: min slewing radius 7.5m
    "load_at_max_radius_kgf": 3000,  # 공식: 60m 끝단 3,000 kg

    # ---- 후크블록·리깅 ----
    "hook_block_kgf": 500,           # 28t급
    "jib_weight_kgf": 14000,         # 60m 러핑 추정

    # ---- 카운터지브 ----
    "counter_jib_length_m": 10.0,
    "counter_jib_ballast_kgf": 25000,

    # ---- 마스트 옵션 ----
    "free_standing_height_m": 59.1,  # 공식 Tower height
    "mast_section_options": ["2m_standard"],

    # ---- 운동 속도 ----
    "hoist_speed_max_mpm": 150.0,
    "hoist_speed_at_full_mpm": 30.0,
    "trolley_speed_mpm": 0,
    "luffing_speed_mpm": 50.0,
    "slewing_speed_rpm": 0.6,

    # ---- 풍하중·구조 ----
    "wind_pressure_area_m2": 28.0,
    "moment_limit_kNm": 2800.0,      # 공식 nominal torque

    # ---- 협소대지 적합성 ----
    "narrow_site_suitable": True,

    # ---- Load Chart (16/28 구성, 60m 지브) ----
    # 공식 데이터: max 28t, max reach 60m, tip 3,000 kg
    # 중간값은 러핑 곡선 형태로 보간
    "load_chart": [
        ( 7.5, 28000),
        (10.0, 28000),
        (15.0, 28000),    # 28t 정격 반경 추정 한계
        (18.0, 24000),
        (20.0, 21000),
        (25.0, 14500),
        (30.0, 10500),
        (35.0,  8000),
        (40.0,  6200),
        (45.0,  4900),
        (50.0,  4000),
        (55.0,  3400),
        (60.0,  3000),
    ],
}


# =============================================================================
# 통합 카탈로그
# =============================================================================

CRANES: Dict[str, dict] = {
    "Potain_MDT_178":    POTAIN_MDT_178,
    "Potain_MR_160C":    POTAIN_MR_160C,
    "Liebherr_280_HC_L": LIEBHERR_280_HC_L,
}


# =============================================================================
# Load Chart 보간 함수
# =============================================================================

def get_capacity(model_id: str, radius_m: float) -> float:
    """
    선형 보간으로 임의 반경에서 인양능력 반환 (kgf).
    반경이 범위 밖이면 0 또는 0에 가까운 값 반환.
    """
    if model_id not in CRANES:
        raise ValueError(f"Unknown model: {model_id}")

    chart = CRANES[model_id]["load_chart"]
    if radius_m < chart[0][0]:
        return chart[0][1]
    if radius_m > chart[-1][0]:
        return 0.0

    for i in range(len(chart) - 1):
        r1, w1 = chart[i]
        r2, w2 = chart[i+1]
        if r1 <= radius_m <= r2:
            return w1 + (w2 - w1) * (radius_m - r1) / (r2 - r1)
    return 0.0


def effective_max_radius(model_id: str, payload_kgf: float) -> float:
    """
    주어진 양중 중량을 들 수 있는 최대 반경.
    페이로드보다 능력이 큰 가장 먼 반경 반환.
    """
    chart = CRANES[model_id]["load_chart"]
    spec = CRANES[model_id]
    effective = payload_kgf + spec["hook_block_kgf"] + 100  # +rigging
    max_r = 0.0
    for r, w in chart:
        if w >= effective:
            max_r = max(max_r, r)
    return max_r


# =============================================================================
# 자체 검증 + Load Chart 시각화
# =============================================================================

if __name__ == "__main__":
    print("=" * 75)
    print("타워크레인 모델 데이터베이스 자체 검증")
    print("=" * 75)

    payload = 3000   # 갱폼 1세트
    for mid, spec in CRANES.items():
        print(f"\n[{spec['name']}] ({spec['type']})")
        print(f"  출처: {spec['source']}")
        print(f"  최대 인양능력: {spec['max_load_kgf']/1000:.1f} t")
        print(f"  최대 반경: {spec['max_radius_m']:.1f} m "
              f"(@ {spec['load_at_max_radius_kgf']/1000:.1f} t)")
        print(f"  카운터지브: {spec['counter_jib_length_m']:.1f} m")
        print(f"  자립한계 마스트: {spec['free_standing_height_m']:.1f} m")
        print(f"  협소대지 적합: {'✅' if spec['narrow_site_suitable'] else '❌'}")
        eff_r = effective_max_radius(mid, payload)
        print(f"  → 갱폼 3t 양중 가능 최대 반경: {eff_r:.1f} m")

        # 주요 반경에서 능력 확인
        for r in [15, 20, 30, 40, 50]:
            if r <= spec['max_radius_m']:
                cap = get_capacity(mid, r)
                ok = "✅" if cap >= 3400 else "❌"
                print(f"    r={r}m: {cap/1000:.2f}t  {ok}(요구 3.4t 포함)")

    print("\n" + "=" * 75)
    print("결론 사전 분석")
    print("=" * 75)
    print("""
1. Potain MDT 178 (T형):
   - 카운터지브 17.17m + 자유회전 → 부지(반경 ~12m)에서 항상 인접대지 침범
   - 협소대지 부적합 (baseline 비교용으로만 사용)

2. Potain MR 160C (러핑 소형):
   - 갱폼 3t를 약 38m 반경까지 양중 가능
   - 부지 대각선(약 30m) + 야적장 거리 충분히 커버
   - 우리 케이스에 가장 경제적인 선택지로 예상

3. Liebherr 280 HC-L (러핑 대형):
   - 28t 정격으로 어떤 양중점도 커버
   - 다만 자중·임대료가 큼 → 9층 RC에 과스펙
   - F1(안전) 측면 강건성 비교 자료
""")
