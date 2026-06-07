"""공덕동 10-seed honest CV 측정 — knee point 안정성 중심"""
import numpy as np, time
from site_loader import load_site
from site_helpers import use_site
site = load_site('sites/gongdeok_256_42.json'); use_site(site)
from optimizer import run_dual_branch_optimization
from pymoo.indicators.hv import Hypervolume

REF = np.array([2000.0, 250.0])
def knee(F):
    if len(F) < 2: return F[0] if len(F) else None, 0
    fn = (F - F.min(0)) / (np.ptp(F, 0) + 1e-9)
    d = np.linalg.norm(fn, axis=1)
    return F[d.argmin()], int(d.argmin())

seeds = [42, 7, 13, 100, 2024, 1, 55, 314, 777, 2025]
hvs, sizes, knee_f1s, knee_f2s, n_in, n_out = [], [], [], [], [], []
t0 = time.time()
for s in seeds:
    r = run_dual_branch_optimization(pop_size=80, n_gen=30, seed=s, verbose=False)
    F = r.F
    hv = float(Hypervolume(ref_point=REF)(F))
    kf, _ = knee(F)
    hvs.append(hv); sizes.append(len(F)); knee_f1s.append(kf[0]); knee_f2s.append(kf[1])
    n_in.append(int((r.branch==0).sum())); n_out.append(int((r.branch==1).sum()))
    print(f"seed {s:>5}: Pareto {len(F):>3} | HV {hv:>9,.0f} | knee F1={kf[0]:>6.1f} F2={kf[1]:>6.1f} | 부지내 {(r.branch==0).sum():>3}/도로 {(r.branch==1).sum():>3}")

def cv(x): return np.std(x)/np.mean(x)
print(f"\n{'='*60}")
print(f"총 {time.time()-t0:.0f}s, {len(seeds)} seeds")
print(f"HV:        mean {np.mean(hvs):>10,.0f}  CV = {cv(hvs):.3f}")
print(f"Pareto크기: mean {np.mean(sizes):>10.1f}  CV = {cv(sizes):.3f}")
print(f"knee F1:   mean {np.mean(knee_f1s):>10.1f}  CV = {cv(knee_f1s):.3f}  std={np.std(knee_f1s):.1f}")
print(f"knee F2:   mean {np.mean(knee_f2s):>10.1f}  CV = {cv(knee_f2s):.3f}  std={np.std(knee_f2s):.1f}")
print(f"\n→ knee F1 CV {cv(knee_f1s):.3f}, knee F2 CV {cv(knee_f2s):.3f} 가 '추천 안정성'의 핵심")
print(f"   (의사결정 도구는 knee 추천이 시드 무관하게 일관돼야 함)")
