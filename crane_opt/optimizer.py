"""
================================================================================
optimizer.py
================================================================================
NSGA-II 다목적 최적화 알고리즘
--------------------------------------------------------------------------------
두 가지 실행 모드:
  (A) 통합 (per_model=False): 5변수 NSGA-II
  (B) 모델별 (per_model=True, 권장): 각 모델로 4변수 독립 실행 후 합집합 Pareto

목적함수: F1 (안전 지수), F2 (사이클 타임)
제약: 8개 (G1~G8, ≤0)
"""

import time
import numpy as np
from pymoo.core.problem import Problem
from pymoo.core.sampling import Sampling
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import FloatRandomSampling

from constraints import continuous_constraints
from objectives import compute_F1, compute_F2

MODEL_LIST = [
    "Potain_MDT_178",       # idx 0 (T형 baseline)
    "Potain_MR_160C",       # idx 1 (러핑 소형)
    "Liebherr_280_HC_L",    # idx 2 (러핑 대형)
]


class HintAwareSampling(Sampling):
    """초기 인구 일부 (기본 25%) 를 grid-scan feasible 후보 근처로 시드.

    좁은 feasible region 에서 NSGA-II 가 영원히 수렴 못 하는 문제를 해결.
    Pure random initialization 의 보완책으로, 학술적으로도 표준 기법
    (seed initialization, warm start, oracle hint).
    """
    def __init__(self, hint_fraction=0.25, n_hint_seeds=8, model_idx=1,
                  seed=None):
        super().__init__()
        self.hint_fraction = hint_fraction
        self.n_hint_seeds = n_hint_seeds
        self.model_idx = model_idx   # 4변수 모드일 때 사용
        self.seed = seed
        self._rng = np.random.default_rng(seed) if seed is not None else np.random

    def _do(self, problem, n_samples, **kwargs):
        xl = problem.xl
        xu = problem.xu
        n_var = problem.n_var
        rng = self._rng

        # 1) random portion
        n_random = int(n_samples * (1 - self.hint_fraction))
        random_part = xl + rng.random((n_random, n_var)) * (xu - xl) \
                       if self.seed is not None \
                       else xl + np.random.rand(n_random, n_var) * (xu - xl)

        # 2) hint portion
        n_hint = n_samples - n_random
        if n_hint <= 0:
            return random_part

        # 모델 결정 (4변수면 fixed, 5변수면 random)
        if n_var == 5:
            model_for_scan = MODEL_LIST[1]  # MR_160C 가 가장 잘 통하는 경향
        else:
            model_for_scan = MODEL_LIST[int(np.clip(self.model_idx, 0, 2))]

        # quick grid scan
        candidates = self._quick_grid_scan(xl, xu, n_var, model_for_scan)
        if not candidates:
            return np.vstack([random_part,
                                xl + rng.random((n_hint, n_var)) * (xu - xl)
                                if self.seed is not None
                                else xl + np.random.rand(n_hint, n_var) * (xu - xl)])

        # 후보 중에서 무작위 선택 + jitter
        hint_part = []
        for i in range(n_hint):
            cand = candidates[i % len(candidates)]
            if self.seed is not None:
                jitter = rng.standard_normal(n_var) * 1.0
            else:
                jitter = np.random.randn(n_var) * 1.0
            seed_arr = np.array(cand) + jitter
            seed_arr = np.clip(seed_arr, xl, xu)
            hint_part.append(seed_arr)
        hint_part = np.array(hint_part)

        return np.vstack([random_part, hint_part])

    def _quick_grid_scan(self, xl, xu, n_var, model_id):
        """grid scan: violation 가장 작은 후보들 반환."""
        candidates_w_viol = []
        for x in np.linspace(xl[0], xu[0], 6):
            for y in np.linspace(xl[1], xu[1], 6):
                jib_lo, jib_hi = xl[-2], xu[-2]
                mast_lo, mast_hi = xl[-1], xu[-1]
                for jib in np.linspace(jib_lo, jib_hi, 4):
                    for mast in np.linspace(mast_lo, mast_hi, 3):
                        try:
                            g = continuous_constraints((x, y), model_id, mast, jib)
                            viol = max(0, float(g.max()))
                            if n_var == 5:
                                m_idx = float(MODEL_LIST.index(model_id)) + 0.5
                                cand = [x, y, m_idx, jib, mast]
                            else:
                                cand = [x, y, jib, mast]
                            candidates_w_viol.append((viol, cand))
                        except Exception:
                            pass
        candidates_w_viol.sort(key=lambda kv: kv[0])
        return [c[1] for c in candidates_w_viol[:self.n_hint_seeds]]

