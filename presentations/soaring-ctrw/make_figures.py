from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator
from scipy.linalg import toeplitz, eigvalsh
import json

out=Path(__file__).resolve().parent/'assets'
out.mkdir(exist_ok=True)
# Original Monte Carlo/calibration figures are bundled and remain unchanged.
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':13,'axes.spines.top':False,'axes.spines.right':False,'axes.labelsize':13,'xtick.labelsize':11,'ytick.labelsize':11,'legend.fontsize':11,'axes.linewidth':.7,'pdf.fonttype':42,'savefig.transparent':False})
T='#1f50a0'; S='#c83c32'; C='#1e8c46'; gray='#6b7178'; orange='#c37811'; purple='#7c5799'
def save(fig,name):
    fig.savefig(out/f'{name}.pdf',bbox_inches='tight',pad_inches=.06)
    fig.savefig(out/f'{name}.png',dpi=150,bbox_inches='tight',pad_inches=.06)
    plt.close(fig)
def clean(ax):
    ax.grid(alpha=.14,which='major'); ax.set_axisbelow(True)

# An explicitly illustrative horizontal trajectory, preserving phase mechanisms.
fig,ax=plt.subplots(figsize=(10.6,2.2))
p0=np.array([0.,0.]); angle=.16
p1=p0+np.array([4.,.64]); ax.plot([*p0[:1],*p1[:1]],[p0[1],p1[1]],color=T,lw=3)
search=np.array([[0,0],[.55,.25],[.55,.25],[.25,.6],[.65,.68],[.65,.68],[.4,.9],[.85,.75]])+p1
ax.plot(search[:,0],search[:,1],color=S,lw=2.4)
ax.scatter(search[[1,4],0],search[[1,4],1],s=35,color=S,zorder=3)
t=np.linspace(0,4*np.pi,280); climb=np.c_[.28*np.sin(t)+.055*t,.28*(1-np.cos(t))]+search[-1]
ax.plot(climb[:,0],climb[:,1],color=C,lw=2)
p2=climb[-1]; p3=p2+np.array([3.5,-.5]); ax.plot([p2[0],p3[0]],[p2[1],p3[1]],color=T,lw=3)
for x,y,txt,col in [(1.5,.76,'T  transition',T),(3.85,2.05,'S  search',S),(6.05,2.05,'C  climb',C),(7.55,.35,'next glide',T)]:
    ax.text(x,y,txt,color=col,ha='center',fontsize=15)
ax.annotate('',xy=p3,xytext=p3-np.array([.3,-.043]),arrowprops={'arrowstyle':'->','color':T,'lw':2.6})
ax.set_aspect('equal'); ax.set_xlim(-.2,10); ax.set_ylim(-.15,2.6); ax.axis('off')
save(fig,'cycle_trajectory')

# Search: illustrative deterministic schedule, not a fitted or MC trajectory.
t=np.array([0,7,18,24,50,55,86,94,130]); x=np.array([0,7,7,13,13,18,18,26,26])
fig,ax=plt.subplots(figsize=(5.5,3.1))
for i in range(len(t)-1):
    ax.plot(t[i:i+2],x[i:i+2],color=S if x[i+1]!=x[i] else gray,lw=3)
ax.text(5,8.9,'relocation',color=S,fontsize=13)
ax.annotate('turning wait',xy=(38,13),xytext=(51,4.5),color=gray,fontsize=13,arrowprops=dict(arrowstyle='->',color=gray))
ax.set(xlabel='Time within search (arbitrary units)',ylabel='Path length travelled',xticks=[],yticks=[])

save(fig,'search_clock')

# Climb: exact trajectory for a fixed period, with drifting centre.
t=np.linspace(0,90,2000); r=39.; omega=2*np.pi/30; vd=1.9
xx=r*np.sin(omega*t)+vd*t; yy=r*(1-np.cos(omega*t))
fig,axs=plt.subplots(1,2,figsize=(10.8,3.0),gridspec_kw={'width_ratios':[1,1.1]})
ax=axs[0]; ax.plot(xx,yy,color=C,lw=2); ax.plot(vd*t,np.full_like(t,r),'--',color=gray,lw=1.5,label='drifting centre')
ax.set(xlabel='$x$ (m)',ylabel='$y$ (m)',xlim=(-25,215),ylim=(-10,100)); ax.set_aspect('equal',adjustable='box'); ax.legend(frameon=False,loc='upper left'); ax.set_title('One climb, fixed period',fontsize=13)
ax=axs[1]; d=np.logspace(-1,3,800); sigw=omega*10/30
circ=2*r*r*(1-np.exp(-sigw*sigw*d*d/2)*np.cos(omega*d)); drift=vd*vd*d*d
ax.loglog(d,circ+drift,color=C,lw=2.3,label='total'); ax.loglog(d,circ,'--',color=gray,lw=1.6,label='circle'); ax.loglog(d,drift,':',color=orange,lw=2,label='drift')
ax.set(xlabel=r'Lag $\Delta$ (s)',ylabel='Climb MSD (m$^2$)'); clean(ax); ax.legend(frameon=False,loc='upper left'); ax.set_title('Approximate period average',fontsize=13)
fig.tight_layout(w_pad=2); save(fig,'climb_mechanism')

