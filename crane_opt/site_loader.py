"""
================================================================================
site_loader.py
================================================================================
범용 부지 로더 — JSON 파일 → SiteData 객체
--------------------------------------------------------------------------------
이 모듈은 site_model.py 를 대체하지 않고 보완한다.
- site_model.py: 공덕동 전용 하드코딩 (기존 코드 호환 유지)
- site_loader.py: 임의 JSON 부지를 로드 (범용화)

site_loader.load_site("sites/foo.json") 으로 SiteData 인스턴스 획득.
SiteData 인스턴스는 site_model.py 가 노출하던 모든 모듈-레벨 변수를
속성으로 제공한다:

    site.SITE                      : shapely Polygon
    site.SITE_AREA_OFFICIAL_M2     : float
    site.PLANNED_BUILDING          : Polygon
    site.PLANNED_BUILDING_HEIGHT_M : float
    site.PLANNED_BUILDING_FLOORS   : int
    site.PLANNED_BUILDING_STRUCTURE: str
    site.PLANNED_BUILDING_METHOD   : str
    site.ADJACENT_BUILDINGS        : dict
    site.ROADS                     : dict
    site.LIFT_POINTS               : list[(x, y)]
    site.BUILDING_GRID_POINTS      : list[(x, y)]
    site.MATERIAL_YARD             : (x, y)
    site.LIFT_POINT_MATERIAL_PROFILE: dict
    site.MATERIAL_WEIGHTS          : dict     ← 기본값, 모든 부지 공통
    site.MATERIAL_HANDLING_TIME    : dict     ← 기본값
    site.ALLOWED_AREA              : Polygon  ← 부지 ∪ 도로
    site.PAYLOAD_MAX_KGF_OBSERVED  : float
    site.SEARCH_BOUNDS             : dict {"x_range":(-25, 25), "y_range":(-20, 20)}
    site.metadata                  : dict (이름, 출처 등)

설계 의도:
    각 모듈 (constraints, objectives 등) 의 import 부분만 약간 수정하면
    동일 인터페이스로 임의 부지를 다룰 수 있다.
"""
import json
from pathlib import Path
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


# =============================================================================
# 자재 정보 (모든 부지 공통 — RC 9층 건축 시공 기준)
# =============================================================================
DEFAULT_MATERIAL_WEIGHTS = {
    "gangform":  3000,   # 갱폼 1세트 ≈ 3.0 톤
    "rebar":     1500,   # 철근다발 ≈ 1.5 톤
    "concrete":  2000,   # 콘크리트 버킷 ≈ 2.0 톤
    "pc_part":   3500,   # PC 부재 (계단·발코니) ≈ 3.5 톤
    "finishing":  500,   # 마감자재 (창호·외장재) ≈ 0.5 톤
}

DEFAULT_MATERIAL_HANDLING_TIME = {
    "gangform":  {"attach": 45, "release": 30},
    "rebar":     {"attach": 25, "release": 20},
    "concrete":  {"attach": 20, "release": 15},
    "pc_part":   {"attach": 60, "release": 45},
    "finishing": {"attach": 30, "release": 25},
}


# =============================================================================
# Helpers
# =============================================================================
def _parse_footprint(spec):
    """JSON footprint 정의 → shapely Polygon."""
    if isinstance(spec, dict) and spec.get("type") == "rect":
        cx, cy, w, h = spec["cx"], spec["cy"], spec["w"], spec["h"]
        return box(cx - w/2, cy - h/2, cx + w/2, cy + h/2)
    elif isinstance(spec, dict) and spec.get("type") == "polygon":
        return Polygon(spec["vertices"])
    elif isinstance(spec, list):
        # 4-tuple [minx, miny, maxx, maxy] = bounding box
        if len(spec) == 4 and all(isinstance(v, (int, float)) for v in spec):
            return box(*spec)
        # otherwise list of vertices
        return Polygon(spec)
    else:
        raise ValueError(f"Unsupported footprint spec: {spec}")


def _classify_grid_position(idx, nx, ny):
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


