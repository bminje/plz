import sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, FancyArrowPatch
from matplotlib import font_manager as fm
names={f.name for f in fm.fontManager.ttflist}
for n in ["Noto Sans CJK KR","Noto Sans CJK JP"]:
    if n in names: plt.rcParams["font.family"]=n; break
out=sys.argv[1] if len(sys.argv)>1 else "fig_s0_pipeline.png"
fig,ax=plt.subplots(figsize=(10,6.4)); ax.set_xlim(0,100); ax.set_ylim(0,64); ax.axis("off")
steps=[("① 데이터 수집","공공데이터 4종 + 직접 입력\n(정류소, 승하차, 학교,\n신호등, 학교·대학 좌표)"),("② 전처리","인코딩 변환, ID·ARS·이름\n연결, 신호등 좌표 변환\n(EPSG:5186→위경도)"),("③ 그래프 구축","노선-정류장 관계\n(networkx)"),("④ 범주화","허브·길이·피크 집중도\n·아침 흐름형"),("⑤ 분석","시간대 이용 패턴,\n학교-정류장-신호등\n결합")]
x0=1; w=16.5; gap=4
for i,(t,s) in enumerate(steps):
    x=x0+i*(w+gap)
    ax.add_patch(FancyBboxPatch((x,47),w,13.5,boxstyle="round,pad=0.3,rounding_size=1.2",fc="#eaf2f8",ec="#34495e",lw=1.2))
    ax.text(x+w/2,57.3,t,ha="center",va="center",fontsize=10.5,fontweight="bold")
    ax.text(x+w/2,51.3,s,ha="center",va="center",fontsize=8.4,linespacing=1.5)
    if i<4: ax.add_patch(FancyArrowPatch((x+w+0.4,53.7),(x+w+gap-0.4,53.7),arrowstyle="-|>",mutation_scale=14,color="#34495e",lw=1.3))
ax.text(1,43,"그래프 스키마",fontsize=11,fontweight="bold"); ax.plot([1,99],[42,42],color="#bbb",lw=0.8)
def node(cx,cy,w,h,label,dashed=False,fc="#fdebd0"):
    ax.add_patch(Ellipse((cx,cy),w,h,fc=fc,ec="#34495e",lw=1.4,ls="--" if dashed else "-"))
    ax.text(cx,cy,label,ha="center",va="center",fontsize=10.5,fontweight="bold")
node(15,32,19,8,"Route (노선)"); node(50,32,19,8,"Stop (정류장)",fc="#d5f5e3"); node(85,32,19,8,"School (학교·대학)",dashed=True,fc="#f5eef8"); node(50,12,19,8,"Signal (신호 지점)",dashed=True,fc="#fadbd8")
ax.text(15,24,"노선번호, 정류장 수, 교통수단,\n피크 집중도",ha="center",va="center",fontsize=8.2,linespacing=1.5)
ax.text(41,24.6,"정류장ID, 경유 노선 수, 허브 등급,\n시간대별 승하차, 좌표",ha="center",va="center",fontsize=8.2,linespacing=1.5)
ax.text(85,24,"학교명, 학교급, 좌표, 학생 수",ha="center",va="center",fontsize=8.2)
ax.text(50,4,"좌표, 신호등 종류",ha="center",va="center",fontsize=8.2)
ax.add_patch(FancyArrowPatch((24.8,32),(40.2,32),arrowstyle="-|>",mutation_scale=15,color="#2c3e50",lw=1.6)); ax.text(32.5,35,"PASSES",ha="center",fontsize=9.3,fontweight="bold")
ax.add_patch(FancyArrowPatch((75.2,32),(59.8,32),arrowstyle="-|>",mutation_scale=15,color="#7d3c98",lw=1.4,ls="--")); ax.text(67.5,35,"NEAR (≤300m)",ha="center",fontsize=9,fontweight="bold",color="#7d3c98")
ax.add_patch(FancyArrowPatch((56,15.4),(56,28.7),arrowstyle="-|>",mutation_scale=15,color="#c0392b",lw=1.4,ls="--")); ax.text(58.5,20,"NEAR (≤50m)",ha="left",fontsize=9,fontweight="bold",color="#c0392b")
ax.text(84,8,"점선(School, Signal)은 본 연구에서 좌표 거리로\n계산한 관계이며, 그래프 DB 통합은 향후 과제",ha="center",va="center",fontsize=8.3,linespacing=1.6,color="#444")
plt.tight_layout(); plt.savefig(out,dpi=170); print("ok")
