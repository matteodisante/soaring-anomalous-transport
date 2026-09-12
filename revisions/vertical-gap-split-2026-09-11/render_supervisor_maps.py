"""Re-layout the existing launch maps with readable labels, using metadata only.

Uses the original plot function, bins, positions, geographic extents and colours.
No trajectory arrays, raw IGC reads, fitted parameters or bootstrap are involved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import runpy

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
GENERATOR=ROOT/'scripts/reporting/ch2_dataset/generate_prelim_figure.py'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry(ax):
    """Identify the data shown before and after changing only typography/layout."""
    signature=hashlib.sha256()
    for item in [ax.get_xlim(),ax.get_ylim(),ax.get_aspect()]:
        signature.update(str(item).encode())
    for c in ax.collections:
        for item in [c.get_offsets(),c.get_array(),c.get_clim()]:
            if item is not None:
                array=np.ma.asarray(item)
                signature.update(np.asarray(array.filled(0)).tobytes())
                signature.update(np.ma.getmaskarray(array).tobytes())
        if hasattr(c,'get_coordinates'):
            signature.update(np.asarray(c.get_coordinates()).tobytes())
    return signature.hexdigest()


def render(run,out):
    manifest_path=run/'manifest.json'
    release=json.loads(manifest_path.read_text())
    stage=next(s for s in release['stages'] if s['id']=='preliminary')
    if stage['status']!='complete':
        raise ValueError('The original preliminary-map stage must be complete')
    command=stage['command']
    audit_dir=Path(command[command.index('--audit-dir')+1])
    source=runpy.run_path(str(GENERATOR))
    loaded={}; inputs={}
    for name,glider in source['DISCIPLINES'].items():
        audit=audit_dir/f'audit_flights_{glider.slug}.parquet'
        path=glider.derived_dir()/'flights_meta.parquet'
        ids=pd.read_parquet(audit,columns=['flight_id'])
        meta=pd.read_parquet(path,columns=['flight_id','drop_reason','lat0','lon0'])
        meta=meta.loc[meta.drop_reason.isna(),['flight_id','lat0','lon0']]
        frame=ids.merge(meta,on='flight_id',how='left',validate='one_to_one',sort=False)
        if len(ids)!=len(meta) or frame[['lat0','lon0']].isna().any().any():
            raise ValueError('Launch metadata must cover every retained audit flight')
        loaded[name]={'flights':frame}
        for p in [audit,path]: inputs[str(p)]={'sha256':digest(p),'size_bytes':p.stat().st_size}
    out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'serif','font.serif':['STIXGeneral'],
                        'mathtext.fontset':'stix','pdf.fonttype':42})
    outputs={}
    for index,tag in enumerate(('france','reunion','world')):
        fig=source['draw_maps'](loaded)
        ax=fig.axes[index]; before=geometry(ax)
        fig.set_layout_engine(None)
        fig.set_size_inches(6.8,3.8)
        for a in fig.axes: a.set_visible(a is ax)
        ax.set_position([.10,.17,.70,.73])
        if index==0:
            cb=fig.axes[3]; cb.set_visible(True); cb.set_position([.84,.22,.025,.61])
            cb.tick_params(labelsize=12); cb.yaxis.label.set_size(14)
        ax.xaxis.label.set_size(14); ax.yaxis.label.set_size(14)
        ax.tick_params(labelsize=12)
        ax.set_title(ax.get_title(loc='left'),fontsize=14,loc='left')
        for label in ax.texts:
            label.set_fontsize(12)
            if label.get_text()=='Alps':
                label.set_position((9.7,46.5)); label.set_ha('right')
            elif label.get_text()=='Massif Central':
                label.set_text('Massif\nCentral'); label.set_position((2.0,46.2))
        if geometry(ax)!=before:
            raise ValueError('Map data, colour limits or geographic extents changed')
        path=out/f'supervisor-map-{tag}.pdf'
        fig.savefig(path,bbox_inches='tight',pad_inches=.04,metadata={'CreationDate':None})
        outputs[path.name]={'sha256':digest(path),'unchanged_map_geometry_sha256':before}
        plt.close(fig)
    manifest={'operation':__doc__,'annotation_layout':'Regional label sizes and line breaks adjusted; Alps label placed inside the plotted extent.',
              'numerical_run':str(run),
              'completed_source_stage':stage['id'],'source_stage_command':command,
              'cleaning':release['cleaning'],'inputs':inputs,'plot_function_sha256':digest(GENERATOR),
              'basemap_sha256':digest(source['BASEMAP']),'script_sha256':digest(Path(__file__)),
              'flight_counts':{k:len(v['flights']) for k,v in loaded.items()},'outputs':outputs}
    (out.parent/'supervisor-map-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Rendered three launch maps; existing plotted data and extents unchanged.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); render(args.run,args.out)
