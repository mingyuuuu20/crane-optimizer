"""방배동 2252 (FT-80L 외부설치) site JSON 조립.
출처: 시공사 설계도면(DWG) + 한일타워 현장기사 + FT-80L 카탈로그 3중 검증.
좌표계: 대지 중심 원점, East(+x)/North(+y), meter.

대지 방위 가정: 대지 16.9×15.15m. 도면 입면상 크레인이 건물 좌측 코어(계단실)
외벽에 밀착하여 외부설치. 6m 골목도로가 코어측(서측)에 접함(지브 조립에 활용).
장변(16.9m)을 동서(E-W), 단변(15.15m)을 남북(N-S)으로 배치.
"""
import json, numpy as np

# ── 대지: 16.9(E-W) × 15.15(N-S), 중심원점 직사각형 ──
W_lot, H_lot = 16.9, 15.15
hw, hh = W_lot/2, H_lot/2
lot = [[-hw,-hh],[hw,-hh],[hw,hh],[-hw,hh]]  # 반시계: SW,SE,NE,NW
area = W_lot*H_lot
print(f"대지 {W_lot}×{H_lot} = {area:.1f}㎡")

# ── 건물 footprint: 오피스텔. 대지 동측에 치우쳐 배치(서측에 크레인 설치공간 확보) ──
# 실제: 8층 기계식주차 오피스텔. 1층에 주차진입+코어. 서측(도로측)에 크레인 외부설치
#   공간(기초 5.4×5.4m + 작업폭)을 남기고 건물은 동측으로 set-back.
# footprint_box = [xmin,ymin,xmax,ymax]. 서측 외벽 x=-4.5 (서측에 4m 공간 확보)
off = 0.5
bx0 = -4.5            # 서측 외벽(코어측) — 좌측에 크레인 공간
bx1 = hw - off       # 동측 외벽
by0 = -hh + off
by1 = hh - off
footprint_box = [round(bx0,2), round(by0,2), round(bx1,2), round(by1,2)]
print(f"건물 footprint {footprint_box}  ≈{(bx1-bx0)*(by1-by0):.0f}㎡ (건폐율 {(bx1-bx0)*(by1-by0)/area*100:.0f}%)")

# ── 크레인 실제위치(도면 기반): 서측 코어 외벽 옆, 대지 안·footprint 밖 ──
# 외부설치. 건물 서측 외벽(x=-4.5) 바깥, 대지 서측 공간. 남북 중앙.
crane_actual = [round(bx0 - 1.8, 2), 0.0]   # 외벽서 1.8m 서측(기초중심), 대지 안
print(f"크레인 실제위치(외부설치, 서측 코어 옆) = {crane_actual}")

# ── 도로: 서측 6m 골목 (지브 조립에 활용) ──
# 대지 서변(x=-hw) 바깥. 도로 중심 = 서변 - (gap + 3m반폭)
west_road = [
    [-hw-0.5, -hh-3], [-hw-6.5, -hh-3], [-hw-6.5, hh+3], [-hw-0.5, hh+3]
]
west_road = [[round(a,2),round(b,2)] for a,b in west_road]

# ── 인접건물: 방배현대홈타운 2차(동측), 기타 인접 ──
# 협소부지라 3면이 인접건물/대지에 면함. 동측=현대홈타운, 남측·북측=인접 다세대
adjacent = [
    {"key":"hyundai_2","name":"방배현대홈타운 2차아파트 (동측, 고층)",
     "footprint":{"type":"rect","cx":hw+16,"cy":0,"w":20,"h":40},"height_m":45.0,"floors":15,
     "source":"도면+지도(인접 대단지 아파트). 대지 경계서 이격, 크레인 지브 비통과 영역.",
     "airspace_easement":False},
    {"key":"south_adj","name":"남측 인접건물 (다세대/근생, 저층)",
     "footprint":{"type":"rect","cx":0,"cy":-hh-5,"w":16,"h":9},"height_m":12.0,"floors":4,
     "source":"지도 추정(밀집 다세대). 상공권 동의 가정 — 저층, 지브 상공 통과.",
     "airspace_easement":True},
    {"key":"north_adj","name":"북측 인접건물 (다세대/근생, 저층)",
     "footprint":{"type":"rect","cx":2,"cy":hh+5,"w":16,"h":9},"height_m":12.0,"floors":4,
     "source":"지도 추정(밀집 다세대). 상공권 동의 가정 — 저층, 지브 상공 통과.",
     "airspace_easement":True},
]

site = {
  "$schema_version":"1.0",
  "metadata":{
    "site_id":"bangbae_2252",
    "display_name":"서초구 방배동 2252 오피스텔 (FT-80L)",
    "location":"서울특별시 서초구 방배동 2252, 2252-2 (이수역 인근)",
    "official_area_m2":round(area,1),
    "zoning":"제2종일반주거지역 추정 (도시형생활주택/오피스텔)",
    "FAR_pct":None,"BCR_pct":None,
    "source_notes":[
      "현장/규모: 한일타워 현장기사 — 방배동 오피스텔+근생, 지하1층(4.5m)+지상8층(36.6m)",
      "대지 16.9×15.15m(≈256㎡): 한일타워 기사 명시 (도면 표제란 397㎡는 조경산출 영역, 실대지 아님)",
      "크레인 FT-80L(무인 러핑 L형): 도면 라벨 起升机构/拉臂机构 + 기사 모델명 + 카탈로그",
      "슬루반경 20m: 도면 R20m 풀서클 + 기사 '20m 반경' + 카탈로그(max25m중 20m적용) 3중일치",
      "지브 20m, 마스트 50m, 2회 인상, 정격 2.9t/팁2.0t, 기초 5.4×5.4m: 카탈로그+기사",
      "외부설치+월브레싱 2단: 도면 입면(마스트가 좌측 코어 외벽 밀착, 6층·12층 정착) + 기사 '건물 외부 설치'",
      "6m 골목도로(서측): 기사 '6m 도로 활용 지브 조립·인양'",
      "인접: 방배현대홈타운 2차(동측, 도면+지도), 남북 밀집 다세대(지도 추정)",
      "대지 방위·인접건물 형상은 가정값(직사각형 확실, 회전각은 위성 미확정). 길A 프레이밍: 결정변수 무관 입력"
    ]
  },
  "coordinate_system":{"origin":"site centroid","x_axis":"East (+)","y_axis":"North (+)","unit":"meter"},
  "lot_vertices":[[round(a,2),round(b,2)] for a,b in lot],
  "planned_building":{
    "footprint_box":footprint_box,
    "height_m":36.6,"floors":8,"structure":"RC",
    "method":"기계식주차+RC, 외부 타워크레인",
    "use":"오피스텔+근린생활시설 8F/B1 (도시형생활주택)"
  },
  "adjacent_buildings":adjacent,
  "roads":[
    {"key":"west_alley","name":"서측 6m 골목도로 (지브 조립 활용)",
     "polygon":west_road,"width_m":6.0,
     "source":"verified(기사: 6m 도로 활용)","occupation_allowed":True}
  ],
  "lift_points":{"building_grid":{"nx":4,"ny":4},"material_yard":[round(-hw-3,2),0.0]},
  "search_bounds":{"x_range":[round(-hw-7,1),round(hw+3,1)],"y_range":[round(-hh-3,1),round(hh+3,1)]},
  "as_built_crane":{
    "position":crane_actual,
    "model":"FT-80L (무인 러핑 L형)",
    "jib_m":20.0,"mast_height_m":50.0,"slew_radius_m":20.0,
    "mount_type":"external_wall_tie",
    "source":"시공사 설계도면(DWG 입면: 좌측 코어 외벽 밀착) + 한일타워 기사(외부설치) + FT-80L 카탈로그.",
    "note":"외부설치+월브레싱 2단. 크레인 중심=건물 서측 코어 외벽 0.7m 바깥, 남북중앙. 역삼·신사(내부설치)와 구분되는 제3유형."
  }
}

with open("sites/bangbae_2252.json","w") as f:
    json.dump(site,f,ensure_ascii=False,indent=2)
print("\n>>> wrote sites/bangbae_2252.json")
