# Regional interpretation: thesis and supervisor discussion

Status: review criteria prepared while the numerical run is active. These are not
claims that the refreshed plots have already confirmed the old visual pattern.
Implement in BOTH final thesis and complete Chapter3 supervisor deck after allruns.

## Preserve the proposed explanation

If the new curves confirm smaller east/north second-moment imbalance for the
C/D/CCC group, discuss whether equipment and pilot decisions could moderate the
directional constraints associated with wind and terrain. Similar mountain profiles
might motivate a shared environmental constraint; a stronger coastal group contrast
might motivate different responses to wind. Each remains an interpretation to test.

## Mathematical objections and how to resolve them

1. The plotted ratio is a ratio of ensemble raw second moments on paired support,
   not the average of individual E²/N² ratios, a covariance eigenvalue ratio, or a
   measure of each pilot's navigational performance.
2. Unit ratio only equalizes the geographic diagonal entries of M=E[XXᵀ]. For a
   centered Gaussian with covariance [[1,.9],[.9,1]], the ratio is1 but the principal
   variances differ19-fold. Even M proportional to I is only second-order isotropy,
   not rotation invariance of the full law. A scalar common scaling exponent can
   coexist with an anisotropic law.
3. M=Cov(X)+E[X]E[X]ᵀ: a change in mean drift can change the ratio without the same
   change in centered fluctuations. Compare raw tensor, centered covariance and
   angular structure, making any centering explicit.
4. 'Closer to one' should be compared symmetrically under swapping axes, e.g.
   |log(M_EE/M_NN)|, not linear |ratio-1| when curves cross1. This remains an
   axis-specific imbalance, not a full anisotropy invariant. Do not silently replace
   the existing estimator or claim a new tested contrast from visual proximity.
5. An ensemble balanced between east-aligned and north-aligned flights can have
   ratio1 while every individual flight is strongly directional. It does not follow
   that individual experienced pilots 'fly more isotropically'. Group aggregation
   and individual directional behavior answer different questions.
6. Isotropic ground displacement is not intrinsically successful flight. A deliberate
   downwind cross-country route can be strongly directional. Ground velocity is the
   vector sum of air-relative velocity and wind; no independent wind is measured
   by this ratio.

## Observational objections

- Labels Beginners/Experts are EN A/B versus EN C/D/CCC equipment proxies. Actual
  skill is unmeasured; experienced pilots can use A/B. Skill and equipment effects
  are inseparable here. Certification classes describe flight behavior/requirements,
  not a direct measured aerodynamic performance ranking.
- The x-axis is elapsed time since launch t, not increment lag tau. Support changes
  with duration, segmentation and available derivatives. Compare n(t), cluster
  counts, and durations before reading the late-time separation as changed behavior.
- Regional boxes classify launch locations, not the entire route or weather. A
  flight may leave its launch region. The coastal box is not a zero-relief control.
- DREAL documents chalk cliffs and coastal valleys within the Channel Coast box;
  low relief can still orient ridge-soaring routes. Wind and terrain can interact,
  so the proposed 'coast=wind only, mountains=terrain' separation is unsupported.
- Different sites, days, wind directions, seasons, intended tasks, flight lengths,
  route mixtures and declaration/wing-class availability can confound contrasts.
- Similar curve shape does not establish a common cause or unavoidable terrain
  constraint. Different orientation mixtures may also reduce an aggregate ratio.
- Plotted intervals are pointwise10–90% percentiles of200 site/date cluster draws,
  not simultaneous bands, a95% interval, or a direct between-group contrast.
  Display guards are30 paired flights and10 clusters per time, not precision proof.
  Missing site/date keys need review in the generated summary.

## Discussion questions and next comparisons

- Does the group difference persist within the same launch site/day and comparable
  duration/task? First inspect whether both classes have overlapping support there.
- Is it a difference in mean ground drift, centered directional variability, or the
  mixture of individual route directions? Compare individual and pooled tensors.
- Does aligning with an independent wind field or local ridge direction explain
  more variation than geographic east/north? Both require additional measurements.
- Would a same-pilot/different-wing comparison help separate equipment from pilot
  choice, if enough such matched flights exist and weather/task can be controlled?
- Which outcome would supervisors regard as 'resisting wind': airspeed/polar,
  upwind progress, route choice, or another measure? The present ratio does not
  define this performance target.

## Primary source notes (accessed12September2026)

DREAL Normandie, 'Le pays de Caux', published23February2018:
https://www.normandie.developpement-durable.gouv.fr/le-pays-de-caux-a1902.html
Describes coastal chalk cliffs, plateau and valleys in the relevant broad region.
Use for geographic correction only; it does not characterize these flights' weather
or measure local terrain exposure along their routes.

