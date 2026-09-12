# Current checkpoint — post-remount verification PASSED, stage24 active

Validated preparation completed successfully. Current recovery run:
20260912T104500Z-5cfc4e8c, under this revision's recovery-runs/ directory on the
INTERNAL disk. --run is active in exec session 69460, driver PID 54892;
full structural verifier PID 54947 completed successfully; stage24 transport_full is active. caffeinate -im is active. Local console:
recovery-console.log. Manifest and per-stage logs live in the internal run directory.
Do not launch duplicate recovery or modify guarded sources/helper.

Both staged stores passed size/finite/owner/segment checks and exact increment
oracles at all 31 lags for 26 flights per discipline. 155085 para / 6060 hang flights;
171663465 / 7301634 saved positions. 274 staged input proofs, 23 preserved prefix
logs, 41 reused required outputs. All staged hashes were checked again under locks
before starting full verification. Internal free ~11 GiB before six display arrays.
Prepared source identities exactly match the interrupted original; cleaning2.3.0.
10 local fault-injection tests passed; recovery-integrity-tests.json records hashes.

Full post-remount verification passed all 1,404,375,505 fixes, with unchanged
counts and completed-prefix output hashes. post-remount-verification.json records
evidence and its limits. Parent stale running status is now corrected to failed,
with original bytes preserved. Canonical stage24 resumed with --reuse; stages24–39
still need to finish. Partial in-memory bootstrap results must recompute.

Original main run 20260911T213634Z-7b7367f1 stopped during transport_full after
23/39 stages. Driver PID 19168 and reporter PID 44301 are dead. SIGBUS occurred
after the 140 s bootstrap lag. Local evidence: ssd-disconnection-20260912.json
and its .log. The old manifest still says running because its failure write
failed on the missing SSD. Partial in-memory bootstrap results must recompute.
No auxiliary numerical runs remain. Keep guarded src/scripts/configs/manuscript
sources unchanged until the numerical continuation completes. Pending tasks below.

Freshregionalcounterexample: Expertscloser-to1notuniversal—Pyreneesorderingreverses;
coastlatepositionAB1.740/CDCCC1.043 at9086s butunequalsupport188/1733flights.
Detailedcriticisms+numbers:regional-interpretation-review.md,regional-contrasts-audit.json.
FreshcontrolledPSDcomparison: same2008flights, GNSSfloorp90 3.758→.590 solelychanging
wholetracevsvalidpairedblockselection (currentdecoder/sameWelch/noSG). Currentcache
reproduced. psd-selection-comparison.json recordsrawhashes,codeandmethod; putresult
inBOTHCh2thesisandslides. Trimmingrescan reproducedbothcaches/all3outputsexactly.

Userlateststeering: splitoversizedCh3sec3.3 intorescaling/selfsimilarity/quantiles/joint
versusregionalPCA/terrain/wingclasses, improveflowandavoidrepeat. DoAFTERALLruns.
Stillpending: finishmainrun; audit_full_chapter3.py; reconcileallnumericclaims,
structuralreviewCh3anduserhypothesis+criticismsinthesis; reviewedcompile;
WHOLEchapter2/3supervisordecks(notfixed-durationtalks),notes/questions/limitations;
finaldocschecks,artifactverificationandLOCALCOMMITS(no push). No structuralreview,
canonicalthesisedits,deckproductionorcommitsyethappenedinthiscontinuation.
No subagentsallowed. no-ai-slopskillnotyetread/applied; considerforfinalprose.

The entries below are the chronological working record; later entries supersede earlier
stage/status statements. Main manifest and live stdout are authoritative.

# Live execution state — 11 September 2026, 21:44 UTC

Standalone full cleaning completed successfully. Both archives have validated complete
pipeline 2.3.0 manifests, with no cleaning error records. Raw data are safe.
Cleaning source hash db1e245f47cf4c1bd623ecc5aa8a8b8879a41c8d4d2b585689e9632ef91ccd85.

**The active full downstream rebuild is the process launched by the other session:**
`/Volumes/SSD_DISANTE/derived-audit/runs/20260911T213634Z-7b7367f1`
PID 19168, started 21:36 UTC, 8 workers / one native thread / full speed.
This session verified its full source hash AND numerical source hash match the
prepared frozen copy and the current working tree exactly. Follow this existing run;
do not launch another rebuild. It owns the global rebuild and preprocessing locks.

