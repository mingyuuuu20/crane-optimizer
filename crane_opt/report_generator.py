"""
report_generator.py — 타워크레인 배치 검토 보고서 자동 생성

사용법:
    python report_generator.py sites/내현장.json
    python report_generator.py sites/내현장.json --pop 100 --gen 60 --seed 0

결과:
    reports/<현장>_보고서.pdf  (전문 검토 보고서)
"""
import sys, os, argparse, datetime, base64, tempfile
import numpy as np

from site_loader import load_site
from site_helpers import use_site
import objectives, constraints, optimizer
import report_figures as RF

MODEL_NAMES = ["Potain MDT 178", "Potain MR 160C", "Liebherr 280 HC-L"]
MODEL_KEYS  = ["Potain_MDT_178", "Potain_MR_160C", "Liebherr_280_HC_L"]
GNAMES = [("G1", "인양능력", "모든 양중점에서 인양능력 ≥ 요구하중"),
          ("G2", "인접건물 이격", "선회면-인접건물 ≥ 0.6m (KOSHA)"),
          ("G3", "본체 침범", "인접건물 footprint 침범 금지"),
          ("G4", "풍하중 모멘트", "전도모멘트 ≤ 허용 모멘트"),
          ("G5", "도달거리", "전 양중점 도달 (사각지대 없음)"),
          ("G6", "후크 높이", "마스트 높이 ≥ 건물높이 + 여유"),
          ("G7", "설치 영역", "내부/외부 설치 영역 적합"),
          ("G8", "벽체정착", "Wall-tie 가능거리 이내"),
          ("G9", "공중 침범", "선회면 ⊆ 허용영역 (±15%)")]


def b64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def run_report(site_path, pop=100, gen=60, seed=0):
    s = load_site(site_path); use_site(s)
    name = s.metadata.get("display_name", os.path.basename(site_path))
    loc = s.metadata.get("location", "")
    area = s.SITE.area

    # 최적화
    r = optimizer.run_dual_branch_optimization(pop_size=pop, n_gen=gen, seed=seed, verbose=False)
    feasible = (r.F is not None and len(r.F) > 0)

    tmp = tempfile.mkdtemp()
    fig_site = os.path.join(tmp, "site.png")
    RF.fig_site_diagram(s, fig_site)

    ctx = {"name": name, "loc": loc, "area": area, "feasible": feasible,
           "fig_site": b64(fig_site),
           "date": datetime.date.today().strftime("%Y년 %m월 %d일"),
           "pop": pop, "gen": gen, "seed": seed,
           "n_adj": len(s.ADJACENT_BUILDINGS), "n_road": len(s.ROADS),
           "floors": s.PLANNED_BUILDING_INFO.get("floors", "-") if hasattr(s, "PLANNED_BUILDING_INFO") else "-"}

    if feasible:
        f1, f2 = r.F[:, 0], r.F[:, 1]
        ki = optimizer.select_knee(r.F, r.X)
        kx, ky, kmi, kj, km = r.X[ki]
        model_key = MODEL_KEYS[int(kmi)]
        F1d = objectives.compute_F1((kx, ky), model_key, kj)
        F2d = objectives.compute_F2((kx, ky), model_key)
        g = constraints.continuous_constraints(np.array([kx, ky]), model_key, km, kj)

        fig_par = os.path.join(tmp, "par.png"); RF.fig_pareto(r.F, ki, fig_par)
        fig_pla = os.path.join(tmp, "pla.png"); RF.fig_placement(s, (kx, ky), kj, fig_pla)
        fig_f1 = os.path.join(tmp, "f1.png"); RF.fig_f1_breakdown(F1d["breakdown"], fig_f1)

        ctx.update({
            "kx": kx, "ky": ky, "model": MODEL_NAMES[int(kmi)], "jib": kj, "mast": km,
            "F1": F1d["F1"], "F2h": F2d["F2_calendar_hours"], "F2d": F2d["F2_calendar_days_at_8h"],
            "npareto": len(r.F),
            "fig_par": b64(fig_par), "fig_pla": b64(fig_pla), "fig_f1": b64(fig_f1),
            "constraints": [(gn[0], gn[1], gn[2], float(gv), float(gv) <= 1e-6)
                            for gn, gv in zip(GNAMES, g)],
            "all_ok": all(float(gv) <= 1e-6 for gv in g),
        })

    html = build_html(ctx)
    os.makedirs("reports", exist_ok=True)
    base = os.path.splitext(os.path.basename(site_path))[0]
    out_pdf = f"reports/{base}_보고서.pdf"
    from weasyprint import HTML
    HTML(string=html).write_pdf(out_pdf)
    return out_pdf, ctx


