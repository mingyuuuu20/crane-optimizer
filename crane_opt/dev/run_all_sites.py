"""
================================================================================
run_all_sites.py
================================================================================
범용화 통합 검증 스크립트
--------------------------------------------------------------------------------
sites/ 폴더의 모든 JSON 부지를 순차적으로 로드하여 NSGA-II 다목적 최적화를
실행하고, 결과를 통일된 표/CSV 로 정리한다.

이것이 "어떤 부지 정보든 입력하면 최적 배치 추천" 약속의 정량 증명.

산출물:
  - results/site_comparison.csv : 부지별 최적해 표
  - results/site_comparison.json: 상세 결과 (Pareto 전체)
  - results/site_<id>_pareto.png: 부지별 Pareto front 시각화 (옵션)

사용법:
  python run_all_sites.py                      # 모든 부지, 기본 파라미터
  python run_all_sites.py --pop 80 --gen 50    # 정밀 모드
  python run_all_sites.py --only gongdeok      # 특정 부지만
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from site_loader import load_site, list_sites
from site_helpers import use_site


MODEL_NAMES = ["Potain_MDT_178", "Potain_MR_160C", "Liebherr_280_HC_L"]
MODEL_SHORT = {"Potain_MDT_178": "MDT 178 (T)",
                "Potain_MR_160C": "MR 160C (러핑 소)",
                "Liebherr_280_HC_L": "280 HC-L (러핑 대)"}


def _find_knee(F_sorted):
    """정규화 (0,0) 기준 최근접 점 인덱스."""
    if len(F_sorted) < 2:
        return 0
    f1 = F_sorted[:, 0]; f2 = F_sorted[:, 1]
    f1n = (f1 - f1.min()) / (f1.max() - f1.min() + 1e-9)
    f2n = (f2 - f2.min()) / (f2.max() - f2.min() + 1e-9)
    return int(np.argmin(f1n**2 + f2n**2))


def run_single_site(site_path, pop=80, n_gen=40, seed=42,
                     algorithm="dual"):
    """단일 부지에서 NSGA-II 실행 후 결과 dict 반환."""
    print(f"\n{'─'*78}")
    site = load_site(site_path)
    print(f"▶ {site.metadata.get('display_name', site_path)}")
    print(f"  부지: {site.SITE.area:.0f}㎡ | 건물 {site.PLANNED_BUILDING.area:.0f}㎡ "
          f"{site.PLANNED_BUILDING_HEIGHT_M:.0f}m {site.PLANNED_BUILDING_FLOORS}층 | "
          f"인접 {len(site.ADJACENT_BUILDINGS)}동 | 도로 {len(site.ROADS)}개")

    use_site(site)

    # late import 로 site 동기화 후에만 optimizer 가 올바른 검색범위 사용
    from optimizer import run_optimization, run_dual_branch_optimization

    t0 = time.time()
    if algorithm == "dual":
        result = run_dual_branch_optimization(
            pop_size=pop, n_gen=n_gen, seed=seed, verbose=False
        )
    else:
        result, _ = run_optimization(
            pop_size=pop, n_gen=n_gen, seed=seed,
            per_model=True, verbose=False
        )
    elapsed = time.time() - t0

    if result is None or result.F is None or len(result.F) == 0:
        print(f"  ❌ feasible solution 0개 — 실행불가성 분석 시작...")
        try:
            from infeasibility_analyzer import grid_scan_min_violation, CONSTRAINT_NAMES
            infeas = grid_scan_min_violation()
            # 최저 위반 모델 추출
            best_model = min(infeas["per_model"].items(),
                              key=lambda kv: kv[1]["min_violation"])
            bm_name, bm_info = best_model
            primary = bm_info["primary_violation"]
            print(f"     · 최소위반 {bm_info['min_violation']:.2f} ({bm_name})")
            print(f"     · 주요 제약: {primary}")
            # 제약 위반 빈도 top 2
            freqs = infeas["per_constraint_freq"]
            top = sorted(enumerate(freqs), key=lambda x: -x[1])[:2]
            print(f"     · Top 제약 빈도: " +
                  ", ".join(f"{CONSTRAINT_NAMES[i].split('  ')[0]}({f}회)" for i, f in top))
            note = f"최소위반 {bm_info['min_violation']:.2f}, 주요제약 {primary.split('  ')[0]}"
        except Exception as e:
            infeas = None
            note = f"No feasible solution; analyzer error: {e}"
        return {
            "site_id": site.metadata.get("site_id"),
            "site_name": site.metadata.get("display_name"),
            "site_area_m2": float(site.SITE.area),
            "bldg_area_m2": float(site.PLANNED_BUILDING.area),
            "bldg_height_m": float(site.PLANNED_BUILDING_HEIGHT_M),
            "bldg_floors": int(site.PLANNED_BUILDING_FLOORS),
            "n_adjacent": len(site.ADJACENT_BUILDINGS),
            "n_roads": len(site.ROADS),
            "n_lift_points": len(site.LIFT_POINTS),
            "n_pareto": 0,
            "elapsed_s": elapsed,
            "feasible": False,
            "note": note,
            "infeasibility_analysis": infeas,
        }

    F = result.F; X = result.X
    order = np.argsort(F[:, 0])
    F_sorted = F[order]; X_sorted = X[order]

    # 대표 3개 해
    safety = {
        "F1": float(F_sorted[0, 0]),  "F2_h": float(F_sorted[0, 1]),
        "x": float(X_sorted[0, 0]),    "y": float(X_sorted[0, 1]),
        "model": MODEL_NAMES[int(X_sorted[0, 2])],
        "jib_m":  float(X_sorted[0, 3]), "mast_m": float(X_sorted[0, 4]),
    }
    knee_i = _find_knee(F_sorted)
    knee = {
        "F1": float(F_sorted[knee_i, 0]), "F2_h": float(F_sorted[knee_i, 1]),
        "x": float(X_sorted[knee_i, 0]), "y": float(X_sorted[knee_i, 1]),
        "model": MODEL_NAMES[int(X_sorted[knee_i, 2])],
        "jib_m":  float(X_sorted[knee_i, 3]), "mast_m": float(X_sorted[knee_i, 4]),
    }
    efficiency = {
        "F1": float(F_sorted[-1, 0]), "F2_h": float(F_sorted[-1, 1]),
        "x": float(X_sorted[-1, 0]),    "y": float(X_sorted[-1, 1]),
        "model": MODEL_NAMES[int(X_sorted[-1, 2])],
        "jib_m":  float(X_sorted[-1, 3]), "mast_m": float(X_sorted[-1, 4]),
    }

    # 모델 분포
    from collections import Counter
    model_counts = dict(Counter(MODEL_NAMES[int(m)] for m in X[:, 2]))

    # 부지 점용 분석
    n_inside_site = int(sum(site.SITE.contains_properly(
        __import__("shapely.geometry", fromlist=["Point"]).Point(float(x), float(y)))
        for x, y in X[:, :2]))
    n_on_road = len(F) - n_inside_site

    print(f"  ✅ Pareto {len(F)}개 ({elapsed:.1f}s)")
    print(f"     F1∈[{F[:,0].min():.1f},{F[:,0].max():.1f}]  "
          f"F2∈[{F[:,1].min():.1f},{F[:,1].max():.1f}]h")
    print(f"     모델: {model_counts}")
    print(f"     부지내 {n_inside_site} / 도로점용 {n_on_road}")
    print(f"     ★ Knee: {MODEL_SHORT[knee['model']]} "
          f"({knee['x']:+.1f},{knee['y']:+.1f}) "
          f"jib={knee['jib_m']:.1f}m mast={knee['mast_m']:.1f}m "
          f"→ F1={knee['F1']:.0f} F2={knee['F2_h']:.1f}h")

    return {
        "site_id": site.metadata.get("site_id"),
        "site_name": site.metadata.get("display_name"),
        "site_area_m2": float(site.SITE.area),
        "bldg_area_m2": float(site.PLANNED_BUILDING.area),
        "bldg_height_m": float(site.PLANNED_BUILDING_HEIGHT_M),
        "bldg_floors": int(site.PLANNED_BUILDING_FLOORS),
        "n_adjacent": len(site.ADJACENT_BUILDINGS),
        "n_roads": len(site.ROADS),
        "n_lift_points": len(site.LIFT_POINTS),
        "n_pareto": int(len(F)),
        "n_inside_site": n_inside_site,
        "n_on_road": n_on_road,
        "model_distribution": model_counts,
        "elapsed_s": elapsed,
        "feasible": True,
        "safety_optimal": safety,
        "knee": knee,
        "efficiency_optimal": efficiency,
        "F_range": [float(F[:,0].min()), float(F[:,0].max())],
        "F2_range": [float(F[:,1].min()), float(F[:,1].max())],
        # full Pareto (for plotting later)
        "_F": F.tolist(),
        "_X": X.tolist(),
    }


def build_comparison_table(results):
    """결과 list → 비교 DataFrame."""
    rows = []
    for r in results:
        row = {
            "site_id":      r["site_id"],
            "name":         r["site_name"],
            "면적(㎡)":     f"{r['site_area_m2']:.0f}",
            "건물(㎡)":     f"{r.get('bldg_area_m2', 0):.0f}",
            "층수":          r.get("bldg_floors", "-"),
            "인접":          r.get("n_adjacent", "-"),
            "도로":          r.get("n_roads", "-"),
            "feasible":     "✓" if r["feasible"] else "✗",
            "Pareto":       r["n_pareto"],
            "부지내/도로":  (f"{r.get('n_inside_site',0)}/{r.get('n_on_road',0)}"
                              if r["feasible"] else "-"),
        }
        if r["feasible"]:
            k = r["knee"]
            row["Knee 모델"]   = MODEL_SHORT.get(k["model"], k["model"])
            row["Knee 위치"]   = f"({k['x']:+.1f},{k['y']:+.1f})"
            row["Knee jib"]    = f"{k['jib_m']:.1f}m"
            row["Knee mast"]   = f"{k['mast_m']:.1f}m"
            row["Knee F1"]     = f"{k['F1']:.0f}"
            row["Knee F2(h)"]  = f"{k['F2_h']:.1f}"
        else:
            # infeasibility 정보 표시
            note = r.get("note", "infeasible")
            row["Knee 모델"]   = "INFEAS"
            row["Knee 위치"]   = note[:30] if note else "-"
            for c in ["Knee jib", "Knee mast", "Knee F1", "Knee F2(h)"]:
                row[c] = "-"
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pop", type=int, default=80,
                         help="population size (default 80)")
    parser.add_argument("--gen", type=int, default=40,
                         help="generations (default 40)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--only", type=str, default=None,
                         help="substring filter for site_id")
    parser.add_argument("--algorithm", choices=["dual", "single"],
                         default="dual",
                         help="dual-branch (recommended) or single-branch")
    parser.add_argument("--sites-dir", default="sites")
    parser.add_argument("--out-dir", default="results")
    args = parser.parse_args()

    site_files = list_sites(args.sites_dir)
    if args.only:
        site_files = [s for s in site_files if args.only in s]
    if not site_files:
        print(f"No site files matched in {args.sites_dir}")
        return

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    print(f"\n{'='*78}")
    print(f"  범용 부지 비교 실행: {len(site_files)}개 부지")
    print(f"  알고리즘: NSGA-II ({args.algorithm}-branch)")
    print(f"  pop={args.pop}, n_gen={args.gen}, seed={args.seed}")
    print(f"{'='*78}")

    results = []
    for sf in site_files:
        r = run_single_site(sf, pop=args.pop, n_gen=args.gen,
                              seed=args.seed, algorithm=args.algorithm)
        results.append(r)

    # 표 출력
    df = build_comparison_table(results)
    print(f"\n{'='*78}")
    print(f"  ▼ 부지 비교 표")
    print(f"{'='*78}")
    print(df.to_string(index=False))

    # 저장
    csv_path = out_dir / "site_comparison.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n→ CSV 저장: {csv_path}")

    # JSON 상세 (full Pareto 포함)
    json_path = out_dir / "site_comparison.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"→ JSON 저장: {json_path}")

    print(f"\n총 시간: {sum(r.get('elapsed_s',0) for r in results):.1f}초")

    return results


if __name__ == "__main__":
    main()