def _build_material_profile(n_grid_points, nx, ny):
    """양중점 × 자재 종류 × 사이클 수 dictionary 생성.

    한국갱폼협회 + 일반 RC 9층 시공계획 기준 분포.
    - 코너: 갱폼·마감 多, PC부재 多
    - 변(중간): 갱폼·콘크리트
    - 중앙: 콘크리트·철근 위주
    """
    profile = {}
    for idx in range(n_grid_points):
        pos = _classify_grid_position(idx, nx, ny)
        if pos == "corner":
            profile[idx] = {
                "gangform":  60, "rebar":     35, "concrete":  25,
                "pc_part":   20, "finishing": 30,
            }
        elif pos == "edge":
            profile[idx] = {
                "gangform":  30, "rebar":     25, "concrete":  30,
                "pc_part":    5, "finishing": 15,
            }
        else:
            profile[idx] = {
                "gangform":   5, "rebar":     20, "concrete":  35,
                "pc_part":    0, "finishing":  5,
            }
    return profile


# =============================================================================
# SiteData class
# =============================================================================
class SiteData:
    """JSON 정의로부터 구성된 부지 데이터.

    site_model.py 의 모듈 레벨 변수들과 동일한 인터페이스를 attribute 로 제공.
    """
    def __init__(self, spec, source_path=None):
        self._spec = spec
        self.source_path = source_path
        self.metadata = spec.get("metadata", {})

        # ---- 1) 부지 ----
        verts = spec["lot_vertices"]
        self.LOT_VERTICES = [tuple(v) for v in verts]
        self.SITE = Polygon(self.LOT_VERTICES)
        self.SITE_AREA_OFFICIAL_M2 = self.metadata.get(
            "official_area_m2", self.SITE.area
        )

        # ---- 2) 신축 건물 ----
        pb = spec["planned_building"]
        if "footprint_box" in pb:
            self.PLANNED_BUILDING = box(*pb["footprint_box"])
        elif "footprint" in pb:
            self.PLANNED_BUILDING = _parse_footprint(pb["footprint"])
        else:
            raise ValueError("planned_building 에 footprint_box 또는 footprint 필요")
        self.PLANNED_BUILDING_HEIGHT_M = float(pb.get("height_m", 32.0))
        self.PLANNED_BUILDING_FLOORS = int(pb.get("floors", 9))
        self.PLANNED_BUILDING_STRUCTURE = pb.get("structure", "RC")
        self.PLANNED_BUILDING_METHOD = pb.get("method", "갱폼 + 시스템동바리")
        self.PLANNED_BUILDING_USE = pb.get("use", "도시형생활주택")

        # ---- 3) 인접 건물 ----
        # airspace_easement: 해당 인접건물 상공으로의 지브 선회 통과 동의 여부.
        #   [근거] 도심 협소대지에서 슬루 반경이 대지를 초과하는 것은 통상적이며
        #   (대지면적 << π·R²), 실무에서는 인접 소유자 동의/협정 하에 인접건물
        #   '상공'으로 지브를 통과시킨다. 단, 지브·인양물이 인접건물보다 충분히
        #   높이 지나가야 충돌이 없다 → G2/G3에서 높이 조건으로 판정(아래 constraints).
        #   플래그가 없으면 False(기존 동작: 평면 침범 자체를 금지) → 하위 호환.
        self.ADJACENT_BUILDINGS = {}
        for b in spec.get("adjacent_buildings", []):
            self.ADJACENT_BUILDINGS[b["key"]] = {
                "name":      b["name"],
                "footprint": _parse_footprint(b["footprint"]),
                "height_m":  float(b["height_m"]),
                "floors":    int(b.get("floors", 1)),
                "source":    b.get("source", "unknown"),
                "airspace_easement": bool(b.get("airspace_easement", False)),
            }

        # ---- 3b) 공지(빈 인접대지: 공터·주차장) ----
        # [근거] 빈 대지(주차장/공터)는 점유 건물·재실자가 없으므로 그 상공으로의
        #   선회는 인접대지 공중침범(G9)에 해당하지 않는다(소유자 동의 전제, 실무 통례).
        #   따라서 ALLOWED_AREA 에 포함시켜 선회를 허용한다.
        #   단 F1 제3자위험에서는 여전히 'empty'(취약성 0.5, 저위험)로 집계되어
        #   도로(5.0)·인접건물(3.0) 대비 위험 기여가 작다 → 빈 대지 특성과 일치.
        #   공덕동/역삼동 등 vacant_lots 미정의 부지는 영향 없음(하위 호환).
        self.VACANT_LOTS = {}
        for v in spec.get("vacant_lots", []):
            self.VACANT_LOTS[v["key"]] = {
                "name":      v.get("name", v["key"]),
                "footprint": _parse_footprint(v["footprint"]),
                "source":    v.get("source", "unknown"),
            }

        # ---- 4) 도로 ----
        self.ROADS = {}
        for r in spec.get("roads", []):
            self.ROADS[r["key"]] = {
                "name":     r["name"],
                "polygon":  Polygon(r["polygon"]),
                "width_m":  float(r["width_m"]),
                "source":   r.get("source", "unknown"),
                "occupation_allowed": bool(r.get("occupation_allowed", True)),
            }

        # ---- 5) 양중점 ----
        lp = spec.get("lift_points", {})
        grid_spec = lp.get("building_grid", {"nx": 5, "ny": 5})
        nx = int(grid_spec.get("nx", 5))
        ny = int(grid_spec.get("ny", 5))
        bb = self.PLANNED_BUILDING.bounds  # (minx, miny, maxx, maxy)
        self.BUILDING_GRID_POINTS = []
        for j in range(ny):
            for i in range(nx):
                x = bb[0] + (i + 0.5) * (bb[2] - bb[0]) / nx
                y = bb[1] + (j + 0.5) * (bb[3] - bb[1]) / ny
                self.BUILDING_GRID_POINTS.append((x, y))

        my = lp.get("material_yard", None)
        if my is None:
            # default: 부지 최북단 +1m 외측
            x_c = self.SITE.centroid.x
            _, _, _, ymax = self.SITE.bounds
            my = (x_c, ymax + 1.5)
        self.MATERIAL_YARD = tuple(my)
        self.LIFT_POINTS = self.BUILDING_GRID_POINTS + [self.MATERIAL_YARD]

        self.LIFT_POINT_MATERIAL_PROFILE = _build_material_profile(
            len(self.BUILDING_GRID_POINTS), nx, ny
        )

        # ---- 6) 자재 (기본값) ----
        self.MATERIAL_WEIGHTS = dict(DEFAULT_MATERIAL_WEIGHTS)
        self.MATERIAL_HANDLING_TIME = dict(DEFAULT_MATERIAL_HANDLING_TIME)
        self.PAYLOAD_MAX_KGF_OBSERVED = max(self.MATERIAL_WEIGHTS.values())

        # ---- 7) 허용 설치 영역 ----
        # 부지 ∪ (점용허용 도로) ∪ (공지: 빈 인접대지) ∪ (상공권 동의 인접건물)
        #   상공권(airspace easement) 동의 인접건물은 그 상공으로 지브 선회가
        #   허용되므로 G9(인접대지 공중침범) 판정에서 ALLOWED 로 포함한다.
        #   실제 충돌(높이) 안전성은 G2/G3 가 height-aware 로 별도 판정.
        road_polys = [r["polygon"] for r in self.ROADS.values()
                       if r["occupation_allowed"]]
        vacant_polys = [v["footprint"] for v in self.VACANT_LOTS.values()]
        easement_polys = [b["footprint"] for b in self.ADJACENT_BUILDINGS.values()
                           if b.get("airspace_easement", False)]
        self.ALLOWED_AREA = unary_union(
            [self.SITE] + road_polys + vacant_polys + easement_polys
        )

        # ---- 8) 검색 경계 ----
        sb = spec.get("search_bounds", None)
        if sb:
            self.SEARCH_BOUNDS = {
                "x_range": tuple(sb.get("x_range", [-25.0, 25.0])),
                "y_range": tuple(sb.get("y_range", [-20.0, 20.0])),
            }
        else:
            # auto: ALLOWED_AREA 의 bbox에 여유 ±2m
            minx, miny, maxx, maxy = self.ALLOWED_AREA.bounds
            self.SEARCH_BOUNDS = {
                "x_range": (minx - 2, maxx + 2),
                "y_range": (miny - 2, maxy + 2),
            }

    # convenience
    def summary(self):
        s = []
        s.append(f"[Site] {self.metadata.get('display_name', '(unnamed)')}")
        s.append(f"  면적         : {self.SITE.area:.1f} m² "
                  f"(공식 {self.SITE_AREA_OFFICIAL_M2} m²)")
        s.append(f"  건물풋프린트 : {self.PLANNED_BUILDING.area:.1f} m² · "
                  f"{self.PLANNED_BUILDING_HEIGHT_M}m {self.PLANNED_BUILDING_FLOORS}층")
        s.append(f"  인접건물     : {len(self.ADJACENT_BUILDINGS)}동")
        s.append(f"  도로         : {len(self.ROADS)}개")
        s.append(f"  양중점       : {len(self.LIFT_POINTS)}개 "
                  f"(building grid {len(self.BUILDING_GRID_POINTS)} + 야적장 1)")
        s.append(f"  허용설치영역 : {self.ALLOWED_AREA.area:.1f} m²")
        s.append(f"  검색범위     : x∈{self.SEARCH_BOUNDS['x_range']}, "
                  f"y∈{self.SEARCH_BOUNDS['y_range']}")
        return "\n".join(s)


