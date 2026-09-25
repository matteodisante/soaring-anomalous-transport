"""Projection-sized figures from thesis reports and the slide-11 cadence extension."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.patches
from matplotlib import patheffects
from matplotlib.path import Path as MplPath
from matplotlib.transforms import Affine2D, ScaledTranslation, blended_transform_factory
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)
R = json.loads((ROOT / "thesis/generated/ch3_transport_report.json").read_text())
C = json.loads((ROOT / "thesis/generated/ch3_conditional.json").read_text())
CADENCE = json.loads((OUT.parent / "cadence-support-report.json").read_text())
OPEN = json.loads((OUT.parent / "open-circuits-report.json").read_text())
BLUE, RUST, STEEL, TEAL, GOLD, WINE = "#3477A8", "#B5482A", "#4A6079", "#2E7D8A", "#C98A1E", "#8E3B5C"
ALT = [BLUE, TEAL, GOLD, WINE]
# Match altPlains, altHills, altLow and altHigh on the characteristics slide.
ALT_TINTS = ["#B5D69A", "#DCE0A0", "#DDBE8E", "#B8A89A"]
NAMES = ["Plains", "Hills", "Low mountains", "High mountains"]
# Schematic terrain, with a shared width and baseline: flat, rounded, then
# progressively higher and sharper peaks. Local x spans [-1, 1]; the baseline is y = 0.
TERRAIN = [
    ([(-1,0),(-1,.12),(-.35,.16),(.25,.12),(1,.15),(1,0),(0,0)],
     [MplPath.MOVETO]+[MplPath.LINETO]*5+[MplPath.CLOSEPOLY]),
    ([(-1,0),(-1,.1),(-.8,.1),(-.7,.56),(-.35,.56),(-.05,.56),
      (.06,.16),(.25,.16),(.45,.16),(.55,.42),(.72,.42),(.88,.42),
      (.94,.1),(1,.1),(1,0),(0,0)],
     [MplPath.MOVETO,MplPath.LINETO]+[MplPath.CURVE4]*12+
     [MplPath.LINETO,MplPath.CLOSEPOLY]),
    ([(-1,0),(-1,.1),(-.56,.65),(-.25,.33),(.15,.87),(.5,.48),
      (.7,.6),(1,.1),(1,0),(0,0)],
     [MplPath.MOVETO]+[MplPath.LINETO]*8+[MplPath.CLOSEPOLY]),
    ([(-1,0),(-1,.1),(-.64,.77),(-.37,.41),(.06,1.3),(.43,.58),
      (.65,.85),(1,.1),(1,0),(0,0)],
     [MplPath.MOVETO]+[MplPath.LINETO]*8+[MplPath.CLOSEPOLY]),
]
def edge_of(tint): return tuple(.7*c for c in matplotlib.colors.to_rgb(tint))
def terrain(ax, i, transform):
    """Draw altitude class i's silhouette; transform maps its local coordinates to display."""
    tint = ALT_TINTS[i]
    ax.add_patch(matplotlib.patches.PathPatch(
        MplPath(*TERRAIN[i]),transform=transform,facecolor=tint,
        edgecolor=edge_of(tint),lw=.8,joinstyle="round",clip_on=False))
    # A small snow cap distinguishes the high, alpine silhouette at slide scale.
    if i == 3:
        ax.add_patch(matplotlib.patches.Polygon(
            [(-.09,.99),(.06,1.3),(.22,.99),(.1,1.04),(.02,.97)],
            transform=transform,facecolor="white",edgecolor="none",clip_on=False))

plt.rcParams.update({"font.family":"serif", "font.serif":["Palatino","DejaVu Serif"], "font.size":13,
 "axes.labelsize":13, "axes.titlesize":14, "legend.fontsize":11, "xtick.labelsize":11,
 "ytick.labelsize":11, "axes.spines.top":False,"axes.spines.right":False,
 "pdf.fonttype":42,"axes.edgecolor":"#666666", "text.color":"#202A35"})

def a(x): return np.asarray(x, dtype=float)
def hci(h):
    return f"{h['point']:.3f} [{h['low']:.3f}, {h['high']:.3f}]"