DHV, 'Classification':
https://www.dhv.de/en/type-inspection/classification/
Official explanation distinguishes test flight characteristics from performance and
states class-specific pilot requirements. Page uses LTF nomenclature: do not cite it
as verbatim EN standard text or evidence of actual pilot competence in the archive.

## Structure steering

Split current oversized3.3 into distributional rescaling/self-similarity and
regional/environment/equipment anisotropy; choose final sequence after allruns.
Introduce tensor/axis distinctions once and cross-reference rather than repeat.
Keep t-since-launch and tau-increment questions explicit. Reserve causal language
for hypotheses and identify measurements needed to assess each mechanism.

## Estimator distinction to retain when separating sections

Current regional PCA uses centered covariance of all eligible signed increment
origins in each region/lag, pooled with equal weight PER ORIGIN. Longer supported
segments therefore contribute more origins. It is not the equal-flight fixed-common-
origin joint-law measure. The plotted covariance ellipses are centered at zero and
normalized by sqrt(trace(covariance)), showing orientation and shape while suppressing
absolute scale and mean drift. The source report retains means/covariances.

Current geographic kinematic ratios instead use paired finite flights at each
elapsed time since takeoff, one contribution per flight, raw moments. These measures
are complementary but not direct replicas. Explain support, weighting, centering and
clock differences when moving PCA beside terrain/wing-class panels. Do not attribute
a difference between PCA and raw ratios solely to a physical effect before accounting
for these changes of estimand. Regional PCA requires8contributingflights; this is an
operational inclusion floor and there are no calibrated uncertainty bands on its
ellipses/eigenvalue ratios. Source: region_geometry inarchive_diagnostics.py and
generate_revision_diagnostics.py regional loop/draw, read during active run.

The site/date cluster bootstrap addresses one dependence structure in uncertainty
estimation; it does not match the wing groups on weather/site, remove confounding,
or turn an association into a causal effect. Likewise, using the complete archive
reduces sampling loss but does not remove selection into declared flights or the
loss of support at long times. Distinguish these issues in the supervisor discussion.

## Fresh regional results: stage23 completed and audited

The fresh kinematic_isotropy_terrain_level.pdf was visually inspected at2100pixels;
labels, bands and shared axes are readable. regional-contrasts-audit.json identifies
its source JSON and extracts supported curves. IMPORTANT: the refreshed data do NOT
support a universal experts-closer-to-one rule. The user was informed immediately.

- Alps: C/D/CCC position AND velocity raw moment ratios are closer to1 at every one
  of the58plotted supported times. At9086s, positionratiosAB=.5283,CDCCC=.6273;
  velocityratios=.7639,.7785. Positioncontrastpersists, velocitycontrastnarrows.
- Pyrenees: ordering reverses. C/D/CCC closer in31/58positiontimes,25/58velocitytimes.
  These correlated-grid counts are DESCRIPTIVE, not a binomial test or evidence
  of independent replication. At9086s positionratiosAB=5.0461,CDCCC=5.1079;
  velocityratiosAB=1.0866,CDCCC=1.2542. The high-classgroup is not uniformlymore
  balanced. Similaroverallregionalshape is visible but not evidenceidentifyingcause.
- ChannelCoast: C/D/CCCcloser in55/58positionand49/58velocitytimes. At9086s
  positionratiosAB=1.7401,CDCCC=1.0430;velocityratiosAB=1.3821,CDCCC=1.0577.
  LatepairedsupportAB188flights/163site-dateclusters vsCDCCC1733/1007; at10s
  support874/3681flights. WideABbands andchanging/unequalpopulationneeddiscussion.

Use these observations to retain and qualify the user's proposed explanation:
patterns differ byregion andquantity. Do not claim universalexpertability, a
wind-onlycoast, a measuredperformancebenefit, or fullisotropyfromratio1.

Fresh low-relief-box figure also visually reviewed:kinematic_isotropy_flat_level.pdf,
previewfresh-low-relief-review.png. Poitou-Charente curves cross and bands overlap
substantially; it is not another clean universal expert-isotropy result. Champagne-
Lorraine shows a latepositioncontrast, but theC/D/CCCcurve also risesabove1.
Avoid treating the coastalpicture as a genericflatlandexperiment or treating all
regionalboxes as DEM-verifiedplains. SourceJSONsummaries omitflat-groupstrata;
this note is a visual review, not an extracted quantitative group test.