# =============================================================================
# 로더 함수
# =============================================================================
class SiteSpecError(Exception):
    """부지 JSON이 잘못되었을 때 사용자에게 보여줄 친절한 오류."""
    pass


def validate_site_spec(spec, path=""):
    """부지 JSON 필수 항목·형식을 검사. 문제가 있으면 SiteSpecError(읽기 쉬운 메시지)."""
    if not isinstance(spec, dict):
        raise SiteSpecError("부지 파일의 최상위가 객체(JSON object)가 아닙니다.")
    problems = []
    # 대지
    lv = spec.get("lot_vertices")
    if lv is None:
        problems.append("• 'lot_vertices'(대지 꼭짓점)가 없습니다.")
    elif not isinstance(lv, list) or len(lv) < 3:
        problems.append("• 'lot_vertices'는 꼭짓점 3개 이상의 배열이어야 합니다 (예: [[x,y], ...]).")
    else:
        for i, v in enumerate(lv):
            if (not isinstance(v, (list, tuple))) or len(v) != 2:
                problems.append(f"• lot_vertices[{i}]가 [x, y] 형식이 아닙니다: {v!r}")
                break
    # 신축 건물
    pb = spec.get("planned_building")
    if pb is None:
        problems.append("• 'planned_building'(신축 건물)이 없습니다.")
    elif not ("footprint_box" in pb or "footprint" in pb):
        problems.append("• planned_building에 'footprint_box' 또는 'footprint'가 필요합니다.")
    # 인접/도로는 선택이지만, 있으면 형식 체크
    for b in spec.get("adjacent_buildings", []) or []:
        if "footprint" not in b or "key" not in b:
            problems.append("• adjacent_buildings의 각 항목에는 'key'와 'footprint'가 필요합니다.")
            break
    if problems:
        head = f"부지 파일을 읽을 수 없습니다" + (f" ({path})" if path else "") + ":\n"
        raise SiteSpecError(head + "\n".join(problems))


