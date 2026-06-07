"""NSGA-II 경로 F2 vs 직접 compute_F2 일치하는지 교차검증"""
import numpy as np
from site_loader import load_site
from site_helpers import use_site

site = load_site('sites/gongdeok_256_42.json')
use_site(site)
from optimizer import run_dual_branch_optimization, MODEL_LIST
from objectives import compute_F1, compute_F2

# NSGA-II 돌려서 Pareto 해 1개 뽑고, 그 X로 직접 F 재계산
r = run_dual_branch_optimization(pop_size=80, n_gen=30, seed=42, verbose=False)
X, F = r.X, r.F
print(f"NSGA-II Pareto {len(F)}개\n")
print("=== NSGA-II 반환 F  vs  같은 X로 직접 compute_F1/F2 재계산 ===")
print(f"{'idx':>3} {'m':>2} {'Cx':>7} {'Cy':>7} {'jib':>6} | {'F_ret[0]':>9} {'F1_recalc':>9} | {'F_ret[1]':>9} {'F2_recalc':>9}")
for i in range(min(5, len(X))):
    x = X[i]
    m_idx = int(round(x[0])); Cx, Cy, jib = x[1], x[2], x[3]
    mast = x[4] if len(x) > 4 else 45
    model = MODEL_LIST[m_idx]
    f1r = compute_F1((Cx,Cy), model, jib)["F1"]
    f2r = compute_F2((Cx,Cy), model)["F2_hours"]
    print(f"{i:>3} {m_idx:>2} {Cx:>7.2f} {Cy:>7.2f} {jib:>6.1f} | {F[i,0]:>9.1f} {f1r:>9.1f} | {F[i,1]:>9.3f} {f2r:>9.3f}")

print()
print("=== F[:,1] 단위 추정 ===")
print(f"NSGA-II F[:,1] 평균: {F[:,1].mean():.2f}  (이게 152~160 → 시간 단위로 보임)")
print(f"  만약 초(s)였다면 시간변환: {F[:,1].mean()/3600:.4f}h (말 안 됨)")
# decision var 구조 확인
print(f"\nX shape: {X.shape}  (열 개수 = 결정변수 개수)")
print(f"X[0] = {[round(float(v),2) for v in X[0]]}")