def group_label(key, name, source=C):
    g = source["groups"][key]
    return f"{name} (N={g['flights']:,})\nH={hci(g['fit']['hurst'])}"
def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=.05, metadata={"CreationDate":None,"ModDate":None})
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", pad_inches=.05, dpi=180)
    plt.close(fig)
def style(ax, logy=True, xlabel=r"Lag $\tau$ (s)"):
    ax.set_xscale("log")
    if logy: ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.grid(which="major", color="#E2E7EC", lw=.6)
    ax.set_axisbelow(True)
def band(ax, x, stats, color, label=None, idx=None, scale=1e6):
    p,l,h=[a(stats[k]) for k in ["point","low","high"]]
    if idx is not None: p,l,h=p[idx],l[idx],h[idx]
    ax.fill_between(x,l/scale,h/scale,color=color,alpha=.17,lw=0)
    ax.plot(x,p/scale,"o-",color=color,lw=1.7,ms=3,mfc="white",label=label)
def curve(ax, key, color, label=None, source=C):
    g=source["groups"][key]
    band(ax,a(source["lags_s"]),g["msd"],color,label)
    ax.set_xlim(10,10000); ax.set_ylim(.006,14000)
    ax.set_ylabel(r"MSD (km$^2$)");style(ax)
def herror(ax,x,h,color,**kw):
    ax.errorbar(x,h["point"],yerr=[[h["point"]-h["low"]],[h["high"]-h["point"]]],fmt="o",color=color,ms=7,capsize=4,lw=1.6,**kw)

# Selection comparison: identical fit ranges for every comparison.
fig,axs=plt.subplots(1,2,figsize=(7.3,3.8),layout="constrained",sharey=True)
for ax,slug,title in zip(axs,["para","hang"],["Paragliders","Hang gliders"]):
    d=R["results"][slug]
    for j,ran in enumerate(["10-100","10-1000"]):
        fits=d["cohort_h_comparisons"][ran]["fits"]
        for key,offset,color in [("100",-.18,"#B5C0CD"),("1000",0,"#7C92AB"),("10000",.18,STEEL)]:
            label = rf"$C_{{{key}}}$: N={d['cohorts'][key]['flights']:,}"
            if key in fits: herror(ax,j+offset,fits[key]["hurst"],color,label=label if j==0 else None)
    ax.set_title(title);ax.set_xticks([0,1],["10–100 s","10–1000 s"]);ax.set_xlabel("Same fit range")
    ax.grid(axis="y",color="#E2E7EC");ax.set_xlim(-.5,1.5)
    ax.legend(frameon=False,fontsize=9.5,loc="lower left",handlelength=1)
axs[0].set_ylabel("Effective exponent H")
save(fig,"selection")

# Available population: the flights averaged at each lag change with the lag.
fig,axs=plt.subplots(1,2,figsize=(9.0,4.2),layout="constrained",gridspec_kw={"width_ratios":[1.2,1]})
tail=[]
for slug,color,label in [("para",BLUE,"Paragliders"),("hang",RUST,"Hang gliders")]:
    g=R["results"][slug]["general"]
    x,n=a(g["lags"]),a(g["tamsd_support"])
    # Common 10 s grid only; the descriptive band needs enough site-day groups.
    keep=(x>=10)&(a(g["tamsd_group_support"])>=g["minimum_groups_for_descriptive_band"])
    n10=n[x==10][0]
    band(axs[0],x[keep],g["tamsd"],color,f"{label} (N={n10:,.0f} at 10 s)",idx=keep)
    axs[1].plot(x[keep],n[keep]/n10,"o-",color=color,lw=1.7,ms=3,mfc="white")
    last=np.flatnonzero(keep)[-1]
    axs[1].annotate(f"{n[last]:,.0f} flights",(x[last],n[last]/n10),xytext=(-6,0),
                    textcoords="offset points",ha="right",va="center",fontsize=10,color=color)
    late=keep&(x>=1e4)
    tail+=list(zip(x[late],a(g["tamsd"]["point"])[late]/1e6))