def load_site(path):
    """JSON 부지 정의 파일 → SiteData. (친절한 오류 처리 포함)"""
    p = Path(path)
    if not p.exists():
        raise SiteSpecError(f"부지 파일을 찾을 수 없습니다: {path}")
    try:
        with open(p, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except json.JSONDecodeError as e:
        raise SiteSpecError(
            f"부지 파일이 올바른 JSON 형식이 아닙니다 ({path}).\n"
            f"  위치: {e.lineno}번째 줄, {e.colno}번째 칸 — {e.msg}\n"
            f"  (쉼표 ',' 누락이나 대괄호 '[ ]' 짝 불일치가 흔한 원인입니다)"
        )
    validate_site_spec(spec, str(p))
    try:
        return SiteData(spec, source_path=str(p))
    except SiteSpecError:
        raise
    except Exception as e:
        raise SiteSpecError(
            f"부지 데이터를 구성하는 중 오류가 발생했습니다 ({path}).\n  상세: {e}"
        )


def list_sites(sites_dir="sites"):
    """sites 폴더의 모든 JSON 파일 목록."""
    p = Path(sites_dir)
    if not p.exists():
        return []
    return sorted([str(x) for x in p.glob("*.json")])


# =============================================================================
# CLI 검증
# =============================================================================
if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "sites/gongdeok_256_42.json"
    site = load_site(target)
    print(site.summary())
    print()
    print(f"[인접건물 상세]")
    for k, b in site.ADJACENT_BUILDINGS.items():
        print(f"  {k}: {b['name']} · {b['height_m']}m · "
              f"footprint {b['footprint'].area:.0f}㎡")
    print(f"\n[도로 상세]")
    for k, r in site.ROADS.items():
        print(f"  {k}: {r['name']} · 폭 {r['width_m']}m · "
              f"{r['polygon'].area:.0f}㎡ · 점용가능={r['occupation_allowed']}")
