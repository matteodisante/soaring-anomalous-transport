"""Assemble full-chapter review drafts without altering the delivered decks.

Select and order existing and new frames, replacing obsolete statements. Numerical
macros and all final figure/layout checks must be refreshed after run completion.
"""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def frames(path):
    return re.findall(r'\\begin\{frame\}.*?\\end\{frame\}', path.read_text(), re.S)


def select(bank, prefix):
    matches = [frame for frame in bank if re.match(
        r'\\begin\{frame\}(?:\[[^\]]*\])?\{' + re.escape(prefix), frame)]
    if len(matches) != 1:
        raise ValueError((prefix, len(matches)))
    return re.sub(r'\\timing\{[^}]*\}', r'\\speaker', matches[0])


def replace(frame, old, new):
    if old not in frame:
        raise ValueError(f'Missing replacement: {old}')
    return frame.replace(old, new)


def notes(frame, text):
    if '\\speaker{' in frame:
        # Speaker notes are the final command in each extracted frame.
        frame = frame[:frame.index('\\speaker{')]
    else:
        frame = frame[:frame.rindex('\\end{frame}')]
    return frame + '\\speaker{' + text + '}\n\\end{frame}'


def make_ch2():
    old = frames(ROOT/'presentations/chapter2.tex')
    additions = frames(HERE/'chapter2-additional-frames.tex')
    extra = frames(HERE/'chapter2-completion-frames.tex')
    old_frame = lambda s: select(old, s)
    new_frame = lambda s: select(additions, s)
    extra_frame = lambda s: select(extra, s)
    ordered = []
    def add(section, entries):
        ordered.append('\\section{'+section+'}')
        ordered.extend(entries)
    def plot(title, asset, question, note, height=59):
        return (r'\begin{frame}{'+title+'}\n'+r'\centering\fig['+str(height)+'mm]{'+asset+'}\n'
                +r'\question{'+question+'}\n'+r'\speaker{'+note+'}\n'+r'\end{frame}')

    archive = old_frame('The archive contains')
    archive = replace(archive, r'Retention &84.0\%&90.7\%',
                      r'Retention &\StatPipeParaKeptPct\%&\StatPipeHangKeptPct\%')
    archive = notes(archive, 'The attempted and retained counts are imported from the current completed pipeline census. Catalogue entries, downloaded tracks and retained flights have different denominators. Participation, declarations, devices and the cross-country restrictions jointly select the observed population.')
    add('Archive, records and population', [archive,
        new_frame('Acquisition preserves'), new_frame('An IGC fix'),
        new_frame('Equipment classes')])
    add('Processing contract and altitude evidence', [old_frame('The processing order')])
    channel = old_frame('GNSS supplies')
    channel = replace(channel, '72.1\\% para / 84.8\\% hang',
        r'\StatPipeParaBaroWitnessPct\% para / \StatPipeHangBaroWitnessPct\% hang')
    channel = replace(channel, 'Keep usable horizontal trajectories; assess witness-dependent results with a paired-coverage sensitivity analysis.',
        'How sensitive are witness-dependent decisions to the availability of paired pressure observations?')
    ordered.append(channel)
    ordered.append(r'''\begin{frame}{Recorded altitude traces combine flight motion and channel behaviour}
\centering\fig[52mm]{altitude-traces.pdf}
\question{Which common variations plausibly reflect flight motion, and which differences need a sensor explanation?}
\speaker{These are representative recorded traces, not ground-truth altitude. A difference between channels can involve datum, atmospheric effects, quantization or recording defects. The spectra and availability diagnostic use separately stated populations.}
\end{frame}''')
    psd = new_frame('The paired PSD')
    psd = replace(psd, r'\centering\fig[47mm]{altitude_noise.pdf}'+'\n'+r'\small Same valid block for both channels; linear resampling and Welch detrending.'+'\n'+'No pipeline Savitzky--Golay smoothing enters these spectra.',
        r'''\begin{columns}[c,onlytextwidth]
\column{.56\textwidth}\fig[57mm]{altitude-psd-panel.pdf}
\column{.41\textwidth}\small
Same valid block for both channels; linear resampling and Welch detrending.
\medskip
No pipeline Savitzky--Golay smoothing enters these spectra.
\medskip
Shading is the per-frequency 10--90\% range across selected flights.
\end{columns}''')
    ordered.extend([psd,new_frame('Selecting valid intervals')])
    ordered.append(r'''\begin{frame}{GNSS availability is a separate flight-level selection}
\begin{columns}[c,onlytextwidth]
\column{.56\textwidth}\fig[57mm]{altitude-availability.pdf}
\column{.41\textwidth}\small
The channel gate requires at least 95\% usable GNSS altitude and at least 30 m range.
The availability census is broader than the selected paired-spectrum population.
\end{columns}
\question{Which recorders, periods and flight types are preferentially lost through this requirement?}
\speaker{The barometer remains an independent operational witness where it is eligible and locally complete. Its availability does not repair missing GNSS support in the cleaned vertical trajectory.}
\end{frame}''')
    ordered.append(new_frame('A common altitude channel'))
    horizontal = old_frame('A Hampel flag')
    horizontal = re.sub(r'\\begin\{columns\}.*?\\end\{columns\}',
        lambda m:r'\centering\fig[56mm]{defect-position.pdf}',horizontal,count=1,flags=re.S)
    horizontal = replace(horizontal, 'Resolved: the Hampel flag is not required for deletion. A long corrupt block can contaminate the median and evade that flag.',
        'Which cases can contaminate the median without defeating the reachability check?')
    horizontal = replace(horizontal, 'Real paraglider flight 20030236. The displayed coordinate is a projection used to show the defect; the rule uses geodetic horizontal distances.',
        'Real flight 20030236; the gate uses geodetic distances.')
    frozen = old_frame('A frozen-position')
    frozen = re.sub(r'\\begin\{columns\}.*?\\end\{columns\}',
        lambda m:r'\centering\fig[56mm]{defect-frozen.pdf}',frozen,count=1,flags=re.S)
    frozen = replace(frozen, 'A removed frozen candidate never becomes an interpolated straight flight. Its unobserved motion stays separated.',
        'How would genuine slow motion differ from this frozen-position signature?')
    frozen = replace(frozen, "Real paraglider flight 20050872. These signatures support a cleaning action; they do not prove the receiver's internal lock state.",
        'Real flight 20050872; the removed interval remains a gap.')
    witness = old_frame('The complete frozen')
    witness = replace(witness, r'\small Let $E_I$',
        r'\small Require $D_I<15$ m, $T_I\ge60$ s and $W_I=1$. Here $D_I$ is the horizontal bounding-box diagonal.\par\medskip Let $E_I$')
    witness_history = old_frame('Requiring complete local')
    witness_history = replace(witness_history,
        'Targeted old/new-rule comparison', 'Historical comparison: 2.0.0 to 2.0.1')
    witness_history = replace(witness_history,
        'The complete archive was subsequently rebuilt with the corrected rule.',
        'These counts use the former 30 m/s vertical threshold; they do not measure the impact of version 2.3.0.')
    witness_history = notes(witness_history,
        'This historical targeted comparison isolates the complete-local-pressure witness correction in cleaning 2.0.0 versus 2.0.1, under the then-current 30 metres per second vertical threshold. It preserves a documented example of how a concern changed decisions. The current pipeline retains that correction but uses a 10 metres per second threshold and splits long vertical gaps. The 2388 candidates, 189 changed flights and 22468 additionally retained fixes are not a current-versus-old whole-pipeline ablation, nor a labelled estimate of detector accuracy.')
    add('Fix-level decisions', [extra_frame('Timestamp and'),
        horizontal, old_frame("The identifier's scale"),
        plot('An isolated unreachable fix has an immediate reachable rejoin',
             'gate-spike-pair.pdf', 'Does deleting the suspect fix restore reachability from the last accepted anchor?',
             'The synthetic 700-metre spike lasts one second. Both original panels are retained: position and chord speed from the accepted anchor. The horizontal working bound is 45 metres per second for paragliders, 55 for hang gliders. This example illustrates the implemented rule rather than an independent sensor label.'),
        plot('A moderate offset can become reachable within the block horizon',
             'gate-rejoin-pair.pdf', 'How does keeping the anchor fixed change which early fixes are removed?',
             'The 400-metre offset is reachable within the twenty-second block horizon as allowed displacement grows with elapsed time. The scan removes the shortest block that restores reachability, rather than all fixes that disagree with the original trend. This is a stated limitation of the operational gate.'),
        plot('Without a reachable rejoin, the scan imposes a boundary',
             'gate-boundary-pair.pdf', 'What information remains unresolved after a large reacquisition offset?',
             'The four-kilometre offset cannot rejoin within the block horizon. The implementation imposes boundaries rather than silently treating the whole interval as an isolated spike. Such a split prevents cross-boundary increments but does not independently validate the new absolute position.'),
        frozen,
        witness, witness_history,
        old_frame('The vertical-speed threshold'), old_frame('Two window medians')])
    altitude = old_frame('Altitude invalidation preserves')
    altitude = replace(altitude, 'Altitude invalidation preserves the horizontal trajectory',
                      'Altitude invalidation precedes the full-trajectory support decision')
    altitude = replace(altitude, 'Horizontal fixes remain, unless they fail their own tests.',
                      'At this stage horizontal fixes remain. Later, long missing-altitude intervals split the complete trajectory.')
    altitude = replace(altitude, 'Reconstructed altitude is identified later by a separate quality flag.',
                      'Only short admitted altitude holes are reconstructed and flagged.')
    altitude = re.sub(r'\\begin\{columns\}.*?\\end\{columns\}',
        lambda m:r'\centering\fig[53.5mm]{defect-altitude.pdf}',altitude,count=1,flags=re.S)
    altitude = replace(altitude, 'An inspectable decision is useful evidence of implementation behavior. It does not supply an independent label of the true altitude.',
        'What evidence could independently distinguish an altitude defect from a genuine manoeuvre?')
    level = old_frame('An unreturned altitude')
    level = replace(level, '47,341 para / 1,349 hang', '47,440 para / 1,350 hang')
    ordered.extend([altitude,
        plot('An isolated altitude spike can leave a populated-window median low',
             'vertical-spike.pdf', 'What evidence does the separate opposite-sign bounding-step test add?',
             'The synthetic example is processed by the current implementation. Sparse windows fall back to individual step magnitudes. An algorithmic synthetic example isolates a branch of the rule; it does not estimate a detector error rate.'),
        plot('Sustained excess raises both neighbouring window statistics',
             'vertical-sustained.pdf', 'Which plausible physical descents could also satisfy this operational criterion?',
             'Both neighbouring robust statistics enter the decision, and their windows overlap. They are not independent confirmations. Altitude invalidation is followed by the bounded-support resampling decision.'), level])
    trimming = new_frame('Time removed')
    trimming = re.sub(r'\\small\nPara medians:.*?\\question',
        lambda m:r'\question',trimming,count=1,flags=re.S)
    trimming = replace(trimming,r'\fig[52mm]',r'\fig[60mm]')
    trimming = replace(trimming, 'Are the longest removed intervals consistent with continued ground logging, or do they hide slow flight?',
        'Do the longest removed intervals reflect continued ground logging or slow flight?')
    ground = new_frame('Interior ground')
    ground = replace(ground,r'\centering\fig[40mm]{trim_interior_excisions.pdf}', '')
    add('Trimming and flight selection', [new_frame('Outer trimming'),
        trimming,ground,
        plot('Interior excisions affect a small part of the full trimming census',
             'trim_interior_excisions.pdf', 'Does a small affected count also imply a small effect on phase statistics?',
             'There are 231 affected paraglider and three hang-glider records among those reaching the trimming census. The count is not an independently labelled false-positive rate. Every excision creates a boundary.'),
        new_frame('Flight-level gates')])
    sampling = plot('Recorder cadence varies across the raw archive', 'sampling_intervals.pdf',
        'Which native cadences resolve the shortest scales used later?',
        'Preprocessing retains the native median cadence, while Chapter 3 applies a separate common ten-second grid to eligible segments. Horizontal interpolation is shape-preserving cubic and altitude interpolation linear, within the bounded support. A finer numerical grid would not restore missing physical resolution.')
    add('Coordinates and supported segments', [new_frame('Geographic coordinates'),
        new_frame('The ENU basis'),new_frame('Rotated Up'),sampling,
        new_frame('The same duration bound'),new_frame('Long altitude holes'),
        new_frame('A segment boundary'),extra_frame('A usable segment'),
        new_frame('Quality flags')])
    add('Smoothing and differentiation', [old_frame('One local polynomial'),
        old_frame('The nominal 5-s'),new_frame('The value filter'),
        extra_frame('Smoothing modifies')])
    census = old_frame('The complete first-failure census')
    census = replace(census, 'pipeline version 2.2.0', 'pipeline version 2.3.0')
    add('Retained archive and checks', [census,
        plot('Retained duration and path describe the surviving pieces','retained-duration-path.pdf',
             'How do the final distributions differ from the parent-flight selection variables?',
             'Duration and path sum over retained segments after all segment gates. Values can lie below the parent-flight thresholds because those gates were applied before later pieces were discarded. The histograms preserve the original bins and normalization.'),
        plot('Retained cadences define the available temporal resolution','retained-cadence.pdf',
             'Which results could be sensitive to the changing mixture of recorder intervals?',
             'The plotted cadence distribution concerns retained flights, unlike the broader raw-record diagnostic shown earlier. Higher counts at a cadence do not prove equal device quality or equal coverage of sites and seasons.'),
        plot('Participation and available tracks change across seasons','seasons-counts.pdf',
             'Which temporal comparisons also change equipment, geography or logging technology?',
             'Attempted and retained counts are on the original logarithmic scale. The lower original season labels are appended without changing horizontal coordinates.'),
        plot('Similar aggregate retention can conceal different selection','seasons-retention.pdf',
             'Are cadence and regional retention stable within the larger seasons?',
             'Open markers indicate seasons with fewer than one thousand flights. Similar overall retention is not evidence that every subgroup is selected at the same rate.'),
        plot('The duration of retained records also changes with season','seasons-duration.pdf',
             'Would matching season change the apparent equipment or regional contrast?',
             'These medians describe survivors. They combine real flight duration, who declares and records flights, device support and cleaning selection.'),
        replace(old_frame('Geographic coverage'), 'prelim_map.pdf','supervisor-map-france.pdf'),
        r'''\begin{frame}{La R\'eunion and other recorded sites extend the geographical population}
\begin{columns}[c,onlytextwidth]
\column{.47\textwidth}\fig[55mm]{supervisor-map-reunion.pdf}
\column{.50\textwidth}\fig[55mm]{supervisor-map-world.pdf}
\end{columns}
\question{Which pooled results combine different climates, seasons and flight environments?}
\speaker{Both disciplines are pooled. The La Reunion density uses the original 0.01-degree cells; the elsewhere map uses 0.5-degree site cells with marker area reflecting their count. Bins, geographic extents and plotted values are unchanged from the chapter; only typography and layout have been adapted.}
\end{frame}''',
        extra_frame('Logged starting altitude')])
    checks = old_frame('What has been checked')
    checks = replace(checks, 'Current cleaning and all 38 rebuild stages.',
        'Cleaning 2.3.0 and identified numerical products.')
    checks = replace(checks, 'Reproduction of stored cleaned outputs for 250 retained flights per discipline.',
        'Complete post-remount structural scan: 1.404 billion retained fixes.')
    checks = notes(checks, 'Final delivery must identify the completed numerical run, its source hashes and the reviewed manuscript. The full structural scan checks operational tolerances; it reports small residual anomalies and is not an external sensor reference. Retain the separate reproduction and targeted-rule audits in the evidence manifest. Independent labelled examples and sensitivity of scientific observables remain open.')
    ordered.append(checks)
    viewer = old_frame('Inspect one of the records')
    viewer = notes(viewer, 'Use the viewer if raw data and the registered local launcher are available. The frozen example is also in the slide for offline discussion. Loading one flight may recompute that flight with the current code; it does not rebuild the archive. Independently assess the neighbouring trajectory before using an algorithmic decision as a label.')
    ordered.append(viewer)
    priorities = old_frame('Which cleaning uncertainties')
    priorities = replace(priorities, 'assess an explicit limit on altitude-only reconstruction.',
        'assess sensitivity to the adopted vertical gap bound.')
    priorities = notes(priorities, 'The vertical gap cap has been implemented. The remaining question is its scientific sensitivity, alongside altitude-step candidates, cadence and smoothing. Compare common populations where possible and report changes in admission separately. Agree which independently labelled or injected defects would most improve confidence in the phase features.')
    ordered.extend([priorities,new_frame('The next chapter'),old_frame('Methods and provenance')])
    head = r'''\documentclass[11pt,aspectratio=169]{beamer}
\newcommand{\TalkShort}{Chapter 2: data and cleaning}
\input{theme}
\input{data/pipeline_census.tex}
\input{data/dataset_stats.tex}
\input{data/stats.tex}
\input{data/census.tex}
\input{data/altitude_noise.tex}
\input{data/trim.tex}
\hypersetup{pdftitle={From IGC records to measurable trajectories: full chapter and supervisor discussion}}
\begin{document}
\titleframe{From IGC records to measurable trajectories}
 {Methods, results and questions for the supervisors}
 {Chapter 2\enspace$\bullet$\enspace Complete chapter review}
\speaker{This deck covers the whole chapter. It has no prescribed talk duration. The methodological choices, current results and unresolved validation questions are intended to be discussed together.}
'''
    draft = head+'\n\n'.join(ordered)+'\n\\end{document}\n'
    draft = draft.replace(r'\begin{frame}{An isolated altitude spike',
                          r'\begin{frame}[label=median-backup]{An isolated altitude spike')
    for obsolete in ('20-minute', '2.2.0', '\\timing{', 'no duration cap', '38 rebuild'):
        assert obsolete not in draft, obsolete
    return draft.replace('\n\\medskip\n', '\n\\par\\medskip\n')


