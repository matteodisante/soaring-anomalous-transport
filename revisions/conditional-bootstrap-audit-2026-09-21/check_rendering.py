"""Check the actual renderer's band vertices and their size on logarithmic axes."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'scripts/tesi/ch03_fixed_transport'))
import conditional_ch3_transport as plotter
from matplotlib.figure import Figure
r = json.loads((ROOT/'thesis/generated/ch3_conditional.json').read_text())
checks = []
def inspect(self, filename, *args, **kwargs):
    name = Path(filename).stem.removeprefix('ch3_conditional_')
    self.canvas.draw()
    for ax, (_, entries) in zip(self.axes, plotter.PANELS[name],strict=True):
        assert ax.get_yscale() == 'log'
        assert len(ax.collections) == len(entries)
        for poly, (key, _) in zip(ax.collections,entries,strict=True):
            vertices = poly.get_paths()[0].vertices
            row = r['groups'][key]['msd']
            lags = np.asarray(r['lags_s'])
            for j,lag in enumerate(lags):
                y = vertices[np.isclose(vertices[:,0],lag,atol=0,rtol=1e-13),1]
                np.testing.assert_allclose([y.min(),y.max()],np.array([row['low'][j],row['high'][j]])/1e6,rtol=2e-12)
            j = int(np.flatnonzero(lags==100)[0])
            coords=ax.transData.transform([[100,row['low'][j]/1e6],[100,row['high'][j]/1e6]])
            height_pt=float((coords[1,1]-coords[0,1])*72/self.dpi)
            checks.append(dict(figure=name,group=key,band_height_pt_at_100s=height_pt,
                line_width_pt=float(ax.lines[2*entries.index((key,_))].get_linewidth())))
    # No PDF is authored: inspect in-memory artist geometry only.
Figure.savefig = inspect
with tempfile.TemporaryDirectory(prefix='ch32-render-audit-') as temporary:
    plotter.render(r,Path(temporary))
run = ROOT/'revisions/conditional-transport-2026-09-19/run-altitude'
hashes={}
for name in plotter.PANELS:
    filename=f'ch3_conditional_{name}.pdf'
    hashes[filename]=hashlib.sha256((ROOT/'thesis/generated'/filename).read_bytes()).hexdigest()
    assert hashes[filename] == hashlib.sha256((run/filename).read_bytes()).hexdigest()
json.dump(dict(all_band_vertices_correct=True,all_published_pdfs_match_saved_run=True,
    pdf_hashes=hashes,rendered_bands=checks), (OUT/'rendering.json').open('w'),indent=2)
print(f'PASS: all {len(checks)} displayed conditional bands have correct percentile coordinates.')
print('Band heights at 100 s in circuit figure:',[(c['group'],c['band_height_pt_at_100s']) for c in checks if c['figure']=='circuit'])
