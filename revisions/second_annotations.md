# Annotation digest — `main_revision_second.pdf`

294 annotations, reading order. `source` is a SyncTeX anchor (±1 line: confirm by grepping the marked text).


## page 2  (pdf p. 2)

### [1] green Highlight
- **marked**: seeks a minimal stochastic transport model able to reproduce those statistics,
- **note**: OK

### [2] green Highlight
- **marked**: As the work develops it will also examine how flying in competition changes the motion relative to solo flights. This document reports the current state of the project. A first dataset has been acquired reproducibly—the archive of the FFVL in its paraglider and hang- Coupe Fédérale de Distance, glider disciplines—and the document describes its acquisition, the dataset and its statistics, and the pre-processing that turns the raw logs into analysis-ready trajectories, before setting out the planned transport analysis and modelling. Chapter 2 reports the dataset and its coverage in full; Chapter 3 the analysis ahead.
- **note**: OK

### [3] red StrikeOut
- **marked**: rather than only comparing the data against existing models.
- **note**: rather than only comparing the data against existing models.


## page 5  (pdf p. 5)

### [4] green Highlight
- **marked**: air currents in the atmosphere,
- **note**: Ok

### [5] green Highlight
- **marked**: one of the settings
- **note**: ok

### [6] orange Highlight
- **marked**: ↑ ↓ ↔ Continuous-time random walks and Lévy walks are the standard modelling frameworks for such regimes [1, 2],
- **note**: Reading what you’ve written it seems like CTRW and LW are totally different framework while it’s not. LW is a particular case of a CTRW when the pdf of jump length and waiting time is coupled. ψ(x,t)=1/2 * ​δ(∣x∣−vt)*w(t),

### [7] red Highlight
- **marked**: in animal movement [3],
- **note**: The cited reference doesn’t talk about animal movement!! Remove or change it. If you want to keep the application to animal movement is ok for me but you need to choose another paper. Otherwise, you can keep the present cited paper but you’ve to change the topic treated by it.

### [8] orange Highlight
- **marked**: These two frameworks sit at opposite ends of a spectrum: a plain continuous-time random walk carries no memory of direction between successive steps, whereas a Lévy walk is a continuous-time random coupled walk, in which each waiting time is tied to a ballistic displacement.
- **note**: It’s not fair saying that these two models sit at opposite ends! From “a plain” to “to a ballistic displacement” is formally true but it’s doesn’t help here. The whole part here talking about model framework and the fact that the best one here should probably be a sort of correlated/persistent random walk (not discrete but in continuous time) has to be rewritten. It must help the reader instead of confusing them as the actual description does.

### [9] red Highlight
- **marked**: cycle—directed glides interrupted by localized climbs—falls
- **note**: In fact, they are directed glides each interrupted by first a search phase and then a localized climb. So every cycle is made by three parts

### [10] orange Highlight
- **marked**: between them,
- **note**: Questa frase è in parte vera in parte falsa. È vero che il soaring cycle sembra essere un po’’ a metà tra un plain CTRW e un LW perchè ha dei tratti balistici a velocità costante (come il LW) e ha dei siti in cui si hanno delle attese (come il CTRW plain) e dove queste attese sarebbero le fasi si search e climb (che nello sviluppo di un modello minimale possono essere trattate come un’unica fase di waiting. Ora questa affermazione farla qui, ad inizio tesi, è un po’’ prematuro perché viene fuori da alcune analisi precedenti fatte da me e da vilpellet. Quindi accennerei solo la cosa e poi andrei a spiegare bene il perchè trattiamo queste due fasi come un’unica fae quando andrò a sviluppare il modello quantitativo.)

### [11] orange Highlight
- **marked**: so that both the leg statistics and the correlation between successive flight directions are retained.
- **note**: This sentence has a vague meaning. I don’t get it

### [12] yellow Highlight
- **marked**: Isolating such a minimal model is one aim of the analysis developed later.
- **note**: Qui il punto è piuttosto fare tutta una serie di test per capire le caratteristiche empiriche dei dati e da queste andare a couture un persistente random walk appropriato. Certo il punto è che sto dicendo persistent perchè credo che sia present una memoria angolare, ma questo si saprò solo dopo ver analizzato le traiettorie empiriche.

### [13] yellow Highlight
- **marked**: minimal
- **note**: minimal

### [14] green Highlight
- **marked**: ↗ →|r(t)| ↑ ↓ so that a value 1/2 1 marks superdi!usive transport). < H <
- **note**: ok

### [15] green Highlight
- **marked**: revisits the cleaning and filtering that precede any analysis,
- **note**: ok


## page 6  (pdf p. 6)

### [16] yellow Highlight
- **marked**: to test for anomalous transport and
- **note**: Testing for anomalous transport is something that will be done in point 2 right after analysis-ready trajectories are available. In fact, testing for anomalous transport is strictly linked to “to define (and analyze) suitable transport observables”. Point 4 is just for building a minimal stochastic model

### [17] red StrikeOut
- **marked**: rather than only comparing the data against existing models;
- **note**: , rather than only comparing the data against existing models;

### [18] yellow Highlight
- **marked**: here;
- **note**: Make the proper reference with the linked section in the thesis (like when you write (Sec. 2.1)

### [19] yellow Highlight
- **marked**: here;
- **note**: Make the proper reference with the linked section in the thesis (like when you write (Sec. 2.1)

### [20] green Highlight
- **marked**: This document reports the current state of the project and is revised as the work proceeds. Its statistics, tables, and figures are produced directly from the dataset by the analysis code, so the numbers quoted in the text cannot drift from the data they describe. Chapter 2 follows the data end to end: its acquisition and the reproducibility of the pipeline (Sec. 2.1); the tracklog format and the flight catalog (Secs. 2.2–2.3); the glider categories and the coverage statistics (Secs. 2.4–2.5); the known data-quality caveats (Sec. 2.6); the pre-processing that turns the raw logs into analysis-ready trajectories (Sec. 2.7); a first characterization of the cleaned dataset (Sec. 2.8); and a one-map summary of the whole pipeline that closes the chapter (Sec. 2.9).
- **note**: ok

### [21] green Highlight
- **marked**: is collected in Implementation and Computational Details, from p. 50.
- **note**: ok

### [22] yellow Highlight
- **marked**: from p. 50.
- **note**: from p. 50.


## page 7  (pdf p. 7)

### [23] green Highlight
- **marked**: them pilot, date, take-o! and landing sites, scored distance, duration, and glider, with the full set of fields listed in Sec.
- **note**: Ok

### [24] green Highlight
- **marked**: its columns detailed in Sec. 2.3)
- **note**: Ok

### [25] green Highlight
- **marked**: The catalog is itself rebuildable from the archived XMLs and likewise uncommitted (Sec. 2.3).
- **note**: ok


## page 8  (pdf p. 8)

### [26] green Highlight
- **marked**: These are the tracklogs actually fetched; they cover a subset of the flights that carry a track at all (Sec. 2.5).
- **note**: ok

### [27] red StrikeOut
- **marked**: (203,343 flights, 186,225 tracklogs)
- **note**: (203,343 flights, 186,225 tracklogs)

### [28] red StrikeOut
- **marked**: (9,259 flights, 6,746 tracklogs)
- **note**: (9,259 flights, 6,746 tracklogs)

### [29] green Highlight
- **marked**: A comparable research-access request has been sent to XContest; as of 20 July 2026 neither WeGlide nor XContest has replied. All of these can be acquired with the same approach, each producing a catalog in the same format.
- **note**: ok

### [30] green Highlight
- **marked**: Its layout is fixed by that standard, so a fix can be decoded from fixed character positions rather than parsed heuristically; every downloaded track is validated against the standard at acquisition (Sec. 2.1).
- **note**: ok

### [31] red StrikeOut
- **marked**: rather than parsed heuristically;
- **note**: rather than parsed heuristically;


## page 9  (pdf p. 9)

### [32] green Highlight
- **marked**: The validity flag takes two values and concerns the solution only. marks a fix GNSS A whose GNSS altitude is usable; marks a GNSS drop-out, or a fix for which the receiver could V not resolve altitude, in which case the standard requires the GNSS-altitude field to be written as zero. A flag therefore does not make the fix two-dimensional: the latitude and longitude V stay usable and—on a logger with a working pressure sensor—so does the barometric altitude, which is the channel this analysis adopts (Sec. 2.7.1). What a flag signals lost is the GNSS V altitude, not the horizontal position.
- **note**: Ok

### [33] yellow Highlight
- **marked**: and—on a logger with a working pressure sensor—so
- **note**: Meglio fare le virgole o i “- - ”?

### [34] green Highlight
- **marked**: The two altitude channels di!er in reference and in noise; the analysis adopts the barometric one for the vertical dynamics, for reasons quantified in Sec. 2.7.1—a choice that matters because the vertical velocity derived from it feeds the phase segmentation.
- **note**: Ok

### [35] green Highlight
- **marked**: Beyond the identifiers and links, the available fields are collected in Table 2.1. Table 2.1. Flight metadata preserved from the season XML (raw attribute names), beyond the identifiers and links.
- **note**: Ok


## page 10  (pdf p. 10)

### [36] red Highlight
- **marked**: Table 2.2. Performance-class ladders recorded in one system per discipline (low to high aile_class, performance).
- **note**: Task: fact-check a LaTeX table in <path/to/file.tex> listing paraglider and
  hang glider classes, and correct it. Precision matters more than completeness.
  
  SCOPE RULE (strict):
  - Do NOT add rows, columns, or explanatory content. The table stays as short as
    it is now.
  - Only change what is demonstrably wrong or unsupportable.
  - Every claim left in the table must be traceable to a primary source. If a
    claim cannot be verified against one, DELETE it rather than softening or
    rephrasing it. An empty Notes cell is acceptable; a plausible-sounding
    unverified note is not.
  
  PRIMARY SOURCES ONLY:
  - FAI Sporting Code, Common Section 7 (and subsections 7A / 7G), current
    edition, downloaded from fai.org. Check the edition date on the cover; CIVL
    amends the rules most years, so an older PDF is not authoritative.
  - The EN 926 standard text (or an official EN/LTF/DHV publication) for
    paraglider certification.
  - Do not use paragliding shops, blogs, forums, or Wikipedia as the basis for
    any correction. They may be used only to find a lead, never as the source.
  
  ITEMS TO CHECK (these are open questions, not established facts — verify each
  independently and report what the source actually says):
  1. Section heading "EN/AFNOR ladder": is the numeric scale 1 / 1-2 / 2 / 2-3
     an AFNOR classification, or does it belong to another body? Whatever the
     answer, the heading must name the scheme that actually produced those
     numbers.
  2. The parenthetical French forms ("A ou 1", "B ou 1-2", etc.): are these
     documented anywhere authoritative, or informal pilot slang? If the latter,
     they either go, or the table must not present them as classification labels.
  3. Whether any official EN-to-numeric equivalence exists at all. If the mapping
     is only approximate, the table must not assert it as an identity.
  4. Row "tandem / non-certified": are these one category or two distinct things?
     Check whether two-seater wings are certifiable under the current standard.
  5. Row "CCC — CIVL Competition Class racing wings": verify against the relevant
     Section 7 subsection.
  6. Row "EN A — most stable, recreational": verify the standard actually
     characterises A this way.
  7. Hang glider rows: check the exact FAI class definitions and confirm whether
     "flexible wing" / "rigid wing" is what distinguishes Class 1 from Class 2
     from Class 5, or whether the classes are defined on a different criterion.
     Note that Class 2 and Class 5 currently carry an identical note — determine
     whether that is defensible.
  8. "Delta Class Sport": verify whether it is a class in its own right or
     something else within the FAI scheme, and whether "flexible wing,
     intermediate" is accurate.
  9. Heading "Hang gliders — FAI/CIVL classes": check whether the FAI class
     scheme covers only hang gliders. If it does not, the heading is misleading
     and needs rewording (without adding rows).
  
  OUTPUT, in two steps:
  Step 1 — report only. For each of the 9 items: verdict (confirmed / refuted /
  unverifiable), the source URL, its edition date, and the exact section or
  clause number. Quote nothing longer than a short phrase; paraphrase. Flag
  explicitly anything you could not settle from a primary source.
  Step 2 — after I approve the report, edit the .tex file. Preserve the existing
  booktabs style, two-column layout, and row order. Show a diff.
  
  Do not edit anything before I approve Step 1.

### [37] green Highlight
- **marked**: so the catalog itself need not be versioned.
- **note**: Ok

### [38] green Highlight
- **marked**: hang gliders (delta ↓ wing, spanning flexible framed wings and rigid wings; faster, glide ratio 10–15), and ↓ sailplanes (rigid aircraft; fastest, glide ratio 25). They are, in e!ect, di!erent aircraft— ↭ di!ering several-fold in cruise speed, glide ratio and turn radius—which is why the reference study [7] analyses each separately rather than pooling them.
- **note**: ok

### [39] green Highlight
- **marked**: Because the FFVL competition is split by discipline (Sec. 2.1), the present dataset spans glider types: both
- **note**: ok

### [40] red Highlight
- **marked**: Paragliders follow the EN/AFNOR certification ladder, hang gliders the FAI/CIVL classes; in both cases the ladder tracks performance (higher classes fly faster and flatter),
- **note**: I’m not sure about the rightness of this certificate ladder. Compare the note in Table 2.2

### [41] red StrikeOut
- **marked**: playing the role that glider type plays across sources.
- **note**: , playing the role that glider type plays across sources.

### [42] green Highlight
- **marked**: normalisation here means merging the label variants of the same class onto one canonical value per discipline and, where possible, recovering a blank or placeholder entry from the wing model
- **note**: ok

### [43] red StrikeOut
- **marked**: name—since a small fraction of rows carry a blank or placeholder
- **note**: —since a small fraction of rows carry a blank or placeholder


## page 11  (pdf p. 11)

### [44] red StrikeOut
- **marked**: class.
- **note**: class.

### [45] red StrikeOut
- **marked**: Three distinct counts recur throughout the document and should not be conflated: flights (every catalog entry, with or without a track), flights and tracklogs declared carrying a tracklog, All are generated from the season index by the reporting scripts, so downloaded and verified. each occurrence in the text quotes the same underlying number.
- **note**: Three distinct counts recur throughout the document and should not be conflated: flights declared (every catalog entry, with or without a track), flights carrying a tracklog, and tracklogs downloaded and verified. All are generated from the season index by the reporting scripts, so each occurrence in the text quotes the same underlying number.


## page 12  (pdf p. 12)

### [46] green Highlight
- **marked**: These are the flights outside the “With GPS” column of Tables 2.3 and 2.4.
- **note**: Ok

### [47] green Highlight
- **marked**: whose download fails or returns something that is not valid IGC content
- **note**: ok


## page 13  (pdf p. 13)

### [48] green Highlight
- **marked**: availability of the two altitude channels, and per-fix positioning noise
- **note**: ok

### [49] green Highlight
- **marked**: Altitude channel. A sizeable minority of loggers record no pressure altitude – almost a third of paraglider and roughly a sixth of hang-glider flights – which fall back to the GNSS altitude, with the channel actually used recorded per flight (Sec. 2.7.1).
- **note**: ok

### [50] orange Highlight
- **marked**: Incomplete dates. Some historical entries have placeholder dates, written as the sentinel value at acquisition. Such flights are kept—the trajectory is una!ected— 0000-00-00 and the sentinel makes them recognizable, so any date-based analysis (e.g. a per-season stratification) can exclude them explicitly.
- **note**: Check how many flights suffer this issue. If they are a negligible number, report how many and write that they will be deleted/ignored. Never considered In any further step.
  Warning: a good check would also pay attention at what are the seasons more affected. For example, it could be that all the problematic flights are the ones that refer to the older season. In this case, one should check how many flights of a given season remain after removing the issued one having placeholder date.

### [51] green Highlight
- **marked**: i i i i – with both altitude channels retained (implementation details: Sec. 2.6).
- **note**: ok

### [52] yellow Highlight
- **marked**: are scalar distances, which the great-circle (haversine) formula gives directly from latitude and longitude,
- **note**: Ok but cite the formula in the document (Eq 2.1)

### [53] green Highlight
- **marked**: with the origin at the first fix that survives the trimming, so the tangent-plane frame is built from good data(Sec. 2.7.5).
- **note**: ok

### [54] green Highlight
- **marked**: (vi)–(vii) come last for a di!erent reason: unlike the scalar checks above, they produce quantities—the components of the 3D vector position, velocity and acceleration—which require Cartesian axes to be expressed in, and therefore cannot run before the frame of step (v) exists.
- **note**: okw

### [55] yellow Highlight
- **marked**: Steps
- **note**: New line

### [56] green Highlight
- **marked**: The analysis adopts the altitude rather than the GNSS altitude for the vertical barometric dynamics.
- **note**: ok

### [57] yellow Highlight
- **marked**: The barometric (pressure) altitude resolves altitude changes at the metre level (the IGC format in any case rounds both channels to whole metres)
- **note**: It’s useless saying that the baro is able to resolve altitude change at the metre level. Just keeping th fact that the iGC format rounds altitude channels to integer numbers so the force resolution is 1 meter (Check what I’ve written here in the present note but I’m quite sure of what I’ve written.)

### [58] green Highlight
- **marked**: and carries very little high-frequency noise.
- **note**: ok

### [59] green Highlight
- **marked**: Its errors are slow:
- **note**: ok


## page 14  (pdf p. 14)

### [60] green Highlight
- **marked**: (visible in Fig. 2.1a as the gap between the two channels; most of that gap is the barometric o!set, though the GNSS altitude contributes a smaller bias of its own),
- **note**: ok

### [61] green Highlight
- **marked**: that already reaches tens of metres within the half-hour window of Fig. 2.1b, and can grow further over a multi-hour flight,
- **note**: ok

### [62] orange Highlight
- **marked**: following the synoptic pressure and the atmosphere’s departure from the ICAO profile.
- **note**: It’s not clear if these are the causes behind the presence of a (costant?) drift in the baro sensor. Are they the very real reasons which caused the baro to drift? Are there any other reasons?

### [63] red Highlight
- **marked**: autocorrelation).
- **note**: Does autocorrelation involve differencing?

