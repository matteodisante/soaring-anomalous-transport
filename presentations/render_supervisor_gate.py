"""Re-layout the existing synthetic reach-gate examples for projection.

Calls the original example function with its save callback redirected in memory.
The synthetic inputs and implemented cleaning decisions are unchanged. No observed
flight data or canonical generated outputs are read or overwritten.
"""
from pathlib import Path
import hashlib
import json
import runpy

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from soaring.reporting.snapshot import current_cleaning

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent/'assets'
SOURCE=ROOT/'scripts/reporting/ch2_dataset/generate_cleaning_explainers.py'


def plotted_data(axes):
    h=hashlib.sha256()
    for ax in axes:
        h.update(str((ax.get_xlim(),ax.get_ylim(),ax.get_yscale())).encode())
        for line in ax.lines:
            h.update(np.asarray(line.get_xdata(),dtype=float).tobytes())
            h.update(np.asarray(line.get_ydata(),dtype=float).tobytes())
        for patch in ax.patches:
            h.update(patch.get_path().vertices.tobytes())
    return h.hexdigest()


def main():
    source=runpy.run_path(str(SOURCE))
    captured=[]
    source['horizontal_gate'].__globals__['save']=lambda fig,name:captured.append(fig)
    source['horizontal_gate']()
    if len(captured)!=1:
        raise ValueError('Expected the original single six-panel example')
    fig=captured[0]; fig.set_layout_engine(None); fig.set_size_inches(7.2,3.3)
    records={}
    for column,tag in enumerate(('spike','rejoin','boundary')):
        axes=[fig.axes[column],fig.axes[column+3]]
        before=plotted_data(axes)
        for ax in fig.axes: ax.set_visible(ax in axes)
        for ax,x in zip(axes,[.11,.62],strict=True):
            ax.set_position([x,.21,.33,.65])
            ax.set_xlabel('Time [s]',fontsize=12)
            ax.xaxis.label.set_size(12); ax.yaxis.label.set_size(12)
            ax.tick_params(labelsize=11,labelbottom=True)
            ax.set_title(ax.get_title(loc='left'),loc='left',fontsize=12)
            for text in ax.texts: text.set_fontsize(11)
        if before!=plotted_data(axes):
            raise ValueError('Synthetic plotted data or limits changed during re-layout')
        path=OUT/f'gate-{tag}-pair.pdf'
        fig.savefig(path,bbox_inches='tight',pad_inches=.04,metadata={'CreationDate':None})
        records[path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                            'unchanged_data_sha256':before}
    plt.close(fig)
    captured.clear()
    source['median'].__globals__['save']=lambda fig,name:captured.append(fig)
    source['median']()
    if len(captured)!=1:
        raise ValueError('Expected the original three-row vertical example')
    fig=captured[0]; fig.set_layout_engine(None); fig.set_size_inches(7.2,3.3)
    for row,tag in [(1,'spike'),(2,'sustained')]:
        axes=fig.axes[2*row:2*row+2]
        before=plotted_data(axes)
        for ax in fig.axes: ax.set_visible(ax in axes)
        for ax,x in zip(axes,[.10,.61],strict=True):
            ax.set_position([x,.21,.34,.65])
            ax.set_xlabel('Time [s]',fontsize=12)
            ax.xaxis.label.set_size(12); ax.yaxis.label.set_size(12)
            ax.tick_params(labelsize=11,labelbottom=True)
            ax.set_title(ax.get_title(loc='left'),loc='left',fontsize=12)
        axes[1].legend(frameon=False,fontsize=8,loc='upper left')
        if before!=plotted_data(axes):
            raise ValueError('Vertical example values changed during re-layout')
        path=OUT/f'vertical-{tag}.pdf'
        fig.savefig(path,bbox_inches='tight',pad_inches=.04,metadata={'CreationDate':None})
        records[path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                            'unchanged_data_sha256':before}
    plt.close(fig)
    manifest={'operation':__doc__,'plot_function_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'cleaning':current_cleaning(ROOT),'outputs':records}
    (OUT.parent/'supervisor-gate-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Re-laid out five original synthetic example pairs; plotted values unchanged.')


if __name__=='__main__': main()