for ax in axs: style(ax,logy=True);ax.set_xlim(10,4e4)
ax=axs[0];ax.set_ylim(1e-3,2e5)
ax.set_ylabel(r"MSD (km$^2$)");ax.legend(frameon=False,loc="upper left")
ax.set_title("MSD over all available flights")
# Outline the MSD points from 10^4 s onward, never covering them: build the ellipse in a
# frame where one unit is the same length on both axes, then map it back to axes units.
fig.canvas.draw()
bbox=ax.get_window_extent();aspect=np.array([bbox.width,bbox.height])/bbox.width
pts=(ax.transScale+ax.transLimits).transform(np.array(tail))*aspect
centre=(pts.min(0)+pts.max(0))/2
d=pts[np.argmax(pts[:,0])]-pts[np.argmin(pts[:,0])];d/=np.hypot(*d)
u,v=(pts-centre)@d,(pts-centre)@np.array([-d[1],d[0]])
b=np.abs(v).max()+.05;semi_a=1.05*np.max(np.abs(u)/np.sqrt(1-(v/b)**2))+.03
theta=np.linspace(0,2*np.pi,200)
ring=centre+np.outer(semi_a*np.cos(theta),d)+np.outer(b*np.sin(theta),[-d[1],d[0]])
ax.add_patch(matplotlib.patches.Polygon(ring/aspect,closed=True,fill=False,ec="#4A6079",lw=1.3,
             transform=ax.transAxes,clip_on=False,zorder=5))
lowest=ring[np.argmin(ring[:,1])]/aspect
ax.annotate("From ~6×10³ s the flight\nset shrinks: the MSD mixes\ndynamics and selection",
            xy=lowest,xycoords="axes fraction",xytext=(.97,.04),textcoords="axes fraction",
            ha="right",va="bottom",fontsize=12.5,color="#4A6079",linespacing=1.25,
            arrowprops=dict(arrowstyle="-|>",color="#4A6079",lw=1.1,shrinkA=3,shrinkB=1))
axs[1].axhline(.1,color="#999999",ls=":",lw=1)
axs[1].text(12,.075,"10× fewer flights than at 10 s",fontsize=10,color="#666666",va="top")
axs[1].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_:f"{100*v:g}%"))
axs[1].set_ylim(8e-5,1.8);axs[1].set_ylabel("Share of the flights at 10 s")
axs[1].set_title("Contributing flights")
save(fig,"available")

# Full C_10000 from 10 s onward; increasing cadence-limited support below 10 s.
fig,axs=plt.subplots(1,2,figsize=(11.8,4.1),layout="constrained")
for ax in axs:
    ax.axvline(10,color="#A0ACBA",lw=.8,ls="--",zorder=-1)
for slug,color,label in [("para",BLUE,"Paragliders"),("hang",RUST,"Hang gliders")]:
    d=CADENCE["results"][slug];h=d["fit_10_10000"]
    x=a(CADENCE["lags_s"])
    population = f"{label} (N={d['flights']:,} from 10 s)"
    for ax,field,scale,legend in [(axs[0],"msd",1e6,f"{population}\nH = {hci(h)}"),
                                 (axs[1],"local_h",1,population)]:
        p,l,u=[a(d[field][k])/scale for k in ["point","low","high"]]
        ax.fill_between(x,l,u,color=color,alpha=.17,lw=0)
        ax.plot(x,p,color=color,lw=1.7,label=legend)
        # Explicit integer-second evaluations in the cadence-limited range.
        short=x<=10
        ax.plot(x[short],p[short],"o",color=color,ms=2.8,mfc="white")
    # Horizontal band from the local minimum near 10 s to the local maximum near 40-50 s.
    h_loc=a(d["local_h"]["point"])
    h_min=h_loc[(x>=8)&(x<=15)].min();h_max=h_loc[(x>=30)&(x<=60)].max()
    axs[1].axhspan(h_min,h_max,color=color,alpha=.2,lw=0,zorder=-2)
    for h_edge in (h_min,h_max): axs[1].axhline(h_edge,color=color,lw=.8,ls="--",zorder=-1)