### [64] yellow Highlight
- **marked**: referenced to a fixed geometric surface (the WGS84 ellipsoid), so it carries no atmospheric o!set, but it is vertically noisier: the satellite geometry resolves the vertical coordinate less well than the horizontal one (the vertical dilution of precision),
- **note**: Ok. Just give a very short why the horizontal position is resolved better than the vertical one. Add the why in a footnote

### [65] red Highlight
- **marked**: typically by a factor 1.5–2,
- **note**: It would be nice to keep this factor linked to the vertical dilution of positions BUT we absolutely need a reference to cite. If not, we’re forced to remove this 1,5-2 factor in the text.
  Please be careful checking the rightness of the cited paper/reference: it should explicitly contain the cited numbers.

### [66] red Highlight
- **marked**: and reaching the antenna only after reflecting o! terrain or multipath—signals the pilot’s own equipment—adds high-frequency jitter of a few metres.
- **note**: Task: correct one sentence in <path/to/thesis.tex>. Locate it with
  grep -n "multipath" .
  
  Current text:
  "and multipath—signals reaching the antenna only after reflecting off terrain
  or the pilot's own equipment—adds high-frequency jitter of a few metres"
  
  Two elements are suspect. Verify each independently against the literature
  before editing; do not assume the framing below is correct.
  
  1. The parenthetical definition. Check whether "signals reaching the antenna
     ONLY after reflecting" is how the standard references define multipath, or
     whether it describes specifically the non-line-of-sight (NLOS) case.
     Establish whether multipath is normally defined as the superposition of the
     direct signal with delayed replicas at the correlator, and whether the
     multipath/NLOS distinction is treated as material in the literature.
  
  2. The claim that multipath "adds high-frequency jitter of a few metres".
     Determine the temporal character of code-phase multipath error: white and
     uncorrelated between epochs, or correlated and slowly varying? Find what
     sets its time scale — check the notion of fringe frequency, i.e. the rate of
     change of excess path length divided by the carrier wavelength — and what
     values it takes for a receiver moving at ~10 m/s near terrain and sampled at
     1 Hz, including whether aliasing can make a fast-varying multipath error
     appear white. Then establish what actually dominates epoch-to-epoch position
     scatter in open-sky conditions (candidate: receiver tracking/thermal noise
     scaled by DOP), and whether "a few metres" is the correct order of magnitude
     for code multipath specifically.
  
  SOURCES: standard GNSS references only — Misra & Enge; Kaplan & Hegarty;
  Groves; Braasch's multipath chapter in the Springer Handbook of GNSS; or
  peer-reviewed papers. Not blogs, forums, vendor pages, or Wikipedia. Give
  author, work, and section or page number for every claim that survives into the
  replacement sentence.
  
  CONSTRAINTS ON THE FIX:
  - One sentence, two at most. This is a passing remark inside an error-budget
    paragraph, not a subsection on GNSS error sources. No equations, no figures.
  - Do not repair it by making it vague. "May introduce some error" is not
    acceptable. Either state the mechanism and its time scale correctly, or drop
    the jitter claim and keep only what is defensible.
  - Preserve the em-dash apposition and the surrounding sentence flow.
  - If a claim cannot be sourced, delete it rather than hedge it.
  
  ALSO CHECK (report only, do not edit): whether any other sentence in the same
  paragraph or in the data pre-processing section attributes the observed
  positional scatter to multipath, and whether the noise model used downstream —
  in particular any white-noise offset subtracted from the MSD at short lags — is
  consistent with the corrected description.
  
  OUTPUT: Step 1, a report: for each item, verdict, source, and proposed wording.
  Step 2, after my approval only, apply the edit and show a diff.

### [67] green Highlight
- **marked**: The data confirm this picture, with one qualification.
- **note**: ok

### [68] orange Highlight
- **marked**: over a subsample sized for a robust spectral estimate
- **note**: In sezione 2.6.1 di implemntation details è riportato per bene come è stata scelta ala grandezza del sub-sample. Cita la sezione dopo che dicii “”over a subsample sized” e devi dire nel testo pricniaplae oppure/anche nella caption che sono stati usati 3000 voli per ciascuna categoria.

### [69] yellow Highlight
- **marked**: spectral
- **note**: spectral

### [70] red StrikeOut
- **marked**: though not uniformly.
- **note**: , though not uniformly.

### [71] green Highlight
- **marked**: the same flat high-frequency plateau—the level at which the spectra in panel c flatten towards the Nyquist frequency—set by the metre resolution to which the IGC format rounds channels, both
- **note**: ok

### [72] green Highlight
- **marked**: (di!erencing scales a spectral component of frequency by 2 sin(ϖf !t)/!t, an f amplification that grows with : it acts as a high-pass filter), f
- **note**: ok

### [73] green Highlight
- **marked**: One channel per flight.
- **note**: ok

### [74] green Highlight
- **marked**: Source recorded. Which channel a flight uses is recorded as a per-flight attribute of the processed dataset, so the two source groups remain separable in every downstream analysis; the raw IGC files are never modified (implementation details: Sec. 2.6.1).
- **note**: ok

### [75] green Highlight
- **marked**: Missing fixes.
- **note**: ok

### [76] orange Highlight
- **marked**: only 4.4 % of barometric paraglider flights (2.1 % of hang gliders) miss any barometric value at all, with a median of 3 (10) missing fixes among 4 them—against 10 fixes in a typical track—plus a rare pathological tail. ↓
- **note**: Are we 100% sure of these numbers? Please carefully check them!

### [77] red StrikeOut
- **marked**: The census quantifies “few”:
- **note**: The census quantifies “few”:

### [78] green Highlight
- **marked**: Whether the ↓ dropped fixes are scattered or consecutive, the hole they leave is handled downstream like any other gap(Sec. 2.7.6).
- **note**: ok


## page 15  (pdf p. 15)

### [79] red StrikeOut
- **marked**: multi-hour flight can drift further—so only its constant part (annotated) is subtracted.
- **note**: —a multi-hour flight can drift further—so only its constant part (annotated) is subtracted.

### [80] orange Highlight
- **marked**: Presence alone is not enough:
- **note**: Presente of what? Please be more precise

### [81] red StrikeOut
- **marked**: not estimated from a sample:
- **note**: , not estimated from a sample

### [82] orange Highlight
- **marked**: The transport horizontal analysis, the primary result (MSD and its scaling),
- **note**: OK CI STA PERò QUI IL PUNTO non è tanto stare a dire che il risultato primario è il mad e il suo scaling quanto piuttosto l’analisi generale del volo in2d, orizzontale. In generale l’analisi di trasporto si concentra sul volo 2d. Poi certo anche la component everiticla eè importante ma lo diventa in fase di segmentazione. Non starei a direi che solo il mad è importante. È in generale il traosrot orizzontale ad essere il main topic

