"""Install reviewed prose against the completed full-archive Chapter 3 report.

This edits only the working manuscript, after isolated continuation has started.
The running frozen numerical source is not changed.
"""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
record=json.loads((HERE/'isolated-continuation.json').read_text())
assert record['status'] in ('running','complete')
audit=json.loads((HERE/'chapter3-results-audit.json').read_text())
for name, expected in audit['reports_sha256'].items():
 assert hashlib.sha256((ROOT/'thesis/generated'/name).read_bytes()).hexdigest()==expected
ch2=(HERE/'chapter2-prose-review-draft.tex').read_text()
ch3=(HERE/'chapter3-prose-review-draft.tex').read_text()

def change(old,new):
 global ch3
 assert ch3.count(old)==1,old[:100]
 ch3=ch3.replace(old,new,1)

change('Its sign need not imply monotonic change. The controlled ratios rise from about\n'
'1.94 to 4.48 in paragliders and from 2.23 to 5.89 in hang gliders between\n'
'\\SI{10}{\\second} and \\SI{80}{\\second}, then fall towards a minimum near\n'
'\\SI{2000}{\\second}. At \\SI{10000}{\\second}, they reach about 3.03 and 2.65.\n'
'The negative fitted slope describes the long decline after the early maximum.',
r'''Its sign need not imply monotonic change. In the controlled population, the
paraglider ratio rises from 1.97 at \SI{10}{\second} to a sampled maximum of
4.20 at \SI{90}{\second}; the hang-glider ratio rises from 2.27 to 5.52 at
\SI{80}{\second}. After these early maxima, the ratios fall to local minima of
2.23 at \SI{2410}{\second} and 2.32 at \SI{1970}{\second}, respectively.
They then rise to 3.01 and 2.60 at \SI{10000}{\second}. The negative fitted
contrast summarises this curved evolution; it does not describe a monotone
narrowing over the full interval.''')
change('For paragliders, north--east contrasts are positive at all four ranks, with paired\n'
'intervals excluding zero. For hang gliders, the other three rank intervals include\n'
'zero. The radial median slope lies below both component median slopes: different\n'
'observations can occupy the component and radial ranks.',
r'''In both disciplines, north--east contrasts are positive at all four ranks,
with their paired pointwise intervals excluding zero. The radial rank contrasts
are negative, also with intervals excluding zero. These comparisons support
rank- and direction-dependent effective growth within the fixed long-flight
population under the stated resampling assumptions. They do not establish a
single power law at each rank. The radial median slope lies below both component
median slopes: different observations can occupy the component and radial ranks.''')
change('For an uninterrupted path, small $\\chi_f^{\\rm obs}$ means little net progress\n'
'relative to its length. None of the increment statistics crosses a segment boundary.',
r'''Restricting to flights with one eligible observed segment gives closely similar
open/closed medians: 0.364/0.027 in paragliders and 0.177/0.026 in hang gliders.
This sensitivity check preserves the descriptive ordering; one eligible segment
need not cover the complete original flight. For an uninterrupted observed path,
small $\chi_f^{\rm obs}$ means little net progress relative to its length.
None of the increment statistics crosses a segment boundary.''')
change('The radius has the largest power-rescaling\n'
'distance in both disciplines. Dividing by each lag\'s median reduces that discrepancy\n'
'but leaves separation for all three quantities: allowing an arbitrary scale at each\n'
'lag still does not remove the observed shape changes.',
r'''The radius has the largest power-rescaling
distance in both disciplines, about 0.27 for paragliders and 0.33 for hang gliders.
Dividing by each lag's median reduces these radial distances to about 0.19 and
0.23, but leaves separation for all three quantities. Thus allowing an arbitrary
scale at each lag still does not remove the observed shape changes. These are
empirical discrepancies without a calibrated sampling-error threshold.''')
change(r''' \label{fig:joint-hang}
\end{figure}

\FloatBarrier''',r''' \label{fig:joint-hang}
\end{figure}

The candidate vector exponents are $H_*=0.920$ for paragliders and 0.911 for
hang gliders. After this common rescaling, the central concentration and
orientation still evolve with lag. In particular, the long-lag law occupies a
smaller spread in the rescaled coordinates; the geographical mean also changes.
These changes concern the signed vector distribution, beyond the magnitude
comparisons. At the chosen resolution, pairwise distances range from 0.099 to
0.370 for paragliders and from 0.136 to 0.441 for hang gliders. The 10-s versus
10000-s distances are 0.370 and 0.403, respectively. Overflow mass is zero to
numerical precision, so the measured separation is not caused by omitting a tail
outside the displayed square.

The fixed flights and origins rule out changing membership as the source of
these particular differences. They do not distinguish changes of marginal shape,
mean motion and component dependence. A larger binned distance also does not
rank the disciplines by strength of a physical mechanism: the finite-flight
sampling error and sensitivity to bin size have not been calibrated.

\FloatBarrier''')
for chapter,text,name in ((2,ch2,'03-dataset.tex'),(3,ch3,'04-global-transport.tex')):
 (ROOT/'thesis/sections'/name).write_text(text)
refs=ROOT/'thesis/references.bib'
addition=(HERE/'regional-review-references.bib').read_text()
assert 'dhv_classification' not in refs.read_text()
refs.write_text(refs.read_text().rstrip()+'\n\n'+addition)
(HERE/'manuscript-install-review.json').write_text(json.dumps({
 'source_run':audit['run_id'], 'reports_sha256':audit['reports_sha256'],
 'isolated_continuation':record['run_dir'],
 'scope':'Working manuscript only; frozen sources unchanged. Final compilation and phase-stage results remain pending.',
 'files_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'thesis/sections/03-dataset.tex',ROOT/'thesis/sections/04-global-transport.tex',refs)},
 'checked_interpretations':['task slopes and observed-path closure sensitivity','fixed quantile ordering','relative spread extrema and nonmonotonicity','paired rank and direction contrasts','marginal exact ECDF distances','common exponents over three fitting ranges','signed joint-law distances and overflow','duration/equipment ratios at 576,1695,7149 s','regional equipment contrasts and limitations','both-discipline negative long-lag VACF'],
},indent=2)+'\n')
print('Installed current Chapter 2/3 prose and regional references; frozen run unchanged.')