axs[0].set_ylabel(r"MSD (km$^2$)");style(axs[0]);axs[0].set_xlim(1,10000);axs[0].legend(frameon=False)
axs[0].set_title("MSD; H fitted over 10–10,000 s")
style(axs[1],logy=False);axs[1].set_ylabel(r"Local growth exponent $H_{\rm loc}$")
axs[1].axhline(.5,color="#999999",ls=":",lw=1);axs[1].text(1.25,.515,"Diffusive",fontsize=11,color="#666666")
lower=min(min(CADENCE["results"][s]["local_h"]["low"]) for s in ["para","hang"])
upper=max(max(CADENCE["results"][s]["local_h"]["high"]) for s in ["para","hang"])
axs[1].set_xlim(1,10000);axs[1].set_ylim(min(.26,lower-.025),max(1.07,upper+.035));axs[1].legend(frameon=False,loc="lower left")
axs[1].set_title("Local slope on a dense lag grid")
save(fig,"fixed")

# Slide 5: the MSD over its local slope, sharing the lag axis, sized for the left half of the slide.
fig,(ax,axh)=plt.subplots(2,1,figsize=(5.6,5.3),sharex=True,layout="constrained",gridspec_kw={"height_ratios":[1.3,1]})
for panel in (ax,axh): panel.axvline(10,color="#A0ACBA",lw=.8,ls="--",zorder=-1)
for slug,color,label in [("para",BLUE,"Paragliders"),("hang",RUST,"Hang gliders")]:
    d=CADENCE["results"][slug];x=a(CADENCE["lags_s"])
    p,l,u=[a(d["msd"][k])/1e6 for k in ["point","low","high"]]
    ax.fill_between(x,l,u,color=color,alpha=.17,lw=0)
    ax.plot(x,p,color=color,lw=1.7,label=f"{label} (N={d['flights']:,} from 10 s)\nH = {hci(d['fit_10_10000'])}")
    ax.plot(x[x<=10],p[x<=10],"o",color=color,ms=2.8,mfc="white")
    p,l,u=[a(d["local_h"][k]) for k in ["point","low","high"]]
    axh.fill_between(x,l,u,color=color,alpha=.17,lw=0)
    axh.plot(x,p,color=color,lw=1.5)
ax.set_ylabel(r"MSD (km$^2$)");style(ax,xlabel="");ax.set_xlim(1,10000);ax.legend(frameon=False,loc="upper left")
ax.set_title("MSD; H fitted over 10–10,000 s")
# Lower panel: the local slope of the same curves (the right panel of the full figure).
style(axh,logy=False);axh.set_ylabel(r"Local slope $H_{\rm loc}$")
axh.axhline(.5,color="#999999",ls=":",lw=1);axh.text(1.25,.52,"Diffusive",fontsize=11,color="#666666")
axh.set_ylim(.35,1.05);axh.set_yticks([.5,.75,1])
# The long-lag fall comes from closed circuits (open/closed split, slide 8); ellipse in axes units, as x is log.
axh.add_patch(matplotlib.patches.Ellipse((.935,.43),.17,.86,transform=axh.transAxes,fill=False,ec=STEEL,lw=1.2,ls="--",clip_on=False))
axh.text(.84,.47,"Closed-circuit effect,\nanalysed later",transform=axh.transAxes,ha="right",va="center",fontsize=11,color=STEEL)
save(fig,"fixed-msd")

cadence_tex=[]
for slug,prefix in [("para","CadencePara"),("hang","CadenceHang")]:
    d=CADENCE["results"][slug]
    cadence_tex.append("\\newcommand{\\"+prefix+"Count}{"+f"{d['flights']:,}"+"}")
    cadence_tex.append("\\newcommand{\\"+prefix+"StartCount}{"+f"{d['support'][0]:,}"+"}")
    for suffix,key in [("H","point"),("Low","low"),("High","high")]:
        cadence_tex.append("\\newcommand{\\"+prefix+suffix+"}{"+f"{d['fit_10_10000'][key]:.3f}"+"}")
cadence_tex.append(r"\newcommand{\CadenceLagCount}{"+str(len(CADENCE["lags_s"]))+"}")
(OUT.parent/"cadence-values.tex").write_text("\n".join(cadence_tex)+"\n")