### [83] red Highlight
- **marked**: and their statistics checked for compatibility (Sec. 2.8).
- **note**: No, il check importante non è presente in sezione 2.8. poiché l’altezza influenza la segmentazione direi che un buon check è fare la segmentazione e poi confrontare le segmentazioni dei voli baro e quelli gnss. Intendo dire magari andare a vedere le percentuali di tempo passate in ciascuna fase sia per i voli gnss che per i voli baro e edere se le frazioni di tempo in ciascuna fase sono compatibili (media +- errore di gnss interseca media +- errore di baro). Che dici? È segnato? Pensaci bene? Non voglio complicare troppo le cose nel fare questo check ma voglio comunque un buon check, che sia solido e facile da capire. Pensa appunto al fatto di cosa va a influenza l’altezza. Direi che va ad nfleuzare la velcoità verticale che sarà undo degli attributi della segmentazione. Ma non direi che va ad ifneulnzare le osservabili generali che invece vengono calcolate prima della segmnteaizone ed è dove conta solo il traporto orizzontale.

### [84] green Highlight
- **marked**: the per-flight altitude-source record introduced above
- **note**: ok


## page 16  (pdf p. 16)

### [85] green Highlight
- **marked**: The cleaning runs on the raw geodetic coordinates (ω ), before the Cartesian conversion (Sec. 2.7), so distances between fixes cannot be , ε i i Euclidean;
- **note**: ok

### [86] red Highlight
- **marked**: (Sec. 2.7),
- **note**: 2.7.5 is the right subsection to cite

### [87] orange Highlight
- **marked**: great-circle (haversine) distances
- **note**: Devi citare “https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.haversine_distances.html”. Qui è presente la formula 2.1

### [88] green Highlight
- **marked**: i+1 i ↘ The same distance also z,i i+1 i i+1 ↘ ↘ yields two whole-flight quantities used below: the = !s , the total distance path length L i i " flown along the track, and the = max !s(fix fix ), the farthest any fix lies from extent D , 0 i i the first. The spherical approximation is ample here. Replacing the WGS84 ellipsoid by a sphere perturbs an inter-fix distance by at most a fraction of the order of the ellipsoid’s flattening, 0.3 %—about 3 cm on a 10 m step—whereas the horizontal position error of ↫ consumer GNSS receivers is of the order of metres; the correction is therefore far below the noise on the very same quantity. Working on the raw coordinates also avoids converting them before the trajectory has been cleaned.
- **note**: ok

### [89] red Highlight
- **marked**: by at most a fraction of the order of the ellipsoid’s flattening, 0.3 ↫
- **note**: Non si capisce da dove viene questo 0.3%. Sembra una magia. Inserire in footnote o non in footnote da dove viene questo numero, quale formula è stata usata e perchè. Intendo a livello quantiativativo anche. Altrimenti non si capisce cosa vuole ire rimpiazzare il wgs84 con una sera e quindi da dove viene il 0.3%

### [90] orange Highlight
- **marked**: step—whereas the horizontal position error of consumer GNSS receivers is of the order of metres;
- **note**: Please carefully check if that’s true. Is the horizontal position error uncertainty really of the order of meters?  Please check

### [91] orange Highlight
- **marked**: within tens of metres of the true track
- **note**: Al più entro decine di metri ma tipicamente entro epsilon, che è fissato a 15 metri. Non citare qui il valore di epsilon ma questo è il punto. Così com’è ora sembra che spesso uno spurious fix dista decine di metri ma mi sembra che non è cproprio così. Sto forse sbagliando?

### [92] green Highlight
- **marked**: the absolute floor of the outlier ϱ min ↗ test defined below in Eq. (2.3)),
- **note**: ok

### [93] yellow Highlight
- **marked**: _(no text captured)_
- **note**: Fullstop not semicolons

### [94] orange Highlight
- **marked**: a corrupt channel
- **note**: Saying “corrupt channel” do you mean altitude channels? If so, please specify you’re referring to altitude. Otherwise, saying “a corrupt channel” could let the reader think about any channel, also the ones of the horizontal position. Ad it wouldn’t be true that a corrupt xy poison is restore at resampling. If I’m right, if a corrupt xy positions happens then its linked fix is discarded. Never resampled.

### [95] green Highlight
- **marked**: and is already implemented and unit-tested,
- **note**: ok

### [96] green Highlight
- **marked**: Let the window of fix be the set of k fixes within of , and let = med{ω : and = med{ε : t ω̃ t w} ε̃ t w} j j j j k k k k k ±w |t ↘ | ≃ |t ↘ | ≃ be the component-wise window medians. The residual of fix is its great-circle distance from k that median point, = !s (ω ), ( ) (2.2) r , ε ω̃ , ε̃ , k k k k k # $ 12
- **note**: ok


## page 17  (pdf p. 17)

### [97] yellow Highlight
- **marked**: 2.7. Trajectory pre-processing with !s as in Eq. (2.1), and the robust local scale of the residuals is MAD = med{r : j k t w}. j k |t ↘ | ≃
- **note**: Let the window of fix kbe the set of fixes within ±w of tk, and let˜ φk = med{φj : |tj−tk|≤w}and˜ λk = med{λj : |tj−tk|≤w} be the component-wise window medians. The residual of fix k is its great-circle distance from that median point, rk = ∆s (φk,λk),( ˜ φk, ˜ λk), (2.2) 12 2.7. Trajectory pre-processing with ∆s as in Eq. (2.1), and the robust local scale of the residuals is MADk = med{rj : |tj−tk|≤w}.

### [98] orange Highlight
- **marked**: robust
- **note**: Fai una footnote in cui spieghi brevemente perché è robustos

### [99] red Highlight
- **marked**: collected in Table 2.2;
- **note**: Valutare se ha senso riportare una tabella del genere anche nel corpo principale. Potrebbe essere comoda/utile/ giusta? Diciamo che non mi dispiacerebbe avere nel corpo centrale una tabella con tutti i parametri usati nel fix-level cleaning e nel flight-level cleaning con i loro valore e con la spiegazione. Potrebbe essere molto utile forse. Certo il punto sarebbe poi toglierla eventualmente dalla sezione “”implmenetation details” per evitare di avere duplicati

### [100] purple Highlight
- **marked**: A flag alone does not delete: the fix is removed only when this local flag is by an corroborated absolute bound that rules the step physically impossible. v xy
- **note**: Are we really sure we need this double check using also the velocity bound? Is it useful? Why don not simplifying using just the hamper identifier?

### [101] green Highlight
- **marked**: A genuine but under-sampled xy tight turn is therefore kept: it may be flagged by the local test, but it flies at an ordinary speed.
- **note**: ok

### [102] red Highlight
- **marked**: concerns the vertical channel: an impossible altitude or climb rate is caught by an absolute bound that needs no context. (The horizontal analogue, the bound, v xy never acts alone; it serves as the corroboration of the o!-the-trend test above, Table 2.5.)
- **note**: Non si capisce perché mai con la posizione orizzontale è stato usato un ampex identifier e poi un check sulla velocità e non viene fatto lo stesso qui con la z. Mi sembra che possa essere sensato anche qui applicare un hampel identifier e poi un check sulla velocità per corroborare. Dici di no? Direttamente velocità? E perchè? E allora perchè non si è fatto la stessa cosa su xy usando solo il check sulla velocità ed evitando di applicare l’hapel? Qui si deve fare un bel ragionamento. O si applica l’hamper anche per la z. O non si applica l’hamper neanche alla xy. Oppure si applica alla xy e non si applica alla z ma si spiega perchè alla z non si applica hamper. Mi racocamando, ragionamento sensato, solido, corretto. Non sparare a caso

### [103] yellow Highlight
- **marked**: xy never acts alone; it serves as the corroboration of the o!-the-trend test above, Table 2.5.) The thresholds are set in two ways. The absolute bounds are placed on data: the bounds v xy (45/55 m s , para/hang) and the bound (13 m s ) sit where the per-fix distributions of ↔1 ↔1 z |v | Fig. 2.2 stop decaying, and the altitude window ([↘100, 6000] m) is a sensor-plausibility band audited on the same distributions (lower bound negative for the reference-o!set reason in the caption of Table 2.5). The remaining parameters—those of the Hampel test (k, , w, ϱ min Eq. (2.3)) and of the frozen-lock rule (ϱ, , , defined with Eq. (2.4) below)—are working φ ↼ freeze z values fixed a priori; their reasonableness is then checked a
- **note**: Qui forse potrebbe far comodo usare una tabella con i vari parametri usati nel fix-level cleaning. Invece del testo intendo. Magari scrivendo la caption della tabella. Non so, Vedi anche nota poco sopra che tratta la stessa questione

### [104] green Highlight
- **marked**: z their reasonableness is then checked a posteriori on the fraction of fixes each rule removes (paragraph below). Validating the cleaning
- **note**: Ok

### [105] green Highlight
- **marked**: (Status: the routine that walks a trajectory applying the three detectors is still to be built.)
- **note**: (Status: the routine that walks a trajectory applying the three detectors is still to be built.)

### [106] green Highlight
- **marked**: What happens to a defective fix depends on of its values is corrupt, and the asymmetry which follows from a single criterion: keep every genuine horizontal sample, and never hide a hole in the horizontal record. In both cases the corrupt value itself is simply discarded—nothing is estimated in its place at this stage; whatever needs reconstructing is reconstructed once, at the resampling step (Sec. 2.7.6). If the corrupt value is the the fix is kept and only its altitude is marked missing. altitude, The horizontal position and the timestamp are intact, so the fix still samples the path—exactly the information the transport analysis measures—and discarding it would throw that genuine sample away. The missing altitude is restored by interpolation at resampling; the barometric channel is smooth enough that this costs less than the sensor noise (Sec. 2.7.1). If the corrupt value is the the whole fix is deleted. One could horizontal position or the time, imagine the symmetric treatment—keep the fix and mark the horizontal position missing—but that would be dangerous: the resampling step decides whether to bridge a hole or to split the flight by looking at the between surviving fixes. Ten consecutive kept-but-positionless time gap fixes would look like ten samples of a continuously recorded stretch; the gap rule would never fire, and the resampler would lay an invented straight line across an interval that may hold a full thermalling circle. Deleting the fixes leaves the hole visible, and the gap rule then does its
- **note**: ok

### [107] yellow Highlight
- **marked**: and the asymmetry
- **note**: Non si capisce asimmetria tra cosa. Maggiore chiarezza

### [108] yellow Highlight
- **marked**: In both cases
- **note**: It’s not clear what are these “both cases”.

### [109] yellow Highlight
- **marked**: its altitude is marked missing.
- **note**: Ok ma come? In che senso? Nella pratica cosa succede a quel fix? Come viene segnata l’assenza di vertical position?


## page 18  (pdf p. 18)

### [110] green Highlight
- **marked**: job: a short hole is bridged, a long one splits the flight (Sec. 2.7.6). The altitude sample lost with the deleted fix is the cheap part, for the same smoothness reason as above. The IGC validity flag needs no rule of its own here: a flag certifies a degraded GNSS V altitude (Sec. 2.2), so on a barometric flight the fix is untouched, and on a GNSS-fallback flight it reduces to the corrupt-altitude case above.
- **note**: ok

### [111] red StrikeOut
- **marked**: through which the anomalous exponent is determined (Ch. 3, Appendix 2.B).
- **note**: , through which the anomalous exponent is determined (Ch. 3, Appendix 2.B).

### [112] red StrikeOut
- **marked**: not step.
- **note**: , not step.

### [113] yellow Highlight
- **marked**: a tolerance of this rule set a few times above the GPS ϱ, noise (distinct from the Hampel floor , though currently set equal; working values ϱ min in Sec. 2.6.2).
- **note**: È il caso di indicare il diametro con un simbolo diverso da epsilon, per evitare di confonderlo con hampel

### [114] green Highlight
- **marked**: (the structure of Eq. (2.4) makes this explicit: on a barometric flight the witness is a flat barometer a byte-identical repeat, so nothing else can cut a run whose barometer or climbs).
- **note**: ok


## page 19  (pdf p. 19)

### [115] yellow Highlight
- **marked**: no declaration
- **note**: Non si cpiasce chi è questa declearation

### [116] red StrikeOut
- **marked**: and only the wind drift the receiver never recorded is lost.
- **note**: , and only the wind drift the receiver never recorded is lost.

### [117] green Highlight
- **marked**: ordinary values for tight thermalling)
- **note**: ordinary values for tight thermalling)

