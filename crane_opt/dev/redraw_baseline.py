"""지배율 중심 baseline 그림 재생성 (한글 정상)"""
import numpy as np, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 폰트 직접 등록
fp = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
fm.fontManager.addfont(fp)
plt.rcParams["font.family"] = fm.FontProperties(fname=fp).get_name()
plt.rcParams["axes.unicode_minus"] = False

from site_loader import load_site, list_sites
from site_helpers import use_site
import baseline_comparison as bc

# 4부지 재계산 (가벼운 세팅, 그림용)
sites = list_sites("sites")
results = []
for sf in sites:
    site = load_site(sf)
    use_site(site)
    rnd = bc.run_random_search(site, n_samples=1000, seed=42)
    nsga = bc.run_nsga2(site, pop_size=60, n_gen=25, seed=42)
    def dom(a,b): return bool(np.all(a<=b) and np.any(a<b))
    Rf, Nf = rnd["F_pareto"], nsga["F_pareto"]
    rd = sum(1 for r in Rf if any(dom(n,r) for n in Nf)) if len(Rf) and len(Nf) else 0
    results.append({
        "name": site.metadata.get("display_name"),
        "rnd_feas": rnd["feasible_rate"]*100,
        "rnd_n": rnd["n_pareto"], "nsga_n": nsga["n_pareto"],
        "rnd_dom": rd, "Rf": Rf, "Nf": Nf,
        "Rall": rnd["F_all"],
    })

# ── 2x2 그림: 왼쪽위=feasible율 막대, 오른쪽위=Pareto크기 막대,
#              아래 2개 = 대표 부지 2개의 front (지배 강조)
fig = plt.figure(figsize=(15, 11))
gs = fig.add_gridspec(2, 2, hspace=0.32, wspace=0.24)

names = [r["name"] for r in results]
short = ["공덕동\n(타겟)", "합성A\n직사각", "합성B\nL자코너", "합성C\n점용불가"]
x = np.arange(len(results))

# (a) feasible rate
ax = fig.add_subplot(gs[0,0])
bars = ax.bar(x, [r["rnd_feas"] for r in results], color="#E69138", width=0.55)
ax.set_title("(a) Random Search feasible 비율", fontsize=13, fontweight="bold")
ax.set_ylabel("feasible 비율 (%)", fontsize=11)
ax.set_xticks(x); ax.set_xticklabels(short, fontsize=9)
for b, r in zip(bars, results):
    ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.02,
            f"{r['rnd_feas']:.1f}%", ha="center", fontsize=10, fontweight="bold")
ax.set_ylim(0, 1.2)
ax.text(0.5, 0.88, "무작위 탐색은 협소대지에서\n해를 거의 못 찾음 (≤0.8%)",
        transform=ax.transAxes, ha="center", fontsize=10,
        bbox=dict(boxstyle="round", fc="#FFF2CC", ec="#E69138"))
ax.grid(axis="y", alpha=0.3)

# (b) Pareto size
ax = fig.add_subplot(gs[0,1])
w = 0.38
ax.bar(x-w/2, [r["rnd_n"] for r in results], w, label="Random", color="#E69138")
ax.bar(x+w/2, [r["nsga_n"] for r in results], w, label="NSGA-II", color="#1976D2")
ax.set_title("(b) Pareto 해 개수", fontsize=13, fontweight="bold")
ax.set_ylabel("Pareto 해 개수", fontsize=11)
ax.set_xticks(x); ax.set_xticklabels(short, fontsize=9)
for i, r in enumerate(results):
    ax.text(i-w/2, r["rnd_n"]+1, str(r["rnd_n"]), ha="center", fontsize=9)
    ax.text(i+w/2, r["nsga_n"]+1, str(r["nsga_n"]), ha="center", fontsize=9, fontweight="bold", color="#1976D2")
ax.legend(fontsize=10); ax.grid(axis="y", alpha=0.3)

# (c)(d) front 비교 — 공덕동, 합성B
for col, r in zip([0,1], [results[0], results[2]]):
    ax = fig.add_subplot(gs[1,col])
    if len(r["Rall"]):
        ax.scatter(r["Rall"][:,0], r["Rall"][:,1], c="lightgray", s=12, alpha=0.4, label="Random 표본")
    if len(r["Nf"]):
        order = np.argsort(r["Nf"][:,0])
        ax.plot(r["Nf"][order,0], r["Nf"][order,1], "-", color="#1976D2", lw=1.6, zorder=2)
        ax.scatter(r["Nf"][:,0], r["Nf"][:,1], c="#1976D2", s=45, edgecolors="k", linewidths=0.4,
                   label=f"NSGA-II Pareto ({r['nsga_n']})", zorder=3)
    if len(r["Rf"]):
        ax.scatter(r["Rf"][:,0], r["Rf"][:,1], c="#E69138", s=75, marker="D", edgecolors="k",
                   linewidths=0.6, label=f"Random Pareto ({r['rnd_n']})", zorder=4)
    ax.set_title(f"({'c' if col==0 else 'd'}) {r['name']} — front 비교\n"
                 f"Random {r['rnd_dom']}/{r['rnd_n']}개가 NSGA-II에 지배당함",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("F1 — 제3자 안전위험 (낮을수록 안전)", fontsize=10)
    ax.set_ylabel("F2 — 양중 사이클타임 (h, 낮을수록 효율)", fontsize=10)
    ax.legend(fontsize=9, loc="best"); ax.grid(alpha=0.3)

fig.suptitle("Random Search vs NSGA-II — 무작위 탐색 대비 우월성 검증",
             fontsize=15, fontweight="bold", y=0.98)
out = "results/baseline_comparison_v2.png"
plt.savefig(out, dpi=140, bbox_inches="tight")
plt.close()
print("저장:", out)
