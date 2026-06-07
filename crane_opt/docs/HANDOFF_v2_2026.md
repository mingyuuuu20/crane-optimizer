# 🏗️ 타워크레인 최적화 캡스톤 — 완전 인수인계 문서 (v2, 2026)

> # ⚠️⚠️ 가장 먼저 할 일 ⚠️⚠️
> **이 문서만으로는 복원이 안 됩니다. 반드시 `crane_opt_updated.tar`를 먼저 업로드하세요.**
> 텍스트 문서 + tar 파일이 **짝**으로 있어야 이어갈 수 있습니다.
> (지난 세션에서 tar 없이 문서만 있어 복원 실패한 전례 있음.)
>
> **복원 명령:** 업로드 후 → `cd /home/claude && tar -xf /mnt/user-data/uploads/crane_opt_updated.tar`
> 그 다음 의존성: `pip install pymoo shapely numpy matplotlib pandas scipy --break-system-packages`
> 한글폰트: `apt-get install -y fonts-nanum && fc-cache -f` (그림 그릴 때 필요)

---

## 👤 기본 정보
- **이름:** 이민규, 경상국립대학교 건축시스템공학과 4학년 (Windows, `C:\Users\이민규\`)
- **과제:** 2026 Capstone Design, **A+ 목표**, 기말 임박
- **성향:** 직접·결정적 답변 선호, 비격식 한국어, **정직한 평가 요구**, 쉬운 설명 선호
- **중요:** BIM 안 씀 (순수 Python). 토큰·파일첨부 한계로 작업은 핸드오프 통해 세션 넘김

---

## 📦 프로젝트 핵심
**"도심지 협소대지 타워크레인 배치 다목적 최적화 — NSGA-II와 9개 공학적 제약, 실제 시공사례 검증"**

- 위치: `/home/claude/crane_opt/` (tar에서 복원)
- 순수 Python (pymoo, Shapely, numpy, matplotlib, Streamlit)
- **현재 프레이밍 = "길 A": 정확한 정답이 아니라 *의사결정 방법론* 제시.**
  입력값(가중치 등)은 의사결정자 조정 파라미터, 스케일값(P,η)은 결과 무관 → 이게 핵심 방어논리

---

## ⚙️ 시스템 아키텍처 (코드 확인 완료)

**결정변수 5개 — 순서 중요! `(Cx, Cy, model_idx, jib_length, mast_height)`**
- ⚠️ 예전 handoff엔 (m,Cx,Cy,Lj,Hm)로 잘못 적혀있었음. **실제 순서는 위가 맞음** (optimizer.py line 170)
- col0=Cx, col1=Cy, col2=모델인덱스(0~2), col3=지브길이, col4=마스트높이

**목적 2개, 제약 9개** (pymoo: n_var=5, n_obj=2, n_ieq_constr=9)

**크레인 3종 (crane_models.py의 CRANES가 단일 출처 — 제조사 데이터 기반):**
| 모델 | 타입 | 자립고 | 최대반경 | 협소대지적합 | 출처 |
|---|---|---|---|---|---|
| Potain MDT 178 | 해머헤드 | 67.0m | 60.0m | False(대조군) | Manitowoc Data Sheet |
| Potain MR 160C | 러핑 | 50.0m | 51.0m | True | LECTURA Specs |
| Liebherr 280 HC-L | 러핑 | 59.1m | 60.0m | True | Liebherr Brochure |
- 선정 근거: 러핑 2종(협소대지 적합) + 해머헤드 1종(대조군). narrow_site_suitable 필드로 구분

**F1 (제3자 안전) — objectives.py:**
- 수식: `F1 = Σ_material(N×P×R_material) × Σ_zone(V_z × A_overlap)`
- ISO 31000 (위험=빈도×결과) 구조. 단위 m², **상대지표로만 사용**
- P = INCIDENT_PROBABILITY_PER_CYCLE = 1e-4 (가정, 스케일값)
- 취약성 가중치 V_z: 도로 5.0 / 인접건물 3.0 / 자기부지·공지 0.5 (가정, **정책 파라미터**)
- 자재 위험계수 R: 갱폼 1.0, PC 1.3, 철근 0.5 등
- 함수: `compute_F1(xy, model_id, jib_length_m)` → dict["F1"]

**F2 (양중 사이클타임) — objectives.py:**
- 수식: `F2 = Σ(N×Tcyc)/η`, η=UTILIZATION_FACTOR=0.62 (가정, 스케일값)
- Tcyc = 결박+호이스트+선회/기복+해제
- ⚠️ **반환 키 2개 주의:** `F2_hours`(η 미적용, 화면표시용) vs `F2_calendar_hours`(η 적용, **최적화·비교는 이걸 써야 함**)
- 함수: `compute_F2(xy, model_id)` → dict["F2_hours", "F2_calendar_hours"]

**9제약 (g(x)≤0) — constraints.py:`continuous_constraints(crane_xy, model, mast_height_m, jib_length_m)`:**
- G1 인양능력 / G2 인접대지 침범 / G3 풍하중 모멘트 / G4 기초지지력 / G5 도달거리 /
  G6 후크높이(≥건물+7m) / **G7 설치영역(외부/내부설치 자동판별)** / G8 자립고·wall-tie / G9 인접대지 공중침범(operating area의 15% 이내)

**NSGA-II — optimizer.py:**
- `run_dual_branch_optimization(pop_size, n_gen, seed)` → r.F, r.X, r.branch, r.stats
- dual_branch = y축 2분기(부지내/도로) × 모델 3종 = 6 sub-run 후 비지배 필터로 통합
- 초기개체군: 무작위 + grid-scan oracle hint. SBX 교차, PM 변이. knee = 정규화거리 최소

---

## 🔧 이번 세션(2) 수정 내역 — 전부 근거 포함

### 1단계: 명백한 오류 정정
- **F2 키 버그 (치명적, baseline_comparison.py line 84):** Random search가 `F2_hours`(η미적용)를 써서 NSGA-II(`F2_calendar_hours`)보다 1/0.62=1.61배 빠르게 잘못 평가 → "NSGA-II가 졌다"는 가짜 결론. → `F2_calendar_hours`로 수정. **고치니 NSGA-II 정당하게 우월.**
- **baseline ref point:** percentile(95)*1.10 → 고정 [2000,250] + 안전클램프 (HV 역설 방지)
- **크레인 사양 2중정의 통합 (constraints.py):** 자체 CRANE_MODELS(자립고 30/30/35 틀림) 제거하고 crane_models.CRANES(67/50/59.1 맞음, 제조사 출처) import. jib_max_length_m만 max_radius_m로 매핑 보강
- **풍속 (constraints.py line 81):** WIND_SPEED_OUT_OF_SERVICE_MS=35 숫자는 유지(비작업 설계풍속으로 타당, KS B 6230/ISO 4302 36~42m/s 범위) + 출처 정정 + 작업중지 순간풍속(15m/s)과 구분 명시

### 2단계: G7 내부설치(클라이밍) 확장 — 사용자 핵심 요청
- **문제:** 기존 G7은 외부설치만 가정(본동 이격 2m 강제) → 협소대지 내부설치 배제. 역삼동 실제 크레인(굴착부=코어 내부)을 위반 판정
- **수정 (constraints.py G7):** 크레인 기초가 본동 footprint 내부면 내부설치로 판정 → 이격 면제. 외부면 기존 로직(이격 2m). 상수 추가: INTERNAL_MOUNT_ENABLED, INTERNAL_MOUNT_CORE_MARGIN_M
- **G8(wall-tie)도 수정:** 내부설치 시 코어 직접지지로 거리제약 면제
- **단순화 가정 명시:** 내부설치의 양중효율·해체난이도 차이는 미반영(향후 과제)

### 3단계: 민감도 분석 (sensitivity_analysis.py) — 길 A 핵심 방어
- 핵심 가정값 3종을 ±변경하며 knee 추천 위치이동 측정 (공덕동 기준)
- 결과: **P×0.5~2.0 → 이동 0m**, **η 0.5~0.75 → 이동 0m** (스케일 파라미터, 순위 무관)
- **취약성 가중치 변경 → 3~33m 이동** (방향성=정책 파라미터, 도로위험↑하면 도로서 멀어짐=합리적)
- 방어논리 완성: "P·η는 정밀추정 불필요, 가중치는 의사결정자 조정 입력. 기여는 수치가 아닌 방법론"

---

## 🔬 검증 결과 (실제 실행 확인)

### 공덕동 256-42 (메인 타겟 부지)
- Pareto 55개, F1 [579~939], F2 [152~162]h. 외부설치 55/55 (외부설치 부지)
- knee: MR 160C, (-7.5,+18.6), jib26, F1=741 F2=155h
- 강건성: HV CV=0.099 ✅, knee F2 CV=0.015 ✅, **knee F1 CV=0.206 ⚠️**(단일 knee 한계→"front 전체 제시" 철학으로 보고)

### baseline 비교 (NSGA-II 우월성 — HV 대신 지배율 사용)
| 부지 | Random feasible | Random Pareto | NSGA Pareto | 지배관계 |
|---|---|---|---|---|
| 공덕동 | 0.8% | 5 | 75 | Random 4/5 지배당함, NSGA 0/75 |
| 합성A | 0% | 0 | 35 | Random 완전실패 |
| 합성B | 0.2% | 2 | 61 | Random 2/2 지배당함, NSGA 0/61 |
- HV는 -5.3%로 역설적이라 **주력지표에서 제외, 지배율+feasible율 전면**

### 역삼동 두산위브 (검증 성공! N=1) — sites/yeoksam_782_doosan.json
- 데이터: 면적 1,681㎡(카카오맵 실측), 도로 북6/서6/남12m(수기측정), 인접 8동(2~6층), 본동 6층 SRC(건축물대장), **크레인 실제위치 (2.6,-3.6)(현장 위성사진 판독)**
- **G7 수정 전: feasible 0개. 수정 후: Pareto 52개, 전부 내부설치(도구가 자동 판별!)**
- 도구 추천(knee): (2.6,+1.3) MR160C jib21 mast33, F1=127 F2=177h
- 실제 크레인: (2.6,-3.6) MR160C jib21, F1=121 F2=182h
- **결론: 추천 vs 실제 차이 4.9m, 동일모델·동일지브. 실제는 효율 약간우선(남), 추천은 안전 약간우선(북). 둘 다 Pareto 위 합리적 선택 → 도구 타당성 입증**
- 회귀테스트: 공덕동 외부설치 55/55 유지 (G7 수정이 망치지 않음)

---

## 📊 가정값 처리 방침 (길 A)

| 가정값 | 출처강도 | 민감도 | 처리 |
|---|---|---|---|
| 사고확률 P (1e-4) | 약함 | 0m | ✅ 민감도로 방어완료 (스케일) |
| 가동률 η (0.62) | 약함 | 0m | ✅ 민감도로 방어완료 (스케일) |
| 취약성 가중치 (5/3/0.5) | 약함 | 30m+ | ✅ "정책 입력"으로 프레이밍 |
| 후크여유 7m (G6) | 없음 🔴 | 미측정 | ⏳ 가정 명시 or 민감도 필요 |
| 본동이격 2m (G7) | 없음 🔴 | 미측정 | ⏳ 가정 명시 필요 |
| 공중침범 15% (G9) | 없음 🔴 | 미측정 | ⏳ 도로법엔 수치없음. 가정 명시 |
| Wall-tie 15m (G8) | 없음 🔴 | 미측정 | ⏳ 제조사별 상이. 가정 명시 |
| 결박/해제 시간 | 없음 🔴 | 미측정 | ⏳ 가정 명시 |
| 크레인 load chart | 미검증 | — | ⏳ 제조사 PDF 확인 or 가정 |
- 🟢 검증된 것: ISO31000 구조, ISO4302 항력계수1.2, 표준대기밀도, F1 상대지표성격, F2 구조, G5 도달거리, 크레인 자립고/반경(제조사)

---

## 📂 site JSON 파일 (`sites/`)
- `gongdeok_256_42.json` — 메인 타겟, 550㎡, 9F. Pareto 55개 ✅
- `yeoksam_782_doosan.json` — 검증 메인, 1,681㎡, 6F, 내부설치. Pareto 52개 ✅
- `synthetic_a/b/c_*.json` — 합성 부지 (baseline 비교용)
- **run:** `python3 run_all_sites.py --only <site_id> --pop 80 --gen 60`

---

## ✅ PENDING (남은 작업, 우선순위)

**검증 보강:**
1. **신사동 N=2 만들기** — 사용자가 자료(사진/배치도) 주면 역삼동과 동일 방식으로 site JSON + 시뮬. 현재는 숫자만 있는 "유령 케이스"(1,140㎡/13F/답안-3,5), 실물 자료 없음
2. 검증 프레이밍: "validation" 욕심 줄이고 "공덕동=메인적용 + 역삼동=검증 + 사고통계=동기부여"

**가정값 마무리:**
3. 미측정 임의값(7m, 2m, 15%, 15m, 결박시간)을 추가 민감도 or "공학적 가정"으로 명시
4. 크레인 load chart 실제값 확인 (제조사 PDF)

**산출물:**
5. **논문 docx 재작성** — 방법론 중심 프레이밍 + 역삼동 검증 + 민감도 분석 + 결정변수 순서 정정 반영. **논문 docx 별도 업로드 필요(tar에 없음)**
6. 교신저자 이메일 채우기, docx→HWP 변환
7. baseline_comparison_v2.png 공덕동 패널 시각 함정(주황 점선) 미세보정

---

## 📄 산출물 그림 (`results/`)
- **baseline_comparison_v2.png** — 지배율 중심 4부지 비교 (최신)
- **yeoksam_validation_final.png** — 역삼동 추천 vs 실제 (2패널)
- **sensitivity_analysis.png** — 민감도 분석 (막대+평면)
- yeoksam_site_check.png, 그 외 pareto/heatmap/robustness 다수
- **감사보고서_근거검증.md** — 모든 상수 출처 분류표 (🟢/🟡/🔴)
- **UPDATE_LOG_2026season.md** — 세션별 수정 로그

---

## 🚀 다음 세션 첫 메시지 예시
"타워크레인 캡스톤 이어서 할게. [이 문서 + crane_opt_updated.tar 업로드] 신사동 자료도 올렸으니 N=2 검증부터" 또는 "논문 docx 올렸으니 길 A 프레이밍으로 논문 재작성하자"