### [118] green Highlight
- **marked**: ↗ Against the working value of ϱ (15 m, Table 2.2), test (i) therefore misses by a factor of at least 2 for the tightest paraglider circles and 3 for hang gliders, more for anything wider—ratios to be rescaled if ↭
- **note**: Against the working value of ε (15 m, Table 2.2), test (i) therefore misses by a factor of at least 2 for the tightest paraglider circles and ≳ 3 for hang gliders, more for anything wider—ratios to be rescaled if

### [119] yellow Highlight
- **marked**: (2R 50 m). ↭
- **note**: Non si capisce che valore di velcoità è stato usato per ottenere 50m

### [120] yellow Highlight
- **marked**: ϱ
- **note**: Come prima da cambiare notazione per il diametro

### [121] yellow Highlight
- **marked**: (working value in Sec. 2.6.2).
- **note**: È bene avere tutti i working values dichiarati in una tabella nella main section. E non solo nella sezione sugli implementation details

### [122] green Highlight
- **marked**: the flatness tolerance , which is set well below that scale φ z
- **note**: the flatness tolerance δz, which is set well below that scale

### [123] green Highlight
- **marked**: The duration threshold itself is set on the motion’s timescale:
- **note**: Thedurationthresholditselfissetonthemotion’stimescale

### [124] red Highlight
- **marked**: ↼ freeze
- **note**: DAMNDA: E COSA SUCCEDE SE PASSO I PRIMI DUE TEST MA DELTA_T_RUN è inferiore a tau_freeze?? Non c’è il rischio di avere dei froozen-run con questo problema, ovvero freon-sul effettivi e reali ma corti? In questo caso tocca che me li tenga per evitare che vegnonano togliti dei genuine run?

### [125] yellow Highlight
- **marked**: Cutting a genuine climb on a barometric flight therefore requires two failures at once: the geometric margin of test (i) and the barometric witness of test (ii).
- **note**: Aggiungi un commento dunque sull’affidbailità di questo cut nel senso di bassissima “probabilità” che venga tagliato un genuine run.

### [126] yellow Highlight
- **marked**: no moving receiver writes.
- **note**: È il caos di dire “real moving receiver? Sto interpretando bene?

### [127] green Highlight
- **marked**: The rule assumes a functioning barometric channel, and weakens where that channel is absent. This is not in tension with adopting the GNSS altitude for the of fallback flights (Sec. 2.7.1): there, GNSS is used because it is the only altitude dynamics available; here, the question is di!erent—whether an instrument can a suspected GNSS witness lock loss—and the GNSS altitude cannot, because it comes from the very receiver whose lock is in doubt and freezes together with the position it would be checking. On GNSS-fallback flights the witness slot of Eq. (2.4) is therefore filled by the recorder’s declarations alone (the V flag or zeroed GNSS altitude, or a byte-identical repeat); the diameter and duration conditions still apply unchanged, so “alone” refers only to the witness, not to the whole rule. The residual error cases are then:
- **note**: The rule assumes a functioning barometric channel, and weakens where that channel is absent. This is not in tension with adopting the GNSS altitude for the dynamics of fallback flights (Sec. 2.7.1): there, GNSS is used because it is the only altitude available; here, the question is different—whether an instrument can witness a suspected GNSS lock loss—and the GNSS altitude cannot, because it comes from the very receiver whose lock is in doubt and freezes together with the position it would be checking. On GNSS-fallback flights the witness slot of Eq. (2.4) is therefore filled by the recorder’s declarations alone (the V flag or zeroed GNSS altitude, or a byte-identical repeat); the diameter and duration conditions still apply unchanged, so “alone” refers only to the witness, not to the whole rule. The residual error cases are then:

### [128] green Highlight
- **marked**: cases are then: • (GNSS-fallback only): a circling climb tight enough to stay within whose Wrongly cut ϱ fixes carry a flag—with no barometer to defend it, the declarations cut it. V
- **note**: or cases are then: • Wrongly cut (GNSS-fallback only): a circling climb tight enough to stay within ε whose fixes carry a V flag—with no barometer to defend it, the declarations cut it.

### [129] green Highlight
- **marked**: • (GNSS-fallback only): an undeclared freeze. Some receivers, Wrongly kept jittering having lost the lock, do not repeat the last position byte-for-byte but re-estimate it each
- **note**: • Wrongly kept (GNSS-fallback only): an undeclared jittering freeze. Some receivers, having lost the lock, do not repeat the last position byte-for-byte but re-estimate it each

### [130] green Highlight
- **marked**: 1 The coordinated-turn relation: in a steady banked turn the lift balances gravity vertically, cos = L L ω mg, 2 while its horizontal component provides the centripetal force, sin = dividing the two gives L ω mv /R; 2 2 tan = i.e. = tan ω v /(gR), R v /(g ω).
- **note**: 1The coordinated-turn relation: in a steady banked turn the lift L balances gravity vertically, Lcos ϕ= mg, while its horizontal component provides the centripetal force, Lsin ϕ= mv2/R; dividing the two gives tan ϕ= v2/(gR), i.e. R= v2/(gtan ϕ).


## page 20  (pdf p. 20)

### [131] green Highlight
- **marked**: second, so consecutive positions di!er by a metre or two of receiver noise: the run is genuinely frozen, yet neither byte-identical nor declared, and it is kept.
- **note**: second, so consecutive positions differ by a metre or two of receiver noise: the run is genuinely frozen, yet neither byte-identical nor declared, and it is kept.

### [132] green Highlight
- **marked**: (barometric flights): a jittered freeze under a barometer Kept, at bounded cost climbing is kept by construction.
- **note**: Kept, at bounded cost (barometric flights): a jittered freeze under a climbing barometer is kept by construction.

### [133] red Highlight
- **marked**: The cost is bounded because the recorded positions all sit within the of the last true position: what the trajectory loses is only the wind drift the ϱ-ball receiver never recorded during the run.
- **note**: Non capisco perchè viene detto che il costo è limitato. E che perdo solo il wind drift. A me sembra che perda un possibile vero spostamento. Ovvero con un jitter e un baro che cambia potrei avere un vero spostamento che sto perdendo e sto tenendo come un run dove in pratica lo spostamento è irrisorio. Se è come sembra a me va detto che c’è questa possibilità. Altrimenti spiega meglio

### [134] orange Highlight
- **marked**: The first two sets are expected to be small—they require a lock loss, a fallback flight and a borderline geometry at once—but how often each rule fires is measured, not assumed(paragraph below). Validating the cleaning
- **note**: Mmmh. A quality due sets ti riferisci?? Se stai parlando dei casi • Wrongly cut, Kept, at bounded cost , Wrongly kept  NON CREDO che sia possibile misurarne le occorrenze. Sono i casi in cui la regola fallisce e, per definizione, il run passa silenziosamente.

### [135] yellow Highlight
- **marked**: borderline geometry
- **note**: Spiga cosa intendi con borderline geometry, oppure non dire borderete geometry e spiga in altro modo, con altri termini

### [136] yellow Highlight
- **marked**: Table 2.5.
- **note**: La tabella va resa più leggibile usando barre verticali e orizzontali a separazione.
  
  Scrivi sensor value: ma intendi il valore di baro o gps lungo z?

### [137] red StrikeOut
- **marked**: (the aeronautical QNH setting),
- **note**: (the aeronautical QNH setting)


## page 21  (pdf p. 21)

### [138] green Highlight
- **marked**: absolute bounds test—bounds that serve both the out-of-range rule and, through the bound, the v xy corroboration of the o!-the-trend detector
- **note**: absolute bounds test—bounds that serve both the out-of-range rule and, through the vxy bound, the corroboration of the off-the-trend detector

### [139] red Highlight
- **marked**: In panel (a) the hang-glider curve shows the genuinely flat plateau at 55 m s to 90 m s — →1 →1 sustained speeds with no credible flight explanation — that places their bound.
- **note**: Para mostrano il plateau tra 45 e 55 m/s. Invece hang lo mostrano tra 55 e 70 m/s.

### [140] yellow Highlight
- **marked**: the validation of the robust detectors:
- **note**: Che intendi? Quali sono i robust detectors? E in che senso robust? E quali detector? E cosa c’entrano con questa figura?

### [141] green Highlight
- **marked**: delete a fix (a corrupt horizontal position) or mark a channel missing (a barometric spike, a fix on a GNSS-fallback flight) – because V the guarantee is established one step later, at resampling (Sec. 2.7.6). A is a maximal segment stretch of the flight between two splits—equivalently, between long
- **note**: delete a fix (a corrupt horizontal position) or mark a channel missing (a barometric spike, a V fix on a GNSS-fallback flight) – because the guarantee is established one step later, at resampling (Sec. 2.7.6). A segment is a maximal stretch of the flight between two splits—equivalently, between long gaps—

### [142] yellow Highlight
- **marked**: gaps—analysed as a unit
- **note**: Questo “analysed as a unit” non molto chiaro su cosa vuol dire.

### [143] yellow Highlight
- **marked**: The invariant is
- **note**: Che intendi con “The invariant”?

### [144] green Highlight
- **marked**: established by the single audited interpolation of Sec. 2.7.6.
- **note**: established by the single audited interpolation of Sec. 2.7.6.

### [145] green Highlight
- **marked**: the flight is dropped whole.
- **note**: the flight is dropped whole.

### [146] green Highlight
- **marked**: All the detector parameters are validated by one procedure, run once the cleaning routine is built (Ch. 3):
- **note**: All the detector parameters are validated by one procedure, run once the cleaning routine is built (Ch. 3):

### [147] green Highlight
- **marked**: The thresholds are fixed a priori at the values of Table 2.5 Freeze the working values. and Sec. 2.6.2; nothing is tuned on the transport observables themselves.
- **note**: Freeze the working values. The thresholds are fixed a priori at the values of Table 2.5 and Sec. 2.6.2; nothing is tuned on the transport observables themselves.

### [148] green Highlight
- **marked**: The cleaning is run over the full archive with per-rule Audit the removal fractions. counters (the same machinery as the integrity gate): for each rule and each discipline, the fraction of fixes flagged and the fraction removed. The expectation is that each rule touches only a small fraction of fixes; this is the criterion to be verified, not a fact assumed in advance.
- **note**: Audit the removal fractions. The cleaning is run over the full archive with per-rule counters (the same machinery as the integrity gate): for each rule and each discipline, the fraction of fixes flagged and the fraction removed. The expectation is that each rule touches only a small fraction of fixes; this is the criterion to be verified, not a fact assumed in advance.

### [149] red Highlight
- **marked**: Each parameter is varied around its working value and the removal fractions are recomputed. A well-placed threshold sits on a plateau: tightening it a little should not change what is removed by much. A rule whose removals grow rapidly under a small tightening is biting into real dynamics, and its working value is reconsidered.
- **note**: Qui la cosa delicata è capire cosa vuol dire piccolo e grande. Serve una strategia quantitativa solida e definita per dire che un parametro è nel plateau.

### [150] green Highlight
- **marked**: Sweep each threshold.
- **note**: Sweep each threshold.

### [151] green Highlight
- **marked**: The same sweep covers the split cap of Sec. 2.7.6, monitored on its split fractions rather than on removed fixes.
- **note**: The same sweep covers the split cap of Sec. 2.7.6, monitored on its split fractions rather than on removed fixes.

### [152] green Highlight
- **marked**: Steps (b)–(c) measure what the cleaning removes, not what it False negatives, if needed. misses—the corrupted fixes that pass undetected. If the audit leaves a specific rule in
- **note**: False negatives, if needed. Steps (b)–(c) measure what the cleaning removes, not what it misses—the corrupted fixes that pass undetected. If the audit leaves a specific rule in


## page 22  (pdf p. 22)

### [153] red Highlight
- **marked**: doubt,
- **note**: Cosa vuol dire che la regola è in dubbio? Nella pratica come una regola si può dire in dubbio?

### [154] green Highlight
- **marked**: defects of known size (spikes, frozen runs, time glitches) are injected into clean tracks and the fraction recovered as a function of size measures the false-negative rate directly.
- **note**: defects of known size (spikes, frozen runs, time glitches) are injected into clean tracks and the fraction recovered as a function of size measures the false-negative rate directly.

### [155] orange Highlight
- **marked**: This is the expensive check, kept as a targeted follow-up rather than run by default.
- **note**: Forse potrebbe essere utilissimo. Si sa quanti defects vengono injected. A quel punto si fa una bella tabella per vedere l’efficacia di ogni rule contro ogni tipo di defect. Molto interessante. Direi di adottare questa procedura. Mi sembra un metodo molto solido. In questo modo si potrebbe costruire una tabella con il numero di falsi positivi, negativi e vero positivo vero negativo

