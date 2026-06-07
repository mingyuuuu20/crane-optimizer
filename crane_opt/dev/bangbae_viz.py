import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly, Circle
import matplotlib.font_manager as fm
fm.fontManager.addfont('/usr/share/fonts/truetype/nanum/NanumGothic.ttf')
plt.rcParams['font.family']='NanumGothic'; plt.rcParams['axes.unicode_minus']=False
from shapely.geometry import Point
from site_loader import load_site
from site_helpers import use_site
import constraints, objectives
MODEL_NAMES=["Potain_MDT_178","Potain_MR_160C","Liebherr_280_HC_L"]
s=load_site('sites/bangbae_2252.json'); use_site(s)
d=np.load('/home/claude/bangbae_pareto.npz'); F,X=d['F'],d['X']
f1,f2=F[:,0],F[:,1]
f1n=(f1-f1.min())/(f1.max()-f1.min()+1e-9); f2n=(f2-f2.min())/(f2.max()-f2.min()+1e-9)
ki=int(np.argmin(f1n**2+f2n**2)); kx,ky,kmi,kjib,kmast=X[ki]; kmodel=MODEL_NAMES[int(kmi)]
actual=(-6.3,0.0); ajib=20.0

fig,(ax1,ax2)=plt.subplots(1,2,figsize=(16,7.5))
# (1) Pareto
order=np.argsort(F[:,0])
ax1.plot(F[order,0],F[order,1],'-o',color='#1f77b4',ms=4,lw=1.2,label=f'도구 Pareto ({len(F)}개, 전부 내부설치)')
ax1.scatter([F[ki,0]],[F[ki,1]],s=400,marker='*',c='gold',ec='k',lw=1.5,zorder=5,label='도구 추천 knee (내부설치)')
ax1.set_xlabel('F1 — 제3자 안전위험',fontsize=11)
ax1.set_ylabel('F2 — 양중 사이클타임 (h)',fontsize=11)
ax1.set_title('방배동 2252 — 도구 Pareto front\n(실제 외부설치는 모델 적용범위 밖 → front에 없음)',fontsize=12,fontweight='bold')
ax1.legend(fontsize=9,loc='upper right'); ax1.grid(alpha=0.3)

# (2) 평면
def draw(ax):
    for k,r in s.ROADS.items():
        ax.add_patch(MplPoly(list(r['polygon'].exterior.coords),fc='#EEEEEE',ec='#999',lw=0.6,zorder=1))
        cc=r['polygon'].centroid; ax.text(cc.x,cc.y,f"6m\n도로",ha='center',va='center',fontsize=7,color='#666')
    for k,b in s.ADJACENT_BUILDINGS.items():
        ease=b.get('airspace_easement',False)
        fc='#9CC' if ease else '#C44'
        ax.add_patch(MplPoly(list(b['footprint'].exterior.coords),fc=fc,ec='k',lw=1,alpha=0.45,zorder=2))
        cc=b['footprint'].centroid
        tag=f"{k}\n{b['floors']}F\n{'상공OK' if ease else '고층'}"
        ax.text(cc.x,cc.y,tag,ha='center',va='center',fontsize=6.5,fontweight='bold')
    ax.add_patch(MplPoly(list(s.SITE.exterior.coords),fc='#FFF3CD',ec='k',lw=2,zorder=3,label='대지 16.9×15.15m'))
    ax.add_patch(MplPoly(list(s.PLANNED_BUILDING.exterior.coords),fc='none',ec='#3366CC',lw=1.4,zorder=4,label='본동 footprint'))
draw(ax2)
# 추천(내부) gold star + 슬루
ax2.add_patch(Circle((kx,ky),kjib,fc='none',ec='gold',ls='--',lw=1.3,alpha=0.8,zorder=4))
ax2.scatter([kx],[ky],s=440,marker='*',c='gold',ec='k',lw=1.5,zorder=6,
            label=f'도구추천 ({kx:.1f},{ky:.1f}) 내부설치 jib{kjib:.0f}')
# 실제(외부) red X + 슬루 (R20)
ax2.add_patch(Circle(actual,ajib,fc='none',ec='red',ls=':',lw=1.3,alpha=0.8,zorder=4))
ax2.scatter([actual[0]],[actual[1]],s=320,marker='X',c='red',ec='k',lw=1.5,zorder=6,
            label=f'실제 ({actual[0]},{actual[1]}) 외부설치 FT-80L R20')
ax2.set_xlabel('East (m)',fontsize=11); ax2.set_ylabel('North (m)',fontsize=11)
ax2.set_title('추천(내부설치) vs 실제(외부설치+월브레싱)\n공법 차이 → 거리 8.7m. 모델은 외부 월타이 미지원',fontsize=12,fontweight='bold')
ax2.legend(fontsize=8,loc='upper left'); ax2.set_aspect('equal'); ax2.grid(alpha=0.3)
ax2.set_xlim(-16,30); ax2.set_ylim(-16,16)
plt.tight_layout()
plt.savefig('results/bangbae_validation_final.png',dpi=130,bbox_inches='tight')
print('saved results/bangbae_validation_final.png')