The earlier downstream run 20260911T204919Z-a9801d6d stopped after raw_diagnostics
because concurrent manuscript edits changed the full source hash; numerical sources
were unchanged. An isolated continuation was prepared and passed all reuse checks,
but its attempt 20260911T214153Z-8bb61976 correctly failed on the existing lock,
without executing or changing any stage. The frozen copy remains a recovery option.

**Do not edit src/, scripts/, configs/, thesis sections/appendices/main/references
while the active driver runs: it checks full source identity at every stage.**
Docs, README and revision notes are outside that hash. Once the numerical run completes,
review manuscript conclusions against its new outputs and run
`scripts/review_thesis.py --run <completed directory>` to record the updated PDF.

The user now explicitly requests commits AFTER the full cleaning, full Chapter 3
(including joint plots), numerical verification and thesis/documentation update.
Preserve concurrent session changes; no push was requested. This session is monitoring
and reviewing, not starting a duplicate pipeline.

Latest clarification to user: full eligible archive is used at every supported lag;
fixed long-flight/common-origin comparisons are an ADDITIONAL population-control
analysis. The 20000 s threshold provides origins at the maximum 10000 s lag; it is
an operational statistical choice, not a Mac computational limit. Short flights
remain in the full changing-population analysis. Avoid saying fixed selection is
mathematically necessary at precisely 20000 s or suggesting it replaces full data.

Structural verification in the active run passed in 596 s on 1,404,375,505 fixes.
`audit_full_chapter3.py --run <run>` is ready outside hashed sources: run it only
once transport_full completes. It checks full provenance, cohort membership,
quantile consistency and joint masses/distances, then extracts review values.

## Completed validation

870 full tests passed (223.27 s), 24 existing hmmlearn NumPy deprecation warnings.
Additional tests after that pass: irregular-source vs flagged-grid distinction;
streamed regional covariance equivalence; full cache incomplete-marker rejection.
Focused checks passed. Strict MkDocs passed before final guide wording updates.
New report smoke test renders complete marginal and joint figures from disk-backed
synthetic multisegment flights. `joint-render-smoke.png` is SYNTHETIC, not real data.
Bootstrap benchmark: 996140 origins, 1000 flights, 401 draws, one coordinate in1.63 s.

After cleaning: para156406 retained,194208 segments,1369807970 fixes; hang6094,
7662 segments,34567535 fixes. Witness20171597 now retains t0–6805 and7450–10703,
excludes old644s reconstructed interval, longest flagged reconstruction1s.
See `after-cleaning.json` and executable `audit_completed_cleaning.py`.

The audit initially assumed incorrectly that `z_gap_max_s <= g_max_s` must hold.
Four para flights had flagged-grid runs24–30s with gmax20s. All four were independently
reprocessed; each output point's bracketing finite source readings were checked:
actual maximum interpolation spans16or20s, zero violations. Valid source readings
between grid nodes need not clear nearest-fix flags. See `check_flagged_support.py`
and `flagged-support-audit.json`; regression test pins the distinction. No cleaning
source change, no extra cleaning rerun needed. Overall flagged-run max176s is at
coarse native cadence; the rule is cadence-dependent. It is not a uniform20s cap.
Incomplete candidate reason is `channel_not_reconstructable` (29407para,1637hang).

## Chapter3 implementation

User requested all eligible data on M1,8CPU,8GB RAM; latest authorized doing what
is scientifically best for missing joint-law problem. No subagents authorized.

- `archive_diagnostics.py`: stream_flights reassembles storage boundaries; all
  eligible segments (native<=10s,>=2 points on10s grid), no count/rowgroup/longest cap.
  DiskFrames compact coordinate memmap + rows with half-open segment ranges.
  All increment stencils remain within segments; per-flight means pool their
  segment origins then flights have equal weight. VACF normalizes per segment,
  averages supported segments within flight, then gives flights equal weight.
  Bounded ordered ProcessPool queues, default CPU count/env/--jobs. All per-lag
  vectors(float64) and owners(int32) on disk. Moments and Mardia chunked, quantiles
  one coordinate/lag at a time. Regional PCA now chunked to avoid several-GB copies.
  `archive_quantile_control` reduces four populations one lag/variant at a time.
  Save/load compact measurement.pkl references backing pools; `.incomplete` marker
  rejects interrupted stores.
