# GNSS-only altitude, windowed $v_z$ rule, and the full pipeline re-run

## Context

Two coupled changes to the pre-processing, plus the end-to-end re-run they force.

**1. One altitude channel, GNSS, for every flight.** Today the pipeline picks a channel per
flight (`adopt_alt_channel`, [altchannel.py:114-141](src/soaring/analysis/preproc/altchannel.py#L114-L141)):
barometric when present and alive, GNSS otherwise. Today that leaves ~70 % of paraglider and
~82 % of hang-glider flights on baro (`\StatPipeParaBaroPct 69.6`, `\StatPipeHangBaroPct 82.5`)
and the rest on GNSS. §2.7.1 ([03-dataset.tex:276-387](thesis/sections/03-dataset.tex#L276-L387))
argues for that mixture. The new position: the median high-frequency floors of the two channels
coincide, so the typical flight loses nothing on GNSS, and a single channel for the whole
population removes both the two-channel apparatus and any `alt_source`-correlated selection
effect. This is also a move *towards* the reference study `vilpellet2026`, which derives $z$
from GNSS; the current text calls the baro choice "a deliberate departure" from it.

**2. The $|v_z|$ bound becomes a windowed test.** `max_vertical_speed_mps = 13` is applied today
between *consecutive* fixes ([cleaning.py:680-716](src/soaring/analysis/preproc/cleaning.py#L680-L716)).
A gust can push one fix-to-fix step past 13 m/s legitimately; a whole neighbourhood past 13 m/s
cannot.

The two changes are not independent, and this is the load-bearing finding of the exploration:
**GNSS vertical noise alone trips the per-step bound.** A clean 3 m/s climb with σ = 4 m of
vertical noise at 1 Hz produces a maximum step $|v_z|$ of **14.1 m/s** — over the bound — while
its window median reads 5.6 m/s. Change 1 without change 2 would make the vertical cleaning fire
on noise across the archive. The windowed rule is a *prerequisite* of the GNSS switch, not a
separate improvement.

Both changes alter which flights and segments survive, so `preprocess.py` and all 21 steps of
`regenerate.sh` are re-run on a faster machine.

---

## Decisions taken

| | Decision |
|---|---|
| Scope of the $v_z$ verdict | **Censor the altitude only** (`alt → NaN`), never delete the fix. Preserves the invariant at [cleaning.py:15-22](src/soaring/analysis/preproc/cleaning.py#L15-L22) and the test that fixes it. |
| Windowed statistic | **Rolling median of $\|v_z\|$.** The only candidate blind to both a gust and an isolated spike while still firing on a sustained excess (table below). |
| Threshold | **Re-measured from the data**, on the new statistic and the GNSS channel — the same method that set 45/55 m/s ([preprocessing.yaml:20-31](configs/preprocessing.yaml#L20-L31)). |
| Barometric channel | **Kept as a diagnostic witness only** — frozen-lock and interior-ground — never as an analysis quantity. Flights without a usable GNSS altitude are dropped with a new reason. |

Measured behaviour of the three candidates (1 Hz, ±5 fixes), which is why the median wins:

| case | max step $\|v_z\|$ | **median** | mean | chord |
|---|---|---|---|---|
| clean 3 m/s climb | 3.0 | 3.0 | 3.0 | 3.0 |
| gust bump (+16, +14) | 19.0 | **3.0** | 5.2 | 4.6 |
| single 200 m sensor spike | 203 | **3.0** | 42.4 | 23.0 |
| real spiral dive, 18 m/s for 15 s | — | **15.0** | 39.0 | 28.2 |
| GNSS noise, σ = 4 m | 14.1 | **5.6** | 5.6 | 3.9 |

---

## Part A — Measure first, on this machine, before touching the pipeline

Three numbers decide the new thresholds and one of them could still change the decision.
All four scripts involved are **not** in `regenerate.sh` and must be run by hand.

### A1. GNSS presence over the *whole* archive — the go/no-go

Today `\StatAltOffParaFallbackGnssPct 99.6` / `\StatAltOffHangFallbackGnssPct 94.3` say GNSS is
usable on the flights that *have no barometer*. Nothing measures GNSS presence on the ~70/82 %
that do, and some loggers write a pressure altitude while leaving the GNSS field at `00000`.
If that population is large, GNSS-only costs real flights.

- Extend `_SCAN_COLUMNS` ([census.py:126-139](src/soaring/analysis/census.py#L126-L139)) with
  `gnss_present_frac`, `gnss_alt_min_m`, `gnss_alt_max_m`, and a GNSS `max_vz_mps`.
- Add `gnss_present_fraction` next to `baro_present_fraction`
  ([igc.py:235-255](src/soaring/analysis/igc.py#L235-L255)) — same three lines on `gnss_alt`.
- **Full rescan** of `track_scan.parquet` per discipline (tens of minutes each; the cache has no
  GNSS columns so there is no incremental path).
- New macros from `generate_census_stats.py`: `\StatScanParaNoGnssPct`, `…GnssMissFlightsPct`,
  and the joint cell "no usable altitude on either channel".

### A2. Re-derive the $|v_z|$ bound and the window width

`fig:fixlevel` is drawn by [generate_preproc_figure.py](scripts/reporting/ch2_dataset/generate_preproc_figure.py),
fed by `fix_level_distributions` ([census.py:247-307](src/soaring/analysis/census.py#L247-L307)),
which today **restricts $v_z$ and altitude to barometric flights** (`census.py:270`). Two things
that the old 13 m/s rested on both stop being true: the channel and the statistic.

- Change `_fix_level_arrays` to emit the GNSS-channel **window median of $|v_z|$** alongside the
  per-step $|v_z|$, over the whole population.
- Place the bound where the fine-histogram bin-to-bin ratio settles near 1, exactly as the
  horizontal bounds were placed.
- Sweep window half-width ∈ {3, 5, 10, 20} s against candidate thresholds on the seeded sample
  and report per-rule removal fractions — the a-posteriori check the chapter already promises.
- Expect the bound to land **above** 13 m/s: a real spiral dive holds 15–20 m/s of sustained sink
  and reads 15.0 on this statistic. If the measured knee sits below the dive envelope, say so and
  keep the higher value with the physical argument stated.

### A3. Size the noisy-GNSS minority directly

The intended justification — *"the medians coincide, so the noisy flights must be few, otherwise
they would have moved the median"* — **does not hold as an inference.** A median is unmoved by
anything up to 50 % of the population, so equal medians bound the noisy fraction at 50 %, not at
"few". Worse, the 10–90 band already fanning out means the fraction is *at least* 10 %. A referee
will puncture this in one line.

The fix is to measure the fraction instead of inferring it, and the machinery is already there:
`_Accumulator._psd` ([altitude_noise.py:264](src/soaring/analysis/altitude_noise.py#L264)) keeps
the per-flight spectra individually rather than pre-summed.

- Add `hf_floor(channel, f_min)` beside `band_psd`
  ([altitude_noise.py:315-348](src/soaring/analysis/altitude_noise.py#L315-L348)): per-flight
  median PSD over $f \ge f_{\min}$ (use `FLOOR_BAND = (0.35, 0.5)` Hz, already defined in
  `estimate_savgol_timescales.py:53`), returning one number per flight.
- New macros: the fraction of flights whose GNSS floor exceeds $k\times$ the barometric median,
  for $k \in \{3, 10\}$, and the GNSS floor quantiles (p50, p90, p99) against the baro ones.
- The claim then reads *"X % of flights carry a GNSS high-frequency floor more than 3× the
  barometric median; for the other (100−X) % the two channels are indistinguishable"* — measured,
  and it survives review.

Note `collect()` restricts the PSD to flights carrying a barometer (`altitude_noise.py:415-417`),
which is the right paired comparison; state that scope in the caption.

---

## Part B — Code changes

### B1. `altchannel.py` — the channel choice becomes a channel *gate*

`adopt_alt_channel` no longer chooses. It adopts `gnss_alt` unconditionally, and returns two
independent verdicts:

- **the analysis channel** — GNSS, with the same presence + liveness pair the baro channel used
  (`gnss_present_min`, `gnss_min_range_m`). Failing either is now a **flight-level drop**, a new
  reason (`DROP_NO_ALTITUDE = "no_usable_altitude_channel"`) surfaced in the cascade table;
- **the witness channel** — the raw baro, usable when present and alive, exposed as a boolean
  `baro_witness` on the record.

`ALT_SOURCES` and the `"baro"`/`"gnss"` string plumbing go away. Keep `baro_present_frac` and
`baro_range_m` on `FlightRecord`: they are still the witness evidence and still the census.

### B2. `cleaning.py` — the windowed rule, and the witness

**The new rule, precisely** (this is the answer to *"non so quale fix dovrei eliminare"*):

$v_z$ lives on *steps*, not fixes. For step $j$ (between fix $j$ and $j+1$), let $W_j$ be the
steps whose midpoint lies within $\pm$`vz_window_s` of step $j$'s midpoint, and

$$\tilde v_j \;=\; \operatorname{med}\{\,|v_{z,i}| : i \in W_j\,\}.$$

A step is *bad* when $\tilde v_j >$ `max_vertical_speed_mps`. **Fix $k$ is censored when both the
step into it and the step out of it are bad**: `censor[k] = bad[k-1] & bad[k]`. That is what
"which fix" means — a fix is condemned by its neighbourhood on both sides, never by one step, so
a gust (which makes one step large and leaves the median where it was) censors nothing, and a
sustained run is censored through its interior with its endpoints left as the boundary between
good and bad data.

Deliberately **not** added: an "and its own step exceeds the bound" corroboration. Inside a long
run one fix may happen to sit on a small step, and the corroboration would punch holes in an
otherwise uniformly censored stretch.

**Sparse-cadence fallback.** Where $W_j$ holds fewer than `vz_min_window_fixes` (reuse the
Hampel convention, 5), the median is not estimable and the step falls back to the per-step
bound. This is safe *because* it is the sparse case: at 1 Hz a 13 m/s bound is 13 m per step,
within reach of gust plus noise; at a 10 s cadence it is 130 m per step, which no gust produces.
The gust problem is a fast-cadence problem, and the fallback only ever runs at slow cadence.

Also in this module:

- `_clean_altitude` returns the new `vz_sustained` mask in place of `vz_spike`. Keep the
  `n_alt_level_shift` counter as it is — the unreturned step is a different shape and still
  uncensored by anything, which the thesis already flags as an open decision.
- Decide the fate of the isolated **out-and-back spike** rule (`spike[1:-1] = both & opposite`).
  Recommendation: **keep it**, renamed, as a second and clearly separate rule. It does not fire on
  gusts (a gust is not an out-and-back with both legs past the bound) and dropping it would let
  the 5117 m/s artefact the docstring describes back into the written table. The windowed rule
  cannot catch it — that is exactly the property that makes the median the right statistic.
- `_is_witnessed` ([cleaning.py:576-601](src/soaring/analysis/preproc/cleaning.py#L576-L601)):
  the `alt_source` branch becomes a `baro_witness` branch, reading the **raw** `baro_alt` column
  rather than the adopted `alt`. Flights without a usable barometer keep the weaker declared-only
  witness, as the GNSS-fallback flights already do today.
- The `if alt_source == "gnss": invalidated |= ~valid` rule at
  [cleaning.py:798-801](src/soaring/analysis/preproc/cleaning.py#L798-L801) now applies to
  **every** flight — the V flag always certifies a degraded GNSS altitude now.

### B3. `trimming.py` — the interior-ground guard

`_is_flat` ([trimming.py:141-179](src/soaring/analysis/preproc/trimming.py#L141-L179)) runs on the
adopted `alt` with a 5 m tolerance, which GNSS vertical noise will not clear. Pass the raw baro
column as the witness where `baro_witness` holds, and fall back to the horizontal-speed condition
alone where it does not. `pipeline.py:251-252` already threads `frozen_delta_z_m / frozen_tau_s`
through as `max_drift_mps`; the same call site carries the witness flag.

### B4. `smoothing.py` and the savgol config

`savgol_windows(..., alt_source=...)` ([smoothing.py:168-196](src/soaring/analysis/preproc/smoothing.py#L168-L196))
collapses to a single vertical timescale. `tau_c_vertical_baro_s` / `tau_c_vertical_gnss_s` become
one `tau_c_vertical_s`; they hold the same value today, so this changes no output. Fix the stale
`SavgolParams` docstring ([config.py:129-132](src/soaring/analysis/config.py#L129-L132)), which
still asserts the asymmetric-window story the YAML records as disconfirmed.

This also **resolves a live inconsistency**: `estimate_savgol_timescales.py:142` and
`generate_savgol_spectrum_figure.py:158` split flights into baro-vertical and GNSS-vertical at a
hardcoded `>= 0.5`, half the pipeline's 0.95, contradicting the "single source of truth" claim in
`altitude_noise.py:79-87`. With one vertical channel the split disappears and so does the bug.

### B5. `configs/preprocessing.yaml`

```yaml
fix_level:
  max_vertical_speed_mps: <from A2>   # now the WINDOW MEDIAN of |v_z| on the GNSS channel
  vz_window_s: 5.0                    # half-width; at the modal 1 Hz cadence this is +-5 fixes
  vz_min_window_fixes: 5              # below this the median is not estimable -> per-step bound

alt_channel:                          # no longer a choice: a gate on GNSS + a witness on baro
  gnss_present_min: 0.95
  gnss_min_range_m: 30.0
  baro_witness_present_min: 0.95
  baro_witness_min_range_m: 30.0
```

Rewrite the block comments: the file header says "altitudes are barometric" (line 10), and
`min_altitude_m` / `max_altitude_m` / `frozen_delta_z_m` / `ground_flatness_m` all carry
barometric rationale that no longer describes what they bound. `min_altitude_m: -100` in
particular was justified by the ICAO reference offset — on an ellipsoidal height the argument is
different (geoid separation, roughly −50 to +50 m over France) and the value should be restated,
not silently reused.

### B6. Tests

- `test_altchannel.py` — rewrite around the gate/witness split.
- `test_cleaning.py:341` `test_a_sustained_dive_is_not_censored_but_counted` **asserts the
  opposite of the new rule** at 18 m/s. It becomes the test that pins the re-measured bound:
  a dive inside the envelope survives, one beyond it is censored.
- New: a gust (one step over, median under) censors nothing; an isolated spike is still caught by
  the out-and-back rule; a sustained run is censored through its interior; the sparse-cadence
  fallback fires below `vz_min_window_fixes`.
- `test_cleaning.py:368` `test_no_altitude_rule_ever_deletes_a_fix` must keep passing unchanged —
  it is the invariant.
- `test_smoothing.py:123-126` — the two-vertical-window assertions go.
- `generate_pipeline_census.py:68-98` reflects over every `DROP_*` constant and exits if
  `DROP_LABELS` misses one, so the new drop reason must be registered there or step 2 fails.

---

## Part C — Thesis

### C1. §2.7.1, `sec:altchannel` — rewritten ([03-dataset.tex:276-387](thesis/sections/03-dataset.tex#L276-L387))

New argument, in this order:

1. **One channel for the whole population**, on homogeneity: a vertical observable that is the
   same physical quantity for every flight, with no `alt_source`-correlated selection effect
   leaking into the statistics.
2. **It costs nothing at the median** — Fig. `fig:altnoise`c, the two median spectra coincide,
   both quantization-limited.
3. **And the noisy tail is this big** — the measured fraction from A3, *not* the median argument.
4. **GNSS is available** — the A1 presence census, and the flights dropped for lacking it.
5. **The barometer keeps a job**: an independent instrument witnessing a frozen GNSS lock. Say
   plainly that this is not channel mixing — it enters no observable.
6. Drop the "deliberate departure from `vilpellet2026`" sentence; the departure is gone.

Removed: the `revblock` "Mixing costs no more scatter than the weather already does"
(lines 350-373) — there is nothing left to mix. "The scatter is weather" (375-386) can stay as a
short instrument-vs-weather note in `impl:altoffset`, or go. Note the removed block also carries
the load-bearing sentence *"the horizontal transport analysis uses no altitude at all"*, which is
what makes this whole change safe; re-state it where the new text needs it.

The `\StatAltOff*` family (111 macros) mostly stops being quoted. `check_generated_macros.py`
treats *defined-but-not-quoted* as a note, not a failure, so nothing breaks — but the reverse is
a build-killer, so every new macro must exist before the text quotes it.

While in this file, fix the defects the exploration found: the stray `...` and double period at
line 354, the contraction at line 324, trailing whitespace at 284/291/302.

### C2. §2.7.2, `sec:fixlevel`

- Lines 486-496 "An unreturned vertical step" and 498-514 "Why the vertical channel is treated
  differently" both argue from the per-step bound. The third bullet, *"keeping the vertical rule
  to a bound that only fires on the physically impossible"*, is now delivered by the window
  median rather than asserted — that is a stronger version of the same argument, and the GNSS
  noise result (14.1 m/s from clean noise) is the evidence for why the per-step form could not.
- Line 446-449 "an absolute bound that runs with no local test alongside it" and *"the vertical
  channel is the one place the bound acts by itself"* is no longer true: the window median **is**
  a local test. Rewrite.
- Table `tab:cleaning` row at 729-732 and `tab:workingparams` at 2123 get the new statistic and
  the two new keys.

### C3. Elsewhere (consistency sweep)

`03-dataset.tex` lines 28-33, 221-224, 566-568, 750, 881-883, 928-929, 1245-1256, 1537-1556,
1643-1646, 1911-1918, 2136-2141, 2196-2199; `appendices/impl/C2-dataset.tex:429-742`
(`impl:altchannel` + `impl:altoffset`); `appendices/B-psd.tex:54-57`;
`appendices/geodesy.tex:176-177` (says "the vertical coordinate is the barometric altitude
itself" — now simply wrong).

Per the standing preference, do **not** reintroduce `\begin{revblock}` / `\rev{}` into
`03-dataset.tex`.

Optional, cheap: `thesis/generated/alt_offset_hist.pdf` is generated by
`regenerate.sh` step 7 and included **nowhere** — no `\includegraphics`, no `fig:altoffset`
label. Either give it a home in `impl:altoffset` or drop the step.

---

## Part D — The re-run on the faster machine

### D1. Python 3.6.6 is not a problem

Nothing here uses the system Python. The repo is `requires-python = ">=3.12"`, pinned by
`.python-version`, `uv.lock` and CI. Below 3.12 it does not merely misbehave, it does not parse:
75 modules open with `from __future__ import annotations` (a hard `SyntaxError` on 3.6), and
there are 323 PEP 585 generics, 171 PEP 604 unions, `itertools.pairwise` and `Path.is_relative_to`
(3.9/3.10), plus `pandas>=2.0` / `scipy>=1.11` / `pyarrow>=14` floors that exclude 3.6 on their
own. Backporting is not on the table.

The answer is `uv`, which downloads and manages its own CPython in userspace, **no root needed**:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # installs to ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"
cd soaring-anomalous-transport
uv python install 3.12
uv sync                       # reproduces uv.lock exactly
uv run python -c "import sys, numpy, pandas, scipy, pyarrow; print(sys.version)"
```

Use `uv sync` and not conda: `scripts/check_reproducible.py` asserts byte-for-byte reproduction of
seeded results, and `np.random.default_rng` streams are not stable across numpy majors. The
lockfile is what makes that check meaningful.

### D2. Getting the work across

`main` is level with `origin/main`, but 21 files are modified and 5 untracked (`alt_offset.py`,
`msd_duration.py`, and friends). Commit and push everything, including the untracked figure
modules, before pulling on the other machine — otherwise the re-run silently uses the old code.

### D3. Order of operations there

```bash
export SOARING_PARA_DATA_ROOT=/Volumes/<SSD>/paragliders/ffvl_cfd_igc
export SOARING_DELTA_DATA_ROOT=/Volumes/<SSD>/hang_gliders/delta_cfd_igc
export AUDIT_DIR=/Volumes/<SSD>/derived-audit     # persistent: re-runs cost seconds, not an hour
export PY="uv run python"
```

1. `uv run pytest` — the suite is pinned to the real config, so it is the first check that the new
   thresholds are self-consistent.
2. **Rescan + re-measure (Part A)** — census scan with GNSS columns, `generate_preproc_figure.py`,
   `generate_altitude_noise_figure.py`. These are **not** in `regenerate.sh` and they produce the
   numbers the new bound is read off, so they run *first*.
3. Freeze the measured thresholds into `configs/preprocessing.yaml`, commit.
4. `uv run python scripts/preprocess.py --discipline all` — the full pass. `fixes.parquet` is
   43 GB / 1.36×10⁹ rows for paragliders alone, so plan disk and hours. `--jobs` defaults to
   `min(8, cpu_count)`; raise it on the faster box.
5. `PY="uv run python" scripts/regenerate.sh` — 21 steps. It refuses to start while
   `preprocess.py` is alive or while `<root>/derived/.run_incomplete` exists, so let step 4 finish
   cleanly. Step 1 (`verify_dataset.py`) is the gate; `set -euo pipefail` means a failure there
   stops everything, which is the intended behaviour.
6. `uv run python scripts/reporting/tools/estimate_savgol_timescales.py` and
   `generate_savgol_spectrum_figure.py` — also manual, and their baro/GNSS split changes.
7. Commit the regenerated `thesis/generated/*` and push; finish the prose back here.

---

## Verification

- `uv run pytest` green, including the rewritten vertical-rule tests and the untouched
  `test_no_altitude_rule_ever_deletes_a_fix`.
- `scripts/verify_dataset.py` (step 1) passes on the new tables — it re-checks the speed bound,
  completeness, uniformity, origin, reachability and referential integrity on what was actually
  written.
- `check_generated_macros.py` reports **zero** quoted-but-undefined macros. This is the one that
  turns a missing number into dozens of *Extra }* errors pointing at innocent lines.
- `generate_pipeline_census.py` runs without `SystemExit` — proof the new drop reason is
  registered in `DROP_LABELS`.
- Compare `pipeline_census.tex` before/after and state the retention change explicitly: paragliders
  are at 83.7 % kept today (`\StatPipeParaKept 155788` of `186052`). A large move in
  `DropNoSegmentSurvived` (today 21089, the dominant loss) or a non-trivial count on the new
  no-altitude reason is the signal that a threshold went the wrong way.
- Sanity-check that `n_alt_vz_spike`-equivalent removal fractions did not explode: the whole point
  of the window median is that GNSS noise stops tripping the rule.
- `latexmk -pdf` completes, and `thesis/main.pdf` §2.7.1 reads against the regenerated numbers.
