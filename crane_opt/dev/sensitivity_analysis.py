"""
================================================================================
sensitivity_analysis.py
================================================================================
핵심 가정값(assumption)에 대한 민감도 분석.

목적: "이 값들은 공학적 가정이지만, ±50% 흔들어도 본 방법론(NSGA-II로 도출한
       Pareto front와 knee 추천)의 결론은 강건하다"를 정량 증명.

대상 가정값:
  (A) 사고확률 P (INCIDENT_PROBABILITY_PER_CYCLE, 1e-4)   — F1 스케일
  (B) 가동률 η (UTILIZATION_FACTOR, 0.62)                  — F2 스케일
  (C) 취약성 가중치 비율 (도로5 : 건물3 : 부지0.5)          — F1 방향성 (핵심)

측정 지표:
  - knee 추천 위치 이동거리 (m): 가정값 변경 전후 추천이 얼마나 움직이나
  - knee 모델/지브 변화 여부
  - 추천 위치의 순위 안정성

산출물: results/sensitivity_*.png, results/sensitivity_summary.csv
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
fp = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
fm.fontManager.addfont(fp)
plt.rcParams["font.family"] = fm.FontProperties(fname=fp).get_name()
plt.rcParams["axes.unicode_minus"] = False

from site_loader import load_site
from site_helpers import use_site
import objectives as obj
from optimizer import run_dual_branch_optimization, MODEL_LIST


def knee_of(F, X):
    """Pareto front에서 knee point의 (F, X) 반환."""
    if len(F) < 2:
        return (F[0], X[0]) if len(F) else (None, None)
    fn = (F - F.min(0)) / (np.ptp(F, 0) + 1e-9)
    ki = np.linalg.norm(fn, axis=1).argmin()
    return F[ki], X[ki]


def run_once(site_path, seed=42, pop=60, gen=25):
    site = load_site(site_path)
    use_site(site)
    r = run_dual_branch_optimization(pop_size=pop, n_gen=gen, seed=seed, verbose=False)
    return r.F, r.X


def main():
    SITE_PATH = "sites/gongdeok_256_42.json"  # 메인 타겟 부지로 분석
    print("="*70)
    print("민감도 분석 — 공덕동 256-42 기준")
    print("="*70)

    # 원본값 백업
    P0 = obj.INCIDENT_PROBABILITY_PER_CYCLE
    ETA0 = obj.UTILIZATION_FACTOR
    VW0 = dict(obj.VULNERABILITY_WEIGHTS)

    rows = []

    # ── baseline ──
    F0, X0 = run_once(SITE_PATH)
    k0F, k0X = knee_of(F0, X0)
    print(f"\n[Baseline] P={P0:.0e}, η={ETA0}, 가중치=도로{VW0['road']}/건물{VW0['adjacent_residential']}/부지{VW0['own_site']}")
    print(f"  knee: 위치({k0X[0]:+.1f},{k0X[1]:+.1f}) {MODEL_LIST[int(round(k0X[2]))]} jib{k0X[3]:.0f}, F1={k0F[0]:.0f} F2={k0F[1]:.0f}h")
    base_pos = np.array([k0X[0], k0X[1]])

    # ── (A) 사고확률 P 흔들기 ──
    print(f"\n── (A) 사고확률 P 민감도 (스케일 파라미터 예상) ──")
    for factor in [0.5, 2.0]:
        obj.INCIDENT_PROBABILITY_PER_CYCLE = P0 * factor
        F, X = run_once(SITE_PATH)
        kF, kX = knee_of(F, X)
        shift = np.linalg.norm(np.array([kX[0], kX[1]]) - base_pos)
        print(f"  P×{factor}: knee({kX[0]:+.1f},{kX[1]:+.1f}) jib{kX[3]:.0f}, 위치이동 {shift:.1f}m, F1={kF[0]:.0f}")
        rows.append({"param": f"P×{factor}", "knee_x": round(kX[0],1), "knee_y": round(kX[1],1),
                     "shift_m": round(shift,2), "model": MODEL_LIST[int(round(kX[2]))], "jib": round(kX[3],0)})
    obj.INCIDENT_PROBABILITY_PER_CYCLE = P0

    # ── (B) 가동률 η 흔들기 ──
    print(f"\n── (B) 가동률 η 민감도 (스케일 파라미터 예상) ──")
    for val in [0.50, 0.75]:
        obj.UTILIZATION_FACTOR = val
        F, X = run_once(SITE_PATH)
        kF, kX = knee_of(F, X)
        shift = np.linalg.norm(np.array([kX[0], kX[1]]) - base_pos)
        print(f"  η={val}: knee({kX[0]:+.1f},{kX[1]:+.1f}) jib{kX[3]:.0f}, 위치이동 {shift:.1f}m, F2={kF[1]:.0f}h")
        rows.append({"param": f"eta={val}", "knee_x": round(kX[0],1), "knee_y": round(kX[1],1),
                     "shift_m": round(shift,2), "model": MODEL_LIST[int(round(kX[2]))], "jib": round(kX[3],0)})
    obj.UTILIZATION_FACTOR = ETA0

    # ── (C) 취약성 가중치 비율 흔들기 (핵심 — 방향성에 영향) ──
    print(f"\n── (C) 취약성 가중치 민감도 (방향성 — 핵심) ──")
    scenarios = {
        "도로위험↑(7/3/0.5)": {"road": 7.0, "adjacent_residential": 3.0, "own_site": 0.5, "planned_building": 0.5, "empty": 0.5},
        "건물위험↑(5/5/0.5)": {"road": 5.0, "adjacent_residential": 5.0, "own_site": 0.5, "planned_building": 0.5, "empty": 0.5},
        "균등(3/3/1)":        {"road": 3.0, "adjacent_residential": 3.0, "own_site": 1.0, "planned_building": 1.0, "empty": 1.0},
    }
    for name, w in scenarios.items():
        obj.VULNERABILITY_WEIGHTS = w
        F, X = run_once(SITE_PATH)
        kF, kX = knee_of(F, X)
        shift = np.linalg.norm(np.array([kX[0], kX[1]]) - base_pos)
        print(f"  {name}: knee({kX[0]:+.1f},{kX[1]:+.1f}) jib{kX[3]:.0f}, 위치이동 {shift:.1f}m")
        rows.append({"param": name, "knee_x": round(kX[0],1), "knee_y": round(kX[1],1),
                     "shift_m": round(shift,2), "model": MODEL_LIST[int(round(kX[2]))], "jib": round(kX[3],0)})
    obj.VULNERABILITY_WEIGHTS = VW0

    # ── 요약 ──
    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv("results/sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    print(f"\n{'='*70}")
    print("민감도 요약 (knee 위치이동 거리):")
    print(df.to_string(index=False))
    print(f"\n→ results/sensitivity_summary.csv")

    # 해석
    scale_shifts = [r["shift_m"] for r in rows if r["param"].startswith(("P×","eta"))]
    dir_shifts = [r["shift_m"] for r in rows if not r["param"].startswith(("P×","eta"))]
    print(f"\n📊 해석:")
    print(f"  스케일 파라미터(P,η) 평균 위치이동: {np.mean(scale_shifts):.1f}m (작을수록 강건)")
    print(f"  방향성 파라미터(가중치) 평균 위치이동: {np.mean(dir_shifts):.1f}m")

    np.save('/tmp/sens_base.npy', np.array([k0X[0], k0X[1], k0F[0], k0F[1]]))


if __name__ == "__main__":
    main()