# Distinct flights, not crossings, for each coloured thermal-map category.
thermal_report = json.loads((OUT / "screenshots/thermal-panels-report.json").read_text())
thermal_counts = ["% Generated from the verified saved crossing CSVs by render_figures.py."]
for panel in thermal_report["panels"]:
    csv_path = OUT / "screenshots" / f"{panel['name']}-points.csv"
    assert hashlib.sha256(csv_path.read_bytes()).hexdigest() == panel["points_sha256"]
    points = pd.read_csv(csv_path)
    distinct = points[["discipline", "flight_id"]].drop_duplicates()
    assert len(points) == panel["points"] and len(distinct) == panel["flights"]
    counts = distinct.discipline.value_counts()
    prefix = "Thermal" + "".join(word.capitalize() for word in panel["name"].split("-"))
    for discipline, suffix in [("paragliders", "ParaN"), ("hang gliders", "HangN")]:
        thermal_counts.append(rf"\newcommand{{\{prefix}{suffix}}}{{{counts.get(discipline, 0):,}}}")
(OUT / "screenshots/thermal-flight-counts.tex").write_text("\n".join(thermal_counts)+"\n")

# Conditional curves, without re-fitting any saved result.
fig,ax=plt.subplots(figsize=(7.4,4.2),layout="constrained")
for i,(name,color) in enumerate(zip(NAMES,ALT)):
    g=C["groups"][f"alt{i}"]
    interval=["<300 m","300–800 m","800–1,500 m","≥1,500 m"][i]
    curve(ax,f"alt{i}",color,group_label(f"alt{i}",f"{name}, {interval}"))
ax.legend(frameon=False,loc="upper left")
save(fig,"altitude")

# Composition of each altitude class: a group enters the class MSD as p*M_g, so its share
# w_g=p*M_g/M_a of the class MSD can exceed its share of flights p. Along the lag,
# d ln w_g/d ln tau = 2(h_g-h_a) for local exponents h, so the gap between the two dots
# grows only when the groups grow at different rates. Full class denominators.
fig,axs=plt.subplots(1,2,figsize=(5.6,4.35),layout="constrained",sharey=True)
for k,(ax,key,color,title) in enumerate(zip(axs,["open_{}","experts_alt{}"],[BLUE,GOLD],["Open circuits","Experts"])):
    for i in range(4):
        a_=C["groups"][f"alt{i}"];g=C["groups"][key.format(i)];y=3-i
        p=100*g["flights"]/a_["flights"];w=p*g["msd"]["point"][-1]/a_["msd"]["point"][-1]
        ax.plot([p,w],[y,y],color=color,lw=1.4,zorder=3)
        ax.plot(p,y,"o",ms=8,mfc="white",mec=color,mew=1.6,zorder=4);ax.plot(w,y,"o",ms=8,color=color,zorder=5)
        ax.text(p-5,y,f"{p:.0f}%",ha="right",va="center",fontsize=13,color="#666666",bbox=dict(fc="white",ec="none",pad=.5),zorder=2)
        ax.text(w+5,y,f"{w:.0f}%",ha="left",va="center",fontsize=13,color=color,weight="bold")
    ax.axvline(50,color="#888888",ls="--",lw=1,zorder=1)
    ax.set_xlim(4,113);ax.set_xticks([25,50,75,100],["25%","50%","75%","100%"])
    ax.set_title(title,color=color,weight="bold",fontsize=15)
for ax in axs:
    ax.set_ylim(-.6,3.6);ax.grid(axis="x",color="#E2E7EC",lw=.6);ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False);ax.tick_params(axis="y",length=0,labelsize=13.5);ax.tick_params(axis="x",labelsize=11.5)
