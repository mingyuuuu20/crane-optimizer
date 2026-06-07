# 🤝 새 대화 인계 문서 (HANDOFF)

> 이 파일을 새 대화에 첨부하고 **"이 핸드오프 받았어, 계속 진행해줘"** 라고 말하면 됩니다.

---

## 1. 프로젝트 한 줄 요약

> **건축공학과 캡스톤 디자인**: 도심지 협소대지(서울 마포구 공덕동 256-42, 550.6㎡, 준주거지역)에 들어설 9층 도시형생활주택 시공을 위한 타워크레인 배치를 NSGA-II 다목적 최적화로 찾는 설계 프로그램. **사용자 본인은 이민규**(경상국립대 4학년, Windows 환경, A+ 목표).

## 2. 결정 사항 (변경 금지 — 이미 잠긴 것들)

### 부지
- 서울특별시 마포구 공덕동 256-42 (550.6㎡)
- 지목: 대 / 용도지역: 준주거지역 + 지구단위계획구역
- 용적률 400%, 건폐율 60%
- 비정형 부지 (L자형 단순화)

### 시공 시나리오
- 9층 도시형생활주택 + 1·2층 근린생활시설
- RC + 갱폼 + 시스템동바리
- 연면적 약 2,200㎡, 풋프린트 280㎡

### 크레인 후보 모델 3개
1. **Potain MDT 178** (T형, baseline) — 협소대지 부적합 증명용
2. **Potain MR 160C** (러핑 소형) — 우리 케이스 최적 후보
3. **Liebherr 280 HC-L 16/28** (러핑 대형)

### 목적함수 (2-목적 NSGA-II)
- **F1**: 제3자 안전 지수 (ISO 31000 + KOSHA KRAS, 자재별 risk factor 반영)
- **F2**: 양중 사이클 타임 (가동률 0.62 반영, 자재별 차등)

### 제약 12개 (모두 코드화됨)
C1 인양능력 / C2-1 인접 구조물 0.6m 이격 / C2-2 충전전로 0.9m / C2-3 인접대지 침범 금지 / C3-1 정지 풍하중 / C3-2 작업 풍속 / C4-1 기초반력 150kPa / C5 도달거리 / C6 후크높이 ≥39m / C7 설치 영역 / C8 Wall tie / C9 작업시간 / C10 진입로 / C11 단계 가정 / C12 침하 제외

### 양중점 26개 + 자재 5종
- 건물 footprint 5×5 grid (25개) + 야적장 (1개)
- 자재: 갱폼(3t) / 철근(1.5t) / 콘크리트(2t) / PC부재(3.5t) / 마감재(0.5t)
- 총 2,525 cycles

### 핵심 출처 (4계층 권위)
1. **법령**: 산안기준규칙 별표 5의2, 건설기계관리법, 건축법
2. **공공기준**: KOSHA C-104·C-50, KDS 41 12 00, KDS 11 50 05, KS B 6230
3. **국제기준**: ISO 31000, ISO 4302, ISO 4304, FEM 1.001
4. **학술·제조사**: 손승현 외 (2022) 한국건축시공학회지 22(1) — KOSHA 260건 분석 / Manitowoc·Liebherr 공식 데이터

### 검증 체계
- Level 1 (코드 적합성): 자동 (constraints.py)
- Level 2 (케이스 비교): 미수행 — 지도교수 협조 필요
- Level 3 (민감도): 자동 (validation.py + robustness.py)
- Level 4 (전문가): 시간 남으면

---

## 3. 현재 진행 상황

```
[1] 부지 데이터 모델                                      ✅ 완료
[2] 제약 12개 함수 코드화                                 ✅ 완료
[3] 크레인 3개 모델 데이터 (제조사 공식)                  ✅ 완료
[4] F1·F2 목적함수 (자재 다종화 반영)                     ✅ 완료
[5] NSGA-II per-model 모드 (mixed-integer 문제 해결)      ✅ 완료
[6] Streamlit UI 5탭                                      ✅ 완료
[7] 검증 자동화 (Level 1·3)                               ✅ 완료
[8] 양중점 5→26개 세분화                                  ✅ 완료
[9] 자재 다종화 (1→5종)                                   ✅ 완료
[10] 강건성 검증 (10 seed)                                ⚠️ 부분 완료
─────────────────────────────────────────────────────────
[11] 강건성 개선 (n_gen 늘리기, 두 군집 분석)             ⏳ 남음
[12] 한글 시각화 재생성 (Windows 한글 폰트)               ⏳ 남음
[13] V-World 정확한 부지 폴리곤 입력                      ⏳ 본인 작업 (30분)
[14] 발표자료 PPT                                         ⏳ 남음
[15] 중간보고서·최종보고서                                ⏳ 남음
[16] Level 2 케이스 벤치마크                              ⏳ 지도교수 협조
```

대략 **75% 진행**.

---

## 4. ⚠️ 마지막 미해결 이슈

### 강건성 CV가 0.27로 불안정

**현상**: 10개 seed 로 NSGA-II 돌리면 Hypervolume CV = 0.27, knee 위치 표준편차 2~6m로 seed 마다 결과가 흔들림.

