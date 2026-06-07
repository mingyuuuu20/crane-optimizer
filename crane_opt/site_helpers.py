"""
================================================================================
site_helpers.py
================================================================================
부지 전환 헬퍼 — 한 번의 호출로 모든 의존 모듈 동기화
--------------------------------------------------------------------------------

사용 예:

    from site_loader import load_site
    from site_helpers import use_site

    site = load_site("sites/synthetic_a_rectangular.json")
    use_site(site)        # constraints, objectives, optimizer 모두 동기화

    # 이후 모든 호출이 새 부지 기준
    from optimizer import run_optimization
    result, _ = run_optimization(pop_size=40, n_gen=20, seed=42, per_model=True)
"""

def use_site(site):
    """주어진 SiteData 를 활성 부지로 설정한다 (모든 의존 모듈 동기화)."""
    import constraints
    import objectives
    import optimizer

    constraints.set_active_site(site)
    objectives.set_active_site(site)
    optimizer.set_active_site_bounds(site)

    return site


def current_site_summary():
    """현재 활성 부지의 간단 요약."""
    import constraints, optimizer
    s = []
    s.append(f"부지 면적     : {constraints.SITE.area:.1f} m²")
    s.append(f"건물 풋프린트 : {constraints.PLANNED_BUILDING.area:.1f} m²")
    s.append(f"인접 건물     : {len(constraints.ADJACENT_BUILDINGS)}동")
    s.append(f"도로          : {len(constraints.ROADS)}개")
    s.append(f"양중점        : {len(constraints.LIFT_POINTS)}개")
    s.append(f"검색 범위     : {optimizer.get_search_bounds()}")
    return "\n".join(s)
