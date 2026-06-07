"""
================================================================================
site_model.py
================================================================================
공덕동 256-42 부지 기하학 모델 (작업 1)
--------------------------------------------------------------------------------
좌표계 정의:
  - 원점 (0, 0): 부지 중심 (centroid)
  - X 축: 동쪽 (+) / 서쪽 (-)
  - Y 축: 북쪽 (+) / 남쪽 (-)
  - 단위: meter
  - 회전 방향: 반시계방향 (수학 표준)

데이터 출처:
  - 부지 면적·용도지역: 토지e음 (eum.go.kr)
  - 부지 형상: V-World 지적도 영상 기반 단순화
  - 인접 건물 층수: V-World 건축물정보 (verified) / 영상 추정 (estimated)
  - 도로 폭 12m: V-World 거리측정 도구로 직접 측정 (verified)
  - 도로 폭 8m, 5m: V-World 영상 추정
"""

from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union


# =============================================================================
# 1. 부지 (Lot 256-42)
# =============================================================================
# 토지e음 확인 면적: 550.6 m²
# 형상: 비정형 (L자 형 - 남서측 한 모서리 절단)

LOT_VERTICES = [
    (-12.5,  12.5),   # NW 모서리
    ( 12.5,  12.5),   # NE 모서리
    ( 12.5, -12.5),   # SE 모서리
    ( -5.0, -12.5),   # 남서측 절단부 시작
    ( -5.0,  -2.5),   # 남서측 절단부 안쪽 모서리
    (-12.5,  -2.5),   # 남서측 절단부 끝
]

SITE = Polygon(LOT_VERTICES)
SITE_AREA_OFFICIAL_M2 = 550.6  # 토지e음 공식 값


# =============================================================================
# 2. 신축 건물 (Planned Building)
# =============================================================================
# 용도: 도시형생활주택 + 1·2층 근린생활시설
# 9층 + 옥탑 → 높이 32m
# 건폐율 60% 한도, 안전 여유 두고 약 280 m² 풋프린트

PLANNED_BUILDING = box(-10, -4, 10, 10)   # 20m × 14m = 280 m²
PLANNED_BUILDING_HEIGHT_M = 32             # 9층 × 3m + 옥탑 5m
PLANNED_BUILDING_FLOORS = 9
PLANNED_BUILDING_STRUCTURE = "RC"
PLANNED_BUILDING_METHOD = "갱폼 + 시스템동바리"


# =============================================================================
# 3. 인접 건물 (Adjacent Buildings)
# =============================================================================
# 평균 층고 3m 가정으로 건물 높이 산출
# 모델링: 직사각형 풋프린트 + 높이 스칼라

def _rect(cx, cy, w, h):
    """중심 (cx, cy), 가로 w, 세로 h 직사각형 폴리곤."""
    return box(cx - w/2, cy - h/2, cx + w/2, cy + h/2)


ADJACENT_BUILDINGS = {
    "NW": {
        "name": "북서 20층 빌딩",
        "footprint": _rect(cx=-30, cy=30, w=25, h=20),
        "height_m": 60.0,
        "floors": 20,
        "source": "verified (V-World)",
    },
    "N": {
        "name": "북측 3층 (V-World 정보없음)",
        "footprint": _rect(cx=5, cy=25, w=15, h=10),
        "height_m": 9.0,
        "floors": 3,
        "source": "estimated (V-World 영상)",
    },
    "E": {
        "name": "동측 2층",
        "footprint": _rect(cx=33, cy=5, w=15, h=25),
        "height_m": 7.0,
        "floors": 2,
        "source": "verified (V-World)",
    },
    "S": {
        "name": "남측 1층",
        "footprint": _rect(cx=5, cy=-25, w=15, h=10),
        "height_m": 4.0,
        "floors": 1,
        "source": "verified (V-World)",
    },
    "SE": {
        "name": "남동측 2층",
        "footprint": _rect(cx=33, cy=-25, w=12, h=15),
        "height_m": 7.0,
        "floors": 2,
        "source": "verified (V-World)",
    },
    "SW": {
        "name": "남서측 1층 (소형)",
        "footprint": _rect(cx=-22, cy=-20, w=8, h=10),
        "height_m": 4.0,
        "floors": 1,
        "source": "verified (V-World)",
    },
}