**원인 (이미 진단됨)**: 이건 **버그가 아니라 발견**임. 자재 다종화 후 우리 부지에 두 개의 거의 동등한 좋은 영역이 존재함:
- **부지 내 설치** (y ≈ -8): F1 ≈ 410, 안전 우선
- **북측 도로 점용** (y ≈ +15): F1 ≈ 565, 효율 약간 우위

알고리즘이 seed 에 따라 어느 쪽을 더 잘 탐색하느냐가 달라짐.

**해결 방향 (다음 대화에서 처리)**:
- (가) n_gen 을 120~150으로 늘려 두 영역 모두 탐색 보장
- (나) 부지 내 / 도로 점용을 별도 branch 로 명시적 분리해서 각각 최적화 후 합집합
- (다) 두 영역의 trade-off 를 발표 결과로 강조

**제 추천**: (나) — 새 함수 `run_dual_branch_optimization()` 추가하는 게 가장 깔끔. 발표 메시지 강해짐.

---

## 5. 코드 구조

```
crane_opt/
├── site_model.py            (11.4 KB) 부지·건물·도로 + 양중점 26개 + 자재 5종
├── crane_models.py          (11.9 KB) 3개 크레인 모델 사양
├── constraints.py           (22.2 KB) 제약 12개 + continuous_constraints()
├── objectives.py            (14.2 KB) F1·F2 자재별 처리
├── optimizer.py             ( 7.0 KB) NSGA-II per_model 모드 (권장)
├── validation.py            (15.5 KB) Level 1·3 자동 검증
├── robustness.py            (10.6 KB) 다중 seed 강건성 (이전 버전)
├── robustness_test.py       ( 8.9 KB) 다중 seed 강건성 (최신 버전, 권장)
├── app.py                   (21.9 KB) Streamlit UI (5탭)
│
├── visualize.py             부지 다이어그램
├── load_chart_viz.py        Load chart 비교
├── objectives_heatmap.py    F1·F2 히트맵
├── pareto_viz.py            Pareto front + 부지 위치
│
├── *.png                    시각화 산출물 5개
├── pareto_result.npz        최신 NSGA-II 결과
├── robustness_results.csv   강건성 통계
├── validation_report.txt    검증 리포트 예시
├── requirements.txt         의존성
└── README.md                실행 가이드
```

### 핵심 모듈 진입점

```python
# 부지 데이터
from site_model import (
    SITE, ADJACENT_BUILDINGS, ROADS, PLANNED_BUILDING,
    LIFT_POINTS, BUILDING_GRID_POINTS, MATERIAL_YARD,
    LIFT_POINT_MATERIAL_PROFILE, MATERIAL_WEIGHTS, MATERIAL_HANDLING_TIME,
)

# 크레인 모델
from crane_models import CRANES, get_capacity, effective_max_radius

# 제약·목적함수
from constraints import evaluate_crane_placement, continuous_constraints
from objectives import compute_F1, compute_F2, evaluate_objectives

# 최적화 (per_model=True 권장)
from optimizer import run_optimization, summarize_pareto_front, MODEL_LIST

result, _ = run_optimization(pop_size=80, n_gen=60, seed=42, per_model=True)
```

---

## 6. 새 대화에서 다음 작업 우선순위

**(P1) 강건성 개선** — `optimizer.py` 에 `run_dual_branch_optimization()` 함수 추가  
**(P2) 시각화 한글화** — Windows 한글 폰트 (`Malgun Gothic`) 적용 코드 + 발표용 자료 재생성  
**(P3) Pareto 시각화 갱신** — 자재 다종화 + 두 군집 반영한 새 그래프  
**(P4) Streamlit UI 갱신** — 자재 분포 표시 추가, 두 군집 비교 모드  
**(P5) V-World 정확한 부지 폴리곤** (본인 30분 작업 후 좌표 받아 site_model.py 업데이트)  
**(P6) 발표자료 PPT 21슬라이드 초안**  
**(P7) 중간보고서 DOCX**

---

## 7. 사용자 본인 (이민규) 컨텍스트

- 4학년, 경상국립대 건축공학과 (221138120)
- Windows 11 환경 (C:\Users\이민규\)
- 한국어 직설적 소통 선호 (`고고`, `가보자` 같은 짧은 답으로 진행 컨펌)
- A+ 목표
- 자기 부지 V-World/세움터/토지e음 확인 완료
- 학교 강의로 바쁘니까 답변은 간결하게, 결정 위임 받으면 적극적으로 진행

---

## 8. 새 대화 시작 시 첫 응답 가이드

새 대화에서 받은 사용자 첫 메시지가:

- **"인계 받았어 / 이어서 가자"** → 위 P1~P7 중 다음에 뭐 할지 짧게 제안하고 결정 받기
- **"P1부터 가자"** → 바로 `optimizer.py` 에 dual-branch 함수 추가 시작
- **"발표자료부터"** → P6 PPT 초안 작성 시작 (pptx skill 활용)
- **"코드 받아서 돌려봤는데 ___ 안 됨"** → 디버깅 모드

가급적 **선택지 제시 → 짧게 답 받기 → 진행** 패턴 유지.
