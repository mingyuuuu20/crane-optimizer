# 협소대지 타워크레인 배치 최적화 시스템

도심지 협소대지에서 타워크레인을 **어디에·어떤 기종으로** 세울지,
제3자 안전위험과 양중 효율을 동시에 고려해 추천하는 프로그램.

---

## ⭐ 이것만 실행하세요

```bash
pip install -r requirements.txt      # 최초 1회 (라이브러리 설치)
streamlit run app.py                 # 프로그램 실행 → 브라우저 자동 열림
```

브라우저가 열리면:

1. **➕ 내 현장 만들기** 탭에서 대지·건물·인접·도로를 입력하고 저장
2. **① 부지·환경** 탭에서 새 현장 선택
3. **③ 최적화** 탭에서 실행 → **📄 PDF 보고서 생성** → 다운로드

끝. JSON을 손으로 편집할 필요 없습니다.

---

## 폴더 구성

```
app.py                ← 메인 프로그램 (이걸 실행)
run_my_site.py        ← 명령줄로 현장 1개만 빠르게 분석할 때
report_generator.py   ← PDF 보고서 생성 (app에서 자동 호출됨)

(핵심 엔진 — 직접 실행할 필요 없음)
  optimizer.py        : NSGA-II 다목적 최적화
  objectives.py       : 목적함수 F1(안전)·F2(효율)
  constraints.py      : 9개 공학적 제약
  crane_models.py     : 크레인 기종 사양
  site_loader.py      : 현장 데이터 로더
  site_helpers.py     : 현장 적용 헬퍼
  report_figures.py   : 보고서 그림

sites/                ← 현장 데이터(JSON). _TEMPLATE_새현장.json 참고
reports/              ← 생성된 PDF 보고서가 여기 저장됨
results/              ← 분석 그림 출력
dev/                  ← 개발·실험용 스크립트 (실행 불필요)
```

---

## 명령줄 사용 (선택)

웹앱 없이 빠르게:

```bash
python run_my_site.py sites/현장.json          # 추천 위치 + 그림
python report_generator.py sites/현장.json     # PDF 보고서
```

자세한 사용법은 `실행가이드.txt` 참고.

---

## 필요 환경
- Python 3.10 이상
- 라이브러리: numpy, shapely, matplotlib, pandas, pymoo, streamlit, weasyprint