def make_ch3():
    old = frames(ROOT/'presentations/chapter3.tex')
    additions = frames(HERE/'chapter3-additional-frames.tex')
    extra = frames(HERE/'chapter3-completion-frames.tex')
    old_frame = lambda s: select(old, s)
    new_frame = lambda s: select(additions, s)
    extra_frame = lambda s: select(extra, s)
    ordered = []
    def add(section, entries):
        ordered.append('\\section{'+section+'}')
        ordered.extend(entries)
    def plot(title, asset, question, note, height=54):
        return (r'\begin{frame}{'+title+'}\n'+r'\centering\fig['+str(height)+'mm]{'+asset+'}\n'
                +r'\question{'+question+'}\n'+r'\speaker{'+note+'}\n'+r'\end{frame}')

    scope = old_frame('What motion')
    scope = replace(scope, r'\textbf{Two levels of evidence}', r'\textbf{Retained and eligible populations}')
    scope = replace(scope, r'Detailed diagnostics: \StatRevParaFlights\ and \StatRevHangFlights\ selected flights, one longest segment per flight, on a 10-s grid.',
        r'Full diagnostics: \num{\StatRevParaFlights} and \num{\StatRevHangFlights} eligible flights, all supported segments, on a 10-s grid.')
    scope = replace(scope, r'Archive baseline: equal segment weights. Subset $V_1,V_2$: equal flight weights.',
        r'Archive TAMSD: equal segment weights. Full $V_1,V_2$: equal flight weights.')
    scope = notes(scope, 'The full diagnostic collector has no flight cap and no longest-segment-only restriction. Flights recorded more slowly than ten seconds are ineligible for its common grid. Each lag uses every supported flight; a separate fixed long-flight comparison controls population change. Different grids, minimum segment sizes and weights explain some differences from the archive TAMSD.')
    add('Displacement, support and growth', [scope, extra_frame('Launch averages'),
        plot('Launch averages and time averages use different populations', 'msd-growth.pdf',
             'How much of the difference follows launch synchronization and segment weighting?',
             'These are the upper two panels of the complete archive MSD figure. Blue denotes paragliders and terracotta hang gliders. The quantities use different clocks and weighting; their comparison is not an ergodicity test.'),
        plot('Local slopes must be read together with falling support', 'msd-support.pdf',
             'Which scale interval supports a stable finite-range description?',
             'The lower panels of the archive MSD figure show local slopes and contributing flights or segments. A small bootstrap error does not remove scale dependence or population selection. Values rounded to 0.000 at three decimals indicate less than 0.0005, not zero uncertainty.')])
    growth = old_frame('The MSD grows')
    growth = replace(growth, 'Subset; 10--10,000 s.', 'Full eligible archive; 10--10,000 s.')
    growth = notes(growth, r'The displayed exponents are imported from the completed full report. The first- and second-difference estimators use equal flight weights and do not cross segment boundaries. Their local slopes bend, so these are descriptive fits over the stated range. They differ from the equal-segment archive TAMSD and from pooled-origin high-order moments.')
    drift = old_frame('Second differences')
    drift = replace(drift, '107 para / 56 hang flights',
        r'\num{\StatRevParaLastOrderTwoFlights} para / \num{\StatRevHangLastOrderTwoFlights} hang flights')
    task = old_frame('Open and closed tasks')
    task = replace(task, r'\small\textbf{Measured subset}', r'\small\textbf{Full eligible archive}')
    for discipline, tag, values in [('Para','Para',('391','1.752','1.968','559','1.652','2.054')),
                                    ('Hang','Hang',('171','1.702','1.893','308','1.641','2.004'))]:
        for label, offset in [('Open',0),('Closed',3)]:
            pattern = '&'+'&'.join(values[offset:offset+3])+r'\\'
            macro = '&'+('&'.join(r'\StatRev'+tag+label+k for k in ('Flights','AlphaOne','AlphaTwo')))+r'\\'
            task = replace(task, pattern, macro)
    task = notes(task, 'The task declaration supplies open/closed labels; it does not force every retained segment to return to its start. Counts and slopes are read from the full-run report. Match duration and environment before interpreting task contrasts. The exact circular example illustrates how geometry survives second differencing; it is not a fitted flight model.')
    circle = r'''\begin{frame}[label=circle]{A circle retains its geometry after second differencing}
\small For $\mathbf r(t)=a(\cos\omega t,\sin\omega t)$ and $T_c=2\pi/\omega$,
\[
 V_1=4a^2\sin^2(\pi\tau/T_c),\qquad
 V_2=16a^2\sin^4(\pi\tau/T_c).
\]
\centering\fig[44mm]{closed-loop-variations.pdf}
\question{Which scale effects could follow return geometry without a change of stochastic law?}
\speaker{This is an exact periodically continued circle, not a fitted flight model. Constant speed does not imply ballistic endpoint displacement over every lag. The original two variation panels are retained; the circular path was illustrated on the preceding task slide.}
\end{frame}'''
    ordered.extend([growth,drift,task,circle,extra_frame('Observed-path closure')])
    add('Quantiles and population control', [old_frame('A single displacement scale'),
        new_frame('The full archive'),extra_frame('A fixed long-flight control'),
        new_frame('Holding flights fixed'),
        plot('Membership, flight weights and common origins change the comparison',
             'supervisor-population-controls.pdf',
             'Which part of the slope change comes from each population control?',
             'The four controls use the same ranks and fitting interval. The fixed cohort includes every qualifying long flight. Curves here are descriptive point estimates; the final fixed-control uncertainty uses the whole-flight paired bootstrap.')])
    spread = old_frame('Relative spread changes')
    spread = notes(spread, 'The fixed-control ratio starts near 1.97 for paragliders and 2.27 for hang gliders, peaks near ninety and eighty seconds, and has a post-peak minimum near two thousand seconds. The final values near 3.01 and 2.60 exceed the initial ones. A negative fitted log-ratio slope is therefore not monotone narrowing. Recheck these observations against the completed report and its paired intervals.')
    ordered.extend([spread,
        plot('All quantiles can grow while spread relative to the median narrows',
             'quantile-example-laws.pdf', 'How can a changing distribution shape coexist with increasing displacement scales?',
             'Analytical illustration: R(tau)=(tau/tau0)^0.85 exp(sigma(tau) Z), with standard Gaussian Z and sigma(tau)=0.9-0.1 log(tau/tau0) on the illustrated range. This is not a fit to flight data.'),
        plot('Unequal rank exponents can encode that changing shape',
             'quantile-example-slopes.pdf', 'Which empirical observations would distinguish this example from a true common scale family?',
             'For the same lognormal illustration, Hp=0.85-0.1 Phi-inverse(p). The example explains the algebra without assigning permanent slow/fast identities to particular flights. The actual empirical curves need their own population controls and uncertainty estimates.')])
    add('Vector scaling and dependence', [new_frame('Anisotropy does'),
        new_frame('East, north and radius')])
    for coordinate, label in [('east','east component'),('north','north component'),('radial','radial displacement')]:
        ordered.append(plot('Fixed-population quantiles: '+label, 'supervisor-quantiles-'+coordinate+'.pdf',
            'Do the ranks retain one relative shape as the lag increases?',
            'Both disciplines use the same four ranks and their own complete fixed cohort. East and north use absolute signed-component magnitudes; radius is endpoint separation, not flown path length. Flights, origins and weights remain fixed across lags.'))
    bootstrap = new_frame('Whole-flight bootstrap')
    bootstrap = replace(bootstrap, r'\centering\fig[48mm]{ch3_fixed_exponents.pdf}',
        r'\par\medskip Overlapping origins remain within the resampled flight; they are not treated as independent replicates.')
    ordered.append(bootstrap)
    for tag, name in [('para','Paragliders'),('hang','Hang gliders')]:
        ordered.append(plot(name+': component and radial exponent estimates', 'supervisor-exponents-'+tag+'.pdf',
            'Which differences need a paired contrast instead of comparing overlapping intervals?',
            'Markers are full-range fitted exponents; vertical segments are the exact saved 95-percent percentile endpoints from 400 whole-flight bootstrap draws. They are not simultaneous intervals and do not include sensor, site-day or fitting-range uncertainty.'))
        ordered.append(plot(name+': paired rank and directional contrasts', 'supervisor-contrasts-'+tag+'.pdf',
            'Which differences persist under a change of fitting interval?',
            'The rank contrast is H90 minus H25 for east, north and radius over each saved fit range. The directional contrast is north minus east at each rank over the full range. Both retain pairing inside the flight bootstrap. The zero line marks the stated equality hypothesis, without a multiple-comparison calibration.'))
    ordered.append(plot('A common fitted scale depends on the fitted interval',
        'supervisor-range-sensitivity.pdf', 'Which range has an independent physical justification?',
        'The component-specific common slopes average the four ranks with their own intercepts. The plot uses saved fits and intervals only, not new fitting. Agreement of a common summary does not establish equal individual rank slopes.'))
    for tag, name in [('para','Paragliders'),('hang','Hang gliders')]:
        for coordinate, label in [('east','east'),('north','north'),('radial','radius')]:
            ordered.append(plot(name+': marginal collapse for '+label,
                f'supervisor-collapse-{tag}-{coordinate}.pdf',
                'Does power or median normalization leave a systematic shape change?',
                'The panels show recorded histogram densities, the saved power rescaling, and recorded first-to-ninety-ninth quantile ranks after median normalization. Positive values are displayed on logarithmic axes; any zero mass is reported separately and retained in the exact empirical-CDF distances. Median-normalized ranks do not establish collapse outside that rank range. The same selected lag colours are retained throughout.'))
    ordered.append(new_frame('The joint comparison'))
    for tag, name in [('para','Paragliders'),('hang','Hang gliders')]:
        for pair in range(1,4):
            ordered.append(plot(name+': signed joint laws ('+str(pair)+'/3)',
                f'supervisor-joint-{tag}-{pair}.pdf',
                'Which changes concern orientation, central concentration or mass outside the displayed square?',
                'Each discipline uses one common colour scale across all six lags, one geographic frame and one scalar rescaling. Colours are probability per original cell. Outside mass is retained in overflow cells for the numerical comparison. Equal plot area does not imply equal precision across disciplines.'))
    ordered.append(new_frame('Agreement of binned'))
    add('Directional structure and environment', [new_frame('Regional plots use'),
        new_frame('Equal east and north'),
        plot('Regional position moments differ along east and north', 'terrain-position.pdf',
             'How much imbalance reflects mean drift, route orientation or changing support?',
             'The clock is time since estimated launch, not an increment lag. Position ratios approach five in the Pyrenees. Raw second moments include both covariance and the squared mean. Splits prevent cross-gap stencils but recorded endpoint offsets can still affect these launch-referenced coordinates.'),
        plot('Regional velocity moments show a related directional contrast', 'terrain-velocity.pdf',
             'Which position and velocity contrasts persist under matched conditions?',
             'The regional figure pools paired east/north observations at each elapsed time and uses site-day pointwise bands. Terrain, weather, routes and the disappearing short-flight population can all contribute. Coordinate-moment balance is weaker than full isotropy.'),
        extra_frame('Regional bands')])
    pca = old_frame('PCA describes')
    pca = replace(pca, r'\hyperlink{pca-backup}{Regional PCA and its numerical support}.',
        'The following panels report regional PCA and its support.')
    ordered.append(pca)
    for tag, name in [('alps','Alps'),('pyrenees','Pyrenees'),('coast','Channel Coast')]:
        ordered.append(plot(name+': centred principal axes across four lags',
            'supervisor-pca-'+tag+'.pdf',
            'Does the axis remain stable as lag and contributing population change?',
            'The covariance pools eligible regional origins from the full archive. Ellipses are centred and normalized by the centred RMS radius; they hide absolute magnitude and drift. The axis is modulo 180 degrees and becomes poorly determined near equal eigenvalues. These panels display all four reported lags; the original compact figure drew only three ellipses.'))
    region_notes = {
        'alps': ('Alps: C/D/CCC has smaller coordinate-moment imbalance',
                 'Does the ordering persist after matching site, day, task and duration?',
                 'The fresh Alpine position and velocity ratios stay closer to unity for C/D/CCC over the supported grid. This is a descriptive ensemble observation. It does not establish individual isotropy, greater skill or a causal equipment effect.'),
        'pyrenees': ('Pyrenees: the ordering of the two groups reverses',
                    'What changes between the early and later portions of the curves?',
                    'The Pyrenean curves do not support a uniform expert-proxy advantage. At late times both position ratios exceed five, while the velocity ordering also changes. Adjacent plotted times are correlated observations, not independent tests.'),
        'coast': ('Channel Coast: the late position contrast is pronounced',
                  'Can matching conditions separate directional route choice from wind response?',
                  'Near 9086 seconds the position ratios are about 1.74 for A/B and 1.04 for C/D/CCC, supported by 188 and 1733 paired flights. These are raw ensemble second moments and the samples differ strongly. Coastal cliffs and valleys prevent a wind-only interpretation.'),
        'poitou': ('Poitou-Charente: the group curves cross',
                   'Does this low-relief launch box reproduce the coastal observation?',
                   'The crossing curves and broad overlapping bands do not support a general group ordering. These broad launch-location boxes are neither DEM-verified plains nor controls matched on weather.'),
        'champagne': ('Champagne-Lorraine: a late contrast does not keep C/D/CCC at unity',
                      'Which parts of the coastal hypothesis transfer to this separate region?',
                      'A later position contrast appears, but the C/D/CCC ratio also rises above one. Region, route mixture, weather and declining support must be separated before claiming the same physical cause.'),
    }
    for tag, (title, question, note) in region_notes.items():
        ordered.append(plot(title, 'equipment-'+tag+'-both.pdf', question,
            note+' Violet: A/B; ochre: C/D/CCC. Beginners and experts in the retained figure legend denote equipment proxies. Bands are pointwise 10--90-percent site-day bootstrap ranges, not intervals for the group difference.'))
    ordered.extend([new_frame('A physical interpretation'),new_frame('Define the target')])
    add('Duration and equipment composition', [])
    duration = old_frame('Long flights occur')
    duration = replace(duration, '7,426 beginners', '7,415 A/B flights')
    duration = replace(duration, '27,842 experts', '27,815 C/D/CCC flights')
    ordered.extend([duration,old_frame('Duration and equipment on'),
                    old_frame('Fixing equipment proportions')])
    add('Model comparisons and temporal memory', [])
    moments = old_frame('The moment spectrum')
    moments = notes(moments, r'The current pooled moment spectrum has $\zeta(2)=\StatRevParaMomentZetaTwo$ for paragliders and $\StatRevHangMomentZetaTwo$ for hang gliders. The corresponding $\zeta(q)/q$ ranges are imported in the report. The illustrative beta=1.5 line is not a fitted null. A finite-record comparison must reproduce sample lengths, cadence, selection and weighting, and assess whether the asymptotic branch change would be resolvable.')
    memory = plot('Velocity memory remains visible after averaging over minutes',
        'memory-positive.pdf', 'Do the curves support one decay law over the displayed scales?',
        r'Use $\mathbf v_h(t)=[\mathbf r(t+h)-\mathbf r(t)]/h$ for h=10, 60, 300 seconds. Velocities use adjacent non-overlapping blocks; correlations are centred and normalized within flights before averaging. At 600 seconds the para values are $\StatRevParaVacfTenAtSixHundred$, $\StatRevParaVacfSixtyAtSixHundred$ and $\StatRevParaVacfThreeHundredAtSixHundred$. These upper log panels show positive correlations only.')
    signed = plot('Signed correlations retain the long-lag negative values', 'memory-signed.pdf',
        'What share of the long-lag decrease could follow finite-record centring or route returns?',
        'A log plot cannot show the negative part. Both disciplines have long-lag negative values in the signed representation. Coarse averaging can raise normalized correlations without increasing the underlying physical persistence time. At least twenty flights contribute to each plotted estimate.')
    theory = old_frame('Signed memory')
    theory = replace(theory, 'Signed memory and the finite-persistence alternative',
        'Finite velocity persistence gives a ballistic-to-diffusive crossover')
    theory = replace(theory,r'\begin{columns}[c,onlytextwidth]'+'\n'+r'\column{.55\textwidth}\fig[49mm]{memory-signed.pdf}'+'\n'+r'\column{.42\textwidth}\small', r'\small')
    theory = replace(theory, r'\end{columns}', '')
    ordered.extend([moments,old_frame('Non-Gaussian pooled'),memory,signed,theory,
                    old_frame('Which models are challenged'),extra_frame('Phase-conditioned')])
    decisions = old_frame('Three decisions')
    decisions = notes(decisions, 'Agree the physical target, a small set of explicit candidate processes, and a sampling model for uncertainty. No rotation or rescaling has recovered still-air motion. Phase-conditioned comparisons should include transitions and between-episode dependence. Calibrated comparisons can begin before declaring a final physical model.')
    ordered.append(decisions)
    ordered.append('\\section{Linked representations and sources}')
    ordered.append(new_frame('Squared-displacement'))
    ordered.append(old_frame('Sources and the scope'))
    ordered.append(r'''\begin{frame}{Joint laws and environmental interpretation: additional sources}
\small
\refitem{https://arxiv.org/abs/2206.13612}{Fraiman et al., Cram\'er--Wold results}{Joint laws and projections}
\refitem{https://arxiv.org/abs/1102.1822}{Didier \& Pipiras, operator fractional Brownian motions}{Beyond scalar rescaling}
\refitem{https://www.dhv.de/en/type-inspection/classification/}{DHV classification guidance}{Class is not a performance measure}
\refitem{https://www.normandie.developpement-durable.gouv.fr/le-pays-de-caux-a1902.html}{DREAL Normandie, Le Pays de Caux}{Coastal cliffs and valleys}
\source{The cited pages support specific mathematical or observational cautions. They do not identify the causes of the regional contrasts measured here.}
\end{frame}''')
    head = r'''\documentclass[11pt,aspectratio=169]{beamer}
\newcommand{\TalkShort}{Chapter 3: global transport}
\input{theme}
\input{data/ch3_revision.tex}
\input{data/duration_equipment.tex}
\input{data/kinematic_isotropy.tex}
\input{data/msd.tex}
\hypersetup{pdftitle={Global transport: full chapter, vector laws and supervisor discussion}}
\begin{document}
\titleframe{Global transport in soaring flights}
 {Measurements, controls and questions for the supervisors}
 {Chapter 3\enspace$\bullet$\enspace Complete chapter review}
\speaker{This deck develops the whole chapter without a prescribed duration. Its central distinction is between measured constraints on the observed ground trajectories and hypotheses about their generating process.}
'''
    draft = head+'\n\n'.join(ordered)+'\n\\end{document}\n'
    draft = draft.replace('\n\\medskip\n','\n\\par\\medskip\n')
    for obsolete in ('20-minute','\\timing{','107 para / 56','Measured subset','one longest segment', '7,426','27,842'):
        assert obsolete not in draft, obsolete
    return draft


if __name__ == '__main__':
    chapter2 = make_ch2()
    (HERE/'chapter2-supervisor-draft.tex').write_text(chapter2)
    print(f'Prepared Chapter 2: {chapter2.count(chr(92)+"begin{frame}")+1} frames including title; final numerical and layout review pending.')
    chapter3 = make_ch3()
    (HERE/'chapter3-supervisor-draft.tex').write_text(chapter3)
    print(f'Prepared Chapter 3: {chapter3.count(chr(92)+"begin{frame}")+1} frames including title; final numerical and layout review pending.')
