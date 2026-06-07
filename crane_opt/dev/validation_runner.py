"""
================================================================================
validation_runner.py
================================================================================
범용 검증 실행기 — 임의 부지에 대해 Level 1·3 검증을 자동 실행
--------------------------------------------------------------------------------

사용:
    python validation_runner.py                   # 모든 부지 (knee point)
    python validation_runner.py --site sites/gongdeok_256_42.json
    python validation_runner.py --candidate -9.6 17.4 Potain_MR_160C 45.5 26.7

산출물:
    results/validation_<site_id>.txt  : 사람이 읽는 리포트
    results/validation_summary.csv    : 다부지 비교 표
"""
import argparse
import json
from pathlib import Path

from site_loader import load_site, list_sites
from site_helpers import use_site


def _find_knee_from_results(site_id, results_json="results/site_comparison.json"):
    """run_all_sites 결과 JSON 에서 knee point 회복."""
    if not Path(results_json).exists():
        return None
    with open(results_json, encoding="utf-8") as f:
        data = json.load(f)
    for r in data:
        if r["site_id"] == site_id and r.get("feasible"):
            return r["knee"]
    return None


def validate_one_site(site_path, candidate=None, out_dir="results"):
    """단일 부지 검증."""
    site = load_site(site_path)
    use_site(site)
    site_id = site.metadata.get("site_id", Path(site_path).stem)
    site_name = site.metadata.get("display_name", site_id)

    print(f"\n{'='*78}")
    print(f"검증: {site_name}")
    print(f"{'='*78}")

    # candidate 자동 선택
    if candidate is None:
        knee = _find_knee_from_results(site_id)
        if knee is None:
            # infeasible 부지일 수도 — infeasibility_analyzer로 min-violation 후보
            try:
                from infeasibility_analyzer import grid_scan_min_violation
                ia = grid_scan_min_violation()
                # 가장 작은 위반 후보
                best = min(ia["per_model"].items(),
                           key=lambda kv: kv[1]["min_violation"])
                bm_name, bm = best
                if bm["xy"] is not None:
                    candidate = (bm["xy"][0], bm["xy"][1], bm_name,
                                 bm["mast_m"], bm["jib_m"])
                    print(f"  (knee 없음 → infeasibility analyzer 최소위반 후보 사용)")
                else:
                    print(f"  ⚠️ 유효 후보 없음")
                    return None
            except Exception as e:
                print(f"  ⚠️ knee point 없음 + infeasibility analyzer 실패: {e}")
                return None
        else:
            candidate = (
                knee["x"], knee["y"], knee["model"],
                knee["mast_m"], knee["jib_m"]
            )

    x, y, model, mast, jib = candidate
    print(f"  후보: ({x:+.2f}, {y:+.2f}) {model} jib={jib:.1f}m mast={mast:.1f}m")

    # Level 1
    from validation import (
        level1_compliance_check,
        sensitivity_F1_weights,
        sensitivity_incident_probability,
        sensitivity_utilization,
        monte_carlo_sensitivity,
    )

    print(f"\n  [Level 1: 코드 적합성 검증]")
    L1 = level1_compliance_check((x, y), model, mast, jib, verbose=False)
    print(f"    overall: {'✅ PASS' if L1['overall_pass'] else '❌ FAIL'} "
          f"({L1['n_passed']}/{L1['n_passed']+L1['n_failed']})")
    if L1["failed_constraints"]:
        print(f"    실패 제약:")
        for fc in L1["failed_constraints"]:
            msg = L1['detailed_results'][fc].get('message', '')
            print(f"      ✗ {fc}: {msg}")

    # Level 3
    print(f"\n  [Level 3: 민감도 분석]")
    print(f"    · F1 가중치 민감도 (±50%) ...")
    try:
        s_w = sensitivity_F1_weights((x, y), model, jib)
        base = s_w["baseline_F1"]
        perts = s_w["perturbations"]
        # 각 가중치별 sensitivity_index 의 평균
        sens_indices = [p["sensitivity_index"] for p in perts.values()]
        cv_w = float(sum(sens_indices) / len(sens_indices) / 100.0)
        max_rel = max(abs(p["rel_change_high_pct"]) for p in perts.values())
        print(f"      baseline F1={base:.1f}, 평균 민감도지수={cv_w*100:.2f}%, 최대 ±{max_rel:.1f}%")
    except Exception as e:
        cv_w = None
        print(f"      ⚠️ 실패: {e}")

    print(f"    · 사고 확률 민감도 ...")
    try:
        s_p = sensitivity_incident_probability((x, y), model, jib)
        cv_p = None
        if "results" in s_p:
            res = s_p["results"]
            base = s_p["baseline"]
            base_f1 = next((r["F1"] for r in res if abs(r["P_incident"] - base) < 1e-12),
                            res[len(res)//2]["F1"])
            max_f1 = max(r["F1"] for r in res)
            min_f1 = min(r["F1"] for r in res)
            cv_p = float((max_f1 - min_f1) / max(abs(base_f1) * 2, 1e-6))
            print(f"      F1 범위 [{min_f1:.0f}, {max_f1:.0f}] (baseline {base_f1:.0f})")
    except Exception as e:
        cv_p = None
        print(f"      ⚠️ 실패: {e}")

    print(f"    · 가동률 민감도 ...")
    try:
        s_u = sensitivity_utilization((x, y), model)
        cv_u = None
        if "results" in s_u:
            res = s_u["results"]
            base = s_u["baseline"]
            base_f2 = next((r["F2_calendar_days"] for r in res if abs(r["utilization"] - base) < 1e-9),
                            res[len(res)//2]["F2_calendar_days"])
            max_f2 = max(r["F2_calendar_days"] for r in res)
            min_f2 = min(r["F2_calendar_days"] for r in res)
            cv_u = float((max_f2 - min_f2) / max(abs(base_f2) * 2, 1e-6))
            print(f"      F2 범위 [{min_f2:.1f}, {max_f2:.1f}]일 (baseline {base_f2:.1f}일)")
    except Exception as e:
        cv_u = None
        print(f"      ⚠️ 실패: {e}")

    print(f"    · Monte Carlo 200회 ...")
    try:
        mc = monte_carlo_sensitivity((x, y), model, jib, n_trials=200)
        # 결과는 dict {mean, std, ...}
        f1_d = mc["F1"]; f2_d = mc["F2_days"]
        cv_mc_f1 = float(f1_d["std"] / max(abs(f1_d["mean"]), 1e-6))
        cv_mc_f2 = float(f2_d["std"] / max(abs(f2_d["mean"]), 1e-6))
        print(f"      F1: mean={f1_d['mean']:.1f} ±{f1_d['std']:.1f} (CV={cv_mc_f1:.3f})")
        print(f"      F2: mean={f2_d['mean']:.2f}일 ±{f2_d['std']:.2f} (CV={cv_mc_f2:.3f})")
    except Exception as e:
        cv_mc_f1 = cv_mc_f2 = None
        print(f"      ⚠️ 실패: {e}")

    # Save text report
    out_dir_p = Path(out_dir); out_dir_p.mkdir(exist_ok=True)
    txt_path = out_dir_p / f"validation_{site_id}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"=== {site_name} — 검증 리포트 ===\n\n")
        f.write(f"후보: ({x:+.2f}, {y:+.2f}) {model}\n")
        f.write(f"      jib={jib:.1f}m, mast={mast:.1f}m\n\n")
        f.write(f"[Level 1] {'PASS' if L1['overall_pass'] else 'FAIL'} "
                f"({L1['n_passed']}/{L1['n_passed']+L1['n_failed']})\n")
        for c_id, c_res in L1['detailed_results'].items():
            mark = '✓' if c_res['passed'] else '✗'
            f.write(f"  {mark} {c_id}: {c_res.get('message', '')}\n")
        f.write(f"\n[Level 3] 민감도\n")
        f.write(f"  F1 CV (가중치 ±20%):  {cv_w}\n")
        f.write(f"  F1 CV (확률 ±50%):    {cv_p}\n")
        f.write(f"  F2 CV (가동률 ±15%):  {cv_u}\n")
        f.write(f"  Monte Carlo F1 CV:    {cv_mc_f1}\n")
        f.write(f"  Monte Carlo F2 CV:    {cv_mc_f2}\n")
    print(f"\n  → {txt_path}")

    return {
        "site_id": site_id, "site_name": site_name,
        "candidate": list(candidate),
        "level1_pass": L1["overall_pass"],
        "n_passed": L1["n_passed"],
        "n_failed": L1["n_failed"],
        "failed_constraints": L1["failed_constraints"],
        "cv_weights": cv_w, "cv_probability": cv_p,
        "cv_utilization": cv_u,
        "cv_mc_F1": cv_mc_f1, "cv_mc_F2": cv_mc_f2,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site")
    parser.add_argument("--candidate", nargs=5,
                         metavar=("X", "Y", "MODEL", "MAST", "JIB"),
                         help="x y model_name mast jib")
    parser.add_argument("--sites-dir", default="sites")
    parser.add_argument("--out-dir", default="results")
    args = parser.parse_args()

    summaries = []

    if args.site:
        cand = None
        if args.candidate:
            cand = (float(args.candidate[0]), float(args.candidate[1]),
                     args.candidate[2],
                     float(args.candidate[3]), float(args.candidate[4]))
        s = validate_one_site(args.site, cand, args.out_dir)
        if s: summaries.append(s)
    else:
        # 전 부지 자동 (run_all_sites 결과 knee 사용)
        for sf in list_sites(args.sites_dir):
            s = validate_one_site(sf, None, args.out_dir)
            if s: summaries.append(s)

    # 비교표 저장
    if summaries:
        import pandas as pd
        df = pd.DataFrame(summaries)
        csv_path = Path(args.out_dir) / "validation_summary.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"\n{'='*78}")
        print(f"  검증 요약")
        print(f"{'='*78}")
        cols = ["site_id", "level1_pass", "n_passed", "n_failed",
                 "cv_mc_F1", "cv_mc_F2"]
        print(df[cols].to_string(index=False))
        print(f"\n→ {csv_path}")


if __name__ == "__main__":
    main()