# Exact persistent-walk angular factor, plotted at integer cycle count.
n=np.arange(1,10001); sig=.412; rho=np.exp(-sig*sig/2); nc=2/sig**2
G=n*(1+rho)/(1-rho)-2*rho*(-np.expm1(n*np.log(rho)))/(1-rho)**2
fig,ax=plt.subplots(figsize=(7.0,3.65))
ax.loglog(n,G,color=T,lw=2.8,label='exact $G_N$')
small=n[n<=10]; big=n[n>=35]
ax.loglog(small,small**2,'--',color=orange,lw=1.6,label='$N^2$')
ax.loglog(big,(1+rho)/(1-rho)*big,':',color=gray,lw=2,label=r'$[(1+\rho)/(1-\rho)]N$')
ax.axvline(nc,color=gray,lw=1,alpha=.6); ax.text(nc*1.2,2,'$n_c$',color=gray)
ax.set(xlabel='Number of cycles $N$',ylabel='Coherent contribution $G_N$',ylim=(.8,5e5)); clean(ax); ax.legend(frameon=False,loc='upper left'); save(fig,'persistent_limits')

# Coarse-graining to glide/rest: displacement coordinate along consecutive glides.
times=np.array([0,3,5,8,10,13]); pos=np.array([0,3,3,5.7,5.7,8.6]); fig,ax=plt.subplots(figsize=(10.7,2.4))
for i in range(len(times)-1):
    moving=pos[i+1]!=pos[i]; color=T if moving else gray
    ax.plot(times[i:i+2],pos[i:i+2],color=color,lw=3)
    labels=[r'glide $\theta_1$','$W_1=S_1+C_1$',r'glide $\theta_2$','$W_2=S_2+C_2$',r'glide $\theta_3$']
    ax.text((times[i]+times[i+1])/2,(pos[i]+pos[i+1])/2+.75,labels[i],ha='center',color=color,fontsize=13)
ax.set(xlabel='Time (schematic)',ylabel='Horizontal displacement',xticks=[],yticks=[],ylim=(-.3,10)); save(fig,'glide_wait')

# Discrete Green-Kubo sums. All curves illustrative, no empirical fit.
K=1000000; ks=np.arange(1,K,dtype=float); beta=.24; k0=4.
corrs=[np.exp(-ks/nc),(1+ks/k0)**(-beta)]
labels=['Exponential',r'Power law, $\beta=0.24$']; colors=[T,orange]; styles=['-','-']
idx=np.unique(np.geomspace(1,K,650).astype(int)); fulln=np.arange(1,K+1,dtype=float)
fig,axs=plt.subplots(1,2,figsize=(11,3.35))
slopes={}
for c,label,col,ls in zip(corrs,labels,colors,styles):
    g=fulln+2*(fulln*np.r_[0,np.cumsum(c)]-np.r_[0,np.cumsum(ks*c)])
    lag=np.unique(np.geomspace(1,100000,350).astype(int))
    axs[0].loglog(lag,c[lag-1],label=label,color=col,ls=ls,lw=2.3)
    axs[1].loglog(idx,g[idx-1]/idx,color=col,ls=ls,lw=2.3)
    slopes[label]=float((np.log(g[-1])-np.log(g[-101]))/(np.log(fulln[-1])-np.log(fulln[-101])))
axs[0].set(xlabel='Lag $k$ (glides)',ylabel='Heading correlation $C(k)$',ylim=(.001,1.2),xlim=(1,1e5)); axs[0].legend(frameon=False,fontsize=10.8,loc='lower left')
axs[1].set(xlabel='Number of cycles $N$',ylabel='$G_C(N)/N$',xlim=(1,1e6)); axs[1].text(5e3,34,'diffusive plateau',color=T,fontsize=11); axs[1].text(700,3000,'persistent growth',color=orange,fontsize=11,rotation=20)
for ax in axs: clean(ax)
fig.tight_layout(w_pad=2); save(fig,'correlation_asymptotes')

# Mathematical verification of a valid stationary Gaussian increment sequence.
j=np.arange(600,dtype=float); gam=np.empty_like(j); gam[0]=2*beta*np.log1p(1/k0); gam[1:]=beta*np.log1p(-1/(k0+j[1:])**2)
Gamma=toeplitz(gam); mineig=float(eigvalsh(Gamma,subset_by_index=[0,0])[0]); assert mineig>0
variogram={}
for k in [1,2,10,100,600]:
    v=float(Gamma[:k,:k].sum()); expected=2*beta*np.log1p(k/k0); assert np.isclose(v,expected,rtol=1e-10)
    variogram[k]={'computed':v,'expected':float(expected)}
(out.parent/'math_checks.json').write_text(json.dumps({'minimum_eigenvalue':mineig,'variogram':variogram,'asymptotic_MSD_slopes':slopes},indent=2))
print(json.dumps({'figures':len(list(out.glob('*.pdf'))),'minimum_eigenvalue':mineig,'asymptotic_MSD_slopes':slopes},indent=2))