### [156] green Highlight
- **marked**: (implementation details: Sec. 2.6.2)
- **note**: (implementation details: Sec. 2.6.2)

### [157] green Highlight
- **marked**: Outer ground phases (take-o! and landing).
- **note**: Outer ground phases (take-off and landing).

### [158] orange Highlight
- **marked**: = 30 s, T 0
- **note**: Come è stata scelta questa soglia? È sensata?

### [159] green Highlight
- **marked**: Take-o! is thus the time the speed stays above continuously for , and landing the first last v T 0 0 time it has done so: the same sustained-speed rule read forward and time-reversed. Reading the landing rule backward from the end matters. A rule of the form “cut at the first sustained drop below ” would fire in the middle of the flight, because a wing soaring into wind can v 0 hold a ground speed near zero for minutes while genuinely flying. The persistence prevents T 0 a gust or a GPS glitch on the ground from being mistaken for take-o!. A flight with no sustained stretch at all has no airborne segment and is discarded, with the reason recorded. One caveat is structural. The criterion is a speed, so a slow phase that happens ground to sit right at the start or end of the flight—a launch straight into ridge lift, say—can be clipped along with the ground phase.
- **note**: Take-off is thus the first time the speed stays above v0 continuously for T0, and landing the last time it has done so: the same sustained-speed rule read forward and time-reversed. Reading the landing rule backward from the end matters. A rule of the form “cut at the first sustained drop below v0” would fire in the middle of the flight, because a wing soaring into wind can hold a ground speed near zero for minutes while genuinely flying. The persistence T0 prevents a gust or a GPS glitch on the ground from being mistaken for take-off. A flight with no sustained stretch at all has no airborne segment and is discarded, with the reason recorded. One caveat is structural. The criterion is a ground speed, so a slow phase that happens to sit right at the start or end of the flight—a launch straight into ridge lift, say—can be clipped along with the ground phase.

### [160] red StrikeOut
- **marked**: for minutes
- **note**: for minutes

### [161] orange Highlight
- **marked**: To keep this failure mode auditable, the fraction of each flight that trimming removes is recorded per flight, and its distribution over the archive will be reported as a histogram once the pipeline runs in full; both and a!ect that fraction, v T 0 0 so they are made explicit (implementation details: Sec. 2.6.3).
- **note**: Mi piace ed apprezzo l’idea di fare un istogramma della frazione trimmed però non credo che facendolo sia possibile avere il failure come auditable. Intendo il failure di tritare una parte di moto iniziale

### [162] green Highlight
- **marked**: Interior ground stints (mid-flight landings).
- **note**: Interior ground stints (mid-flight landings).

### [163] green Highlight
- **marked**: above
- **note**: above

### [164] green Highlight
- **marked**: a false long wait in the tail of ) (Sec. 2.7.2). ↽(↼
- **note**: a false long wait in the tail of ψ(τ) (Sec. 2.7.2)

### [165] green Highlight
- **marked**: – the soaring-into-wind failure mode above.
- **note**: – the soaring-into-wind failure mode above.

### [166] yellow Highlight
- **marked**: A stint is cut only when both conditions hold: continuously for at least (order ten minutes, far beyond any search), the and v < v T 0 ground xy barometric altitude flat over the whole stint, within a few metres – a wing at zero ground speed in real air still moves vertically, the same independent-sensor argument as Eq. (2.4). On a GNSS-fallback flight the vertical witness uses the noisier GNSS channel with a wider tolerance, and in doubt the stint is kept.
- **note**: Usa un elenco puntato con i due criteri. Aiuta la comprensione

### [167] orange Highlight
- **marked**: within a few metres
- **note**: Sono sufficienti “”few meters”? Non è che cambiano le condizioni atmosferiche e il baro esce da questi “”few meters” nonostante il pilota sia effettivamente fermo durante un mid-flight landing? Di quanti “”few meters” si tratta? Questo parametro come si chiama? Con quale simbolo si indica? Quanto vale? s

### [168] green Highlight
- **marked**: A stint that is cut is excised, and the flight is split at the excision: the parts before and after are treated from then on as separate segments of the same parent flight, exactly as at a long gap (Sec. 2.7.6). The segment rules apply unchanged—a phase interrupted by the cut is censored rather than counted as complete,
- **note**: A stint that is cut is excised, and the flight is split at the excision: the parts before and after are treated from then on as separate segments of the same parent flight, exactly as at a long gap (Sec. 2.7.6). The segment rules apply unchanged—a phase interrupted by the cut is censored rather than counted as complete,

### [169] red Highlight
- **marked**: and the flight-level cuts of Sec. 2.7.4 are not re-applied to the individual segments.
- **note**: Quindi I flight level cut vegno/devono essere applicati prima del trimming? Perchè qui nel documento hai riportato prima il trimming. E questo confonde qualora il trimming venga applicato dopo ai flight level checks. Anche se chetamente è logico applicare i flight level check dopo il trimmering. Ama allora quanddo spesso un volo il flight check viene applicato come? Sulla somma dei segments? Devi specificare questo aspetto. Fai attenzione. Alla logica e alla chiarezza

### [170] yellow Highlight
- **marked**: – the same flag-without-deleting pattern as the outlier identifier.
- **note**: Quindi verranno riportati gli istogrammi per questi due casi?

### [171] green Highlight
- **marked**: and the flatness tolerance T ground are parameters of this guard; they will join the block of the configuration file when trimming the guard is implemented, with working values recorded in Sec. 2.6.3.
- **note**: Tground and the flatness tolerance are parameters of this guard; they will join the trimming block of the configuration file when the guard is implemented, with working values recorded in Sec. 2.6.3.


## page 23  (pdf p. 23)

### [172] green Highlight
- **marked**: minimal-threshold strategy:
- **note**: minimal-threshold strategy:

### [173] orange Highlight
- **marked**: persistence of the MSD.
- **note**: Cosa si intende qui con “persistence” of the MSD?

### [174] green Highlight
- **marked**: In practice “minimal” is read o! the data, not guessed: for each criterion the full-archive distribution of its quantity is drawn (Fig. 2.3, top row), together with the fraction of flights that the cut alone would retain as the threshold is moved (bottom row).
- **note**: In practice “minimal” is read off the data, not guessed: for each criterion the full-archive distribution of its quantity is drawn (Fig. 2.3, top row), together with the fraction of flights that the cut alone would retain as the threshold is moved (bottom row)

### [175] orange Highlight
- **marked**: The non-genuine population shows up as a distinct cluster at the low end of the distribution, separated from the genuine flights by a sparse tail;
- **note**: The non-genuine population shows up as a distinct cluster at the low end of the distribution, separated from the genuine flights by a sparse tail. FRASE VERA PER “PATH LENGTH” MA NON MOLTO PER “DURATION”. PER DURATION NON SI VEDE QUESTO CLUSTER IN REALTà. Ok parader di cluster ma devi dire che per duration non si vede il cluster nel’istorgamma ma siede una zona piatta nella retention curve.

### [176] green Highlight
- **marked**: the threshold is placed just beyond that cluster, on the stretch where the retained-fraction curve is flat—there, moving the cut changes almost nothing, which is precisely the statement that it removes junk and not signal.
- **note**: the threshold is placed just beyond that cluster, on the stretch where the retained-fraction curve is flat—there, moving the cut changes almost nothing, which is precisely the statement that it removes junk and not signal.

### [177] yellow Highlight
- **marked**: ≃ 15 paraglider “flights” of 16 h to 166 h, with paths up to 10,059 km (and none among the hang gliders),
- **note**: È presente il codice che ha fatto questo census? Come si chiama? Quali sono le classi e i metodi/attributi che hanno fatto questo check? Come si chiamano? 
  
  Questi numeri potrebbero cambiare quando verrà fatto il fix-level cleaning.

### [178] red StrikeOut
- **marked**: The cut is deliberately from the maximum MSD decoupled lag – the ensemble at lag already uses only flights with and the aging in is t T > t, T diagnosed by stratifying in – so large-lag analyses restrict to the long-duration stratum T rather than raising this global cut.
- **note**: The cut is deliberately decoupled from the maximum MSD lag – the ensemble at lag t already uses only flights with T >t, and the aging in T is diagnosed by stratifying in T – so large-lag analyses restrict to the long-duration stratum rather than raising this global cut.

### [179] yellow Highlight
- **marked**: long-lag MSD.
- **note**: More in general, the long lag analyses

### [180] green Highlight
- **marked**: i i " On the census, above 40 min the cut catches 236 of 184,583 paraglider flights (median extent 5 km) and 7 of 6,638 hang-glider flights: a fraction of order 10 of either ensemble. Duration already clears tows and sled runs. ↔3
- **note**: Questi numeri potrebbero cambiare quando verrà fatta l’analisi dopo il fix-level cleaning

### [181] red Highlight
- **marked**: Altitude activity.
- **note**: Altitude activity.per duration e path length abbiamo fatto istogramma e reatino curve. Credo sia giusto farlo anche per altitude-activity. Quando parli di total range of the altitude, coisa intendi a livello quantiativo? La differenza tra il max e il min durante il volo? E se il voto è spezzato in più segmenti? Il criterio si applica ai singoli semgneti? Mi sembra adi no. Ma allora si rischia di far vivere singoli segmenti con un range sotto i 75m?

### [182] yellow Highlight
- **marked**: 75 m:
- **note**: Solo 75m? Sembra poco? Oppure va bene?

### [183] yellow Highlight
- **marked**: The ⇒ census holds a few hundred such candidates among retained paraglider records;
- **note**: Questi numeri potrebbero cambiare dopo il fix-level clearing

### [184] yellow Highlight
- **marked**: The census behind these counts is not throwaway work: the numbers above are generated macros, recomputed by the same committed script that produces every census figure in this chapter (scripts/reporting/generate_census_stats.py) from the cached full-archive track scan (one per-flight summary table per discipline), against the thresholds in the configuration; changing a threshold re-draws the diagnostics without re-reading the raw tracks(implementation details: Sec. 2.6.4). The thin tail of very slow loggers is handled by the !t stratification (Sec. 2.7.6); a separate minimum-fix-count cut would be redundant, since above the duration cut even a 10 s logger records hundreds of fixes.
- **note**: Mi sembra che sia da mettere in implementation details piuttosto che qui

### [185] red Highlight
- **marked**: Figure 2.3 shows these diagnostics for both disciplines, computed on the full census (no subsampling).
- **note**: Va aggiunta la terza diagnostic, ovvero altitude activity.


## page 24  (pdf p. 24)

### [186] red StrikeOut
- **marked**: the diagnostics must be re-examined for the less curated further sources.
- **note**: ; the diagnostics must be re-examined for the less curated further sources.

### [187] green Highlight
- **marked**: The two remaining steps are di!erent in kind (Sec. 2.7):resampling and smoothing
- **note**: The two remaining steps are different in kind (Sec. 2.7):resampling and smoothing

### [188] green Highlight
- **marked**: 2.7):resampling and smoothing operate on coordinates and their derivatives and therefore need actual Cartesian componentwise components to act on. Latitudes and longitudes cannot play that role—they are angles on a curved surface, and di!erencing them componentwise does not yield displacements. The mapping proceeds in two steps.
- **note**: resampling and smoothing operate on coordinates and their derivatives componentwise and therefore need actual Cartesian components to act on. Latitudes and longitudes cannot play that role—they are angles on a curved surface, and differencing them componentwise does not yield displacements. The mapping proceeds in two steps

### [189] yellow Highlight
- **marked**: 2.7):resampling and smoothing operate on coordinates and their derivatives componentwise
- **note**: esampling and smoothing operate on coordinates and their derivatives componentwise

### [190] red Highlight
- **marked**: their derivatives
- **note**: Il resampling e lo smoothing agiscono anche sulle derviate, non solo sulle coordinate? Persanvo agissero solo sulle coordinate.

### [191] green Highlight
- **marked**: the transform is derived step by step in Appendix 2.C.
- **note**: ; the transform is derived step by step in Appendix 2.C.


## page 25  (pdf p. 25)

### [192] green Highlight
- **marked**: The latitude in (2.6) is the latitude: the geodetic ω angle between the equatorial plane and the ellipsoid at the point (Figure 2.4). It must normal not be confused with the geocentric latitude the angle to the line joining the point to the ↽, Earth’s centre On an ellipsoid the two di!er, because the normal does not pass through O. O:
- **note**: The latitude φin (2.6) is the geodetic latitude: the angle between the equatorial plane and the ellipsoid normal at the point (Figure 2.4). It must not be confused with the geocentric latitude ψ, the angle to the line joining the point to the Earth’s centre O. On an ellipsoid the two differ, because the normal does not pass through O:

