"""Projection-sized figures from the current thesis reports; no new fits or resampling."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)
R = json.loads((ROOT / "thesis/generated/ch3_transport_report.json").read_text())
C = json.loads((ROOT / "thesis/generated/ch3_conditional.json").read_text())
BLUE, RUST, STEEL, TEAL, GOLD, WINE = "#3477A8", "#B5482A", "#4A6079", "#2E7D8A", "#C98A1E", "#8E3B5C"
ALT = [BLUE, TEAL, GOLD, WINE]
NAMES = ["Plains", "Hills", "Low mountains", "High mountains"]
plt.rcParams.update({"font.family":"serif", "font.serif":["Palatino","DejaVu Serif"], "font.size":13,
 "axes.labelsize":13, "axes.titlesize":14, "legend.fontsize":11, "xtick.labelsize":11,
 "ytick.labelsize":11, "axes.spines.top":False,"axes.spines.right":False,
 "pdf.fonttype":42,"axes.edgecolor":"#666666", "text.color":"#202A35"})

def a(x): return np.asarray(x, dtype=float)
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
def curve(ax, key, color, label=None):
    g=C["groups"][key]
    band(ax,a(C["lags_s"]),g["msd"],color,label)
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
            if key in fits: herror(ax,j+offset,fits[key]["hurst"],color,label=r"$C_{"+key+"}$" if j==0 else None)
    ax.set_title(title);ax.set_xticks([0,1],["10–100 s","10–1000 s"]);ax.set_xlabel("Same fit range")
    ax.grid(axis="y",color="#E2E7EC");ax.set_xlim(-.5,1.5)
axs[0].set_ylabel("Effective exponent H");axs[0].legend(frameon=False,fontsize=10,loc="lower left")
save(fig,"selection")

# Fixed population, preserving both overall growth and curvature.
fig,axs=plt.subplots(1,2,figsize=(11.8,4.1),layout="constrained")
for slug,color,label in [("para",BLUE,"Paragliders"),("hang",RUST,"Hang gliders")]:
    d=R["results"][slug];h=d["fits"]["10-10000"]["hurst"]
    band(axs[0],a(d["msd_lags"]),d["msd"],color,f"{label}: H = {h['point']:.3f}",idx=3)
    band(axs[1],a(R["lags_s"]),d["fixed_local_h"],color,label,scale=1)
axs[0].set_ylabel(r"MSD (km$^2$)");style(axs[0]);axs[0].set_xlim(10,10000);axs[0].legend(frameon=False)
axs[0].set_title("Equal flight weights; fixed flights and segments")
style(axs[1],logy=False);axs[1].set_ylabel(r"Local growth exponent $H_{\rm loc}$")
axs[1].axhline(1,color="#999999",ls=":",lw=1);axs[1].text(11,1.01,"Ballistic",fontsize=11,color="#666666")
axs[1].axhline(.5,color="#999999",ls=":",lw=1);axs[1].text(11,.515,"Diffusive",fontsize=11,color="#666666")
axs[1].set_xlim(10,10000);axs[1].set_ylim(.26,1.06);axs[1].legend(frameon=False,loc="lower left")
axs[1].set_title("The slope changes across scales")
save(fig,"fixed")

# Conditional curves, without re-fitting any saved result.
fig,ax=plt.subplots(figsize=(7.4,4.2),layout="constrained")
for i,(name,color) in enumerate(zip(NAMES,ALT)):
    g=C["groups"][f"alt{i}"]
    curve(ax,f"alt{i}",color,f"{name}  H={g['fit']['hurst']['point']:.3f}")
ax.legend(frameon=False,loc="upper left")
save(fig,"altitude")

fig,axs=plt.subplots(1,2,figsize=(11.8,4.1),layout="constrained",sharey=True)
for ax,title,keys in zip(axs,[r"Mountain launches: $z_0\geq800$ m",r"Lowland launches: $z_0<800$ m"],
 [[("alps","Alps",WINE),("pyrenees","Pyrenees",GOLD)],[("channel_coast","Channel Coast",TEAL),("champagne_lorraine","Champagne-Lorraine",STEEL)]]):
    for key,label,color in keys:
        h=C["groups"][key]["fit"]["hurst"]["point"]
        curve(ax,key,color,f"{label}  H={h:.3f}")
    ax.set_title(title);ax.legend(frameon=False,loc="upper left")
save(fig,"regions")

fig,ax=plt.subplots(figsize=(7.4,4.2),layout="constrained")
for key,color in [("open",BLUE),("closed",WINE)]:
    g=C["groups"][key];curve(ax,key,color,f"{key.capitalize()}  H={g['fit']['hurst']['point']:.3f}")
ax.legend(frameon=False,loc="upper left");save(fig,"circuit")

# Interaction: display the fitted exponents with their archived intervals.
fig,axs=plt.subplots(1,2,figsize=(11.8,3.95),layout="constrained",sharey=True)
for ax,task,title in zip(axs,["open","closed"],["Open circuits","Closed circuits"]):
    hs=[]
    for i,color in enumerate(ALT):
        g=C["groups"][f"{task}_{i}"];h=g["fit"]["hurst"];hs.append(h["point"])
        herror(ax,i,h,color)
        ax.text(i,h["point"]+.013,f"{h['point']:.3f}",ha="center",fontsize=12,color=color)
        ax.text(i,.784,f"n={g['flights']:,}",ha="center",fontsize=10,color="#666666")
    ax.plot(range(4),hs,color="#ABB6C2",lw=1.1,zorder=0)
    ax.set_xticks(range(4),["Plains","Hills","Low\nmountains","High\nmountains"])
    ax.set_title(title);ax.grid(axis="y",color="#E2E7EC");ax.set_ylim(.775,.985);ax.set_xlim(-.45,3.45)
axs[0].set_ylabel("Effective exponent H")
save(fig,"interaction")

fig,axs=plt.subplots(1,2,figsize=(11.8,4.05),layout="constrained",gridspec_kw={"width_ratios":[1.1,1]})
for key,label,color in [("beginners","EN A/B/C",STEEL),("experts","EN D/CCC",GOLD)]:
    g=C["groups"][key];curve(axs[0],key,color,f"{label}  H={g['fit']['hurst']['point']:.3f}")
axs[0].legend(frameon=False,loc="upper left");axs[0].set_title("All initial altitudes pooled")
ax=axs[1];keys=["experts_beginners"]+[f"equipment_alt{i}" for i in range(4)]
for i,(key,color) in enumerate(zip(keys,[STEEL]+ALT)):
    h=C["contrasts"][key]["hurst"]
    ax.errorbar(h["point"],4-i,xerr=[[h["point"]-h["low"]],[h["high"]-h["point"]]],fmt="o",color=color,ms=7,capsize=4)
ax.axvline(0,ls=":",color="#888888");ax.set_yticks(range(5),list(reversed(["All altitudes"]+NAMES)))
ax.set_xlim(-.002,.031);ax.grid(axis="x",color="#E2E7EC");ax.set_xlabel(r"$\Delta H$: EN D/CCC minus EN A/B/C")
ax.set_title("The difference survives altitude stratification")
save(fig,"equipment")

inputs=["thesis/tesi/01-introduction.tex","thesis/tesi/03-dataset.tex","thesis/tesi/04-fixed-transport.tex",
 "thesis/generated/ch3_transport_report.json","thesis/generated/ch3_conditional.json",
 "thesis/generated/stats.tex","thesis/generated/pipeline_census.tex",
 "thesis/generated/prelim_map.pdf","thesis/generated/cleaning_real_examples.pdf","presentations/theme.tex",
 "docs/guide/thermal-planes.md","src/soaring/viewer/widgets/thermal_plane.py"]
manifest={"scope":"Current thesis Chapters 1–2 and Sections 3.1–3.2, plus a qualitative thermal-viewer comparison", "operation":"Redraw saved estimates and intervals; no refitting, new bootstrap or trajectory processing", "inputs":[]}
for rel in inputs:
    p=ROOT/rel;manifest["inputs"].append({"path":rel,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT.parent/"source-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(f"Saved figures to {OUT}")