def build_html(c):
    feas = c["feasible"]
    # 제약 표 행
    crows = ""
    if feas:
        for gid, gname, gdesc, gval, ok in c["constraints"]:
            badge = '<span class="ok">충족</span>' if ok else '<span class="ng">위반</span>'
            margin = f"{-gval:.2f}" if ok else f"+{gval:.2f}"
            crows += f"<tr><td><b>{gid}</b></td><td>{gname}</td><td>{gdesc}</td><td>{badge}</td><td style='text-align:right'>{margin}</td></tr>"

    result_block = ""
    if feas:
        result_block = f"""
        <div class="section">
          <h2>3. 최적화 결과</h2>
          <div class="reco-box">
            <div class="reco-title">추천 크레인 배치</div>
            <table class="reco">
              <tr><td>설치 좌표</td><td><b>X = {c['kx']:+.1f} m,  Y = {c['ky']:+.1f} m</b> (대지중심 기준)</td></tr>
              <tr><td>추천 기종</td><td><b>{c['model']}</b></td></tr>
              <tr><td>지브 길이</td><td>{c['jib']:.0f} m</td></tr>
              <tr><td>마스트 높이</td><td>{c['mast']:.0f} m</td></tr>
              <tr><td>제3자 안전위험 (F1)</td><td>{c['F1']:.0f}</td></tr>
              <tr><td>양중 사이클타임 (F2)</td><td>{c['F2h']:.0f} 시간 (약 {c['F2d']:.0f} 작업일)</td></tr>
            </table>
          </div>
          <img src="{c['fig_par']}" class="fig"/>
          <p class="cap">그림 2. 다목적 최적화 Pareto Front ({c['npareto']}개 해 중 knee point 선정)</p>
          <img src="{c['fig_pla']}" class="fig"/>
          <p class="cap">그림 3. 추천 크레인 배치 및 작업반경</p>
        </div>

        <div class="section">
          <h2>4. 제3자 안전성 분석</h2>
          <p>추천 배치의 선회면이 덮는 영역을 용도별로 분해한 결과는 다음과 같다. 취약성 가중치는
          도로 5.0, 인접 주거 3.0, 자기 부지·공지 0.5로 부여하였다 (ISO 31000 / KOSHA KRAS 근거).</p>
          <img src="{c['fig_f1']}" class="fig"/>
          <p class="cap">그림 4. 영역별 제3자 안전위험 분해</p>
        </div>

        <div class="section">
          <h2>5. 공학적 제약 검토</h2>
          <p>9개 공학적 제약의 충족 여부는 다음과 같다. 여유값은 제약 한계까지의 여유(양수일수록 안전)를 나타낸다.</p>
          <table class="constr">
            <thead><tr><th>번호</th><th>제약</th><th>내용</th><th>판정</th><th>여유값</th></tr></thead>
            <tbody>{crows}</tbody>
          </table>
          <p class="verdict">{'전체 제약 충족 — 본 배치는 9개 공학적 요건을 모두 만족한다.' if c.get('all_ok') else '일부 제약 미충족 — 아래 위반 항목의 재검토가 필요하다.'}</p>
        </div>

        <div class="section">
          <h2>6. 결론 및 권고</h2>
          <p>본 분석은 제3자 안전위험(F1)과 양중 효율(F2)의 상충 관계를 NSGA-II 다목적 최적화로
          평가하여, 9개 공학적 제약을 만족하는 파레토 최적 배치 중 균형점(knee point)을 추천한다.</p>
          <p>추천 배치는 대지중심 기준 <b>({c['kx']:+.1f}, {c['ky']:+.1f})</b> 위치에 <b>{c['model']}</b>를
          지브 {c['jib']:.0f}m·마스트 {c['mast']:.0f}m로 설치하는 안이다. 본 결과는 설계 초기 단계의
          의사결정 보조 자료이며, 실제 설치 시 현장 측량·지반조사·관련 인허가 검토가 병행되어야 한다.</p>
        </div>
        """
    else:
        result_block = """
        <div class="section">
          <h2>3. 최적화 결과</h2>
          <div class="reco-box" style="border-color:#C0392B">
            <div class="reco-title" style="color:#C0392B">실행 가능한 배치를 찾지 못함</div>
            <p>입력된 부지 조건에서는 9개 공학적 제약을 모두 만족하는 크레인 배치가
            도출되지 않았다. 대지가 과도하게 협소하거나, 인접 구조물·작업반경 제약이
            과한 경우에 해당한다. 부지 입력값(특히 대지·인접 건물 크기, 탐색 범위)을
            재확인하거나, 외부 독립기초·특수 공법의 적용을 검토해야 한다.</p>
          </div>
        </div>
        """

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 18mm 16mm; @bottom-center {{ content: "타워크레인 배치 검토 보고서  ·  {c['name']}  ·  " counter(page) " / " counter(pages); font-size: 8pt; color: #999; }} }}
    body {{ font-family: 'NanumGothic','Noto Sans CJK KR',sans-serif; color: #222; font-size: 10.5pt; line-height: 1.6; }}
    .cover {{ text-align: center; padding-top: 60mm; page-break-after: always; }}
    .cover .kicker {{ color: #C8A24B; font-weight: bold; letter-spacing: 3px; font-size: 12pt; }}
    .cover h1 {{ color: #1F3A5F; font-size: 30pt; margin: 14px 0 6px; line-height: 1.3; }}
    .cover .sub {{ color: #555; font-size: 14pt; margin-bottom: 40px; }}
    .cover .meta {{ color: #333; font-size: 12pt; line-height: 2; margin-top: 30px; }}
    .cover .rule {{ width: 80px; height: 3px; background: #C8A24B; margin: 24px auto; }}
    h2 {{ color: #1F3A5F; font-size: 15pt; border-bottom: 2px solid #C8A24B; padding-bottom: 4px; margin-top: 22px; }}
    .section {{ page-break-inside: avoid; }}
    .fig {{ display: block; width: 78%; margin: 12px auto 4px; }}
    .cap {{ text-align: center; font-size: 8.5pt; color: #777; margin: 0 0 14px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 9.5pt; }}
    .info td {{ padding: 5px 10px; border-bottom: 1px solid #e5e5e5; }}
    .info td:first-child {{ color: #666; width: 32%; }}
    .reco-box {{ border: 2px solid #C8A24B; border-radius: 8px; padding: 6px 18px 14px; background: #FBF6E9; margin: 14px 0; }}
    .reco-title {{ color: #1F3A5F; font-size: 13pt; font-weight: bold; margin: 10px 0; }}
    .reco td {{ padding: 5px 10px; border-bottom: 1px solid #ece2c8; }}
    .reco td:first-child {{ color: #666; width: 38%; }}
    .constr th {{ background: #1F3A5F; color: #fff; padding: 7px; font-size: 9pt; }}
    .constr td {{ padding: 6px 8px; border-bottom: 1px solid #e5e5e5; }}
    .ok {{ background: #2E7D32; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 8.5pt; }}
    .ng {{ background: #C0392B; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 8.5pt; }}
    .verdict {{ background: #EAF2EA; border-left: 4px solid #2E7D32; padding: 10px 14px; margin-top: 12px; font-weight: bold; color: #1b5e20; }}
    </style></head><body>
    <div class="cover">
      <div class="kicker">TOWER CRANE LAYOUT REVIEW</div>
      <h1>타워크레인 배치<br/>검토 보고서</h1>
      <div class="rule"></div>
      <div class="sub">{c['name']}</div>
      <div class="meta">
        분석 일자 : {c['date']}<br/>
        분석 도구 : NSGA-II 다목적 최적화 시스템<br/>
        작성 : 경상국립대학교 건축시스템공학과
      </div>
    </div>

    <div class="section">
      <h2>1. 분석 개요</h2>
      <p>본 보고서는 도심지 협소대지의 타워크레인 배치를 <b>제3자 안전위험</b>과
      <b>양중 효율</b>의 상충 관계로 정식화하고, 9개 공학적 제약을 만족하는
      최적 배치를 다목적 최적화(NSGA-II)로 도출한 결과이다.</p>
      <table class="info">
        <tr><td>대상 현장</td><td>{c['name']}</td></tr>
        <tr><td>위치</td><td>{c['loc'] or '-'}</td></tr>
        <tr><td>대지면적</td><td>{c['area']:.0f} m²</td></tr>
        <tr><td>인접 건물</td><td>{c['n_adj']} 동</td></tr>
        <tr><td>도로</td><td>{c['n_road']} 개소</td></tr>
        <tr><td>최적화 설정</td><td>개체수 {c['pop']}, 세대수 {c['gen']}, seed {c['seed']}</td></tr>
      </table>
    </div>

    <div class="section">
      <h2>2. 부지 현황</h2>
      <img src="{c['fig_site']}" class="fig"/>
      <p class="cap">그림 1. 부지 현황 다이어그램 (대지·신축건물·인접건물·도로·공지)</p>
    </div>

    {result_block}
    </body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--pop", type=int, default=100)
    ap.add_argument("--gen", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    print(f"[보고서 생성] {a.site}  (pop={a.pop}, gen={a.gen}, seed={a.seed})")
    print("최적화 실행 중...")
    out, ctx = run_report(a.site, a.pop, a.gen, a.seed)
    if ctx["feasible"]:
        print(f"  추천: ({ctx['kx']:.1f}, {ctx['ky']:.1f}) {ctx['model']} 지브{ctx['jib']:.0f}m")
    print(f"→ 보고서 생성 완료: {out}")
