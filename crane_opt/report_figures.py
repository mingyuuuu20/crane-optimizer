"""report_figures.py — 보고서용 그림 생성 (배치도/Pareto/F1분해)."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly, Circle, Rectangle
import matplotlib.font_manager as fm

# 한글 폰트 (로컬·클라우드 모두 대응)
_FONT = None
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",      # fonts-nanum (클라우드)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/malgun.ttf",                          # Windows
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",           # macOS
]
for fp in _FONT_CANDIDATES:
    if os.path.exists(fp):
        try:
            if fp.endswith(".ttf"):
                fm.fontManager.addfont(fp)
            _FONT = fm.FontProperties(fname=fp).get_name()
            plt.rcParams["font.family"] = _FONT
            break
        except Exception:
            continue
# 경로로 못 찾으면 시스템에 등록된 한글 폰트명으로 fallback
if _FONT is None:
    for cand in ["NanumGothic", "Noto Sans CJK KR", "Malgun Gothic", "AppleGothic"]:
        try:
            fm.findfont(cand, fallback_to_default=False)
            _FONT = cand
            plt.rcParams["font.family"] = cand
            break
        except Exception:
            continue
plt.rcParams["axes.unicode_minus"] = False

NAVY = "#1F3A5F"; GOLD = "#C8A24B"; RED = "#C0392B"; BLUE = "#3366CC"
GREEN = "#7AA77A"; GREY = "#888888"


def _autoscale_to_site(ax, s, extra=0.0):
    """대지+인접+도로+공지 전체를 포함하도록 축 범위를 명시 설정."""
    geoms = [s.SITE, s.PLANNED_BUILDING]
    for b in s.ADJACENT_BUILDINGS.values():
        geoms.append(b["footprint"])
    for rd in s.ROADS.values():
        geoms.append(rd["polygon"])
    for v in getattr(s, "VACANT_LOTS", {}).values():
        geoms.append(v["footprint"])
    xs0 = min(g.bounds[0] for g in geoms); ys0 = min(g.bounds[1] for g in geoms)
    xs1 = max(g.bounds[2] for g in geoms); ys1 = max(g.bounds[3] for g in geoms)
    m = 3 + extra * 0.1
    ax.set_xlim(xs0 - m, xs1 + m); ax.set_ylim(ys0 - m, ys1 + m)


def fig_site_diagram(s, path, dpi=110):
    """입력 부지 다이어그램 (대지·건물·인접·도로·양중점)."""
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    for k, rd in s.ROADS.items():
        ax.add_patch(MplPoly(list(rd["polygon"].exterior.coords),
                     fc="#EEEEEE", ec=GREY, lw=0.8, zorder=1))
        c = rd["polygon"].centroid
        ax.text(c.x, c.y, f"도로\n{rd.get('width_m','')}m", ha="center", va="center",
                fontsize=8, color="#666")
    for k, v in getattr(s, "VACANT_LOTS", {}).items():
        ax.add_patch(MplPoly(list(v["footprint"].exterior.coords),
                     fc="#D6EAD6", ec=GREEN, hatch="//", lw=0.8, alpha=0.5, zorder=1))
    for k, b in s.ADJACENT_BUILDINGS.items():
        ax.add_patch(MplPoly(list(b["footprint"].exterior.coords),
                     fc="#E8B4B4", ec="k", lw=1, alpha=0.55, zorder=2))
        c = b["footprint"].centroid
        ax.text(c.x, c.y, f"{b['name'][:10]}\n{b.get('floors','')}F",
                ha="center", va="center", fontsize=7, fontweight="bold")
    ax.add_patch(MplPoly(list(s.SITE.exterior.coords),
                 fc="#FFF3CD", ec="k", lw=2.2, zorder=3))
    ax.add_patch(MplPoly(list(s.PLANNED_BUILDING.exterior.coords),
                 fc="none", ec=BLUE, lw=1.6, zorder=4))
    cb = s.PLANNED_BUILDING.centroid
    ax.text(cb.x, cb.y, "신축\n건물", ha="center", va="center",
            fontsize=9, color=BLUE, fontweight="bold")
    ax.set_aspect("equal"); ax.grid(alpha=0.3)
    _autoscale_to_site(ax, s)
    ax.set_xlabel("East (m)"); ax.set_ylabel("North (m)")
    ax.set_title("부지 현황 다이어그램", fontsize=13, fontweight="bold")
    fig.savefig(path, dpi=dpi); plt.close(fig); plt.close("all")


def fig_pareto(F, ki, path, dpi=110):
    """Pareto front + knee."""
    fig, ax = plt.subplots(figsize=(7, 5.2))
    order = np.argsort(F[:, 0])
    ax.plot(F[order, 0], F[order, 1], "-o", color=BLUE, ms=4, lw=1.3,
            label=f"Pareto 최적해 ({len(F)}개)")
    ax.scatter([F[ki, 0]], [F[ki, 1]], s=420, marker="*", c=GOLD,
               ec="k", lw=1.5, zorder=5, label="추천 (knee point)")
    ax.set_xlabel("F1 — 제3자 안전위험 (낮을수록 안전)", fontsize=11)
    ax.set_ylabel("F2 — 양중 사이클타임 (h)", fontsize=11)
    ax.set_title("다목적 최적화 결과 — Pareto Front", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10); ax.grid(alpha=0.3)
    fig.savefig(path, dpi=dpi); plt.close(fig); plt.close("all")


def fig_placement(s, crane_xy, jib, path, dpi=110):
    """추천 크레인 배치도 (선회반경 포함)."""
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    for k, rd in s.ROADS.items():
        ax.add_patch(MplPoly(list(rd["polygon"].exterior.coords),
                     fc="#EEEEEE", ec=GREY, lw=0.8, zorder=1))
    for k, v in getattr(s, "VACANT_LOTS", {}).items():
        ax.add_patch(MplPoly(list(v["footprint"].exterior.coords),
                     fc="#D6EAD6", ec=GREEN, hatch="//", lw=0.8, alpha=0.5, zorder=1))
    for k, b in s.ADJACENT_BUILDINGS.items():
        ax.add_patch(MplPoly(list(b["footprint"].exterior.coords),
                     fc="#E8B4B4", ec="k", lw=1, alpha=0.55, zorder=2))
    ax.add_patch(MplPoly(list(s.SITE.exterior.coords),
                 fc="#FFF3CD", ec="k", lw=2.2, zorder=3))
    ax.add_patch(MplPoly(list(s.PLANNED_BUILDING.exterior.coords),
                 fc="none", ec=BLUE, lw=1.6, zorder=4))
    # 선회 반경
    ax.add_patch(Circle(crane_xy, jib, fc="none", ec=GOLD, ls="--",
                 lw=1.6, zorder=5, label=f"작업반경 {jib:.0f}m"))
    ax.scatter([crane_xy[0]], [crane_xy[1]], s=550, marker="*", c=GOLD,
               ec="k", lw=1.8, zorder=6, label="추천 크레인 위치")
    ax.annotate(f"({crane_xy[0]:.1f}, {crane_xy[1]:.1f})", crane_xy,
                (crane_xy[0], crane_xy[1] + jib * 0.18), ha="center",
                fontsize=10, fontweight="bold", color="#7a5a1a")
    ax.set_aspect("equal"); ax.grid(alpha=0.3)
    _autoscale_to_site(ax, s, extra=jib)
    ax.set_xlabel("East (m)"); ax.set_ylabel("North (m)")
    ax.set_title("추천 크레인 배치", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9, loc="upper right")
    fig.savefig(path, dpi=dpi); plt.close(fig); plt.close("all")


def fig_f1_breakdown(breakdown, path, dpi=110):
    """F1 영역별 위험 기여 막대그래프."""
    label_map = {"own_site": "자기 부지", "road": "도로",
                 "adjacent_residential": "인접 주거", "empty": "공지"}
    names, vals, vuls = [], [], []
    for k, v in breakdown.items():
        rc = v.get("risk_contribution", 0)
        names.append(label_map.get(k, k))
        vals.append(rc)
        vuls.append(v.get("vulnerability", 0))
    colors = [RED if vu >= 5 else (GOLD if vu >= 3 else GREEN) for vu in vuls]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(names, vals, color=colors, ec="k", lw=0.6)
    for b, vu in zip(bars, vuls):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                f"취약성\n{vu}", ha="center", va="bottom", fontsize=8, color="#444")
    ax.set_ylabel("위험 기여도", fontsize=11)
    ax.set_title("영역별 제3자 안전위험 분해 (F1)", fontsize=13, fontweight="bold")
    ax.grid(alpha=0.3, axis="y")
    fig.savefig(path, dpi=dpi); plt.close(fig); plt.close("all")