axs[0].set_yticks(range(4),[f"{n}\nH = {C['groups'][f'alt{i}']['fit']['hurst']['point']:.3f}" for i,n in reversed(list(enumerate(NAMES)))])
# Pooled H falls from Plains to the mountains; Low and High mountains are bracketed together
# because their own order (0.866 < 0.875) runs the other way.
T,x0,grey=axs[0].get_yaxis_transform(),-.9,"#666666"
axs[0].annotate("",(x0,1.3),(x0,3.35),xycoords=T,arrowprops=dict(arrowstyle="-|>",color=grey,lw=1.5,mutation_scale=13),annotation_clip=False)
axs[0].text(x0-.04,2.3,"H decreases",transform=T,rotation=90,ha="right",va="center",fontsize=12.5,color=grey)
axs[0].plot([x0+.04,x0,x0,x0+.04],[1.2,1.2,-.2,-.2],transform=T,clip_on=False,color=grey,lw=1.3)
axs[0].text(x0-.04,.5,f"pooled H = {C['groups']['mountains']['fit']['hurst']['point']:.3f}",transform=T,rotation=90,ha="right",va="center",fontsize=12,color=grey)
marker=dict(marker="o",ms=8,ls="none",mec=grey,mew=1.6)
fig.legend([plt.Line2D([],[],mfc="white",**marker),plt.Line2D([],[],color=grey,**marker)],
           ["share of flights",r"share of the class MSD at τ = 10⁴ s"],loc="outside upper center",ncol=2,frameon=False,fontsize=13,handletextpad=.3,columnspacing=1.2)
save(fig,"altitude-mix")

# Regions, open and closed circuits pooled (thesis Section 3.2.3); lowlands left, mountains right.
fig,axs=plt.subplots(1,2,figsize=(11.8,3.65),layout="constrained",sharey=True)
for ax,title,keys in zip(axs,[r"Lowland launches: $z_0<800$ m, all circuits",r"Mountain launches: $z_0\geq800$ m, all circuits"],
 [[("channel_coast","Channel Coast",TEAL),("champagne_lorraine","Champagne-Lorraine",STEEL)],[("alps","Alps",WINE),("pyrenees","Pyrenees",GOLD)]]):
    for key,label,color in keys:
        curve(ax,key,color,group_label(key,label))
    ax.set_title(title);ax.legend(frameon=False,loc="upper left")
save(fig,"regions")

def local_slope(lags, msd):
    """Half log-log OLS slope, +/-0.25 dex; nearest three at sparse edges (as measure_cadence_support.py)."""
    x,y=np.log10(lags),np.log10(msd);out=[]
    for centre in x:
        distance=np.abs(x-centre);take=np.flatnonzero(distance<=.25+1e-12)
        if len(take)<3: take=np.sort(np.argsort(distance,kind="stable")[:3])
        centred=x[take]-x[take].mean();out.append(.5*centred@y[take]/(centred@centred))
    return a(out)

# Open vs closed: MSD, then its local slope against the fitted H, so the H gap reads by eye.
fig,(ax,axh)=plt.subplots(1,2,figsize=(7.6,3.9),layout="constrained")
for key,color in [("open",BLUE),("closed",WINE)]:
    curve(ax,key,color,key.capitalize())
    g=C["groups"][key];h=g["fit"]["hurst"]["point"]
    axh.plot(C["lags_s"],local_slope(a(C["lags_s"]),a(g["msd"]["point"])),"o-",color=color,lw=1.7,ms=3,mfc="white")
    axh.axhline(h,color=color,lw=1.5,ls="--",label=f"{key.capitalize()}: H = {h:.3f}")
ax.legend(frameon=False,loc="upper left",fontsize=14,handlelength=1.4);ax.set_title("MSD")
style(axh,logy=False);axh.set_xlim(10,10000);axh.set_ylim(.2,1.02);axh.set_ylabel(r"Local slope $H_{\rm loc}$")
axh.axhline(.5,color="#999999",ls=":",lw=1);axh.text(13,.515,"Diffusive",fontsize=11,color="#666666")
axh.legend(frameon=False,loc="lower left",fontsize=13,handlelength=1.6)
axh.set_title("Local slope; dashed: H fitted over 10–10,000 s",fontsize=12);save(fig,"circuit")

