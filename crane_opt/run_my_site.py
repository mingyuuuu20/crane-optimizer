"""
run_my_site.py — 현장 하나를 돌려서 '크레인 추천 위치'를 출력하고 그림으로 저장.

사용법 (터미널에서):
    python run_my_site.py sites/내현장.json

결과:
    - 화면에 추천 좌표·기종·지브·마스트 출력
    - results/내현장_result.png 에 배치 그림 저장
"""
import sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly, Circle
import matplotlib.font_manager as fm

# 한글 폰트(있으면 사용)
for fp in ["/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
           "C:/Windows/Fonts/malgun.ttf"]:
    if os.path.exists(fp):
        fm.fontManager.addfont(fp)
        plt.rcParams["font.family"] = fm.FontProperties(fname=fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

from site_loader import load_site
from site_helpers import use_site
import optimizer

MODEL_NAMES = ["Potain MDT 178", "Potain MR 160C", "Liebherr 280 HC-L"]

def main():
    if len(sys.argv) < 2:
        print("사용법: python run_my_site.py sites/내현장.json")
        sys.exit(1)
    site_path = sys.argv[1]

    # ① 현장 입력
    try:
        s = load_site(site_path)
    except Exception as e:
        print("\n[입력 오류]")
        print(e)
        sys.exit(1)
    use_site(s)
    name = s.metadata.get("display_name", site_path)
    print("=" * 60)
    print(f"① 입력 현장: {name}")
    print(f"   대지면적: {s.SITE.area:.0f} m²")
    print("=" * 60)

    # ② 최적화 실행
    print("② NSGA-II 최적화 실행 중... (수십 초 걸립니다)")
    r = optimizer.run_dual_branch_optimization(
        pop_size=60, n_gen=40, seed=42, verbose=False)

    if r.F is None or len(r.F) == 0:
        print("\n결과: feasible 한 배치를 찾지 못했습니다.")
        print("(대지가 너무 작거나 제약이 과한 경우 — 입력값을 확인하세요)")
        sys.exit(0)

    # ③ knee point = 최종 추천
    f1, f2 = r.F[:, 0], r.F[:, 1]
    f1n = (f1 - f1.min()) / (f1.max() - f1.min() + 1e-9)
    f2n = (f2 - f2.min()) / (f2.max() - f2.min() + 1e-9)
    ki = int(np.argmin(f1n**2 + f2n**2))
    Cx, Cy, midx, jib, mast = r.X[ki]
    model = MODEL_NAMES[int(midx)]

    print("\n" + "=" * 60)
    print("③ 추천 결과")
    print("=" * 60)
    print(f"   크레인 설치 좌표 : X={Cx:+.1f} m,  Y={Cy:+.1f} m  (대지중심 기준)")
    print(f"   추천 기종        : {model}")
    print(f"   지브(붐) 길이    : {jib:.0f} m")
    print(f"   마스트 높이      : {mast:.0f} m")
    print(f"   안전위험 F1={f1[ki]:.0f},  양중시간 F2={f2[ki]:.0f} h")
    print(f"   (파레토 최적해 {len(r.F)}개 중 knee point 선정)")

    # 그림 저장
    os.makedirs("results", exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    for k, rd in s.ROADS.items():
        ax.add_patch(MplPoly(list(rd["polygon"].exterior.coords),
                     fc="#EEEEEE", ec="#999", lw=0.6))
    for k, b in s.ADJACENT_BUILDINGS.items():
        ax.add_patch(MplPoly(list(b["footprint"].exterior.coords),
                     fc="#C44", ec="k", lw=1, alpha=0.4))
    for k, v in getattr(s, "VACANT_LOTS", {}).items():
        ax.add_patch(MplPoly(list(v["footprint"].exterior.coords),
                     fc="#D6EAD6", ec="#7AA77A", hatch="//", alpha=0.5))
    ax.add_patch(MplPoly(list(s.SITE.exterior.coords),
                 fc="#FFF3CD", ec="k", lw=2))
    ax.add_patch(MplPoly(list(s.PLANNED_BUILDING.exterior.coords),
                 fc="none", ec="#3366CC", lw=1.4))
    ax.add_patch(Circle((Cx, Cy), jib, fc="none", ec="gold", ls="--", lw=1.5))
    ax.scatter([Cx], [Cy], s=500, marker="*", c="gold", ec="k", lw=1.5, zorder=6)
    ax.set_aspect("equal")
    ax.set_title(f"{name}\n추천 크레인 위치: ({Cx:.1f}, {Cy:.1f}) {model} 지브{jib:.0f}m")
    ax.set_xlabel("East (m)"); ax.set_ylabel("North (m)"); ax.grid(alpha=0.3)
    out = f"results/{os.path.splitext(os.path.basename(site_path))[0]}_result.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    print(f"\n→ 배치 그림 저장: {out}")

if __name__ == "__main__":
    main()