# --- 활성 부지 검색 경계 (범용화) ----------------------------------------
# 기본값은 공덕동 256-42 와 동일 (기존 동작 보존).
# 다른 부지로 전환하려면 set_active_site_bounds(site) 또는 use_site() 호출.
_SEARCH_X_RANGE = (-25.0, 25.0)
_SEARCH_Y_RANGE = (-20.0, 20.0)
_MAST_RANGE     = (39.0, 52.0)
_JIB_RANGE      = (10.0, 60.0)


def set_active_site_bounds(site):
    """SiteData로부터 검색 범위·마스트·지브 범위를 갱신한다."""
    global _SEARCH_X_RANGE, _SEARCH_Y_RANGE, _MAST_RANGE, _JIB_RANGE
    sb = site.SEARCH_BOUNDS
    _SEARCH_X_RANGE = tuple(sb["x_range"])
    _SEARCH_Y_RANGE = tuple(sb["y_range"])
    # 마스트는 건물 높이 + 안전여유 7m ~ +20m (의미 있는 범위로 좁힘)
    # mast 가 F1·F2 에 직접 영향 없으므로, 시공 실무 기준 최소~여유 범위로 제한
    # 즉 mast 는 거의 결정되어 있고, 알고리즘은 x, y, model, jib 위주로 탐색
    h = site.PLANNED_BUILDING_HEIGHT_M
    _MAST_RANGE = (max(h + 7.0, 30.0), max(h + 20.0, 45.0))
    # 지브는 부지 대각선 + 도로폭 여유 — 너무 작으면 최적화 곤란하니 최소 10m 보장
    minx, miny, maxx, maxy = site.ALLOWED_AREA.bounds
    diag = ((maxx - minx) ** 2 + (maxy - miny) ** 2) ** 0.5
    _JIB_RANGE = (10.0, max(diag * 0.8, 40.0))


def get_search_bounds():
    """현재 활성 검색 범위 (디버그/표시용)."""
    return {
        "x_range": _SEARCH_X_RANGE, "y_range": _SEARCH_Y_RANGE,
        "mast_range": _MAST_RANGE,  "jib_range": _JIB_RANGE,
    }


class CranePlacementProblem(Problem):
    """5변수 통합 문제."""
    def __init__(self):
        xl_arr = np.array([_SEARCH_X_RANGE[0], _SEARCH_Y_RANGE[0],
                            0.0, _JIB_RANGE[0], _MAST_RANGE[0]])
        xu_arr = np.array([_SEARCH_X_RANGE[1], _SEARCH_Y_RANGE[1],
                            2.999, _JIB_RANGE[1], _MAST_RANGE[1]])
        super().__init__(n_var=5, n_obj=2, n_ieq_constr=9,
                          xl=xl_arr, xu=xu_arr)
        self._eval_count = 0

    def _evaluate(self, X, out, *args, **kwargs):
        n = X.shape[0]
        F = np.full((n, 2), 1e6)
        G = np.zeros((n, 9))
        for i in range(n):
            x, y, m_idx, jib, mast = X[i]
            model = MODEL_LIST[int(np.clip(m_idx, 0, len(MODEL_LIST)-1))]
            try:
                G[i] = continuous_constraints((x, y), model, mast, jib)
                f1 = compute_F1((x, y), model, jib)
                f2 = compute_F2((x, y), model)
                F[i, 0] = f1["F1"]
                F[i, 1] = f2["F2_calendar_hours"]
            except Exception:
                G[i] = 1e3
            self._eval_count += 1
        out["F"] = F
        out["G"] = G