# =============================================================================
# 4. 도로 (Roads)
# =============================================================================
# 도로점용 가능성 평가에 사용
# 각 도로의 폴리곤 + 폭 정보

ROADS = {
    "north_main": {
        "name": "북측 주도로",
        "polygon": Polygon([
            (-18, 12.5), (28, 12.5), (28, 24.5), (-18, 24.5)
        ]),
        "width_m": 12.0,
        "source": "verified (V-World 측정)",
    },
    "east_secondary": {
        "name": "동측 보조도로",
        "polygon": Polygon([
            (12.5, -34), (20.5, -34), (20.5, 12.5), (12.5, 12.5)
        ]),
        "width_m": 8.0,
        "source": "estimated",
    },
    "south_alley": {
        "name": "남측 골목",
        "polygon": Polygon([
            (-18, -17.5), (12.5, -17.5), (12.5, -12.5),
            (-5, -12.5), (-5, -17.5)
        ]),
        "width_m": 5.0,
        "source": "estimated",
    },
}


# =============================================================================
# 5. 양중점 (Lift Points) — Grid 기반 세분화
# =============================================================================
# 건물 footprint 내부를 5×5 grid 로 분할 + 야적장 1개 = 26개 양중점
# 각 양중점은 시공 위치(building grid) 또는 자재 야적(material yard) 으로 구분
#
# 시공계획 기반 (한국갱폼협회 + 일반 RC 9층 평균):
#   - 건물 grid 위치별 양중 수: 자재 종류별 합계
#   - 총 약 1,500회 (golf 시공 단계 누적)

from shapely.geometry import box as _box

_BUILDING_BOUNDS = PLANNED_BUILDING.bounds   # (minx, miny, maxx, maxy)
_GRID_NX = 5   # X 방향 5칸
_GRID_NY = 5   # Y 방향 5칸

BUILDING_GRID_POINTS = []   # 건물 footprint 내부 grid points
for j in range(_GRID_NY):
    for i in range(_GRID_NX):
        x_cell = _BUILDING_BOUNDS[0] + (i + 0.5) * (_BUILDING_BOUNDS[2] - _BUILDING_BOUNDS[0]) / _GRID_NX
        y_cell = _BUILDING_BOUNDS[1] + (j + 0.5) * (_BUILDING_BOUNDS[3] - _BUILDING_BOUNDS[1]) / _GRID_NY
        BUILDING_GRID_POINTS.append((x_cell, y_cell))

MATERIAL_YARD = (8.0, 11.0)    # 북측 진입로 인근

# 전체 양중점 = 건물 grid + 야적장
LIFT_POINTS = BUILDING_GRID_POINTS + [MATERIAL_YARD]


# =============================================================================
# 5-B. 양중점별 자재 분포 (Material-aware lift point profile)
# =============================================================================
# 각 grid 양중점이 받는 자재의 종류·빈도를 시공계획 기반으로 분포
#
# 자재 분류 (한국갱폼협회 + 일반 RC 9층 시공계획 기준):
#   gangform   : 갱폼 1세트 ≈ 3.0 톤 (벽체 외곽 위주, 코너 집중)
#   rebar      : 철근다발  ≈ 1.5 톤 (벽체·슬래브 전반)
#   concrete   : 콘크리트 버킷 ≈ 2.0 톤 (슬래브 전반, 펌프카 대체용 일부)
#   pc_part    : PC 부재 (계단·발코니) ≈ 3.5 톤 (특정 위치)
#   finishing  : 마감자재 (창호·외장재) ≈ 0.5 톤 (외곽)
#
# grid 위치별 양중 횟수: 자재 종류 × 시공 단계 × 층수
# 총합 약 1,500회 (9층 골조 + 마감 누적)

# 위치별 자재 분포 패턴
# - 코너(외곽): 갱폼·마감 多
# - 변(중간): 갱폼·콘크리트
# - 중앙: 콘크리트·철근 위주

def _classify_grid_position(idx, nx=_GRID_NX, ny=_GRID_NY):
    """grid index 의 위치 분류: corner / edge / center"""
    i = idx % nx
    j = idx // nx
    is_corner_x = (i == 0 or i == nx - 1)
    is_corner_y = (j == 0 or j == ny - 1)
    if is_corner_x and is_corner_y:
        return "corner"
    elif is_corner_x or is_corner_y:
        return "edge"
    else:
        return "center"