- `segment_support.py` defines common within-segment origins.
- `self_similarity.py`: direct DiskFrames recovery avoids old quadratic owner scan;
  legacy cache recovery uses contiguous offsets. Fixed flights have >=1 segment
  of20000s; all common origins supporting10000s within segments are reused at everylag.
  400 paired whole-flight resamples, equal flight mass. Exact blocked inverse weighted
  CDF avoids scanning every origin400times; tested against original includingatoms.
  Display samples memmapped in full mode. Remaining weightedECDF distances exact,
  descriptive, no iid KS p-values. No site/day bootstrap implemented (clearly stated).
- `joint_distribution.py`: signed bivariate histograms after one scalar commonH
  (mean12rank slopes), fixedgeographicaxes, common reference lengthfromradialmedian
  near1000s,64x64interior[-6,6] plusoverflowcells; equalflightweights. Pairwise binnedTV,
  means,covariances in self_similarityJSON. Figures ch3_joint_para/hang.pdf show sixlags
  with commoncolor limitsand explicit tailmass. This is finite-resolution descriptive
  jointlaw diagnosis, NOT formal processselfsimilarity verification orcalibratedtest.
- generate_revision_diagnostics.py defaultfull, --sample explicitdevelopmentonly;
  fullcache ch3_revision_full.pkl points to ch3-full-para/hang. --reuse validates
  originalinputsandcodecontract. Legacy --saved-snapshot still extends identified
  historicalsample (another user session'sfeature preserved).
- TAMSDAccumulator.add_curve reuses component FFTs: radial=sum E/Ncurves andduration
  cohorts reuse samecurve. Estimator equivalent up tofloatingpoint; oraclepassed.
- configs/rebuild.yaml stage nowtransport_full. Allnewoutputs inGENERATED_OUTPUTS.

Storage preflight afterclean:29GiBavailableexternal,19GiBlocal. Predictedfullpools+
coordinates14.11GB; fixedchosenlawarrays3.24GB. Remaining old/newanalysisproducts
have room; watch duringactualfullrun. Largest para pool171.7Mincrements, fixedorigins
~21.74M. Sortingonecoordinatestillallocates~1.37GB; regionalPCAcopieseliminated.

## Math, docs and user response

Latest user asks if E,N,Rdiagnostics sufficient inanisotropic2D and literature; then
"fai quello che ritieni più giusto per affrontare il problema". Alreadyexplained in
commentary and implemented signedjointdiagnosis:
- E,N,R useful necessarychecks forcommon scalar scaling, not jointidentifiers.
- Even SIGNEDmarginals+Rsame foruniform{(1,2),(-1,-2)} vs{(1,-2),(-1,2)}; jointdifferent.
- Current componentdiagnostics |E|,|N| discard signs. Covariance/Mardiaalsoonlysummaries.
- Anisotropycan coexistwith commonscalarH; operatorselfsimilaritybroader.
- Single-lagjointlaw stilldoesn'tdeterminejointlawsacrosstimes/processselfsimilarity.
- No naive iid p-values foroverlapping pairedorigins; noformalnull calibration claimed.

Primarysourcesread, citeMarkdownURLs in final:
https://arxiv.org/abs/2206.13612 FraimanMorenoRansford(CramerWold allprojections;
finite3directions only underellipticalassumption).
https://arxiv.org/abs/1102.1822 DidierPipiras2011 OFBM/operatormultivariatescaling.
https://pages.stat.wisc.edu/~wahba/stat860public/pdf4/Energy/JSPI5102.pdf
SzekelyRizzo2013EnergyStatistics (finitefirstmoments, energy=0iffequaljointlaws).
Added bibkeysfraiman2022,didier2011,szekely2013; updatedbibliographyguide.

Updated thesis03verticalgaprule/schematic;04fullpopulation/weights/VACFandjointsection;
guidespreprocessing,data-on-disk,globaltransport,scripts,bibliography,README,
ADR0002,CONTEXT. Some files had extensive concurrentother-session changes; preserve.
The numerical chapter conclusions still need reviewing against completednewrun:
quantileordering/shape/intervals, cohort differences, HMM lastlikelihoodgains/examples,
currentcounts andREADMErun/annotationlinks. Do not assert completednewPDF yet.
First failed combined run20260911T160003Z-b26eb528 is correctlymarkedfailed afterSSD
reconnection. READMEauditearlyparagraphstillmentions itasinitialrun; updateforfinal.

## Latest user questions (12 September, local time)

User asks whether completed cleaning and the future Chapter 3 run really match the
version described in the thesis. Direct verification saved in source-consistency-check.json:
current cleaning definition equals run, both completed snapshots validate against it,
no incomplete markers, current full source (including manuscript) and numerical hashes
match the active run. Checked thesis gap equation and whole-trajectory split rule against
resample.py; checked Chapter 3 full scope, within-segment origins, four population
controls, paired bootstrap and joint normalization against code. No sample flag in stage24.

