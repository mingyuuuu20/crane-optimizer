import numpy as np, time
from site_loader import load_site
from site_helpers import use_site
site = load_site('sites/gongdeok_256_42.json'); use_site(site)
from optimizer import run_dual_branch_optimization
from pymoo.indicators.hv import Hypervolume
REF = np.array([2000.0, 250.0])
def knee(F):
    fn=(F-F.min(0))/(np.ptp(F,0)+1e-9); d=np.linalg.norm(fn,axis=1); return F[d.argmin()]
seeds=[42,7,13,100,2024]
hvs,sizes,kf1,kf2=[],[],[],[]
t0=time.time()
for s in seeds:
    r=run_dual_branch_optimization(pop_size=60,n_gen=25,seed=s,verbose=False)
    F=r.F; hv=float(Hypervolume(ref_point=REF)(F)); k=knee(F)
    hvs.append(hv);sizes.append(len(F));kf1.append(k[0]);kf2.append(k[1])
    print(f"seed {s:>5}: Pareto {len(F):>3} | HV {hv:>9,.0f} | knee F1={k[0]:>6.1f} F2={k[1]:>6.1f}")
cv=lambda x:np.std(x)/np.mean(x)
print(f"\n총 {time.time()-t0:.0f}s")
print(f"HV CV={cv(hvs):.3f} | Pareto크기 CV={cv(sizes):.3f} | knee F1 CV={cv(kf1):.3f} | knee F2 CV={cv(kf2):.3f}")
print(f"knee F1: {np.mean(kf1):.0f}±{np.std(kf1):.0f}  |  knee F2: {np.mean(kf2):.0f}±{np.std(kf2):.0f}")