def _build_material_profile():
    """양중점 × 자재 종류 × 사이클 수 dictionary 생성."""
    profile = {}
    for idx in range(len(BUILDING_GRID_POINTS)):
        pos_type = _classify_grid_position(idx)
        if pos_type == "corner":   # 4개
            profile[idx] = {
                "gangform":  60,
                "rebar":     35,
                "concrete":  25,
                "pc_part":   20,
                "finishing": 30,
            }
        elif pos_type == "edge":   # 12개
            profile[idx] = {
                "gangform":  30,
                "rebar":     25,
                "concrete":  30,
                "pc_part":    5,
                "finishing": 15,
            }
        else:                       # center, 9개
            profile[idx] = {
                "gangform":   5,
                "rebar":     20,
                "concrete":  35,
                "pc_part":    0,
                "finishing":  5,
            }
    return profile


LIFT_POINT_MATERIAL_PROFILE = _build_material_profile()


# 자재별 중량 (kgf)
MATERIAL_WEIGHTS = {
    "gangform":  3000,
    "rebar":     1500,
    "concrete":  2000,
    "pc_part":   3500,
    "finishing":  500,
}


# 자재별 결박·해제 시간 (초) — 자재 특성 반영
MATERIAL_HANDLING_TIME = {
    "gangform":  {"attach": 45, "release": 30},
    "rebar":     {"attach": 25, "release": 20},
    "concrete":  {"attach": 20, "release": 15},
    "pc_part":   {"attach": 60, "release": 45},
    "finishing": {"attach": 30, "release": 25},
}


# 최대 자재 중량 (배치 제약 검사용)
PAYLOAD_MAX_KGF_OBSERVED = max(MATERIAL_WEIGHTS.values())   # 3500 (PC 부재)


# =============================================================================
# 6. 허용 설치 영역 (Allowed Crane Installation Area)
# =============================================================================
# 부지 ∪ 도로 영역 = 합법적 설치 가능 공간
# 인접대지는 절대 제외

ALLOWED_AREA = unary_union([SITE] + [r["polygon"] for r in ROADS.values()])


# =============================================================================
# 7. 자체 검증 (Self-Check)
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("공덕동 256-42 부지 데이터 모델 자체 검증")
    print("=" * 60)
    print(f"\n[부지]")
    print(f"  모델 면적: {SITE.area:.1f} m²")
    print(f"  공식 면적: {SITE_AREA_OFFICIAL_M2} m²")
    print(f"  오차: {abs(SITE.area - SITE_AREA_OFFICIAL_M2):.1f} m² "
          f"({100*abs(SITE.area - SITE_AREA_OFFICIAL_M2)/SITE_AREA_OFFICIAL_M2:.1f}%)")
    print(f"  중심점: {SITE.centroid.wkt}")
    print(f"  경계 범위: {SITE.bounds}")

    print(f"\n[인접 건물]")
    for d, b in ADJACENT_BUILDINGS.items():
        print(f"  {d}: {b['name']} - {b['height_m']}m "
              f"(footprint {b['footprint'].area:.0f}m²)")

    print(f"\n[도로]")
    for k, r in ROADS.items():
        print(f"  {r['name']}: 폭 {r['width_m']}m, 면적 {r['polygon'].area:.0f}m²")

    print(f"\n[신축 건물]")
    print(f"  풋프린트: {PLANNED_BUILDING.area:.0f} m² "
          f"(건폐율 {100*PLANNED_BUILDING.area/SITE_AREA_OFFICIAL_M2:.1f}%)")
    print(f"  높이: {PLANNED_BUILDING_HEIGHT_M}m ({PLANNED_BUILDING_FLOORS}층)")

    print(f"\n[양중점] {len(LIFT_POINTS)}개")
    for i, p in enumerate(LIFT_POINTS, 1):
        print(f"  {i}: ({p[0]:.1f}, {p[1]:.1f})")

    print(f"\n[허용 설치 영역]")
    print(f"  총 면적: {ALLOWED_AREA.area:.0f} m² "
          f"(부지 {SITE.area:.0f} + 도로 {sum(r['polygon'].area for r in ROADS.values()):.0f})")

    print("\n검증 완료.")
