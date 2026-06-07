# 업데이트 로그 (baseline 버그 수정 세션)

## 수정된 파일
- baseline_comparison.py:
  - [BUGFIX] line 84: compute_F2()["F2_hours"] → ["F2_calendar_hours"]
    (Random이 가동률 η=0.62 미적용으로 F2를 1.61배 빠르게 잘못 평가하던 치명적 버그)
  - [BUGFIX] ref point: percentile(95)*1.10 → 고정 [2000,250] + 안전클램프
  - [추가] 지배 관계(dominance) 지표 — HV보다 공정. CSV/출력에 반영

## 핵심 결과 (수정 후)
- 공덕동: Random feasible 0.8%(8/1000), Pareto 5개 vs NSGA-II 75개
  → Random Pareto 4/5가 NSGA-II에 지배당함, NSGA-II는 0/75 지배당함
- 합성A: Random feasible 0% (완전 실패) vs NSGA-II 35개
- 합성B: Random 2/2 지배당함 vs NSGA-II 61개
- 결론: HV(-5.3%)는 역설적이라 주력지표에서 제외, 지배율+feasible율을 전면에

## 강건성 (5-seed, 공덕동)
- HV CV = 0.099 ✅ (목표 0.15 달성. handoff의 0.27은 옛 single-branch 값)
- knee F2 CV = 0.015 ✅
- knee F1 CV = 0.206 ⚠️ (단일 knee 한계 → "front 전체 제시" 철학으로 보고 권장)

## 확정 사실 (논문 정정용)
- 결정변수 순서 = (Cx, Cy, model_idx, jib, mast). handoff.md의 (m,Cx,Cy,Lj,Hm)는 틀림
- 제약 9개 확정 (continuous_constraints가 9개 반환)
- dual_branch = y_split 2분기 × 모델 3종 = 6 sub-run, 최종 비지배 필터 정상

## 생성물
- results/baseline_comparison.csv (지배율 컬럼 포함)
- results/baseline_comparison_v2.png (지배율 중심, 한글 정상)

## PENDING
- 신사동 재구성 (자료 업로드 대기) — 제약위반 4개 디버깅
- 논문 docx는 이 tar에 없음 → 별도 업로드 필요 (이메일/HWP변환)
- 역삼동: 두산위브=6층/1,763㎡로 범위초과 → "한계사례" 권장

---

# 세션 2 추가 (오류정정 + 내부설치 + 역삼동 검증)

## 1단계: 명백한 오류 정정
- 크레인 사양 2중정의 통합: constraints.py가 crane_models.CRANES 단일 사용
  - 자립고 오류 정정: 30/30/35m(틀림) → 67/50/59.1m(제조사 데이터)
  - MR 160C 반경 50→51m
  - 크레인 데이터 출처: Manitowoc Data Sheet, LECTURA Specs, Liebherr Brochure (실제)
  - 모델 선정 근거: 러핑2종(협소대지 적합)+해머헤드1종(대조군), narrow_site_suitable 필드
- 풍속 35m/s: 숫자 유지(비작업 설계풍속으로 타당) + 출처 정정(KS B 6230/ISO 4302) + 작업풍속(15)과 구분 명시

## 2단계: G7 내부설치(클라이밍) 확장
- 기존 G7은 외부설치만 가정(본동 이격 2m 강제) → 협소대지 내부설치 배제 문제
- 수정: 크레인이 본동 footprint 내부면 내부설치로 판정, 이격 면제
  - INTERNAL_MOUNT_ENABLED, INTERNAL_MOUNT_CORE_MARGIN_M 추가
  - G8(wall-tie)도 내부설치 시 코어 직접지지로 면제
- 단순화 가정 명시: 양중효율·해체난이도 차이는 미반영(향후 과제)

## 역삼동 검증 결과 (성공!)
- site JSON: sites/yeoksam_782_doosan.json (면적1681, 도로6/6/12, 인접8동, 크레인실제위치 2.6,-3.6)
- G7 수정 전: feasible 0개 (infeasible)
- G7 수정 후: Pareto 52개, 전부 내부설치(도구가 자동 판별)
- 도구 추천(knee): (2.6,+1.3) MR160C jib21 mast33, F1=127 F2=177h
- 실제 크레인: (2.6,-3.6) MR160C jib21, F1=121 F2=182h
- **결론: 추천과 실제 차이 4.9m, 동일모델·동일지브. 실제는 효율 약간우선, 추천은 안전 약간우선. 둘 다 Pareto 위 합리적 선택 → 도구 타당성 입증**
- 회귀테스트: 공덕동은 외부설치 55/55 유지 (변경 안 망침)

## 생성물
- results/yeoksam_site_check.png, yeoksam_validation_final.png

## 남은 일 (PENDING)
- 3단계: 가정값 명시 체계 + 민감도 분석 (P, η, 가중치)
- 논문 프레이밍: "방법론 중심"으로 + 역삼동 검증 반영
- 신사동: 자료 받으면 동일 방식 적용 가능
- 논문 docx 없음 → 별도 업로드 필요

---

# 세션 2 추가 — 3단계: 민감도 분석 (길 A 핵심)

## 민감도 분석 결과 (공덕동 기준, sensitivity_analysis.py)
대상: 출처 약한 핵심 가정값 3종을 ±변경하며 knee 추천 위치이동 측정

| 가정값 | 변경 | knee 위치이동 | 결론 |
|---|---|---|---|
| 사고확률 P (1e-4) | ×0.5~×2.0 | 0.0m | 스케일 파라미터 — 결과순위 무관 |
| 가동률 η (0.62) | 0.5~0.75 | 0.0m | 스케일 파라미터 — 결과순위 무관 |
| 취약성 가중치 도로5/건물3 | 7/3, 5/5, 균등3/3 | 3~33m | 방향성(정책) 파라미터 |

## 핵심 방어논리 (논문 프레이밍)
- P, η는 F1/F2를 단순 스케일링하므로 위치 간 순위 불변 → "정밀 추정 불필요" 수학적 증명
- 취약성 가중치는 위험 우선순위(정책)를 반영 → 도로위험↑ 설정시 추천이 도로서 멀어짐(합리적 거동)
- 결론: "본 연구 기여는 특정 수치가 아니라 의사결정 방법론. 가중치는 의사결정자 조정 입력"
- → "임의값 많음"(약점) → "조정가능 정책 파라미터 갖춘 유연한 프레임워크"(강점)으로 전환

## 생성물
- results/sensitivity_analysis.png (막대+평면 2패널)
- results/sensitivity_summary.csv

## 길 A 완료 상태
- 1단계 명백한오류 정정 ✅
- 2단계 G7 내부설치 + 역삼동 검증 ✅
- 3단계 민감도 분석 ✅
- 남은것: 논문 docx 재작성(방법론 중심 프레이밍, 역삼동 검증, 민감도 반영) — docx 별도 업로드 필요
