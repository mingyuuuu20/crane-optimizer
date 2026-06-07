"""공덕동에서 (1) dual_branch가 두 군집을 찾는지 (2) NSGA-II가 Random을 실제 지배하는지"""
import numpy as np
from site_loader import load_site
from site_helpers import use_site
import baseline_comparison as bc

site = load_site('sites/gongdeok_256_42.json')
use_site(site)
from optimizer import run_dual_branch_optimization

print("=== [1] dual_branch 군집 분석 (seed 42) — branch 정보 ===")
r = run_dual_branch_optimization(pop_size=80, n_gen=30, seed=42, verbose=False)
X, F = r.X, r.F
br = getattr(r, 'branch', None)
Cy = X[:,1]
print(f"전체 Pareto {len(F)}개")
print(f"  Cy<0 (부지내/안전): {(Cy<0).sum()}개,  Cy>=0 (도로점용/효율): {(Cy>=0).sum()}개")
if br is not None:
    br = np.array(br)
    print(f"  branch 라벨 분포: {dict(zip(*np.unique(br, return_counts=True)))}")
print(f"  F2 범위: [{F[:,1].min():.1f}, {F[:,1].max():.1f}]h   F1 범위: [{F[:,0].min():.0f}, {F[:,0].max():.0f}]")

print("\n=== [2] NSGA-II가 Random Pareto를 실제로 지배하는가? ===")
rnd = bc.run_random_search(site, n_samples=1000, seed=42)
Rf, Nf = rnd['F_pareto'], F
def dominates(a, b):  # a가 b를 지배(최소화)
    return np.all(a <= b) and np.any(a < b)
# Random 각 점이 NSGA-II 점 중 하나에 지배당하는가?
dominated = 0
for rp in Rf:
    if any(dominates(np_, rp) for np_ in Nf):
        dominated += 1
print(f"Random Pareto {len(Rf)}개 중 NSGA-II에 지배당하는 점: {dominated}개")
nd2 = 0
for np_ in Nf:
    if any(dominates(rp, np_) for rp in Rf):
        nd2 += 1
print(f"NSGA-II Pareto {len(Nf)}개 중 Random에 지배당하는 점: {nd2}개")

print("\n=== [3] 시드별 두 군집 커버리지 (5 seeds) ===")
for s in [42, 7, 13, 100, 2024]:
    rr = run_dual_branch_optimization(pop_size=80, n_gen=30, seed=s, verbose=False)
    cy = rr.X[:,1]
    n_in, n_road = (cy<0).sum(), (cy>=0).sum()
    print(f"  seed {s:>5}: Pareto {len(rr.F):>3}개 | 부지내 {n_in:>3} / 도로 {n_road:>3} | F2 [{rr.F[:,1].min():.0f},{rr.F[:,1].max():.0f}]")