Explained clearly: CLEANING matches pipeline2.3.0; planned Chapter3 METHOD matches
current thesis sources; CURRENT PDF and numerical conclusions are NOT yet updated.
snapshot_status.tex still says2.2.0, ch3_revision.json predates this run. Final completed
run, fresh-result audit and manuscript review still required. Do not answer blanket
"everything in the current PDF is already validated". The specific pending manuscript
clarifications remain listed in manuscript-review-pending.md (closure across gaps,
joint reference scale, numerical claims, explicit additional-control population).

Monitoring process: exec session73044 emits manifest stage and SSD free space every45s.
Caffeinate tied to active driver PID19168 is exec session34559. Original driver was
launched by another session (not an exec session owned here). As of latest checks,
verify/reproduce/acquisition complete; raw_diagnostics running, all8 workers active.
Source identity still unchanged. No active isolated continuation; do NOT relaunch it.

## New fixed-cohort counts provided to user

User quoted old PDF counts107para/56hang (2.2.0) and asked whether newrun has more.
Computed current completed2.3.0 segment/flight metadata, native<=10s, 10s-grid support:
- para155085 eligible flights,190762 segments,14360 fixed long flights,
  21739115 common origins,171663465 positions;3446 coarse segments excluded.
- hang6060 eligible flights,7620 segments,563 fixed long flights,
  791712 common origins,7301634 positions;42 coarse segments excluded.
Saved new-cohort-counts-preflight.json. Told user these are metadata-derived counts,
to compare with actual full coordinate collector. Old107/56 were long flights within
only955/479 sampled flights; new14360/563 come from the complete eligible archive.
These counts supersede vague estimates. Compare actual final provenance counts before
publishing final figures or assertions; minor grid-storage rounding can be investigated.

Live stdout of the active OTHER-session driver is accessible at
revisions/prose-review-2026-09-11/second-pass/rebuild-resumed.log.
Per-stage logs are buffered until the child exits; use this live stdout for progress.
As of 22:24 UTC-ish, raw_diagnostics finished and stages5–7 completed; altitude_noise
(stage8) is running. The manifest remains the authoritative current state.

## Added user requirement: structural review AFTER ALL RUNS

Latest user explicitly asks to assess whether Chapter3 is clear and well organized,
whether its sequence conveys the messages or jumps between subjects and returns
unnecessarily. They say AFTER all runs. Agreed to read the chapter as one argument,
distinguish order problems from explanation problems, reorganize where useful against
new results, before final compilation and user-requested commits. Do NOT mark task
complete after numerical runs alone. Preserve all numerical/methodological content,
labels/citations and concurrent writing; restructure only once the guarded run ends.
Consider applying no-ai-slop skill for this prose/clarity review (not yet read/applied;
announce when first applied, then read /Users/matteodisante/.agents/skills/no-ai-slop/SKILL.md).
Final review_thesis.py should compile the numerically reconciled AND structurally
reviewed manuscript. Tests/docs build and local commits follow. No push requested.

## Supplemental trimming census — RUNNING, session14021

After active stage15 completed, noticed generate_trimming_figure.py reuses an
UNVERSIONED trim_scan.parquet. Its cache was produced17:32/17:33 local with unchanged
upstream adopt/fix/trim code (all relevant files older), but forcing a fresh census
provides direct provenance rather than relying on timestamps. This does NOT invalidate
the complete2.3.0 cleaning or fullChapter3 plan, both independently hash-validated.

Started `caffeinate -i .venv/bin/python -u
revisions/vertical-gap-split-2026-09-11/refresh_trimming_census.py` in session14021.
It runs the unchanged trimming generator with --rescan, 4workers,nice10,nativeThreads1;
records original/current output/cache hashes, fullsourcehash and dataset identities
in trimming-refresh.json, logs trimming-refresh.log, checks canonical tables and
source remain unchanged. It rewrites ONLY trim cache and the three trim products,
after mainstage15 and well before the final outputs/PDF checks. Mainrun can continue.
Check that this completes before final mainPDF/review. If outputs differ, interpret
fresh results and explain; if identical, this directly confirms the cached outputs.