### [193] green Highlight
- **marked**: at 0.19 (about 11.5 ), which if the two were → ↑ ↘ ↗ ↗ confused would misplace a fix by up to km of ground distance. ↓20
- **note**: t ≈0.19◦(about 11.5′), which if the two were confused would misplace a fix by up to∼20 km of ground distance

### [194] red Highlight
- **marked**: 2 (e sin 2ω ω ↽ /2) ↘ ↗
- **note**: Non si capisce da dove viene questa formula, come si ricava. Vanno messi i passaggi di come si ricava nell’appendice 2.C. e poi va citata l’appendice.

### [195] red Highlight
- **marked**: near 45 →
- **note**: Non capisco perchè “near”. Avrei detto at

### [196] green Highlight
- **marked**: These are also the (ω ) that , ε 0 0 orient the local frame of Step 2 (Figure 2.5).
- **note**: These are also the (φ0,λ0) that orient the local frame of Step 2 (Figure 2.5).

### [197] yellow Highlight
- **marked**: of the track as the trimmed origin—the first fix of free flight, which is close to but not the take-o! point on the ground, since the ground phase has been removed (Sec. 2.7.3),
- **note**: of the trimmed track as the origin—the first fix of free flight, which is close to but not the take-off point on the ground, since the ground phase has been removed (Sec. 2.7.3),

### [198] red Highlight
- **marked**: rotated
- **note**: Siamo davvero sicuro al 100% che qui “rotated” è il termine giusto??

### [199] green Highlight
- **marked**: with the rotation matrix derived in Appendix 2.C. The ENU frame is the local Cartesian frame in which the whole analysis is carried out: points east, north, and along the E N U local vertical (the ellipsoid normal at the origin). The ECEF coordinates of Step 1 are only an intermediate representation of the computation—no observable is ever expressed in them.
- **note**: with the rotation matrix derived in Appendix 2.C. The ENU frame is the local Cartesian frame in which the whole analysis is carried out: E points east, N north, and U along the local vertical (the ellipsoid normal at the origin). The ECEF coordinates of Step 1 are only an intermediate representation of the computation—no observable is ever expressed in them.


## page 26  (pdf p. 26)

