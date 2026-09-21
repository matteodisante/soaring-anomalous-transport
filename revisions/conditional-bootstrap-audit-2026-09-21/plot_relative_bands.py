"""Expose the published band widths without the seven-decade vertical axis."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent
curves=np.load(OUT/'verified_replicates.npz')
fig, axes=plt.subplots(2,2,figsize=(9,6),layout='constrained',sharex=True)
for ax,(key,title) in zip(axes.flat,[('open','Open circuits'),('closed','Closed circuits'),('alps','Alps'),('pyrenees','Pyrenees')],strict=True):
    low,high=np.percentile(curves[key][1:],[5,95],axis=0)
    reference=curves[key][0]
    ax.fill_between(curves['lags'],100*(low/reference-1),100*(high/reference-1),color='#357a9a',alpha=.25)
    ax.plot(curves['lags'],100*(low/reference-1),color='#357a9a',lw=1)
    ax.plot(curves['lags'],100*(high/reference-1),color='#357a9a',lw=1)
    ax.axhline(0,color='#333333',lw=.8)
    ax.set_xscale('log')
    ax.set_title(title)
    ax.set_ylabel('Deviation from observed MSD (%)')
    ax.grid(alpha=.2)
    ax.set_xlim(10,10000)
for ax in axes[-1]:ax.set_xlabel('Lag (s)')
fig.suptitle('Published pointwise 90% bootstrap bands on a relative scale',fontsize=13)
fig.savefig(OUT/'relative_bands.png',dpi=170)
