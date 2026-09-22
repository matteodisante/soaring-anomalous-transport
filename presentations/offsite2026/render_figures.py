"""Projection-sized figures from thesis reports and the slide-9 cadence extension."""
from pathlib import Path
import hashlib
import json
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)
R = json.loads((ROOT / "thesis/generated/ch3_transport_report.json").read_text())
C = json.loads((ROOT / "thesis/generated/ch3_conditional.json").read_text())
CADENCE = json.loads((OUT.parent / "cadence-support-report.json").read_text())
BLUE, RUST, STEEL, TEAL, GOLD, WINE = "#3477A8", "#B5482A", "#4A6079", "#2E7D8A", "#C98A1E", "#8E3B5C"
ALT = [BLUE, TEAL, GOLD, WINE]
NAMES = ["Plains", "Hills", "Low mountains", "High mountains"]
sys.path.insert(0, str(ROOT / "scripts/tesi/ch03_fixed_transport"))
from circuit_msd_weights import compute_weights, plot_weights

plt.rcParams.update({"font.family":"serif", "font.serif":["Palatino","DejaVu Serif"], "font.size":13,
 "axes.labelsize":13, "axes.titlesize":14, "legend.fontsize":11, "xtick.labelsize":11,
 "ytick.labelsize":11, "axes.spines.top":False,"axes.spines.right":False,
 "pdf.fonttype":42,"axes.edgecolor":"#666666", "text.color":"#202A35"})
plot_weights(compute_weights(C), OUT / "circuit-weights.pdf", colors=ALT,
             figsize=(11.8, 3.5), fontsize=13)

def a(x): return np.asarray(x, dtype=float)
def hci(h):
    return f"{h['point']:.3f} [{h['low']:.3f}, {h['high']:.3f}]"
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

# Full C_10000 from 10 s onward; increasing cadence-limited support below 10 s.
fig,axs=plt.subplots(1,2,figsize=(11.8,4.1),layout="constrained")
for ax in axs:
    ax.axvline(10,color="#A0ACBA",lw=.8,ls="--",zorder=-1)
for slug,color,label in [("para",BLUE,"Paragliders"),("hang",RUST,"Hang gliders")]:
    d=CADENCE["results"][slug];h=d["fit_10_10000"]
    x=a(CADENCE["lags_s"])
    for ax,field,scale,legend in [(axs[0],"msd",1e6,f"{label}: H = {hci(h)}"),
                                 (axs[1],"local_h",1,label)]:
        p,l,u=[a(d[field][k])/scale for k in ["point","low","high"]]
        ax.fill_between(x,l,u,color=color,alpha=.17,lw=0)
        ax.plot(x,p,color=color,lw=1.7,label=legend)
        # Explicit integer-second evaluations in the cadence-limited range.
        short=x<=10
        ax.plot(x[short],p[short],"o",color=color,ms=2.8,mfc="white")
axs[0].set_ylabel(r"MSD (km$^2$)");style(axs[0]);axs[0].set_xlim(1,10000);axs[0].legend(frameon=False)
axs[0].set_title("MSD; H fitted over 10–10,000 s")
style(axs[1],logy=False);axs[1].set_ylabel(r"Local growth exponent $H_{\rm loc}$")
axs[1].axhline(.5,color="#999999",ls=":",lw=1);axs[1].text(1.25,.515,"Diffusive",fontsize=11,color="#666666")
lower=min(min(CADENCE["results"][s]["local_h"]["low"]) for s in ["para","hang"])
upper=max(max(CADENCE["results"][s]["local_h"]["high"]) for s in ["para","hang"])
axs[1].set_xlim(1,10000);axs[1].set_ylim(min(.26,lower-.025),max(1.07,upper+.035));axs[1].legend(frameon=False,loc="lower left")
axs[1].set_title("Local slope on a dense lag grid")
save(fig,"fixed")

cadence_tex=[]
for slug,prefix in [("para","CadencePara"),("hang","CadenceHang")]:
    d=CADENCE["results"][slug]
    cadence_tex.append("\\newcommand{\\"+prefix+"Count}{"+f"{d['flights']:,}"+"}")
    cadence_tex.append("\\newcommand{\\"+prefix+"StartCount}{"+f"{d['support'][0]:,}"+"}")
    for suffix,key in [("H","point"),("Low","low"),("High","high")]:
        cadence_tex.append("\\newcommand{\\"+prefix+suffix+"}{"+f"{d['fit_10_10000'][key]:.3f}"+"}")
cadence_tex.append(r"\newcommand{\CadenceLagCount}{"+str(len(CADENCE["lags_s"]))+"}")
(OUT.parent/"cadence-values.tex").write_text("\n".join(cadence_tex)+"\n")

# Conditional curves, without re-fitting any saved result.
fig,ax=plt.subplots(figsize=(7.4,4.2),layout="constrained")
for i,(name,color) in enumerate(zip(NAMES,ALT)):
    g=C["groups"][f"alt{i}"]
    interval=["<300 m","300–800 m","800–1,500 m","≥1,500 m"][i]
    curve(ax,f"alt{i}",color,f"{name} ({interval})\nH={hci(g['fit']['hurst'])}")