### [200] green Highlight
- **marked**: Over the spatial extent of a single flight the tangent-plane approximation is accurate to well below the GPS noise for the horizontal coordinates: projecting onto the tangent plane shortens 3 2 a distance along the surface by ), about 1 cm at = 20 km and 13 cm at 50 km, d d /(24R d ↗ ↓ against metre-scale GPS noise (Appendix 2.C).
- **note**: Over the spatial extent of a single flight the tangent-plane approximation is accurate to well below the GPS noise for the horizontal coordinates: projecting onto the tangent plane shortens a distance d along the surface by ≈d3/(24R2 ⊕), about 1 cm at d= 20 km and 13 cm at 50 km, against metre-scale GPS noise (Appendix 2.C).

### [201] green Highlight
- **marked**: The altitude that enters this transform is the adopted channel of Sec. 2.7.1. The h horizontal coordinates are insensitive to that choice, and the mechanism is visible in Eq. (2.6): enters the horizontal ECEF components only through the radius factor (N + so switching h h), channel—which changes by the inter-reference o!set, at most 100 m (Fig. 2.1a)—rescales h ↓ them by a relative + 2 10 . Across the full extent of a flight (↓50 km) that is ↔5 ↫ φh/(N h) ⇓ under a metre, below the GPS noise on the same coordinates. For the vertical, the analysis does not use the rotation’s component as its working U coordinate: it keeps the adopted altitude channel itself (Sec. 2.7.1; barometric for most flights, GNSS on the fallback minority), = at its measured value—the altitude of the first z(t) h(t), fix is subtracted. Nothing is gained by re-zeroing: every vertical quantity that matters not downstream (the vertical velocity, the climb/sink discrimination of the segmentation) depends on increments, which are invariant to the reference, while keeping the measured value preserves the absolute height, an observable in its own right(potential energy, convective-boundary-layer structure)(Sec. 2.7.8).
- **note**: The altitude h that enters this transform is the adopted channel of Sec. 2.7.1. The horizontal coordinates are insensitive to that choice, and the mechanism is visible in Eq. (2.6): henters the horizontal ECEF components only through the radius factor (N+ h), so switching channel—which changes h by the inter-reference offset, at most∼100 m (Fig. 2.1a)—rescales them by a relative δh/(N + h) ≲ 2 ×10−5. Across the full extent of a flight (∼50 km) that is under a metre, below the GPS noise on the same coordinates. For the vertical, the analysis does not use the rotation’s U component as its working coordinate: it keeps the adopted altitude channel itself (Sec. 2.7.1; barometric for most flights, GNSS on the fallback minority), z(t) = h(t), at its measured value—the altitude of the first fix is not subtracted. Nothing is gained by re-zeroing: every vertical quantity that matters downstream (the vertical velocity, the climb/sink discrimination of the segmentation) depends on increments, which are invariant to the reference, while keeping the measured value preserves the absolute height, an observable in its own right(potential energy, convective-boundary-layer structure)(Sec. 2.7.8).


## page 27  (pdf p. 27)

### [202] red Highlight
- **marked**: given the flight’s own !t (Sec. 2.7.7).
- **note**: Siamo sicuri di questa frase??? La derivata la estrapolerò durante lo smoothing perchè il SAVGOL filter mi da gratuitamente la servita. Non andrò a claolcare differenze finite. In questo senso anche quanto scritto poco sopra “resampling and smoothing operate on coordinates and their derivatives componentwise” mi sembrava errato proprio perchè la derivata ok viene dallo smoothing però ce l’ho “”gratuitamente. Forse sbaglio qualcosa

### [203] green Highlight
- **marked**: (its two scales are motivated in the paragraph The split # $ below) bound has two scales
- **note**: (its two scales are motivated in the paragraph The split bound has two scales below)

### [204] green Highlight
- **marked**: or a position discontinuity such as a re-acquisition o!set, where the track jumps and stays: both sides are genuine and only the transition between them is unknown, so it is handled exactly like a long gap
- **note**: , or a position discontinuity such as a re-acquisition offset, where the track jumps and stays: both sides are genuine and only the transition between them is unknown, so it is handled exactly like a long gap

### [205] green Highlight
- **marked**: The missing-fraction check runs here, and not among the flight-level cuts of Sec. 2.7.4,
- **note**: The missing-fraction check runs here, and not among the flight-level cuts of Sec. 2.7.4,

### [206] orange Highlight
- **marked**: because it needs the time base
- **note**: Perchè il missino fraction check ha bisogno della time base?

### [207] green Highlight
- **marked**: and the splits to exist first. It is evaluated after splitting: per segment, a segment whose residual missing fraction (the grid points that would have to be interpolated) exceeds 10 % is dropped alone, and the flight is lost only if no segment survives. A flight with no long gap is a single segment, so a gap-free flight missing more than 10 % of its grid is dropped whole by the same rule.
- **note**: and the splits to exist first. It is evaluated per segment, after splitting: a segment whose residual missing fraction (the grid points that would have to be interpolated) exceeds 10 % is dropped alone, and the flight is lost only if no segment survives. A flight with no long gap is a single segment, so a gap-free flight missing more than 10 % of its grid is dropped whole by the same rule.

### [208] yellow Highlight
- **marked**: logger hiccups
- **note**: È l’espressione migliore da usare qui?

### [209] green Highlight
- **marked**: The absolute cap of 20 s is pinned by three constraints: • at least 2⇓ the slowest common cadence (10 s, Fig. 2.7), so a single missed fix never splits a flight; • at most about two thirds of a thermalling period, so a bridged gap can never hide a full circle; • well below = 60 s, for consistency: an excised frozen-lock run of that length is split, ↼ freeze so a native gap of comparable length cannot be bridged.
- **note**: The absolute cap of 20 s is pinned by three constraints: • at least 2×the slowest common cadence (10 s, Fig. 2.7), so a single missed fix never splits a flight; • at most about two thirds of a thermalling period, so a bridged gap can never hide a full circle; • well below τfreeze = 60 s, for consistency: an excised frozen-lock run of that length is split, so a native gap of comparable length cannot be bridged.

### [210] yellow Highlight
- **marked**: At the dominant 1 s cadence the relative bound binds
- **note**: Frase non scritta benisismo

### [211] yellow Highlight
- **marked**: 15.3 % of paraglider and 40.5 % of hang-glider flights with at least one split; had the relative part 10 !t acted alone, without the absolute cap, the shares would be 11.8 % and 14.5 %.
- **note**: Questi numeri potrebbero cambiare dopo l’azione del fix-level e del fligh-level filttering e del trimmering


## page 28  (pdf p. 28)

### [212] yellow Highlight
- **marked**: For this reason the absolute cap (20 s) is treated as a working value like the detector thresholds: it is swept in the validation procedure of Sec. 2.7.2 and frozen where the split fractions plateau.
- **note**: Sarà importante far vedere come viene scelto il giusto valore dell’absolute cap usando uno o più grafici

### [213] green Highlight
- **marked**: The bound is the same for every channel, altitude included. One might expect the altitude to tolerate wider gaps, since the vertical speed is about an order of magnitude smaller than the horizontal (v 1 m s against 10 m s ); it does not, for two reasons. First, the ↔1 ↔1 v z xy ↓ ↓ interpolation error over a gap is set by the of the signal, not by its speed: a fast curvature but straight motion is interpolated exactly, a slow but turning one is not, so a slower channel is not automatically a smoother one. Second, and more decisively, the altitude feeds , the v z segmentation’s discriminant. A long altitude gap interpolated linearly returns one average slope, which erases any climb–glide transition inside it—and transitions are exactly where v z swings fastest: typical glide sink is
- **note**: ok

### [214] red Highlight
- **marked**: 1–1.5 m s ↔1
- **note**: Siamo sicuri? Per quale categoria?

### [215] red Highlight
- **marked**: envelope
- **note**: Non si capisce chi è l’envelope!!

### [216] green Highlight
- **marked**: visible in Fig. 2.2b), so a thermal entry swings by several m s within a couple ↔1 v z of seconds, the worst case for interpolation. A real asymmetry between the channels does exist, but it concerns missing samples, not gap width: a single missing altitude is isolated reconstructed far more reliably than a single missing position, because the barometric signal is much smoother—that is what justified “drop the altitude only” at cleaning (Sec. 2.7.2); it does not justify a wider gap bound for z.
- **note**: ok

### [217] green Highlight
- **marked**: The key fact is that a segment keeps its parent’s origin and clock (Sec. 2.7.8): a GPS position is absolute, so the positions after the gap remain exactly as valid as those before it. Ensemble quantities (the MSD, the propagator) need the horizontal position at a given elapsed time, not the path travelled in between, so a split costs them nothing—the flight simply contributes no data at the lags that fall inside the gap. Quantities that instead accumulate along the path—the path length, a phase duration, a step length, any time-averaged window—cannot be evaluated across a stretch whose true course is unknown: sums and windows for these quantities are always taken inside one segment, never straddling a gap.
- **note**: ok

### [218] green Highlight
- **marked**: Boundary-truncated durations are flagged as censored and simply the ) fits and from the phase- excluded—from ↽(↼ duration histograms alike—rather than counted as complete, which would let every split masquerade as a spuriously short wait.
- **note**: ok

### [219] yellow Highlight
- **marked**: Censoring-aware estimators are deliberately not used:
- **note**: E quali sarebbero? E in che senso non vengono usati. Mi sembrava invece che venissero usati (vedi pdf dei waiting times) però con l’accotezza di non considerare le fasi che cadono sui tagli

### [220] green Highlight
- **marked**: as long as the censored fraction stays small (it is recorded per discipline), plain exclusion keeps the estimators transparent at negligible cost, and the recorded fraction tells us if that assumption ever fails.
- **note**: ok

### [221] green Highlight
- **marked**: For observables referenced to the time since the flight began—the time-averaged MSD stratified by duration, for instance (Ch. 3)—a segment starting at parent time 0 is not re-zeroed into a new flight that starts at = 0. t > t 0 It is used for what it is: an observation window [t ] onto a process already old. , t t 0 1 0 Re-zeroing would mix statistics of young and aged trajectories, which an aging analysis must keep apart.
- **note**: ok

### [222] green Highlight
- **marked**: The duration and path cuts of Sec. 2.7.4 were passed by the parent flight and are not re-applied to its segments. Re-applying them would be biased in a specific way: gaps concentrate in particular conditions (weak reception late in long flights, for example), so discarding every sub-40 min segment would
- **note**: ok


## page 29  (pdf p. 29)

### [223] green Highlight
- **marked**: throw away precisely the data recorded around gaps. A segment has to satisfy only what the downstream machinery physically requires—enough duration to support the smoothing window and the statistics computed within it;
- **note**: ok

### [224] red Highlight
- **marked**: one below a minimal duration
- **note**: Qual è la minima duration??? Come si chiama questo parametro?? Quanto vale?? È la minima duration che può avere un segmento?? Nel caso deve essere dichiara qui, non basta dichiararla negli implementation details

### [225] green Highlight
- **marked**: The scope of this step is set by the split bound: a gap longer than splits the flight and is never interpolated, so what is filled here are only the g max holes, up to , that remain inside a segment. The fill is done per channel, where short g max a channel is one of the three scalar series on the uniform grid: the horizontal coordinates and (t) and the adopted altitude The two horizontal coordinates are interpolated E(t) N z(t). independently, which is the componentwise interpolation of the horizontal position; the barometric and GNSS altitudes are never mixed here—only the flight’s adopted channel is filled (Sec. 2.7.1).
- **note**: ok

### [226] red Highlight
- **marked**: (a shape-preserving Hermite interpolant): monotone piecewise cubic
- **note**: Non sono sicurissimo si possa usare. Forse per questo tipo di interpolatole è necessario conoscere il valore della funzione e della sua derivata prima. Noi abbiamo il valore della funzione, esempio (t,x) ma non abbiamo la sua derivata.

### [227] orange Highlight
- **marked**: with slopes constrained so that the interpolant never overshoots the data it passes through.
- **note**: Non capisco questa frase. Non capisco il suo significato. Wikipedia dice questo: “monotone cubic interpolation is a variant of cubic interpolation that preserves monotonicity of the data set being interpolated.”

### [228] red StrikeOut
- **marked**: An unconstrained cubic can swing wide of the sample points, and an overshoot here would invent a position excursion that the smoothing step would then read as real motion.
- **note**: An unconstrained cubic can swing wide of the sample points, and an overshoot here would invent a position excursion that the smoothing step would then read as real motion.

### [229] purple Highlight
- **marked**: The altitude is interpolated linearly.
- **note**: The altitude is interpolated linearly: siamo sicuri che un iteprolatore lunare sia la scelta migliore?

### [230] orange Highlight
- **marked**: The linear error over a hole of width is bounded by g 2 max g /8; |z̈|
- **note**: QUESTA FORMULA VA RICAVATA, MAGARI IN FOOTNOTE

### [231] orange Highlight
- **marked**: in the steady phases
- **note**: Cosa intendi con “ steady phases”? Forse intendi all’interno di una fase e non tra fasi diverse? Se si va detto meglio, altrimenti sembra che una fase sia stazionaria

### [232] yellow Highlight
- **marked**: where holes are bridged the barometric signal changes slope
- **note**: where holes are bridged the barometric signal changes slope

### [233] green Highlight
- **marked**: so the error is at the metre scale even at the 20 s cap and far smaller for typical holes—transitions, where is large, are handled by the flag below. z̈ The result is precisely the completeness invariant promised at cleaning (Sec. 2.7.2): within a (E, retained segment, every grid time carries a defined N, z),
- **note**: ok

### [234] red Highlight
- **marked**: (Fig. 2.1),
- **note**: In realtà da Fig 2.1 non si vede che il baro channel cambia il suo valore slowly

### [235] green Highlight
- **marked**: downstream is never handed a missing value. The altitude values dropped at cleaning (a barometric spike, a fix on a GNSS-fallback flight) are the ones restored here. Every filled point carries V an flag, with a concrete consequence: downstream statistics can distinguish interpolated measured from reconstructed samples, and a phase boundary that the segmentation places inside a bridged stretch is treated like one at a segment boundary—the true transition could lie anywhere inside the hole, so the adjoining phase durations count as censored and are excluded from the duration fits, exactly as at a split.
- **note**: ok

### [236] yellow Highlight
- **marked**: so the segmentation
- **note**: THE SEGMENTATION, AND THE ANALYSIS MORE IN GENERAL

### [237] yellow Highlight
- **marked**: The gap bound g max
- **note**: È il posto giusto dove mettere questo paragrafo?

### [238] red StrikeOut
- **marked**: in the same way as the duration and path-length cuts (implementation details: Sec. 2.6.6).
- **note**: in the same way as the duration and path-length cuts (implementation details: Sec. 2.6.6)

### [239] red Highlight
- **marked**: Figure 2.6
- **note**: Attenzione, molta attenzione a dire e vedere come realmente è stat generata la Figure 2.6 e cosa realmente rappresenta. Il criterio di cut, g, è più complicato di un semplice 10*delta_. Insomma forse la fig 2.6 non riflette il criterio attuale. Oppure av bene. Cioè dipende come è stata generata la fig 2.6. se è stata generata applicando il criterio con il boundary a g allora ok. Se invece è stata generata tendendo conto solo di 10*delta_t allora non va bene perchè il g che determina il bonari gap è più complicato

### [240] red Highlight
- **marked**: (a finite-di!erence velocity,
- **note**: Non calmiererò la velocità in questo modo ma direttamente da svago smoother

### [241] orange Highlight
- **marked**: The dependence is in the observable’s own definition: a finite-di!erence velocity is the mean velocity over one sampling step, and a turning angle is the heading change over one step, so two loggers recording the motion at 1 s and 10 s produce systematically same di!erent distributions of both. Pooling all flights would blend this instrument artefact into the physics; where such observables are compared across flights, the ensemble is therefore stratified by rate or restricted to the dominant one.
- **note**: Forse per il turning angel quest disxros continua ad essere valido, ma per la velcoità direi più no che si dato che la ottengo. Come derivata data da svago. Attenzione però che svago viene citato nel prossimo paragrafo e fino ad ora non è stato ancora citato

### [242] red StrikeOut
- **marked**: (deriv = 0, 1, 2)
- **note**: (deriv = 0,1,2)


## page 30  (pdf p. 30)

### [243] red Highlight
- **marked**: Figure 2.6.
- **note**: Da ri-runnare dopo l’impelemntazioen delle fasi precedenti

### [244] orange Highlight
- **marked**: before its own e!ect hides part of the picture.
- **note**: In realtà a coprire l’effetto non è l’effetto del cut ma al più l’effetto del flight level cleanign

### [245] red Highlight
- **marked**: the threshold is moved:
- **note**: the threshold is moved: intendi g o sempliemnte gap/native_delta_t? Perched la threshold è g

### [246] orange Highlight
- **marked**: with a thin tail beyond 11 s
- **note**: with a thin tail beyond 11 s: questa stessa thin tail è presente anche per paragliders. La differenza è sicuramente in native_delta_t come 10 secondi molto più presenti in hang-gliders che in paragliders


## page 31  (pdf p. 31)

### [247] red Highlight
- **marked**: The derivative outputs are scaled by the flight’s own !t
- **note**: Non si capisce cosa questa frase voglia dire. Anche e soprattutto a alivello qualitativo non è chiaro. E non sono neanche sicuro che sia giusta

### [248] yellow Highlight
- **marked**: and downstream statistics can exclude them where it matters.
- **note**: E come fa a farlo? Come farebbe a scartali? E in che senso? Ed serve davvero scartarli?

### [249] red Highlight
- **marked**: therefore
- **note**: therefore. Perch questo therefore? È logicamente giusto?

### [250] yellow Highlight
- **marked**: (heavily reconstructed flights
- **note**: heavily reconstructed flights. Ovvero quelli con un numero di fix ricostruiti superiore a quanto? Dove è scritto?

### [251] yellow Highlight
- **marked**: recorded
- **note**: recorded. In che senso record? Dove’ come? Non erano già stati segnati i fix che erano stati ricostruiti? Perchè disegnarli ancora?

### [252] green Highlight
- **marked**: Fix as the lowest order that works. An acceleration requires curvature in the fit, so p 2. One order more is needed for the sake of the on a symmetric window, velocity: p ⇒ adding an even-order term leaves the odd-order coe"cients untouched (a parity property of least squares on a symmetric grid), so the velocity of a = 2 fit is identical to that of p a straight-line fit; = 3 is the lowest order p
- **note**: ok

### [253] red Highlight
- **marked**: whose velocity estimate responds to the local curvature of the track.
- **note**: Siamo sicuri che questa frase sia corretta? Piuttosto direi che la velocità è legata alla varzione di accelerazione, e non all’accelerazione. La velocità è il termine a1 del polinomio che, usando un polinomio di grado 3, si mischia con i lemrine a3 che è la variazione di accleraizone

### [254] green Highlight
- **marked**: Going higher only lets the fit follow more noise. Hence = 3. p
- **note**: ok

### [255] orange Highlight
- **marked**: (iii)
- **note**: Invece che fare un punto tre lo metterei come continuazione del punto 1

### [256] orange Highlight
- **marked**: is w ↼ /!t c
- **note**: w is τc/∆t. Cosa si intende con questo i? È vero o è una nostra scelta di porre w = tau/delta_t????

### [257] red StrikeOut
- **marked**: (p + 1 = 4 coe"cients from at least five samples).
- **note**: (p+ 1 = 4 coefficients from at least five samples)

### [258] red Highlight
- **marked**: = 5 samples spans exactly = 5 s, w ↼ c
- **note**: ???? Ma che ne sappiamo che tau_c = 5?

### [259] red Highlight
- **marked**: than more ↼ c
- **note**: !!!! Come facciamo a dirlo se non conosciamo quanto vale \tau_c???

### [260] orange Highlight
- **marked**: The measurement said otherwise: the three knees coincide at 0.2 Hz f c ↗ (↼ = 5 s). c
- **note**: The measurement said otherwise: the three knees coincide at fc ≈0.2 Hz (τc = 5 s). Ok ma serve un opolot che lo faccia vedere. E comunque questo plot andrà fatto sui dati quanto meno puliti sul fix-level e sul floght-level

### [261] green Highlight
- **marked**: c ↗ the flat high-frequency floor of every channel comes c from the rounding the IGC format applies when the file is written—altitudes to whole metres, coordinates to thousandths of an arc-minute—rather than from receiver noise, and rounding noise flattens the spectrum at the same frequency whatever channel it sits on. What distinguishes the noisy GNSS minority is how its floor sits, not high where the knee is (Sec. 2.6.7). So the answer to whether and get di!erent smoothing E, N z
- **note**: the flat high-frequency floor of every channel comes from the rounding the IGC format applies when the file is written—altitudes to whole metres, coordinates to thousandths of an arc-minute—rather than from receiver noise, and rounding noise flattens the spectrum at the same frequency whatever channel it sits on. What distinguishes the noisy GNSS minority is how high its floor sits, not where the knee is (Sec. 2.6.7). So the answer to whether E, N and z get different smoothin

### [262] yellow Highlight
- **marked**: mundane:
- **note**: Trivial va bene?


## page 32  (pdf p. 32)

### [263] green Highlight
- **marked**: timescales is currently no: the per-channel machinery exists, for the noisy GNSS minority, but the adopted windows are equal.
- **note**: timescales is currently no: the per-channel machinery exists, for the noisy GNSS minority, but the adopted windows are equal.

### [264] yellow Highlight
- **marked**: c the acceleration distribution must stay within physical bounds;
- **note**: Ma perchè solo l’acelerazione? Anche la velocità, e forse anche altre variabili

### [265] yellow Highlight
- **marked**: 2.8 Preliminary characterization
- **note**: VOGLIO ANCHE UNA MAPPA DOVE SONO SEGNATI I SITI DI DECOLLO DEI VOLI RETAINEDò MAPPA FORSE DELLA FRANCIA MA FORSE NON BASTA

### [266] orange Highlight
- **marked**: the flights that survive the cleaning, filtering and resampling of Sec. 2.7.
- **note**: Non è solo una questione di survive. Survive va bene quassio si parla di fix-lvele clearing e flight-lelv clemaing ma per lo smoothing e il fitlering non è un survive. Non si sono più cose eliminate

### [267] green Highlight
- **marked**: Its point is to re-establish the basic statistics on that retained ensemble—which is why, for instance, the native-rate distribution reappears here: Figs. 2.6 and 2.7 were computed on parsed flight, as a filtering diagnostic, every whereas the analysis needs the same quantities on the flights actually used. The checks below validate basic assumptions and reveal stratification needs; none of them requires the phase segmentation, so they can run as soon as the pipeline does, ahead of the transport analysis proper.
- **note**: ts point is to re-establish the basic statistics on that retained ensemble—which is why, for instance, the native-rate distribution reappears here: Figs. 2.6 and 2.7 were computed on every parsed flight, as a filtering diagnostic, whereas the analysis needs the same quantities on the flights actually used. The checks below validate basic assumptions and reveal stratification needs; none of them requires the phase segmentation, so they can run as soon as the pipeline does, ahead of the transport analysis proper

### [268] red StrikeOut
- **marked**: _(no text captured)_
- **note**: re-

### [269] green Highlight
- **marked**: For each retained flight: airborne duration , total horizontal path T length, number of valid fixes and native sampling interval !t. Their distributions over the retained ensemble serve three uses: they describe the dataset the results will rest on; they expose any outlier that survived the filtering; and, through !t, they fix the per-flight smoothing window (Sec. 2.7.7). On the raw archive the median recorded duration is 2.6 h for paragliders and 3.1 h for hang gliders, with median flown paths of 86 and 158 km; the same statistics on the retained ensemble are among the first outputs of the pipeline run.
- **note**: For each retained flight: airborne duration T, total horizontal path length, number of valid fixes and native sampling interval ∆t. Their distributions over the retained ensemble serve three uses: they describe the dataset the results will rest on; they expose any outlier that survived the filtering; and, through ∆t, they fix the per-flight smoothing window (Sec. 2.7.7). On the raw archive the median recorded duration is 2.6h for paragliders and 3.1h for hang gliders, with median flown paths of 86 and 158km; the same statistics on the retained ensemble are among the first outputs of the pipeline run.

### [270] green Highlight
- **marked**: The transport analysis would like to study the one-dimensional marginal of the propagator in place of the full two-dimensional density (Section 3.1): a substantial simplification, both statistical and presentational. The reduction is legitimate only if the process is isotropic, and isotropy cannot be assumed here. The CFD flights are not races flown together—each is a solo cross-country flight, later entered into a scoring ladder—but a single flight is still strongly directed: a chosen route, the orography, the valley winds. Isotropy can therefore hold at best at the level of the where take-o! sites and route choices vary, ensemble, never at the level of one flight; and for the genuinely simultaneous competition flights to be
- **note**: The transport analysis would like to study the one-dimensional marginal of the propagator in place of the full two-dimensional density (Section 3.1): a substantial simplification, both statistical and presentational. The reduction is legitimate only if the process is isotropic, and isotropy cannot be assumed here. The CFD flights are not races flown together—each is a solo cross-country flight, later entered into a scoring ladder—but a single flight is still strongly directed: a chosen route, the orography, the valley winds. Isotropy can therefore hold at best at the level of the ensemble, where take-off sites and route choices vary, never at the level of one flight; and for the genuinely simultaneous competition flights to be


## page 33  (pdf p. 33)

### [271] red Highlight
- **marked**: Compatibility across strata.
- **note**: PRIMA PERò è NECESSARIO NOMRALIZZZARE LE DICITURE CON CUI LE VARIE CLSSI VENGONO CHIANATE

### [272] orange Highlight
- **marked**: Geography is a further stratification axis of the same kind: a map of take-o! coordinates and of displacement end-points at fixed reveals the clustering imposed t by France’s orographic zones (Alps, Pyrenees, Massif Central, plains), and if mountain flights di!er markedly from flatland ones the compatibility check above is repeated across geographic strata as well.
- **note**: NON MI è CHAIRO COME E COSA SI VUOLE FARE QUI. E SE HA SENSO

### [273] red Highlight
- **marked**: and no stage ever mixes flights
- **note**: COSA SI VUOLE DIRE? Mi sembra ovvio. Però forse non sto capendo il significato. Per forza il cleaning avviene per ogni volo. Che senso avrebbe mischiare più voli? E in che modo mai si dovrebbero mischiare??


## page 34  (pdf p. 34)

### [274] red Highlight
- **marked**: segments on uniform grids: horizontal posi- tion, measured altitude, velocity, acceleration
- **note**: Non capisco cosa voglia dire


## page 35  (pdf p. 35)

### [275] yellow Highlight
- **marked**: Table 2.6.
- **note**: total_range < 30?? Che signficia??
  
  Perchè in fix-level cleaning is parla di rebuild-share se il rebels non dovrebbe avvenire nel fix-level clenaign? 
  
  In adopted parameters usadi di più gli elenchi puntati per elnachhera i vari parametri con i loro valori
  
  In 6. Come può un segment essere sparse? Non capisco. Capisco solo che può essere too short
  
  Il fatto che i segmenti devono durare almeno 90 secondi deve esser eriprotato nel main text. Appunto in quella famosa tabella o in più tabella in cui ci sono tutti i parametri usati in questa sezione. Magari più tabelle via via che si va costruendo la procedura di cleaning filteirng sampling smoothing
  
  
  Che tau_c sia uguale a 5secondi bho o. Come abbiamo fatto a dirlo? Come facciamo a dirlo per tuti i voli? E comune sia deve essere trovato come valore andando a far eil welch magari su tutti i voli o comqunue su un campione abbastanza grande. Non basta un solo ovolo. Serve un grafico. E sorputto è una procedura che va fatta dopo il clenaing


## page 54  (pdf p. 54)

### [276] red StrikeOut
- **marked**: so that a detail removed from the body sits in the corresponding chapter or section here.
- **note**: so that a detail removed from the body sits in the corresponding chapter or section here.


## page 55  (pdf p. 55)

### [277] yellow Highlight
- **marked**: Table 1.1.
- **note**: La tabella va resa più chiara usando i separatori verticali e orizzontali per delineare righe e colonne


## page 57  (pdf p. 57)

### [278] green Highlight
- **marked**: Both and are regenerated on demand (Sec. 2.3) by the catalog.csv seasons_index.csv acquisition CLI’s subcommand (Sec. 2.1.1) – never hand-edited. build-catalog
- **note**: Both catalog.csv and seasons_index.csv are regenerated on demand (Sec. 2.3) by the acquisition CLI’s build-catalog subcommand (Sec. 2.1.1) – never hand-edited.


## page 58  (pdf p. 58)

### [279] green Highlight
- **marked**: The placeholder class is the literal “0” in where possible the true class is recovered aile_class; from the raw (wing-model) field. The normalisation runs at the fix-level/pre-processing aile stage (Sec. 2.6.2) and is defined in Sec. 2.4. Status: Table 2.1.
- **note**: The placeholder class is the literal “0” in aile_class; where possible the true class is recovered from the raw aile (wing-model) field. The normalisation runs at the fix-level/pre-processing stage (Sec. 2.6.2) and is defined in Sec. 2.4. Status: Table 2.1.

### [280] green Highlight
- **marked**: The season tables of Sec. 2.5 are typeset from the versioned (Sec. 2.3); seasons_index.csv the trajectory-level census numbers quoted from Sec. 2.7 onward come from a di!erent pipeline, the cached track scan described at the head of Sec. 2.6.
- **note**: The season tables of Sec. 2.5 are typeset from the versioned seasons_index.csv (Sec. 2.3); the trajectory-level census numbers quoted from Sec. 2.7 onward come from a different pipeline, the cached track scan described at the head of Sec. 2.6.

### [281] green Highlight
- **marked**: Parsing: each IGC file is decoded by the soaring. parser, which reads the records at their fixed character positions (Sec. 2.2) analysis.igc B and returns both altitude channels alongside time and geodetic coordinates.
- **note**: Parsing: each IGC file is decoded by the soaring. analysis.igc parser, which reads the B records at their fixed character positions (Sec. 2.2) and returns both altitude channels alongside time and geodetic coordinates.

### [282] green Highlight
- **marked**: by the soaring. parser, which reads the records at their fixed character positions (Sec. 2.2) analysis.igc B and returns both altitude channels alongside time and geodetic coordinates. The Welch/PSD procedure used to compare altitude channels is stated once, in Sec. 2.6.1; the smoothing calibration (Sec. 2.6.7) reuses it, applied to the horizontal components and to the flight’s adopted altitude channel.
- **note**: by the soaring. analysis.igc parser, which reads the B records at their fixed character positions (Sec. 2.2) and returns both altitude channels alongside time and geodetic coordinates. The Welch/PSD procedure used to compare altitude channels is stated once, in Sec. 2.6.1; the smoothing calibration (Sec. 2.6.7) reuses it, applied to the horizontal components and to the flight’s adopted altitude channel.

### [283] green Highlight
- **marked**: The census scan and its cache. One full parse of the archive backs every trajectory- census number and figure in this appendix and in Chapter 2: the scan load_or_scan_tracks reads every parsed track (186,025 paraglider, 6,716 hang-glider) once and
- **note**: The census scan and its cache. One full parse of the archive backs every trajectorycensus number and figure in this appendix and in Chapter 2: the load_or_scan_tracks scan reads every parsed track (186,025 paraglider, 6,716 hang-glider) once and

### [284] orange Highlight
- **marked**: caches a per-flight summary table at <data_root>/derived/track_scan.parquet,
- **note**: Voglio maggiore dettaglio su cosa questo file .parquet contiene e come è organizzato. A cosa serve davvero

### [285] yellow Highlight
- **marked**: since the live archive grows only slowly, the cached counts can trail the season tables’ download counts until the cache is refreshed.
- **note**: Ma in che senso l’archivio cresce??? Non che cresce così a caso. Crescerà quando aggiungerò i sailplanes

### [286] orange Highlight
- **marked**: with a few hundred flights the high-frequency part of the median barometric curve is still visibly ragged (under-averaged), and it smooths out only with a few thousand flights, so 3,000 buys a stable band at modest cost.
- **note**: Voglio che riporti i plot usando poche centinaia e il plot riportato anche nel pain text in cui si vede la verità di questa affermazione

### [287] red Highlight
- **marked**: in the subsample);
- **note**: Che inntendi col dire “in the subsample??”


## page 59  (pdf p. 59)

### [288] orange Highlight
- **marked**: Flight selection.
- **note**: Si stanno usando voli con delta_t diverso? E.g. delta_t = 1s oppure delta_t = 9s. Si può fare questa cosa? Causa probelmi?

### [289] red Highlight
- **marked**: linear, so the resampling adds no spurious power near the Nyquist frequency where the noise floor is read.
- **note**: Non capisco cosa vuol dire questa frase

### [290] orange Highlight
- **marked**: a Hann window,
- **note**: a Hann window: quanto grande???

### [291] green Highlight
- **marked**: The median, not the arithmetic mean, because the per-flight spectra are heavy-tailed: a mean swings by one to two orders of magnitude between samples – for the hang-glider 2 barometric floor, from 0.8 to 93 m Hz between an = 114 and an = 727 draw ↔1 n n – whereas the median is stable.
- **note**: The median, not the arithmetic mean, because the per-flight spectra are heavy-tailed: a mean swings by one to two orders of magnitude between samples – for the hang-glider barometric floor, from 0.8 to 93 m2 Hz−1 between an n = 114 and an n = 727 draw – whereas the median is stable.

### [292] orange Highlight
- **marked**: 1 /f Nyq 12
- **note**: Da dove viene questa formula???

### [293] orange Highlight
- **marked**: Census (panel d). Panel (d) is a full census, not a sample: the barometric-presence fraction is read o! the shared track scan (Sec. 2.6), already paid for by the flight-level diagnostics. Presence is whole-file, checked on the same census: when the channel is absent it reads exactly zero for 99.7 % (paragliders) / 100 % (hang gliders) of those flights, and when present it covers every fix for 96 % / 98 % of them (the rest miss only a handful of individual fixes, dropped one by one, Sec. 2.7.2).
- **note**: Forse nel codice un volo è con il baro se ha più del 50% di baro presenti. Non va bene. Threshold troppo bassa. Voglio la threshold sopra il 95%. E quindi va rifatto ilcensus. Questa cosa di qual è la soglia minima oltre il quale unn volo è dichiarato con il baro va dichiarato sia qui in implementato ndetails che nel corpo della tesi. E chiaramente va aggiornato il codice


## page 60  (pdf p. 60)

### [294] green Highlight
- **marked**: Status: Table 2.1 – the detectors are designed and thresholded on the data, their parameters already config keys (Table 2.2); the routine that applies them is the next implementation step. The detectors run in a fixed order, which the subsections below follow:
- **note**: Status: Table 2.1 – the detectors are designed and thresholded on the data, their parameters already config keys (Table 2.2); the routine that applies them is the next implementation step. The detectors run in a fixed order, which the subsections below follow:

