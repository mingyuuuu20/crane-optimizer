"""
================================================================================
app.py — Streamlit 인터랙티브 UI (범용화 v2)
================================================================================
실행: streamlit run app.py

5개 탭:
  ① 부지·환경    : 부지 선택 + 데이터 확인
  ② 크레인 모델  : 3개 후보 모델 사양·Load chart 비교
  ③ 최적화       : NSGA-II 실행 + Pareto front
  ④ 후보 평가    : 사용자 입력 → 12개 제약 자동 검증 + F1·F2 계산
  ⑤ 검증·민감도  : Level 1·3 자동 검증 리포트

NEW (v2): 사이드바에서 부지 선택 가능. 공덕동 또는 합성 부지 (A/B/C) 선택 시
         모든 탭이 자동으로 그 부지 기준으로 작동.
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Circle
from shapely.geometry import Point
import pandas as pd
import os
from pathlib import Path

# 범용 부지 로더
from site_loader import load_site, list_sites
from pathlib import Path as _Path
_SITES_DIR = str(_Path(__file__).parent / "sites")
from site_helpers import use_site

# =============================================================================
# 사이드바: 부지 선택
# =============================================================================
st.set_page_config(
    page_title="협소대지 타워크레인 배치 최적화",
    page_icon="🏗️",
    layout="wide",
)

# 부지 목록 캐시
@st.cache_data
def _list_available_sites():
    items = []
    for sf in list_sites(_SITES_DIR):
        try:
            s = load_site(sf)
            items.append({
                "path": sf,
                "id": s.metadata.get("site_id", Path(sf).stem),
                "name": s.metadata.get("display_name", Path(sf).stem),
            })
        except Exception:
            continue  # 깨진 파일은 건너뜀
    return items

_sites = _list_available_sites()  # 매 실행마다 갱신

with st.sidebar:
    st.header("⚙️ 부지 선택")
    if not _sites:
        st.error("sites/ 폴더에 JSON 부지 정의가 없습니다.")
        st.stop()
    site_names = [s["name"] for s in _sites]
    sel_idx = st.selectbox(
        "분석할 부지를 선택",
        range(len(_sites)),
        format_func=lambda i: site_names[i],
    )
    sel_site_path = _sites[sel_idx]["path"]
    st.caption(f"📁 `{sel_site_path}`")

# 선택한 부지 로드 + 모든 모듈 동기화
try:
    ACTIVE_SITE = load_site(sel_site_path)
    use_site(ACTIVE_SITE)
except Exception as _e:
    st.error(f"부지를 불러오지 못했습니다.\n\n{_e}")
    st.info("다른 부지를 선택하거나, ‘➕ 내 현장 만들기’에서 올바르게 입력해 저장하세요.")
    st.stop()

# import 는 use_site() 이후 — 모듈 내부 캐시 갱신됨
from crane_models import CRANES, get_capacity, effective_max_radius
from constraints import (
    evaluate_crane_placement, continuous_constraints,
)
from objectives import (
    compute_F1, compute_F2, evaluate_objectives,
    VULNERABILITY_WEIGHTS, INCIDENT_PROBABILITY_PER_CYCLE,
    UTILIZATION_FACTOR,
)
from optimizer import MODEL_LIST, run_optimization, run_dual_branch_optimization

# 활성 부지의 변수들을 모듈 레벨 ALIAS 로 (기존 코드 호환)
SITE                       = ACTIVE_SITE.SITE
ADJACENT_BUILDINGS         = ACTIVE_SITE.ADJACENT_BUILDINGS
ROADS                      = ACTIVE_SITE.ROADS
PLANNED_BUILDING           = ACTIVE_SITE.PLANNED_BUILDING
PLANNED_BUILDING_HEIGHT_M  = ACTIVE_SITE.PLANNED_BUILDING_HEIGHT_M
LIFT_POINTS                = ACTIVE_SITE.LIFT_POINTS
MATERIAL_YARD              = ACTIVE_SITE.MATERIAL_YARD
SITE_AREA_OFFICIAL_M2      = ACTIVE_SITE.SITE_AREA_OFFICIAL_M2
ALLOWED_AREA               = ACTIVE_SITE.ALLOWED_AREA

plt.rcParams['axes.unicode_minus'] = False

st.title("🏗️ 도심지 협소대지 타워크레인 배치 최적화")
_meta = ACTIVE_SITE.metadata
st.markdown(
    f"**현재 부지**: {_meta.get('display_name', 'Site')}  "
    f"({SITE_AREA_OFFICIAL_M2:.1f}㎡, {_meta.get('zoning', '용도지역 미상')})  |  "
    f"**알고리즘**: NSGA-II 다목적 최적화  |  "
    f"**캡스톤 디자인** · 건축공학과"
)

st.divider()


# =============================================================================
# 공통 함수 — 부지 다이어그램
# =============================================================================
def draw_site(ax, show_lift_points=True, show_yard=True):
    """부지·건물·도로 기본 다이어그램."""
    for r in ROADS.values():
        coords = list(r["polygon"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#EEE",
                                  edgecolor="#999", linewidth=0.5, zorder=2))
    for direction, b in ADJACENT_BUILDINGS.items():
        coords = list(b["footprint"].exterior.coords)
        ax.add_patch(MplPolygon(coords, facecolor="#888",
                                  edgecolor="black", linewidth=0.8,
                                  alpha=0.55, zorder=3))
        c = b["footprint"].centroid
        ax.text(c.x, c.y, f"{direction}\n{b['floors']}F",
                ha="center", va="center", fontsize=7,
                color="white", fontweight="bold", zorder=4)
    site_xy = list(SITE.exterior.coords)
    ax.add_patch(MplPolygon(site_xy, facecolor="#FFF3CD",
                              edgecolor="red", linewidth=2.5, zorder=5))
    pb_xy = list(PLANNED_BUILDING.exterior.coords)
    ax.add_patch(MplPolygon(pb_xy, facecolor="#1976D2",
                              edgecolor="#0D47A1", linewidth=1.5,
                              alpha=0.4, zorder=6))
    if show_lift_points:
        for i, p in enumerate(LIFT_POINTS, 1):
            color = "#FFEB3B" if i < len(LIFT_POINTS) else "#FF5722"
            marker = "o" if i < len(LIFT_POINTS) else "s"
            ax.scatter(p[0], p[1], s=80, c=color, marker=marker,
                        edgecolors="black", linewidths=1, zorder=8)
    ax.set_aspect("equal")
    ax.grid(alpha=0.25)


# =============================================================================
# 탭 정의
# =============================================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "① 부지·환경", "② 크레인 모델", "③ 최적화 (NSGA-II)",
    "④ 후보 평가", "⑤ 검증·민감도", "➕ 내 현장 만들기"
])


# =============================================================================
# ① 부지·환경 탭
# =============================================================================
with tab1:
    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.subheader("부지 다이어그램")
        fig, ax = plt.subplots(figsize=(9, 9))
        draw_site(ax)
        sb = ACTIVE_SITE.SEARCH_BOUNDS
        ax.set_xlim(sb["x_range"][0] - 8, sb["x_range"][1] + 8)
        ax.set_ylim(sb["y_range"][0] - 6, sb["y_range"][1] + 6)
        ax.set_xlabel("X (East, m)")
        ax.set_ylabel("Y (North, m)")
        ax.set_title(
            f"{_meta.get('display_name', 'Site')} — Site & Surroundings",
            fontsize=11, fontweight="bold"
        )
        st.pyplot(fig)
        plt.close(fig)

    with col2:
        st.subheader("부지 정보")
        st.metric("대지면적", f"{SITE_AREA_OFFICIAL_M2:.1f} m²")
        st.metric("용도지역", _meta.get("zoning", "—"))
        far = _meta.get("FAR_pct")
        st.metric("용적률 한도", f"{far}%" if far else "—")

        st.subheader("신축 건물")
        c1, c2 = st.columns(2)
        c1.metric("층수", f"{ACTIVE_SITE.PLANNED_BUILDING_FLOORS} 층")
        c1.metric("건폐율",
                   f"{100*PLANNED_BUILDING.area/SITE_AREA_OFFICIAL_M2:.0f}%")
        c2.metric("높이", f"{PLANNED_BUILDING_HEIGHT_M:.0f} m")
        floor_area = PLANNED_BUILDING.area * ACTIVE_SITE.PLANNED_BUILDING_FLOORS
        c2.metric("연면적 (추정)", f"~{floor_area:,.0f} m²")

        if ADJACENT_BUILDINGS:
            st.subheader("인접 건물")
            adj_df = pd.DataFrame([
                {"방향": d, "이름": b["name"], "층수": b["floors"],
                 "높이(m)": b["height_m"], "데이터 출처": b["source"]}
                for d, b in ADJACENT_BUILDINGS.items()
            ])
            st.dataframe(adj_df, hide_index=True, use_container_width=True)

        if ROADS:
            st.subheader("도로")
            road_df = pd.DataFrame([
                {"도로": r["name"], "폭(m)": r["width_m"],
                 "점용가능": "✓" if r["occupation_allowed"] else "✗",
                 "출처": r["source"]}
                for r in ROADS.values()
            ])
            st.dataframe(road_df, hide_index=True, use_container_width=True)


# =============================================================================
# ② 크레인 모델 탭
# =============================================================================
with tab2:
    st.subheader("후보 모델 사양 비교")

    spec_df = []
    for mid, spec in CRANES.items():
        spec_df.append({
            "모델": spec["name"],
            "종류": spec["type"],
            "최대 능력(t)": spec["max_load_kgf"]/1000,
            "최대 반경(m)": spec["max_radius_m"],
            "끝단 능력(t)": spec["load_at_max_radius_kgf"]/1000,
            "카운터지브(m)": spec["counter_jib_length_m"],
            "자립 한계(m)": spec["free_standing_height_m"],
            "협소대지 적합": "✅" if spec["narrow_site_suitable"] else "❌",
            "출처": spec["source"][:40] + "...",
        })
    st.dataframe(pd.DataFrame(spec_df), hide_index=True, use_container_width=True)

    st.subheader("Load Chart 비교")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    colors = {"Potain_MDT_178": "#D32F2F",
              "Potain_MR_160C": "#1976D2",
              "Liebherr_280_HC_L": "#388E3C"}
    labels = {"Potain_MDT_178": "Potain MDT 178 (T)",
              "Potain_MR_160C": "Potain MR 160C (Lf)",
              "Liebherr_280_HC_L": "Liebherr 280 HC-L (Lf)"}

    for ax, scale in zip(axes, ["linear", "log"]):
        for mid, spec in CRANES.items():
            rs = [pt[0] for pt in spec["load_chart"]]
            ws = [pt[1]/1000 for pt in spec["load_chart"]]
            ax.plot(rs, ws, "o-", color=colors[mid], label=labels[mid],
                     linewidth=2, markersize=5)
        ax.axhline(y=3.4, color="black", linestyle="--",
                    linewidth=1.5, label="Required: 3.4t")
        ax.set_xlabel("Working radius (m)")
        ax.set_ylabel("Lifting capacity (t)")
        ax.set_yscale(scale)
        ax.set_title(f"{'Linear' if scale=='linear' else 'Log'} scale")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3, which="both")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    st.info(
        "**핵심**: 우리 케이스 요구 양중 3.0t + 후크블록·리깅 = **3.4t**. "
        "세 모델 모두 약 30~50m 반경 내에서 충족하지만, "
        "T형은 카운터지브 17m 자유회전으로 협소대지 부적합."
    )


# =============================================================================
# ③ 최적화 (NSGA-II) 탭
# =============================================================================
with tab3:
    st.subheader("NSGA-II 다목적 최적화")

    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        pop_size = st.slider("Population size", 20, 200, 80, step=20)
    with col_b:
        n_gen = st.slider("Generations", 10, 100, 40, step=10)
    with col_c:
        st.markdown("&nbsp;")
        run_btn = st.button("🚀 NSGA-II 실행", type="primary", use_container_width=True)

    # 캐시된 결과 사용 또는 새로 실행
    @st.cache_resource(show_spinner=False)
    def cached_optimization(pop, gen, seed=42):
        return run_optimization(pop_size=pop, n_gen=gen, seed=seed, verbose=False)

    # 결과는 세션 상태에 보관 (클라우드 다중 사용자 안전, 파일 미사용)
    if run_btn:
        with st.spinner(f"NSGA-II 실행 중... (예상 {pop_size*n_gen//1000+1}초)"):
            result, _ = cached_optimization(pop_size, n_gen)
            F = result.F
            X = result.X
            if F is not None and len(F) > 0:
                st.session_state["opt_F"] = F
                st.session_state["opt_X"] = X
        st.success(f"완료! Pareto front 크기: {len(F) if F is not None else 0}")
    elif st.session_state.get("opt_F") is not None:
        F = st.session_state["opt_F"]; X = st.session_state["opt_X"]
        st.info(f"💾 이전 실행 결과 표시 중 (n={len(F)}) — 다시 실행하려면 위 버튼")
    else:
        F = None; X = None

    if F is not None and len(F) > 0:
        order = np.argsort(F[:, 0])
        F_sorted = F[order]; X_sorted = X[order]

        # 대표 3개
        idx_min_f1 = 0
        idx_min_f2 = len(F_sorted) - 1
        # robust knee: 페널티성 이상치(F1·F2 중앙값+6*MAD 초과) 제외 후 원점최근접
        _keep = np.ones(len(F_sorted), dtype=bool)
        for _j in (0, 1):
            _col = F_sorted[:, _j]; _med = np.median(_col)
            _mad = np.median(np.abs(_col - _med)) + 1e-9
            _keep &= _col <= _med + 6.0 * 1.4826 * _mad
        if _keep.sum() < max(3, len(F_sorted) // 2):
            _keep = np.ones(len(F_sorted), dtype=bool)
        _idxmap = np.where(_keep)[0]
        _Ff = F_sorted[_keep]
        f1_norm = (_Ff[:, 0] - _Ff[:, 0].min()) / (_Ff[:, 0].max() - _Ff[:, 0].min() + 1e-9)
        f2_norm = (_Ff[:, 1] - _Ff[:, 1].min()) / (_Ff[:, 1].max() - _Ff[:, 1].min() + 1e-9)
        idx_knee = int(_idxmap[int(np.argmin(f1_norm**2 + f2_norm**2))])

        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("### Pareto Front")
            fig, ax = plt.subplots(figsize=(8, 6))
            mc = {0: "#D32F2F", 1: "#1976D2", 2: "#388E3C"}
            ml = {0: "MDT 178 (T)", 1: "MR 160C (Lf)", 2: "280 HC-L (Lf)"}
            for m_idx, color in mc.items():
                mask = np.array([int(X[i, 2]) == m_idx for i in range(len(X))])
                if mask.sum() > 0:
                    ax.scatter(F[mask, 0], F[mask, 1],
                                c=color, s=60, alpha=0.65,
                                label=f"{ml[m_idx]} (n={mask.sum()})",
                                edgecolors="black", linewidths=0.5)
            ax.plot(F_sorted[:, 0], F_sorted[:, 1], "k--",
                     linewidth=0.7, alpha=0.4)

            reps = [
                (idx_min_f1, "Min F1 (Safety)", "red"),
                (idx_knee, "Knee (Balanced)", "blue"),
                (idx_min_f2, "Min F2 (Efficiency)", "green"),
            ]
            for idx, label, c in reps:
                f1, f2 = F_sorted[idx]
                ax.scatter(f1, f2, s=280, marker="*", c=c,
                            edgecolors="black", linewidths=2, zorder=10)
            ax.set_xlabel("F1 (Risk Index)")
            ax.set_ylabel("F2 (Cycle hours)")
            ax.legend(fontsize=8)
            ax.grid(alpha=0.3)
            st.pyplot(fig)
            plt.close(fig)

        with col2:
            st.markdown("### 부지 위 대표 위치")
            fig, ax = plt.subplots(figsize=(8, 6))
            draw_site(ax)
            for idx, label, c in reps:
                x, y, m_idx, jib, mast = X_sorted[idx]
                ax.scatter(x, y, s=350, marker="*", c=c,
                            edgecolors="black", linewidths=2, zorder=20)
                circle = Circle((x, y), jib, fill=False,
                                 edgecolor=c, linewidth=2,
                                 linestyle="--", alpha=0.6, zorder=15)
                ax.add_patch(circle)
            sb = ACTIVE_SITE.SEARCH_BOUNDS
            ax.set_xlim(sb["x_range"][0] - 8, sb["x_range"][1] + 8)
            ax.set_ylim(sb["y_range"][0] - 6, sb["y_range"][1] + 6)
            ax.set_xlabel("X (East, m)")
            ax.set_ylabel("Y (North, m)")
            st.pyplot(fig)
            plt.close(fig)

        # 대표 3개 카드
        st.markdown("### 🏆 대표 해 3가지")
        rep_cols = st.columns(3)
        for col, (idx, label, c) in zip(rep_cols, reps):
            x, y, m_idx, jib, mast = X_sorted[idx]
            f1, f2 = F_sorted[idx]
            model = MODEL_LIST[int(m_idx)].replace("_", " ")
            with col:
                st.markdown(f"#### {label}")
                st.metric("F1 (Risk)", f"{f1:.1f}")
                st.metric("F2 (시간)", f"{f2:.1f}h ({f2/8:.1f}일)")
                st.text(f"위치: ({x:.1f}, {y:.1f})")
                st.text(f"모델: {model}")
                st.text(f"지브: {jib:.1f}m  마스트: {mast:.1f}m")

        # 전체 해 테이블 (top 20)
        with st.expander(f"📋 Pareto front 전체 {len(F)}개 해 보기"):
            table = []
            for idx in order:
                x, y, m_idx, jib, mast = X[idx]
                f1, f2 = F[idx]
                table.append({
                    "x": f"{x:.2f}", "y": f"{y:.2f}",
                    "모델": MODEL_LIST[int(m_idx)].replace("_", " "),
                    "지브(m)": f"{jib:.1f}",
                    "마스트(m)": f"{mast:.1f}",
                    "F1": f"{f1:.1f}",
                    "F2(시간)": f"{f2:.1f}",
                    "F2(일)": f"{f2/8:.1f}",
                })
            st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)

        # ---- PDF 검토 보고서 생성 ----
        st.markdown("---")
        st.markdown("#### 📄 검토 보고서 (PDF)")
        st.caption("현재 부지·최적화 설정으로 전문 검토 보고서(PDF)를 생성합니다.")
        if st.button("📄 PDF 보고서 생성", type="primary", use_container_width=True):
            with st.spinner("보고서 생성 중... (최적화 + 그림 + PDF, 약 1분)"):
                try:
                    import report_generator as RG
                    out_pdf, rctx = RG.run_report(sel_site_path,
                                                   pop=pop_size, gen=n_gen, seed=42)
                    with open(out_pdf, "rb") as f:
                        st.session_state["report_pdf"] = f.read()
                    st.session_state["report_name"] = out_pdf.split("/")[-1]
                    st.success(f"보고서 생성 완료: {st.session_state['report_name']}")
                except Exception as e:
                    st.error(f"보고서 생성 실패: {e}")
        if st.session_state.get("report_pdf"):
            st.download_button(
                "⬇️ 보고서 PDF 다운로드",
                data=st.session_state["report_pdf"],
                file_name=st.session_state.get("report_name", "report.pdf"),
                mime="application/pdf",
                use_container_width=True,
            )


# =============================================================================
# ④ 후보 평가 탭
# =============================================================================
with tab4:
    st.subheader("크레인 배치 후보 수동 평가")
    st.markdown("위치·모델·지브·마스트를 입력하면 12개 제약 검증 + F1·F2 자동 계산")

    col_in, col_vis = st.columns([1, 1.3])

    with col_in:
        st.markdown("#### 입력")
        sb = ACTIVE_SITE.SEARCH_BOUNDS
        x_input = st.slider("Crane X (m)",
                              float(sb["x_range"][0]), float(sb["x_range"][1]),
                              0.0, step=0.5)
        y_input = st.slider("Crane Y (m)",
                              float(sb["y_range"][0]), float(sb["y_range"][1]),
                              float(sb["y_range"][1]) * 0.7, step=0.5)
        model_input = st.selectbox("크레인 모델",
                                      MODEL_LIST,
                                      index=1)
        from optimizer import get_search_bounds as _gsb
        _b = _gsb()
        jib_lo, jib_hi   = _b["jib_range"]
        mast_lo, mast_hi = _b["mast_range"]
        jib_input  = st.slider("Jib length (m)",
                                 float(jib_lo), float(jib_hi),
                                 float(min(25.0, jib_hi)), step=0.5)
        mast_input = st.slider("Mast height (m)",
                                 float(mast_lo), float(mast_hi),
                                 float(max(40.0, mast_lo)), step=1.0)

    with col_vis:
        st.markdown("#### 부지 위 배치 시각화")
        fig, ax = plt.subplots(figsize=(8, 7))
        draw_site(ax)

        # 크레인 표시
        ax.scatter(x_input, y_input, s=400, marker="*", c="red",
                    edgecolors="black", linewidths=2, zorder=20)
        circle = Circle((x_input, y_input), jib_input,
                          fill=False, edgecolor="red",
                          linewidth=2, linestyle="--", alpha=0.7, zorder=15)
        ax.add_patch(circle)
        spec = CRANES[model_input]
        if spec["type"] == "hammerhead":
            cj_circle = Circle((x_input, y_input),
                                  spec["counter_jib_length_m"],
                                  fill=False, edgecolor="orange",
                                  linewidth=1.5, linestyle=":",
                                  alpha=0.5, zorder=14)
            ax.add_patch(cj_circle)

        sb = ACTIVE_SITE.SEARCH_BOUNDS
        ax.set_xlim(sb["x_range"][0] - 8, sb["x_range"][1] + 8)
        ax.set_ylim(sb["y_range"][0] - 6, sb["y_range"][1] + 6)
        ax.set_xlabel("X (East, m)")
        ax.set_ylabel("Y (North, m)")
        st.pyplot(fig)
        plt.close(fig)

    # 평가 결과
    st.markdown("#### 평가 결과")

    all_pass, results = evaluate_crane_placement(
        (x_input, y_input), model_input, mast_input, jib_input
    )

    if all_pass:
        st.success("✅ 모든 12개 제약 통과")
    else:
        failed = [k for k, v in results.items() if not v[0]]
        st.error(f"❌ {len(failed)}개 제약 위반: {', '.join(failed)}")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.markdown("**제약조건 검사**")
        for cid, (passed, msg) in results.items():
            mark = "✅" if passed else "❌"
            st.text(f"{mark} {cid}: {msg}")

    with col_c2:
        st.markdown("**목적함수**")
        try:
            obj = evaluate_objectives((x_input, y_input), model_input, jib_input)
            st.metric("F1 (제3자 안전 지수)", f"{obj['F1']['F1']:.2f}",
                      help="낮을수록 안전. ISO 31000 framework 기반")
            st.metric("F2 (사이클 타임, 명목)",
                      f"{obj['F2']['F2_hours']:.1f} h",
                      help="순수 기계 작동 시간")
            st.metric("F2 (실 시공일, 가동률 반영)",
                      f"{obj['F2']['F2_calendar_days_at_8h']:.1f} 일",
                      delta=f"가동률 {obj['F2']['utilization_factor']}")

            with st.expander("F1 영역별 기여도"):
                bd_df = pd.DataFrame([
                    {"영역": k,
                     "가중치": f"{b['vulnerability']:.1f}",
                     "면적(m²)": f"{b['area_m2']:.1f}",
                     "위험기여": f"{b['risk_contribution']:.1f}"}
                    for k, b in obj['F1']['breakdown'].items()
                ])
                st.dataframe(bd_df, hide_index=True, use_container_width=True)
        except Exception as e:
            st.warning(f"목적함수 계산 실패: {e}")


# =============================================================================
# ⑤ 검증·민감도 탭
# =============================================================================
with tab5:
    st.subheader("검증 및 민감도 분석")
    st.markdown("""
    - **Level 1**: 코드 적합성 — 12개 제약 자동 검증
    - **Level 3-A**: F1 가중치 ±50% 민감도
    - **Level 3-B**: 사고확률 변동 (1e-5 ~ 1e-3)
    - **Level 3-C**: 가동률 변동 (0.4 ~ 0.85)
    - **Level 3-D**: Monte Carlo 200회 강건성
    """)

    col1, col2, col3 = st.columns(3)
    sb_v = ACTIVE_SITE.SEARCH_BOUNDS
    with col1:
        v_x = st.number_input("Crane X", value=0.0,
                                min_value=float(sb_v["x_range"][0]),
                                max_value=float(sb_v["x_range"][1]))
    with col2:
        v_y = st.number_input("Crane Y", value=float(sb_v["y_range"][1]) * 0.7,
                                min_value=float(sb_v["y_range"][0]),
                                max_value=float(sb_v["y_range"][1]))
    with col3:
        v_model = st.selectbox("모델", MODEL_LIST, index=1, key="val_model")
    from optimizer import get_search_bounds as _gsb2
    _b2 = _gsb2()
    v_jib = st.slider("Jib length",
                       float(_b2["jib_range"][0]), float(_b2["jib_range"][1]),
                       float(min(25.0, _b2["jib_range"][1])),
                       step=0.5, key="val_jib")
    v_mast = st.slider("Mast height",
                         float(_b2["mast_range"][0]), float(_b2["mast_range"][1]),
                         float(max(45.0, _b2["mast_range"][0])),
                         step=0.5, key="val_mast")

    if st.button("📊 검증 리포트 생성", type="primary"):
        with st.spinner("Monte Carlo 200회 실행 중..."):
            from validation import (
                level1_compliance_check, sensitivity_F1_weights,
                sensitivity_incident_probability, sensitivity_utilization,
                monte_carlo_sensitivity
            )

            L1 = level1_compliance_check((v_x, v_y), v_model, v_mast, v_jib, verbose=False)
            sens_w = sensitivity_F1_weights((v_x, v_y), v_model, v_jib)
            sens_p = sensitivity_incident_probability((v_x, v_y), v_model, v_jib)
            sens_u = sensitivity_utilization((v_x, v_y), v_model)
            mc = monte_carlo_sensitivity((v_x, v_y), v_model, v_jib, n_trials=200)

        # Level 1
        st.markdown("### Level 1: 적합성")
        if L1['overall_pass']:
            st.success(f"✅ 통과: {L1['n_passed']}/{L1['n_passed']+L1['n_failed']}")
        else:
            st.error(f"❌ 위반: {L1['n_failed']}개 (실패: {L1['failed_constraints']})")

        # Level 3-A
        st.markdown("### Level 3-A: F1 가중치 민감도 (±50%)")
        sens_df = pd.DataFrame([
            {"카테고리": cat,
             "+50% F1": f"{p['F1_high']:.1f}",
             "-50% F1": f"{p['F1_low']:.1f}",
             "민감도지수(%)": f"{p['sensitivity_index']:.1f}"}
            for cat, p in sens_w['perturbations'].items()
        ])
        st.dataframe(sens_df, hide_index=True, use_container_width=True)

        # Level 3-D Monte Carlo
        st.markdown("### Level 3-D: Monte Carlo 강건성 (n=200)")
        col_mc1, col_mc2 = st.columns(2)
        with col_mc1:
            st.metric("F1 평균", f"{mc['F1']['mean']:.1f}",
                      delta=f"σ={mc['F1']['std']:.1f}")
            st.text(f"90% 구간: [{mc['F1']['p5']:.1f}, {mc['F1']['p95']:.1f}]")
            cv_f1 = mc['F1']['cv']
            verdict_f1 = "✅ 강건" if cv_f1 < 0.3 else "⚠️ 보통" if cv_f1 < 0.6 else "❌ 취약"
            st.text(f"CV = {cv_f1:.2f} → {verdict_f1}")
        with col_mc2:
            st.metric("F2 평균 (일)", f"{mc['F2_days']['mean']:.1f}",
                      delta=f"σ={mc['F2_days']['std']:.1f}")
            st.text(f"90% 구간: [{mc['F2_days']['p5']:.1f}, {mc['F2_days']['p95']:.1f}]")
            cv_f2 = mc['F2_days']['cv']
            verdict_f2 = "✅ 강건" if cv_f2 < 0.3 else "⚠️ 보통"
            st.text(f"CV = {cv_f2:.2f} → {verdict_f2}")


# =============================================================================
# ➕ 내 현장 만들기 탭 (폼 입력 + 실시간 미리보기 + JSON 저장)
# =============================================================================
with tab6:
    st.subheader("내 현장 만들기")
    st.caption("대지·건물·인접·도로를 입력하면 미리보기가 갱신됩니다. 저장하면 ① 부지 선택 목록에 추가됩니다.")
    import json as _json
    from matplotlib.patches import Polygon as _MplPoly, Rectangle as _Rect

    cL, cR = st.columns([1, 1])
    with cL:
        nm = st.text_input("현장 이름", "내 현장", key="nb_name")
        locn = st.text_input("위치(주소, 선택)", "", key="nb_loc")

        st.markdown("**대지 형상**")
        lot_mode = st.radio("입력 방식", ["간편(가로×세로)", "꼭짓점 직접"],
                            horizontal=True, key="nb_lotmode")
        if lot_mode == "간편(가로×세로)":
            cw, ch = st.columns(2)
            lw = cw.number_input("가로 W (m, 동서)", 5.0, 200.0, 40.0, 1.0, key="nb_w")
            lh = ch.number_input("세로 H (m, 남북)", 5.0, 200.0, 30.0, 1.0, key="nb_h")
            lot = [[-lw/2, -lh/2], [lw/2, -lh/2], [lw/2, lh/2], [-lw/2, lh/2]]
        else:
            st.caption("대지중심(0,0) 기준, 반시계 방향 꼭짓점 (m)")
            lot_df = st.data_editor(
                pd.DataFrame({"x": [-20.0, 20.0, 20.0, -20.0],
                              "y": [-15.0, -15.0, 15.0, 15.0]}),
                num_rows="dynamic", key="nb_lotdf", use_container_width=True)
            lot = [[float(r["x"]), float(r["y"])] for _, r in lot_df.iterrows()
                   if pd.notna(r["x"]) and pd.notna(r["y"])]

        st.markdown("**신축 건물** (footprint, 대지중심 기준 m)")
        b1, b2, b3, b4 = st.columns(4)
        bx0 = b1.number_input("xmin", -100.0, 100.0, -12.0, 1.0, key="nb_bx0")
        by0 = b2.number_input("ymin", -100.0, 100.0, -8.0, 1.0, key="nb_by0")
        bx1 = b3.number_input("xmax", -100.0, 100.0, 12.0, 1.0, key="nb_bx1")
        by1 = b4.number_input("ymax", -100.0, 100.0, 9.0, 1.0, key="nb_by1")
        bh1, bh2 = st.columns(2)
        b_h = bh1.number_input("건물 높이 (m)", 3.0, 300.0, 30.0, 1.0, key="nb_bh")
        b_fl = bh2.number_input("층수", 1, 80, 10, 1, key="nb_bfl")

        st.markdown("**인접 건물** (중심 cx,cy + 크기 w,h + 높이/층수)")
        adj_df = st.data_editor(
            pd.DataFrame({"name": ["북측 건물"], "cx": [0.0], "cy": [22.0],
                          "w": [20.0], "h": [10.0], "height_m": [15.0], "floors": [5]}),
            num_rows="dynamic", key="nb_adjdf", use_container_width=True)

        st.markdown("**도로** (폴리곤 사각 범위 + 폭)")
        road_df = st.data_editor(
            pd.DataFrame({"name": ["서측 도로"], "xmin": [-26.0], "ymin": [-15.0],
                          "xmax": [-21.0], "ymax": [15.0], "width_m": [6.0]}),
            num_rows="dynamic", key="nb_roaddf", use_container_width=True)

    # ----- 미리보기 + 저장 -----
    with cR:
        st.markdown("**미리보기**")
        try:
            from shapely.geometry import Polygon as _Poly
            figp, axp = plt.subplots(figsize=(6.5, 6.5))
            # 도로
            for _, r in road_df.iterrows():
                if pd.isna(r["xmin"]):
                    continue
                axp.add_patch(_Rect((r["xmin"], r["ymin"]),
                              r["xmax"]-r["xmin"], r["ymax"]-r["ymin"],
                              fc="#EEEEEE", ec="#999", lw=0.8, zorder=1))
            # 인접
            for _, r in adj_df.iterrows():
                if pd.isna(r["cx"]):
                    continue
                axp.add_patch(_Rect((r["cx"]-r["w"]/2, r["cy"]-r["h"]/2),
                              r["w"], r["h"], fc="#E8B4B4", ec="k",
                              lw=1, alpha=0.55, zorder=2))
                axp.text(r["cx"], r["cy"], str(r["name"])[:8], ha="center",
                         va="center", fontsize=7, fontweight="bold")
            # 대지
            if len(lot) >= 3:
                axp.add_patch(_MplPoly(lot, fc="#FFF3CD", ec="k", lw=2.2, zorder=3))
            # 건물
            axp.add_patch(_Rect((bx0, by0), bx1-bx0, by1-by0,
                          fc="none", ec="#3366CC", lw=1.6, zorder=4))
            axp.text((bx0+bx1)/2, (by0+by1)/2, "신축\n건물", ha="center",
                     va="center", fontsize=8, color="#3366CC", fontweight="bold")
            axp.set_aspect("equal"); axp.grid(alpha=0.3)
            axp.set_xlabel("East (m)"); axp.set_ylabel("North (m)")
            # 범위
            allx = [p[0] for p in lot] + [bx0, bx1]
            ally = [p[1] for p in lot] + [by0, by1]
            for _, r in adj_df.iterrows():
                if pd.notna(r["cx"]):
                    allx += [r["cx"]-r["w"]/2, r["cx"]+r["w"]/2]
                    ally += [r["cy"]-r["h"]/2, r["cy"]+r["h"]/2]
            if allx:
                axp.set_xlim(min(allx)-5, max(allx)+5)
                axp.set_ylim(min(ally)-5, max(ally)+5)
            st.pyplot(figp); plt.close(figp)
        except Exception as e:
            st.warning(f"미리보기 오류: {e}")

        # 면적 계산
        area_val = 0.0
        if len(lot) >= 3:
            try:
                area_val = _Poly(lot).area
            except Exception:
                pass
        st.metric("대지면적", f"{area_val:.0f} m²")

        site_id = st.text_input("저장 파일명 (영문, 확장자 제외)", "my_site", key="nb_fid")
        if st.button("💾 JSON 저장", type="primary", use_container_width=True):
            try:
                adj_list = []
                for i, r in adj_df.iterrows():
                    if pd.isna(r["cx"]):
                        continue
                    adj_list.append({
                        "key": f"adj_{i}", "name": str(r["name"]),
                        "footprint": {"type": "rect", "cx": float(r["cx"]),
                                      "cy": float(r["cy"]), "w": float(r["w"]),
                                      "h": float(r["h"])},
                        "height_m": float(r["height_m"]), "floors": int(r["floors"])})
                road_list = []
                for i, r in road_df.iterrows():
                    if pd.isna(r["xmin"]):
                        continue
                    poly = [[float(r["xmin"]), float(r["ymin"])],
                            [float(r["xmax"]), float(r["ymin"])],
                            [float(r["xmax"]), float(r["ymax"])],
                            [float(r["xmin"]), float(r["ymax"])]]
                    road_list.append({"key": f"road_{i}", "name": str(r["name"]),
                                      "polygon": poly, "width_m": float(r["width_m"]),
                                      "occupation_allowed": True})
                xs = [p[0] for p in lot]; ys = [p[1] for p in lot]
                site_obj = {
                    "metadata": {"site_id": site_id, "display_name": nm,
                                 "location": locn, "official_area_m2": round(area_val, 1)},
                    "coordinate_system": {"origin": "site centroid", "x_axis": "East (+)",
                                          "y_axis": "North (+)", "unit": "meter"},
                    "lot_vertices": [[round(p[0], 2), round(p[1], 2)] for p in lot],
                    "planned_building": {"footprint_box": [bx0, by0, bx1, by1],
                                         "height_m": b_h, "floors": int(b_fl),
                                         "structure": "RC", "use": "신축"},
                    "adjacent_buildings": adj_list,
                    "roads": road_list,
                    "lift_points": {"building_grid": {"nx": 5, "ny": 5},
                                     "material_yard": [round(min(xs)-3, 1), 0.0]},
                    "search_bounds": {"x_range": [round(min(xs)-7, 1), round(max(xs)+7, 1)],
                                       "y_range": [round(min(ys)-3, 1), round(max(ys)+3, 1)]},
                }
                # site_id는 영문/숫자/언더스코어만 (파일명 안전하게)
                import re as _re
                safe_id = _re.sub(r'[^a-zA-Z0-9_]', '_', site_id).strip('_') or 'my_site'
                out_path = str(_Path(__file__).parent / "sites" / f"{safe_id}.json")
                site_obj["metadata"]["site_id"] = safe_id
                with open(out_path, "w", encoding="utf-8") as f:
                    _json.dump(site_obj, f, ensure_ascii=False, indent=2)
                st.success(f"저장 완료: {out_path}  →  ① 부지 선택에서 새로고침 후 사용")
                st.code(_json.dumps(site_obj, ensure_ascii=False, indent=2)[:600] + " ...")
            except Exception as e:
                st.error(f"저장 실패: {e}")


# =============================================================================
# Footer
# =============================================================================
st.divider()
st.caption(
    "출처: KOSHA GUIDE C-104·C-50 / KDS 41 12 00 / 산안기준규칙 / "
    "ISO 31000 / 손승현 외 (2022) 한국건축시공학회지 / "
    "Manitowoc·Liebherr 공식 데이터시트  |  "
    "캡스톤 디자인 — 건축공학과"
)