class CranePlacementProblemFixedModel(Problem):
    """4변수 모델별 문제. y_range로 검색 영역을 제한 가능."""
    def __init__(self, model_idx, y_range=None):
        self.model_idx = model_idx
        # y_range 미지정 시 활성 검색 범위 사용
        if y_range is None:
            y_range = _SEARCH_Y_RANGE
        self.y_range = y_range
        super().__init__(
            n_var=4, n_obj=2, n_ieq_constr=9,
            xl=np.array([_SEARCH_X_RANGE[0], y_range[0],
                          _JIB_RANGE[0], _MAST_RANGE[0]]),
            xu=np.array([_SEARCH_X_RANGE[1], y_range[1],
                          _JIB_RANGE[1], _MAST_RANGE[1]]),
        )

    def _evaluate(self, X, out, *args, **kwargs):
        n = X.shape[0]
        F = np.full((n, 2), 1e6)
        G = np.zeros((n, 9))
        model = MODEL_LIST[self.model_idx]
        for i in range(n):
            x, y, jib, mast = X[i]
            try:
                G[i] = continuous_constraints((x, y), model, mast, jib)
                f1 = compute_F1((x, y), model, jib)
                f2 = compute_F2((x, y), model)
                F[i, 0] = f1["F1"]
                F[i, 1] = f2["F2_calendar_hours"]
            except Exception:
                G[i] = 1e3
        out["F"] = F
        out["G"] = G


def run_optimization(pop_size=80, n_gen=40, seed=42, verbose=True,
                       per_model=True):
    if not per_model:
        problem = CranePlacementProblem()
        algorithm = NSGA2(
            pop_size=pop_size,
            sampling=HintAwareSampling(hint_fraction=0.3, seed=seed),
            crossover=SBX(eta=15, prob=0.9),
            mutation=PM(eta=20), eliminate_duplicates=True,
        )
        t0 = time.time()
        if verbose:
            print(f"\n[통합 모드] NSGA-II: pop={pop_size}, gen={n_gen}, seed={seed}")
        result = minimize(problem, algorithm, ("n_gen", n_gen),
                          seed=seed, verbose=False)
        elapsed = time.time() - t0
        if verbose:
            print(f"  완료 {elapsed:.1f}s, "
                  f"Pareto {len(result.F) if result.F is not None else 0}개")
        return result, problem

    # per-model mode
    all_F, all_X = [], []
    per_model_stats = {}
    for m_idx in range(len(MODEL_LIST)):
        problem = CranePlacementProblemFixedModel(model_idx=m_idx)
        sub_seed = seed + m_idx * 1000
        algorithm = NSGA2(
            pop_size=pop_size,
            sampling=HintAwareSampling(hint_fraction=0.3, model_idx=m_idx,
                                         seed=sub_seed),
            crossover=SBX(eta=15, prob=0.9),
            mutation=PM(eta=20), eliminate_duplicates=True,
        )
        t0 = time.time()
        res = minimize(problem, algorithm, ("n_gen", n_gen),
                       seed=sub_seed, verbose=False)
        elapsed = time.time() - t0
        n_sol = len(res.F) if res.F is not None else 0
        per_model_stats[m_idx] = {"name": MODEL_LIST[m_idx],
                                    "n_solutions": n_sol, "elapsed": elapsed}
        if verbose:
            print(f"  [{MODEL_LIST[m_idx]:<22}] {n_sol:>3}개 해 ({elapsed:.1f}s)")
        if n_sol > 0:
            X_ext = np.column_stack([
                res.X[:, 0:2],
                np.full(len(res.X), m_idx + 0.001),
                res.X[:, 2:],
            ])
            all_F.append(res.F)
            all_X.append(X_ext)

    if not all_F:
        class E:
            F = None; X = None
        return E(), None

    F_combined = np.vstack(all_F)
    X_combined = np.vstack(all_X)

    # Non-dominated sorting
    is_eff = np.ones(len(F_combined), dtype=bool)
    for i in range(len(F_combined)):
        if is_eff[i]:
            mask = (np.all(F_combined <= F_combined[i], axis=1) &
                    np.any(F_combined < F_combined[i], axis=1))
            is_eff[mask] = False
            is_eff[i] = True

    class Result:
        F = F_combined[is_eff]
        X = X_combined[is_eff]
        stats = per_model_stats

    if verbose:
        print(f"  → 통합 Pareto: {len(Result.F)}개")
    return Result(), None