# Interaction: open and closed exponents on one axis, with their archived intervals.
# Values sit above the open intervals and below the closed ones; flight counts along the bottom.
fig,ax=plt.subplots(figsize=(7.4,4.5))
# Leave a common band below the class names for the four relief silhouettes.
fig.subplots_adjust(left=.10,right=.99,top=.98,bottom=.235)
for task,color,end,dy,va in [("open",BLUE,"high",.006,"bottom"),("closed",WINE,"low",-.006,"top")]:
    hs=[]
    for i in range(4):
        g=C["groups"][f"{task}_{i}"];h=g["fit"]["hurst"];hs.append(h["point"])
        herror(ax,i,h,color)
        ax.text(i,h[end]+dy,f"{h['point']:.3f}",ha="center",va=va,fontsize=12,color=color)
    ax.plot(range(4),hs,color=color,lw=1.6,zorder=0,label=f"{task.capitalize()} circuits")
for i in range(4):
    ax.text(i-.04,.784,f"{C['groups'][f'open_{i}']['flights']:,}",ha="right",fontsize=10,color=BLUE)
    ax.text(i+.04,.784,f"{C['groups'][f'closed_{i}']['flights']:,}",ha="left",fontsize=10,color=WINE)
ax.text(-.42,.784,"n:",fontsize=10,color="#666666")
ax.set_xticks(range(4),["Plains","Hills","Low\nmountains","High\nmountains"])
for label,tint in zip(ax.get_xticklabels(),ALT_TINTS):
    label.set_color(tint)
    label.set_fontweight("bold")
    label.set_fontsize(12)
terrain_transform = blended_transform_factory(ax.transData,fig.transFigure)
for i in range(4):
    terrain(ax,i,Affine2D().scale(.34,.07).translate(i,.025)+terrain_transform)
ax.grid(axis="y",color="#E2E7EC");ax.set_ylim(.775,.985);ax.set_xlim(-.45,3.45)
ax.set_ylabel("Effective exponent H");ax.legend(frameon=False,loc="upper right",fontsize=13)
save(fig,"interaction")

# Experts versus Beginners, open circuits only (measure_open_circuits.py).
fig,axs=plt.subplots(1,2,figsize=(11.8,4.7),layout="constrained",gridspec_kw={"width_ratios":[1.1,1]})
for key,label,color in [("beginners","Beginners",STEEL),("experts","Experts",GOLD)]:
    curve(axs[0],key,color,group_label(key,label,OPEN),OPEN)
axs[0].legend(frameon=False,loc="upper left");axs[0].set_title("Open circuits, all initial altitudes pooled")
ax=axs[1];keys=["experts_beginners"]+[f"equipment_alt{i}" for i in range(4)]
# Strata take the altitude tints of the interaction slide, outlined in their silhouettes' edge colour.
for i,(key,color) in enumerate(zip(keys,[STEEL]+ALT_TINTS)):
    h=OPEN["contrasts"][key]["hurst"];edge=STEEL if i==0 else edge_of(color)
    bars=ax.errorbar(h["point"],4-i,xerr=[[h["point"]-h["low"]],[h["high"]-h["point"]]],fmt="o",
        color=color,ms=8,mec=edge,mew=1,ecolor=edge,elinewidth=1.8,capsize=4,capthick=1.6)
    for line in bars.lines[2]:
        line.set_color(color);line.set_path_effects([patheffects.Stroke(linewidth=3,foreground=edge),patheffects.Normal()])
# Silhouettes stand for the class names; the pooled row keeps its text label.
# Each row's label is centred left of the axis, with both group sizes below it.
row_anchor = blended_transform_factory(ax.transAxes,ax.transData)
for i,suffix in enumerate([""]+[f"_alt{i}" for i in range(4)]):
    y=4-i
    if i==0:
        ax.annotate("All altitudes",(0,y),xycoords=row_anchor,xytext=(-62,-1),textcoords="offset points",ha="center",va="bottom",fontsize=10.5)
    else:
        terrain(ax,i-1,Affine2D().scale(32/72,18/72).translate(-62/72,1/72)
                +fig.dpi_scale_trans+ScaledTranslation(0,y,row_anchor))
    beginners = OPEN["groups"]["beginners"+suffix]["flights"]
    experts = OPEN["groups"]["experts"+suffix]["flights"]
    ax.annotate(f"N: {beginners:,} B / {experts:,} E",(0,y),xycoords=row_anchor,xytext=(-62,-4),textcoords="offset points",ha="center",va="top",fontsize=10)