No canonical src/scripts/config edits were made. Do not modify guarded sources now.
The current rebuild plan lacks --rescan for trimming; its cache loader has no source
contract. Document forced refresh requirement when adoption/fix/trim rules change;
current supplementary run supplies that evidence. Any later code/config fix would
change numerical source identity and must not be silently patched into a completed
run manifest. Main current stage was16terrain at supplemental launch.

## Added final deliverable: complete supervisor decks for Chapters2 AND3

User now requests, at the END of everything, updating existing OLD slides for both
chapters. They must cover the WHOLE chapters, not an hour-long talk. Audience is
supervisors: communicate results, uncertainties, intelligent questions prompted by
plots, and useful requests for their opinions. Promised decks based on final reviewed
thesis/new results, included in final local commits. Do not finish before delivering
both decks and reviewing their rendering. Locate existing presentations after numerical
runs and structural thesis review; preserve useful existing deck infrastructure.
No skill read/applied for slides yet. No subagents authorized.

User interpretation example of old Fig3.17: experts closer E²/N²=1 in Alps/Pyrenees/
ChannelCoast, suggests better resistance to wind/orography and better wings; coastal
beginner anisotropy at long lags attributed only to wind, assumes no coastal relief;
similar mountain shape interpreted unavoidable orography moderated by experts.
Responded constructively: use this as a hypothesis for supervisors, not causal result.
- Ratio1 equalizes two raw component second moments; it does NOT prove full2Disotropy.
- ENwing classes are equipment-based experience proxies, not measured pilot skill;
  cannot separate skill from equipment with these labels alone.
- This plot uses elapsed time since takeoff, NOT increment lag; support/population
  changes at long elapsed times.
- Wind attribution and ignoring coastal orography require verification/controls.
Suggested supervisor question: does smaller axis contrast reflect wing performance,
route choice, weather or long-flight selection, and which comparison separates them?
Need revisit actual refreshed plots (figure numbers may change after restructuring),
verify any geographic/literature claims with primary sources when preparing slides.
Slides should distinguish observations, proposed mechanisms, limitations and concrete
next tests without treating hypotheses as established findings.

Outstanding order: finish main39-stage numerical run + supplementarytrimrefresh;
validate freshresults; review/restructure Chapter3; reconcile other chapters/docs;
compile reviewedthesis; rebuild whole-chapter supervisor decks2and3; verify outputs;
user-requested local commits (no push requested). Update manifests/review records
as appropriate if decks touch numerical hashes (scripts under scripts/ are hashed;
prefer existing presentation source/assets paths outside numerics during final review).

## User steering: split oversized section3.3 and put critique in BOTH artifacts

User explicitly requests their regional wing-class interpretation and its weaknesses
in BOTH thesis and supervisor slides. Preserve it as a recognizable hypothesis,
check refreshed results, and distinguish observation, proposed mechanism, alternative
explanations and tests. Ratio E²/N²=1 alone does not imply isotropy (covariance
[[1,.9],[.9,1]] has equal diagonals but eigenvalue ratio19); ground motion also mixes
wind and air-relative motion. Near-isotropy is not intrinsically better performance.
Wing classes are not measured pilot skill; long-time composition, task, routes,
site/day/weather, equipment and pointwise uncertainty can explain apparent contrasts.
Elapsed time since takeoff is not increment lag. Similar regional profiles alone do
not identify unavoidable orographic effects. Channel Coast is low-relief, not flat:
actual box lon[-1.8,2],lat[48.3,51.2] includes Normandy chalk cliffs and valleys.
Primary sources found for later bibliography (do not edit guarded sources duringrun):
- https://www.normandie.developpement-durable.gouv.fr/le-pays-de-caux-a1902.html
  DREAL, coastal chalk cliffs/valleys, Caux maritime. Supports nonzero relief.
- https://www.normandie.developpement-durable.gouv.fr/le-recul-du-trait-de-cote-a5963.html
  DREAL, Normandy cliffs and coast forms.
- https://www.dhv.de/en/type-inspection/classification/
  DHV official classification, flight behavior and required pilot competence;
  page labels LTF, do not silently treat as direct EN wording or observed experience.

Latest user suggests splitting current lengthy3.3 'Anisotropy, dependence and the
environment' into rescaling/self-similarity/quantiles versus terrain/PCA/wingclasses/
regional comparisons. Agreed this separates two scientific questions. AFTER ALLRUNS,
implement appropriate split and examine order/transitions, avoiding duplicated
anisotropy definitions and overclaiming 'effects of orography'. Working section ideas:
'Distributional rescaling and self-similarity' (signed joint included) and
'Environment, equipment and anisotropy' (association, hypotheses, confounding).
This is added steering within the already-authorized structural review, not a
replacement of run, audit, thesis, slides and commits requirements.