ax.legend(frameon=False,loc="upper left")
save(fig,"altitude")

fig,axs=plt.subplots(1,2,figsize=(11.8,4.1),layout="constrained",sharey=True)
for ax,title,keys in zip(axs,[r"Mountain launches: $z_0\geq800$ m",r"Lowland launches: $z_0<800$ m"],
 [[("alps","Alps",WINE),("pyrenees","Pyrenees",GOLD)],[("channel_coast","Channel Coast",TEAL),("champagne_lorraine","Champagne-Lorraine",STEEL)]]):
    for key,label,color in keys:
        h=C["groups"][key]["fit"]["hurst"]
        curve(ax,key,color,f"{label}\nH={hci(h)}")
    ax.set_title(title);ax.legend(frameon=False,loc="upper left")
save(fig,"regions")

fig,ax=plt.subplots(figsize=(7.4,4.2),layout="constrained")
for key,color in [("open",BLUE),("closed",WINE)]:
    g=C["groups"][key];curve(ax,key,color,f"{key.capitalize()}  H={hci(g['fit']['hurst'])}")
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
for key,label,color in [("beginners","Beginners",STEEL),("experts","Experts",GOLD)]:
    g=C["groups"][key];curve(axs[0],key,color,f"{label}\nH={hci(g['fit']['hurst'])}")
axs[0].legend(frameon=False,loc="upper left");axs[0].set_title("All initial altitudes pooled")
ax=axs[1];keys=["experts_beginners"]+[f"equipment_alt{i}" for i in range(4)]
for i,(key,color) in enumerate(zip(keys,[STEEL]+ALT)):
    h=C["contrasts"][key]["hurst"]
    ax.errorbar(h["point"],4-i,xerr=[[h["point"]-h["low"]],[h["high"]-h["point"]]],fmt="o",color=color,ms=7,capsize=4)
ax.axvline(0,ls=":",color="#888888");ax.set_yticks(range(5),list(reversed(["All altitudes"]+NAMES)))
ax.set_xlim(-.002,.031);ax.grid(axis="x",color="#E2E7EC");ax.set_xlabel(r"$\Delta H$: Experts minus Beginners")
ax.set_title("The difference survives altitude stratification")
save(fig,"equipment")

inputs=["thesis/tesi/01-introduction.tex","thesis/tesi/03-dataset.tex","thesis/tesi/04-fixed-transport.tex",
 "thesis/generated/ch3_transport_values.tex",
 "scripts/tesi/ch03_fixed_transport/write_ch3_text.py",
 "thesis/generated/ch3_transport_report.json","thesis/generated/ch3_conditional.json",
 "thesis/generated/stats.tex","thesis/generated/pipeline_census.tex",
 "thesis/generated/prelim_map.pdf","presentations/theme.tex",
 "thesis/generated/ch3_transport_grid_bootstrap.json","thesis/generated/ch3_transport_grid_bootstrap_values.tex",
 "docs/guide/thermal-planes.md","src/soaring/viewer/widgets/thermal_plane.py",
 "presentations/offsite2026/cadence-support-report.json","presentations/offsite2026/measure_cadence_support.py",
 "scripts/tesi/ch03_fixed_transport/circuit_msd_weights.py", "thesis/references.bib",
 "presentations/offsite2026/offsite-2026.tex",
 "presentations/offsite2026/preprocessing-global-frame.tex",
 "presentations/offsite2026/render_thermal_panels.py",
 "presentations/offsite2026/assets/screenshots/thermal-panels-report.json",
 "presentations/offsite2026/assets/screenshots/thermal-panel-values.tex",
 "data/basemap.json", "presentations/offsite2026/assets/screenshots/cell-locator.pdf",
 "presentations/offsite2026/assets/thermal-mechanism-3d.png",
 "presentations/offsite2026/assets/thermal-mechanism-3d-prompt.txt",
 "src/soaring/viewer/thermal_orography.py",
 "src/soaring/viewer/thermal_ridges.py",
 "scripts/pipeline/prepare_thermal_ridges.py",
 "data/thermal_orography/ign-ridges-185-1295.geojson",
 "data/thermal_orography/ign-ridges-89-1374.geojson"]
manifest={"scope":"Current thesis Chapters 1–2 and Sections 3.1–3.2: marginal and stratified comparisons, within-altitude circuit MSD contributions, and motivation for future factorial/group-solo analysis; plus a qualitative thermal-viewer comparison", "operation":"Redraw saved estimates and intervals. Slide 9 extends C_10000 below 10 s with cadence-limited support, and densely evaluates the original estimator above 10 s. Original bootstrap draws and 10–10000 s fits are preserved; see cadence-support-report.json. Circuit weights use the full altitude-class MSD denominator and observed curves only.", "inputs":[]}
for rel in inputs:
    p=ROOT/rel;manifest["inputs"].append({"path":rel,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT.parent/"source-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(f"Saved figures to {OUT}")