def run_dual_branch_optimization(pop_size=80, n_gen=60, seed=42, verbose=True,
                                   y_split=None):
    """
    부지 북측 경계 y = y_split 을 기준으로 두 분기를 별도 NSGA-II 최적화.

    y_split=None 이면 활성 검색범위의 50% 지점을 자동 사용.

    Branch 0 — 'Inside' : y ∈ [y_min, y_split]   (부지 + 남측·동측 보조)
    Branch 1 — 'Outside': y ∈ [y_split, y_max]   (북측 주도로 점용 등)

    배경:
        자재 다종화 후 두 영역이 trade-off 군집을 형성하면 single-branch NSGA-II
        는 seed 에 따라 한쪽만 충실히 탐색하는 mode collapse 가 발생한다
        (HANDOFF 의 P1 이슈). 명시적 분기로 두 영역을 모두 보장 탐색.

    각 branch 내부에서 per-model 모드 (3 모델 × 2 분기 = 6 sub-runs).

    Returns:
        Result with attributes:
            F: ndarray (n, 2) — 통합 Pareto F1·F2
            X: ndarray (n, 5) — x, y, model_idx, jib, mast
            branch: ndarray (n,) — 0 또는 1 (Inside / Outside)
            stats: dict — branch 별 통계
    """
    # y_split 자동 계산: 현재 검색범위의 중간점 부근
    if y_split is None:
        y_lo, y_hi = _SEARCH_Y_RANGE
        # 공덕동 케이스 (-20, 20) → 12.5 였음 (북쪽 부지 경계)
        # 일반화: 검색범위의 위에서 25% 지점 (즉, 부지 북단 경계 부근)
        y_split = y_lo + 0.75 * (y_hi - y_lo)

    y_lo, y_hi = _SEARCH_Y_RANGE
    branches = [
        ("Inside",  (y_lo, y_split)),
        ("Outside", (y_split, y_hi)),
    ]

    if verbose:
        print(f"\n{'='*70}")
        print(f"Dual-Branch NSGA-II   y_split = {y_split:.1f}   seed = {seed}")
        print(f"{'='*70}")

    all_F, all_X, all_B = [], [], []
    branch_stats = {}

    for branch_idx, (branch_name, y_range) in enumerate(branches):
        if verbose:
            print(f"\n[Branch {branch_idx} · {branch_name}]  "
                  f"y ∈ [{y_range[0]:+.1f}, {y_range[1]:+.1f}]")

        branch_F, branch_X = [], []
        sub_stats = {}
        for m_idx in range(len(MODEL_LIST)):
            problem = CranePlacementProblemFixedModel(
                model_idx=m_idx, y_range=y_range
            )
            # seed 다양화: 모델 + 분기마다 다른 seed offset
            sub_seed = seed + m_idx * 1000 + branch_idx * 100
            algorithm = NSGA2(
                pop_size=pop_size,
                sampling=HintAwareSampling(hint_fraction=0.3, model_idx=m_idx,
                                             seed=sub_seed),
                crossover=SBX(eta=15, prob=0.9),
                mutation=PM(eta=20), eliminate_duplicates=True,
            )
            t0 = time.time()
            res = minimize(problem, algorithm, ("n_gen", n_gen),
                           seed=sub_seed, verbose=False)
            elapsed = time.time() - t0
            n_sol = len(res.F) if res.F is not None else 0
            sub_stats[m_idx] = {
                "name": MODEL_LIST[m_idx],
                "n_solutions": n_sol,
                "elapsed": elapsed,
            }
            if verbose:
                print(f"    [{MODEL_LIST[m_idx]:<22}] "
                      f"{n_sol:>3}개 해 ({elapsed:.1f}s)")
            if n_sol > 0:
                X_ext = np.column_stack([
                    res.X[:, 0:2],
                    np.full(len(res.X), m_idx + 0.001),
                    res.X[:, 2:],
                ])
                branch_F.append(res.F)
                branch_X.append(X_ext)

        if branch_F:
            bF = np.vstack(branch_F)
            bX = np.vstack(branch_X)
            all_F.append(bF)
            all_X.append(bX)
            all_B.append(np.full(len(bF), branch_idx, dtype=int))
            branch_stats[branch_idx] = {
                "name": branch_name,
                "y_range": y_range,
                "n_solutions": len(bF),
                "models": sub_stats,
            }
            if verbose:
                print(f"  → Branch {branch_idx} {branch_name}: {len(bF)}개 해")
        else:
            branch_stats[branch_idx] = {
                "name": branch_name,
                "y_range": y_range,
                "n_solutions": 0,
                "models": sub_stats,
            }

    if not all_F:
        class E:
            F = None; X = None; branch = None; stats = branch_stats
        return E()

    F_all = np.vstack(all_F)
    X_all = np.vstack(all_X)
    B_all = np.concatenate(all_B)

    # 통합 비지배 정렬
    is_eff = np.ones(len(F_all), dtype=bool)
    for i in range(len(F_all)):
        if is_eff[i]:
            mask = (np.all(F_all <= F_all[i], axis=1) &
                    np.any(F_all < F_all[i], axis=1))
            is_eff[mask] = False
            is_eff[i] = True

    class Result:
        F = F_all[is_eff]
        X = X_all[is_eff]
        branch = B_all[is_eff]
        stats = branch_stats

    if verbose:
        n_inside = int((Result.branch == 0).sum())
        n_north  = int((Result.branch == 1).sum())
        print(f"\n  → 통합 Pareto: {len(Result.F)}개 "
              f"(부지내 {n_inside}, 북측도로 {n_north})")

    return Result()