ax.axvline(0,ls=":",color="#888888");ax.set_yticks(range(5),[""]*5);ax.tick_params(axis="y",left=False)
ax.set_ylim(-.6,4.6);ax.set_xlim(-.002,.031);ax.grid(axis="x",color="#E2E7EC");ax.set_xlabel(r"$\Delta H$: Experts minus Beginners")
ax.set_title("Open circuits. B: Beginners; E: Experts")
save(fig,"equipment")

inputs=["thesis/tesi/01-introduction.tex","thesis/tesi/03-dataset.tex","thesis/tesi/04-fixed-transport.tex",
 "thesis/generated/ch3_transport_values.tex",
 "scripts/tesi/ch03_fixed_transport/write_ch3_text.py",
 "thesis/generated/ch3_transport_report.json","thesis/generated/ch3_conditional.json",
 "thesis/generated/stats.tex","thesis/generated/pipeline_census.tex",
 "thesis/generated/prelim_map.pdf","thesis/generated/prelim.tex","presentations/theme.tex",
 "thesis/generated/ch3_transport_grid_bootstrap.json","thesis/generated/ch3_transport_grid_bootstrap_values.tex",
 "docs/guide/thermal-planes.md","src/soaring/viewer/widgets/thermal_plane.py",
 "presentations/offsite2026/cadence-support-report.json","presentations/offsite2026/measure_cadence_support.py",
 "presentations/offsite2026/open-circuits-report.json","presentations/offsite2026/measure_open_circuits.py",
 "scripts/tesi/ch03_fixed_transport/circuit_msd_weights.py", "thesis/references.bib",
 "presentations/offsite2026/offsite-2026.tex",
 "presentations/offsite2026/render_figures.py",
 "presentations/offsite2026/preprocessing-global-frame.tex",
 "presentations/offsite2026/render_thermal_panels.py",
 "presentations/offsite2026/assets/screenshots/thermal-panels-report.json",
 "presentations/offsite2026/assets/screenshots/thermal-panel-values.tex",
 "data/basemap.json", "presentations/offsite2026/assets/screenshots/cell-locator.pdf",
 "presentations/offsite2026/render_thermal_mechanism.py",
 "presentations/offsite2026/assets/thermal-mechanism.pdf",
 "src/soaring/viewer/thermal_orography.py",
 "src/soaring/viewer/thermal_ridges.py",
 "scripts/pipeline/prepare_thermal_ridges.py",
 "data/thermal_orography/ign-ridges-185-1295.geojson",
 "data/thermal_orography/ign-ridges-89-1374.geojson"]
inputs += [f"presentations/offsite2026/assets/screenshots/{p['name']}-points.csv" for p in thermal_report["panels"]]
inputs.append("presentations/offsite2026/assets/screenshots/thermal-flight-counts.tex")
# Preserve recorded artwork and logo sources when refreshing numerical figures.
previous_manifest = OUT.parent / "source-manifest.json"
if previous_manifest.exists():
    for item in json.loads(previous_manifest.read_text())["inputs"]:
        if item["path"] not in inputs:
            inputs.append(item["path"])
manifest={"scope":"Thesis Chapters 1–2 and Sections 3.1–3.2; thermal-plane topography; research agenda with a stochastic-flight schematic, sources and conclusions; factorial, directional-memory and bootstrap appendices (29 slides).", "operation":"Redraw saved estimates and intervals. Slide 9 shows the available-population TA-MSD and its shrinking flight support. Slide 11 extends C_10000 below 10 s with cadence-limited support, and densely evaluates the original estimator above 10 s. Original bootstrap draws and 10–10000 s fits are preserved; see cadence-support-report.json. Altitude-class composition compares flight shares with shares of the class MSD at 10^4 s, with full altitude-class denominators and observed curves only. Every plotted category reports its flight count; thermal-map counts use distinct flights from verified crossing CSVs.", "inputs":[]}
for rel in inputs:
    p=ROOT/rel;manifest["inputs"].append({"path":rel,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT.parent/"source-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(f"Saved figures to {OUT}")
