"""Prepare manuscript prose for post-run review, without editing guarded sources.

The drafts still require the completed Chapter 3 report: this does not certify
the old confidence-interval, collapse, task-ordering or model interpretations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected exactly one replacement: {old[:100]}')
    return text.replace(old, new, 1)


def fragment(name):
    return '\n'.join(line for line in (HERE/name).read_text().splitlines()
                     if not line.startswith('%')) + '\n'


def main():
    chapter2_path = ROOT/'thesis/sections/03-dataset.tex'
    chapter3_path = ROOT/'thesis/sections/04-global-transport.tex'
    structure = json.loads((HERE/'chapter3-structure-check.json').read_text())
    if hashlib.sha256(chapter3_path.read_bytes()).hexdigest() != structure['original_source_sha256']:
        raise ValueError('Regenerate the structural draft against the current manuscript')
    ch2 = chapter2_path.read_text()
    ch3 = (HERE/'chapter3-structure-draft.tex').read_text()
    ch2 = replace_once(ch2, '\\paragraph{Availability.}',
        fragment('chapter2-psd-review-fragment.tex')+'\n'+r'\paragraph{Availability.}')
    ch2 = replace_once(ch2,
        'Among retained-flight metadata, 47,341 paraglider and 1,349 hang-glider records\n'
        'contain at least one candidate. A check of two high-count and two seeded positive-count\n'
        'records per discipline reproduced the counters and found candidate times in usable\n'
        'phase-feature windows in all eight examples.',
        'Among retained-flight metadata, 47,440 paraglider and 1,350 hang-glider records\n'
        'contain at least one candidate. Reprocessing eight previously selected examples\n'
        'with the current pipeline reproduces their counters. In each discipline these\n'
        'include two high-count records and two seeded positive-count records. All eight\n'
        'still have candidate times near usable phase-feature centres. This is temporal\n'
        'association, not proof that an uncorrected sensor defect enters a feature.')
    ch2 = replace_once(ch2,
        'binds, with a $2\\Delta t$ floor allowing one missed fix. For example,',
        'binds, with a $2\\Delta t$ floor allowing one missed fix. Thus the configured\n'
        r'\SI{\PreprocMaxGapS}{\second} value is not an absolute ceiling for every logger:'+'\n'
        r'at $\Delta t=\SI{15}{\second}$, the bound is \SI{30}{\second}. For example,')
    ch2 = replace_once(ch2,
        'These flags identify unsupported vertical dynamics; numerical completeness alone\n'
        'does not establish accuracy.',
        'The flags identify grid times or derivative windows touched by reconstruction;\n'
        'numerical completeness alone does not establish accuracy. The altitude-gap\n'
        'bound concerns the separation of finite source readings, not the duration of\n'
        'a consecutive run of flags on the new grid. With irregular source timing,\n'
        'nearest-fix flagging can merge adjacent reconstructed portions into a longer\n'
        'flagged run even when every finite-altitude bracket satisfies the bound.')
    ch2 = replace_once(ch2,
        "below the verifier's gross-anomaly threshold.",
        r'''below the verifier's gross-anomaly threshold. Across segment boundaries,
\num{\StatVerifyParaOffsetFlights} paraglider and
\num{\StatVerifyHangOffsetFlights} hang-glider flights exceed its separate
speed-envelope diagnostic, which compares displacement with elapsed time and the
declared coordinate tolerance. These boundary anomalies do not establish a unique
sensor-error mechanism. Splitting prevents increment windows from bridging them;
it does not independently validate absolute positions after reacquisition.''')
    ch2 = replace_once(ch2,
        'Panels~(a) and~(b) describe the segments retained after resampling. Their duration\n'
        'and path length can be smaller than those of the trimmed parent flight tested in',
        'Panels~(a) and~(b) describe retained flights. Here duration is the elapsed\n'
        'span from the first to the last retained fix, including intervening gaps;\n'
        'path length sums only within-segment steps. These quantities can be smaller\n'
        'than those of the trimmed parent flight tested in')
    ch2 = replace_once(ch2, 'Median duration [h] &', 'Median retained span [h] &')
    ch2 = replace_once(ch2,
        'Figs.~\\ref{fig:gaps} and~\\ref{fig:sampling}. Duration and path are measured over the\n'
        '  segments a flight keeps after resampling (Sec.~\\ref{sec:uniform}), not over the trimmed\n'
        '  flight the cuts of Sec.~\\ref{sec:flightfilter} tested, which is why a thin tail falls\n'
        '  below those cuts.',
        r'''Figs.~\ref{fig:gaps} and~\ref{fig:sampling}. The duration labelled in panel (a)
is the first-to-last retained-fix span, including gaps, rather than observed airborne
time. Path length in (b) sums only within-segment steps. These retained-record
quantities differ from the trimmed-parent quantities tested by
Sec.~\ref{sec:flightfilter}; no parent-flight threshold is reapplied after resampling.''')
    ch3 = replace_once(ch3,
        'The fixed cohort requires at least one retained segment of\n\\SI{20000}{\\second} per flight.',
        r'''The fixed cohort requires at least one retained segment of
\SI{20000}{\second} per flight. This is an additional population control;
the changing-pool analysis uses every eligible flight at each supported lag.
The \SI{20000}{\second} threshold is an operational choice, not the minimum
duration mathematically required to observe a \SI{10000}{\second} increment.
It supplies at least \num{1001} common 10-s origins in one qualifying segment.
Other eligible segments of these same flights also contribute when they support
the required interval. The cohort therefore fixes flights, not only their longest
segments, and its conclusions remain conditional on long flights.''')
    closure_start = ch3.index('A complementary geometrical descriptor is the closure ratio')
    closure_stop = ch3.index('Matching task groups by duration and region,', closure_start)
    closure = r'''A complementary descriptor compares net displacement with the path actually
observed on the common grid. Let $t_f^-$ and $t_f^+$ be the first and last retained
grid times, and let $L_f^{\rm obs}$ sum only the within-segment chords:
\begin{equation}
 L_f^{\rm obs}=\sum_{s\in\mathcal S_f}\sum_{j=0}^{N_{fs}-2}
       |\mathbf r_{fs,j+1}-\mathbf r_{fs,j}|,\qquad
 \chi_f^{\rm obs}=\frac{|\mathbf r_f(t_f^+)-\mathbf r_f(t_f^-)|}
                         {L_f^{\rm obs}},\quad L_f^{\rm obs}>0.
 \label{eq:closure-ratio}
\end{equation}
For one uninterrupted observed path, the triangle inequality gives
$0\le\chi_f^{\rm obs}\le1$. Across separated segments, the denominator omits
unobserved travel while the numerator spans it, so this bound need not hold.
Reacquisition offsets can also affect the endpoint displacement. The full collector
contains \num{181} paraglider and two hang-glider values above one, all among
flights with multiple eligible segments. This is an observed-path descriptor,
not a reconstruction of the complete distance flown.

In the eligible archive, median $\chi_f^{\rm obs}$ is
\StatRevParaOpenClosure\ for open paraglider tasks and
\StatRevParaClosedClosure\ for closed ones; hang-glider medians are
\StatRevHangOpenClosure\ and \StatRevHangClosedClosure. These medians describe
the endpoint geometry of retained observations, with the gap limitation above.
For an uninterrupted path, small $\chi_f^{\rm obs}$ means little net progress
relative to its length. None of the increment statistics crosses a segment boundary.
'''
    ch3 = ch3[:closure_start]+closure+'\n'+ch3[closure_stop:]
    ch3 = replace_once(ch3,
        'The directional\nimbalance motivates keeping east, north and the radial displacement separate.',
        'The directional\nimbalance supports treating east, north and radial displacement separately.')
    ch3 = replace_once(ch3,
        'asks how much directional structure remains after subtracting each subgroup\'s mean.',
        'asks how much directional structure remains after subtracting each subgroup\'s mean.\n'
        'Launch-referenced positions can retain reacquisition offsets across missing\n'
        'intervals; within-segment increments avoid bridging those intervals but do not\n'
        'independently validate their endpoints.')
    ch3 = replace_once(ch3,
        'determined when the eigenvalues are close.',
        'determined when the eigenvalues are close. Covariances pool all supported\n'
        'baseline increment origins within each take-off box, so flights with more\n'
        'origins receive more weight. They use the eligible regional archive, independently\n'
        'of the fixed long-flight cohort. At least eight flights are required; this\n'
        'display condition supplies neither an uncertainty interval nor a precision guarantee.')
    ch3 = replace_once(ch3,
        'displacement geometry and do not identify wind.}',
        'displacement geometry and do not identify wind. Ellipses show the 10, 90 and\n'
        r'1070-s covariances after trace normalisation; the eigenvalue-ratio curve also'+'\n'
        'includes 10000 s. Normalisation removes their amplitude differences.}')
    ch3 = replace_once(ch3,
        r'\StatRevParaPcaChannelCoastRatio & ---',
        r'\StatRevParaPcaChannelCoastRatio & \SI{\StatRevParaPcaChannelCoastAngle}{\degree}')
    ch3 = replace_once(ch3,
        'Angles run counterclockwise. The Pyrenean axis lies closer to east--west; its\n'
        'long-lag ellipse elongates as support falls, leaving both route geometry and selection\n'
        'as possible contributors. The small coastal sample also has an unequal covariance:\n'
        'low relief alone does not provide an isotropic control.',
        'Angles run counterclockwise from east. The Pyrenean axis lies closer to\n'
        'east--west; its eigenvalue ratio increases towards long lags as support falls,\n'
        'leaving both route geometry and selection as possible contributors. The coastal\n'
        'comparison also has unequal principal variances, with thousands of flights at\n'
        'the reference lag. Its geographical label does not provide an isotropic control.')
    ch3 = replace_once(ch3,
        'and $s_0$ is the radial median near \\SI{1000}{\\second}. Geographic axes remain fixed,',
        r'''and $s_0=Q_{R,.50}(\tau_r)/(\tau_r/\SI{1000}{\second})^{H_*}$,
with $\tau_r=\SI{1070}{\second}$, the available lag nearest the reference time.
Thus the recorded median is adjusted to the common reference by the same power.
Geographic axes remain fixed,''')
    eq_start = ch3.index(r'\paragraph{Equipment within each region.}')
    eq_end = ch3.index(r'\paragraph{Wind and ground velocity.}', eq_start)
    equipment = r'''\paragraph{Equipment within each region.}
EN A/B and EN C/D/CCC provide the beginners and experts proxies of
Sec.~\ref{sec:glider}. In the Alps, the C/D/CCC position and velocity ratios
remain closer to unity at all displayed supported times. The median position
ratio is \StatKinTerrainAlpsEquipmentCDCCCPositionMedian, versus
\StatKinTerrainAlpsEquipmentABPositionMedian\ for A/B. The Pyrenees and coastal
contrasts do not have the same ordering across all times and quantities.

\begin{figure}[p]
 \centering
 \includegraphics[width=\linewidth]{generated/kinematic_isotropy_flat_level}
 \caption{Equipment contrasts in three take-off boxes outside the mountain
 comparison: Channel Coast, Poitou-Charente and Champagne-Lorraine. Position and
 velocity ratios use the paired support, pointwise 10--90\% site--day bootstrap
 bands and display minima of Fig.~\ref{fig:kinematic-equipment}. The coastal row
 is repeated to compare it directly with the two additional regions. The boxes
 label take-off locations; they do not measure terrain exposure along each route
 or match wind conditions between equipment groups.}
 \label{fig:kinematic-low-relief}
\end{figure}

'''
    ch3 = ch3[:eq_start]+equipment+fragment('regional-discussion-fragment.tex')+'\n'+ch3[eq_end:]
    ch3 = replace_once(ch3,
        'durations to 78.9\\% for $T\\ge4$ h. The latter cohort still includes 7,426',
        'durations to 78.9\\% for $T\\ge4$ h. The latter cohort still includes 7,415')
    ch3 = replace_once(ch3,
        'underlying memory. The log--log curves bend, and hang-glider estimates turn\nnegative at long separation;',
        'underlying memory. The log--log curves bend, and estimates in both disciplines\nturn negative at long separation;')
    for chapter, draft in [(2, ch2), (3, ch3)]:
        (HERE/f'chapter{chapter}-prose-review-draft.tex').write_text(draft)
    report = {
        'status': 'draft_only; final numerical interpretation and compilation pending',
        'canonical_manuscript_unchanged': True,
        'inputs_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (chapter2_path, chapter3_path)},
        'pending_fresh_report': [
            'task slope ordering and closure medians',
            'changing/fixed quantile slope ordering and relative-spread values',
            'all paired confidence-interval interpretations',
            'marginal collapse ordering and distance magnitudes',
            'joint-law visual interpretation and finite-bin distances',
            'all fitted-range claims, model and velocity-memory values',
            'exact duration composition ratios at 576 and 1695 seconds',
        ],
        'additional_proofs': [
            'current-level-shift-examples.json', 'current-level-shift-counters.json',
            'observed-path-closure-audit.json', 'regional-contrasts-audit.json',
            'psd-selection-comparison.json',
        ],
    }
    (HERE/'manuscript-prose-draft-check.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Prepared Chapter 2/3 prose drafts; canonical manuscript and slides unchanged.')


if __name__ == '__main__':
    main()