Read-only follow-up confirmed current regional graph code uses200 site/date cluster
bootstrap draws and pointwise10–90% limits, min30pairedflights/10clusters. Added
regional-interpretation-review.md with detailed mathematical/observational critique,
user's hypothesis retained, concrete supervisor questions and primary source notes.
Includes important additional objection: balanced pooled directions do not establish
individual pilots fly more isotropically. |logratio| gives axis-swap-symmetric visual
comparison but remains axis-dependent. DHV explicitly says classification tests
characteristics, not performance; don't assume class is direct performance measure.

Prepared audit_regional_contrasts.py --run <run>, syntaxchecked, execute ONLY after
kinematics stagecomplete. It extracts paired-supported old/new class ratios, symmetric
proximityto1, time-specific flight/cluster/missingkeycounts for narrative review;
noformaltest, no canonical product changes. Outputregional-contrasts-audit.json.

Located existing Beamer decks underpresentations/: chapter2.tex/chapter3.tex,
build.py,prepare_assets.py,render_figures.py,theme.tex,assets/,data/. ExistingREADME
says18main slides/20minutes EACH (older user remembers1hour). Whole-chapter rewrite
must remove timedtalkconstraint and obsolete unlimitedverticalreconstructionclaims.
Buildcommand python3 presentations/build.py all --notes. prepare_assets usespypdf,
render_figures consumesfrozenJSON. Assets/source/figure/validationmanifests mustupdate.
Only inspected infrastructure; no deckproduction or structuralreview beforeallruns.

Fresh paired PSD audit completed while waiting for MSD: paired-psd-audit.json.
Both caches freshlywritten during activealtitude_noisestage,2008pairedspectra.
Per-flightmedianfloor0.35–0.50Hz percentiles10/50/90/99:
baro .17546/.26131/.50785/4.38763; GNSS .17233/.22415/.58973/13.79694.
Confirms similarcentralfloors butGNSSuppertaillarger, not identicaldistributions.
Source reads rawpairedlongestvalidcontinuousblocks, linearuniformresampling,
Welchlineardetrending; no pipelinecleaningorSavitzkyGolay. Selection andlinear
interpolationstillconditiondiagnostic. Tolduserthis incommentary andwillincludeCh2
slides; don'tclaim demonstratedreasonforhistoricalspreadchangewithoutoldmethodcomparison.
PSD additional direct paired-array check:1397para/611hangpairedflights. Only80para/
15hanghaveexactlyequalspectra;95/27near-equal1e-8. PairedGNSS/barofloorratiop10/p50/p90
para .480/.970/2.376, hang .307/1.000/2.509. Similaraggregatebands are not duplicated
channelarrays. EqualPSDs alone do not establish copiedchannels; do not infer device
mechanism without rawchannelcomparison. These figures are inpaired-psd-audit.json.

Latestmonitor: MSD stage17 finishedparagliders156406flights/194048TAMSDsegments,
hangpartstillrunning. TAMSDsegment countdiffersfrom194208cleanedsegments because
measure_msd.py skips segmentswithfewerthan8fixes (existingestimatorfloor); thisis
also distinctfrom10sfullreporteligibility190762segments. Keeppopulationcounts tiedto
observable, don'tpresentallthreeasthesamecohort. No manuscripteditduringrun.
Activeauxtrimstillscanning4workers~57minutes; notfailed, allworkersCPUactive.

SUPPLEMENTARY TRIMMING CENSUS COMPLETED successfully (session14021exit0).
Recomputedallrawfiles,185131para/6580hangadmittedtrimmingrows; upstreamgatesexplain
rowcountbelowrawfilecount (see trim_split_one), not a flight-count cap.
trimming-refresh.json confirms source+canonicaldatasetidentities unchanged,
AND allthreegeneratedoutputs EXACTLYsameSHA256ascachedmainstage15. No numerical
or manuscriptreconciliationchange neededfortrimoutputs. Tolduserfreshrescanvalidates
cacheforthisversion. Noauxrunremains; onlymain39stageruncontinues.

CURRENT MAIN STAGE24 transport_full,23/39completed. Collectorconfirmed155085eligible
paragliders;8workermeasurementalready100000/155085 at~4.8minstageelapsed. Stage20–23
completed. regional-contrasts-audit.json nowexecutedPASS; freshregionalPDFsvisually
reviewed andhashrecordedin fresh-figure-review.json (4freshfiguresMSD,duration,
regionalmountaincoast,low-reliefboxes).

