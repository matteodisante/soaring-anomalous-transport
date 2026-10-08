from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
out=Path(__file__).resolve().parent/'assets'
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':12,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
# Illustration of the same four relocation lengths as the spatial schematic.
# With constant speed, relocation duration is proportional to length.
points=np.array([[0,.20],[1.45,.55],[2.35,1.55],[3.55,.80],[5.05,1.25]])
steps=np.diff(points,axis=0); lengths=np.linalg.norm(steps,axis=1)
headings=np.arctan2(steps[:,1],steps[:,0]); turns=np.diff(headings)
# Choose positive waits compatible with psi_next=psi+epsilon*Omega*wait,
# adding one full rotation to the second wait for a visible longer pause.
Omega=1.4
waits=(np.abs(turns)+np.array([0,2*np.pi,0]))/Omega
fig,ax=plt.subplots(figsize=(7.4,1.15))
t=0.; d=0.
for j,length in enumerate(lengths):
    duration=length
    ax.plot([t,t+duration],[d,d+length],color='#c83c32',lw=2.3)
    t+=duration; d+=length
    if j<len(waits):
        w=waits[j]
        ax.plot([t,t+w],[d,d],color='#6b7178',lw=2.3)
        ax.text(t+w/2,d+.38,str(j+1),ha='center',va='bottom',color='#6b7178',fontsize=11)
        t+=w
ax.set_xticks([]); ax.set_yticks([])
ax.set_ylabel('Distance\ntravelled',rotation=0,ha='right',va='center',labelpad=12)
ax.set_xlabel('Time (schematic)',labelpad=2)
ax.set_ylim(-.2,d+.65); ax.set_xlim(-.2,t+.2)
fig.savefig(out/'search_clock_wide.pdf',bbox_inches='tight',pad_inches=.05)
fig.savefig(out/'search_clock_wide.png',dpi=170,bbox_inches='tight',pad_inches=.05)
plt.close(fig)