def summarize_pareto_front(result, top_k=12):
    if result.F is None or len(result.F) == 0:
        print("Pareto front 비어있음.")
        return None
    F, X = result.F, result.X
    order = np.argsort(F[:, 0])
    print(f"\n{'='*92}")
    print(f"Pareto Front 상위 해 ({min(top_k, len(F))}개)")
    print(f"{'='*92}")
    print(f"{'#':>3} {'x':>7} {'y':>7} {'모델':<22} {'지브':>6} {'마스트':>7} "
          f"{'F1':>9} {'F2(h)':>9} {'F2(d)':>8}")
    print("-" * 92)
    for rank, idx in enumerate(order[:top_k], 1):
        x, y, m_idx, jib, mast = X[idx]
        model = MODEL_LIST[int(m_idx)].replace("Potain_", "P-").replace("Liebherr_", "L-")
        print(f"{rank:>3} {x:>7.1f} {y:>7.1f} {model:<22} {jib:>6.1f} {mast:>7.1f} "
              f"{F[idx, 0]:>9.1f} {F[idx, 1]:>9.1f} {F[idx, 1]/8:>8.1f}")
    return order


def select_knee(F, X=None):
    """
    Pareto front에서 robust knee point 인덱스를 선정한다.

    NSGA-II는 제약 위반 해를 페널티(F1·F2 매우 큼)로 남기는 경우가 있어,
    단순 정규화 후 원점최근접 knee가 그 이상치에 끌려갈 수 있다(seed별 불안정).
    이를 막기 위해 각 목적함수에서 중앙값 기반 이상치(상위 비정상값)를 먼저
    제외한 뒤, 정상 해 집합 안에서 정규화 원점최근접 knee를 선정한다.

    Returns: (knee_idx_in_original_F)
    """
    F = np.asarray(F)
    n = len(F)
    if n == 0:
        return None
    if n <= 2:
        # 정규화 원점최근접
        f1n = (F[:, 0] - F[:, 0].min()) / (F[:, 0].max() - F[:, 0].min() + 1e-9)
        f2n = (F[:, 1] - F[:, 1].min()) / (F[:, 1].max() - F[:, 1].min() + 1e-9)
        return int(np.argmin(f1n ** 2 + f2n ** 2))

    # --- 이상치 마스크: 각 목적함수 중앙값 + 3*MAD 초과를 페널티성으로 간주 ---
    keep = np.ones(n, dtype=bool)
    for j in (0, 1):
        col = F[:, j]
        med = np.median(col)
        mad = np.median(np.abs(col - med)) + 1e-9
        # MAD 기반 robust 상한 (정규분포 환산 계수 1.4826, 여유 크게 6)
        upper = med + 6.0 * 1.4826 * mad
        keep &= col <= upper
    # 너무 많이 걸러지면(절반 이상) 필터 완화 — 안전장치
    if keep.sum() < max(3, n // 2):
        keep = np.ones(n, dtype=bool)

    idx_map = np.where(keep)[0]
    Ff = F[keep]
    f1n = (Ff[:, 0] - Ff[:, 0].min()) / (Ff[:, 0].max() - Ff[:, 0].min() + 1e-9)
    f2n = (Ff[:, 1] - Ff[:, 1].min()) / (Ff[:, 1].max() - Ff[:, 1].min() + 1e-9)
    ki_local = int(np.argmin(f1n ** 2 + f2n ** 2))
    return int(idx_map[ki_local])


if __name__ == "__main__":
    result, _ = run_optimization(pop_size=80, n_gen=60, seed=42, per_model=True)
    summarize_pareto_front(result, top_k=15)
    if result.F is not None and len(result.F) > 0:
        np.savez("pareto_result.npz", F=result.F, X=result.X)
        print(f"\n저장: pareto_result.npz")