CRITICAL FRESH FINDING sharedwithuser: universalExperts-closer-to1 NOTsupported.
Alps closerall58plottedtimesbothposition/velocity; ChannelCoastmostlycloserlateclear;
Pyreneesorderingreverses, positionsboth~5 at9086s andvelocityCDCCC1.254vsAB1.087.
Fullnumbers/supportanddescriptive(noformaltest)counts inregional-interpretation-review.md.
LatecoastAB188flights/163clusters vsCDCCC1733/1007. Userhypothesis+thiscounterexample
MUSTgo BOTH thesisandslides. Poitou-Charente curvescrosswithbroadbands; Champagne-
LorraineCDCCCalsoabove1late. BoxclassificationnotDEM-verifiedplain,clusterbootstrap
notconfoundingadjustment. No thesis/decksourceeditsyet; waitALLrunperuser.

Bothtrimmingcaches themselvesalsoEXACTLYsameSHA256afterforcedrescan, notjustPDF/TeX.
Auxruntime4232.3s;complete. MainMSD17completeall156406para6094hang; stage18/19fresh
values/roundingissues andplotsreview inmanuscript-review-pending.md.

Transportfullstagebaseline measurementcompletedall155085para and reducedall31lags;
firstlag171472703admissibleincrements, lastlag84997(nonoverlappingstrideτbaseline).
This differsfromfixedcommon10s-origincontrol21.7Mbydesign. At~12minstageelapsed,
subsequentpopulationcontrolsarecomputing;SSD16.2GiBfree, noerrors. Lastreporter
stdoutlineinstaticsource still says'Wrote Chapter3 subset figures...' historically;
actualcontract/samplingflag/flightcounts establishFULLmode. Do notmisreadthisoldlog
wordingasasmall-sampleexecutionorchangeguardedsourceforthiscosmeticstringmidrun.

Read-only runtimeprofile savedtransport-runtime-sample.txt via/usr/bin/sample PID44301,
1second/10ms,02:03local. Mainthread inmath.fsum overNumPyscalars (accurateweightedCDF
mass sums), notblockedI/O. Mainprocessphysicalfootprint2.1G, peakSOFAR3.6G; excludes
workersandnotfinalpeak. Memory_pressure-Q48%free;systemswap~5GBalreadyallocated,
don'tclaimno swap. First`sample` resolvedbrokenPython3.14stub(ModuleNotFoundError),
noimpactonrun;correct/usr/bin/sample succeeded. Populationcontrollags10/20/30/40
completedby~15minstage. This serialreduction isremainingcost, notallstages100%CPU.
Do notchangeguardednumericcodejusttooptimizefsumorlogwordingduringthisrun.

NEW bounded auxiliary rawPSD comparison RUNNING session84797:
`caffeinate -i .venv/bin/python -u revisions/vertical-gap-split-2026-09-11/compare_psd_selection.py`
stdout psd-selection-comparison.log, state psd-selection-comparison.json.
Currentmainstage24stillactive; thisauxwritesONLYrevisionartifacts,4workersnice10,
nativethreads1;mustfinishbeforefinalthesis/slidesreview.

ReadgithistoryfoundexactPSDchangein8744a52: previous_collect_psd uniform-resampled
WHOLErawtrace includingzeros/invalidGNSS andgaps; currentuseslongestpairedvalid
uninterruptedblockafterzeros/Vflagmask. BothuseWelchandperfrequencyMEDIAN already;
notmean→medianchangeatthatcommit. Documentation-reviewbefore/afteronlycomments.
Userwasinformedweareisolatingthisselectionchangeonthesamesample, notS-Gfiltering.
Scriptcomputeslegacyselection/currentselectionfromsamecurrentdecoder/rawsample3000
perdiscipline,targetdt1 verifiedagainstcache; reproducescurrentcachedspectra with
allclose1e-12, recordsrawfileSHA256andguardedsourcehash. Compareslegacyallsupport,
legacyoncurrentmatchedflights,andcurrent, preservingchannelorderandexactWelch.
Notanexactrecreationofeveryhistoricalenvironmentchange; isolatesselectionbundle,
notseparateeffects ofzeros,validityflag,longgaps. No canonicalcache/outputchanges.

