"""baseline HV 버그 진단: percentile ref vs 고정 ref 비교"""
import numpy as np
from pymoo.indicators.hv import Hypervolume
from site_loader import load_site
from site_helpers import use_site
import baseline_comparison as bc

site = load_site('sites/gongdeok_256_42.json')
print(f"▶ {site.metadata.get('display_name')}\n")

# Random + NSGA-II 각각 돌리기 (재현)
rnd = bc.run_random_search(site, n_samples=1000, seed=42)
nsga = bc.run_nsga2(site, pop_size=80, n_gen=30, seed=42)

print(f"Random:  feasible {rnd['n_feasible']}/1000, Pareto {rnd['n_pareto']}개")
print(f"NSGA-II: Pareto {nsga['n_pareto']}개\n")

Rf, Nf = rnd['F_pareto'], nsga['F_pareto']
print("=== Pareto 점 분포 (F1, F2) ===")
print(f"Random  F1 range: [{Rf[:,0].min():.0f}, {Rf[:,0].max():.0f}]  F2 range: [{Rf[:,1].min():.1f}, {Rf[:,1].max():.1f}]")
print(f"NSGA-II F1 range: [{Nf[:,0].min():.0f}, {Nf[:,0].max():.0f}]  F2 range: [{Nf[:,1].min():.1f}, {Nf[:,1].max():.1f}]")
print()

# 방법 1: 현재 코드 (percentile 95 * 1.10)
allF = np.vstack([Rf, Nf])
ref_pct = np.array([np.percentile(allF[:,0],95)*1.10, np.percentile(allF[:,1],95)*1.10])
# 방법 2: 고정 이론 최악값 (전 부지 공통)
ref_fixed = np.array([2000.0, 200.0])
# 방법 3: 합친 점들의 진짜 최댓값(nadir) + 마진
ref_nadir = np.array([allF[:,0].max()*1.05, allF[:,1].max()*1.05])

for name, ref in [("percentile(현재버그)", ref_pct), ("고정 [2000,200]", ref_fixed), ("진짜 nadir*1.05", ref_nadir)]:
    hv = Hypervolume(ref_point=ref)
    hr, hn = float(hv(Rf)), float(hv(Nf))
    imp = (hn/hr-1)*100 if hr>0 else float('nan')
    print(f"[{name:22s}] ref=({ref[0]:.0f},{ref[1]:.1f})  HV_Random={hr:>12,.0f}  HV_NSGA={hn:>12,.0f}  개선={imp:+.1f}%")