AuxPSDcomparison84797COMPLETEDexit0in99.46s. Noauxrunleftagain. Currentcachedspectra
reproducedbothdisciplines; legacy2365/current2008, same2008GNSSfloorp90 3.75848→
.589734, p99 16681→13.797. Userinformedthisexplainsreducedspreadviaintervalselection,
notS-G. Allnumbers/caveatsnowinmanuscript-review-pending.md andauditREADME. Include
inCh2thesisandslides; no canonicalresultsmodified. Mainstage24populationcontrolnear
lastlags; watchmainlog. No manuscriptsource/deckeditsuntilALLmainstagesend.

MAINstage24 has nowcompletedbothfullbaseline+populationcontrols andentered
Fixed-population scaling:paragliders. ActualcollectorconfirmsALLpreflightcohortcounts:
para155085eligible/14360fixed;hang6060eligible/563fixed. Userinformedthesearenow
actualrunconfirmed, notjustmetadataforecast. FullV1/V2slopespara1.70269148/2.00324567,
hang1.64896368/1.98533052 (differentestimatorfromearlierTAMSD/ensembleslopes).
Approx15GiBSSDfreeafterbothbaselinepools. Cachefullcollectionscomplete, butstage24
notcompleteuntilselfsimilarity/bootstrap/jointreportsfinish; don'trunfullreportaudit
prematurely. No currentauxruns. Scriptsourcehashstillguardeduntilmain39stagesend.

StoragecheckforremainingHMMstages: existingphase_points.parquet~12Gpara,whole
segmentationdir12G;hang551M. apply_discipline opensParquetWriter DIRECTLYonexisting
phase_points/runs/coveragepaths (notatemporaryduplicate), freeingoldallocationas
replacementstarts. Mainplanhasapply, notcalibrate(whichwouldusetemporaryfiles).
No extra12Gatomiccopyrequired; no manualdeletionsmade. Finalnewproductsstillneed
watchingandvalidation. Fittingcapsunchanged1000flights/1Mobservations/6000persequence,
10restarts8workers200maxiters; thisisCh4modeltraining, notfullCh3scope.
Fixedscalingprogressconfirmedlag10,20,30 each14360flights/21739115origins. Mainstage
~44minelapsed, bootstrappinganddensequantilesstillserialparts; allowrunfinish.


Concrete chapter split is now prepared outside guarded sources: chapter3-structure.patch,
chapter3-structure-draft.tex, chapter3-structure-check.json; all existing labels and
figure/equation/align blocks preserved; git apply --check passes. Do not apply yet.
New helper prepare_review_manifest.py (syntax/help checked, not executed) captures
additional already generated inputs after numerical completion and before editing,
especially the low-relief figure omitted from the old manuscript's required inputs.
Use its review-inputs manifest for reviewed compilation, preserving original run
manifest/PDF. See manuscript-review-pending.md. No manuscript or slide-source edits yet.


Recovered stage24 reporter PID56514 active, bootstrap progressed through50s at the
last console check (18m43s stage elapsed). All31lags still required; roughly3–4min
per lag on this Mac, followed by distribution distances/joint laws and hang gliders.
No source changes, no duplicate jobs. Console recovery-console.log; driver69460.
Validated-cache quantile point estimates extracted to preliminary-full-quantile-values.json
(no bootstrap CIs yet). Full main report must still reproduce these controls.
Regional full-baseline PCA/model/memory figures visually checked and hashed in
fresh-full-baseline-figure-review.json; coastal PCA support4890 at1070s and angle~30deg
must replace old dash/tiny-sample wording. All figure/text notes inmanuscript-review-pending.

Further prepared review material outside guarded sources:
chapter2-psd-review-fragment.tex; regional-discussion-fragment.tex;
regional-review-references.bib (DHV/DREAL rechecked via web); supervisor-decks-coverage.md.
None applied to canonical thesis/slides. All existing labels/figure/equation blocks
preserved in structural draft. Final new slides must cover whole chapters and use
speaker/discussion notes without time slots, and all new joint/low-relief evidence.

After manuscript editing, regenerate docs provenance via generate_provenance.py
again before strict docs build; it writes docs/guide/provenance.md only, not protected
numerical products. The newly included low-relief figure changes which artifacts are
cited. The original numerical manifest remains intact, with additional inputs in the
separate review-inputs manifest prepared immediately after numerical completion.
Do not recommend --saved-snapshot for the full cache: its historical path reads the
embedded measured dictionary, whereas full caches store directories. Current full
workflow uses --reuse, which correctly loads stores. No numerical code was changed
for this unrelated legacy-mode limitation during the guarded run.
