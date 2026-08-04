# Prompt — the total verification pass

Run this **only after every implementation task in `PROMPT.md` is finished**. It verifies;
it does not build. If it finds something unbuilt, that is a finding, not a task to absorb.

---

## 0. What this is, and the standard

One pass over the whole repository and the whole thesis, at doctoral standard and above:
every word, every comma, every claim, every line of code. Keep what should be kept, change
what should be changed, delete what should be deleted.

The thesis must end up **dry but clear** — nothing that does not earn its place, and
nothing removed that a reader needs. The code must be **comprehensible** — a reader who
has never seen it should be able to say what each module does and why it does it that way.

**Question everything, then question it again.** The strongest evidence that this pass is
working is that it finds things wrong. This session alone found: a factor-two error in a
synthetic generator that no exponent test would have caught; a headline claim ("the
time-averaged MSD is a power law") refuted by a runs test on its own residuals; a
false-positive test that was circular by construction; and a long-lag scaling regime that
turned out to be the scoring rule rather than the transport. Assume there are more.

**A finding is not a failure.** Report what is wrong plainly, fix what can be fixed, and
where a claim does not survive, withdraw it in the text rather than softening it.

---

## 1. Verification of the numbers

Nothing in the thesis is believed because it was computed. Each of these is a separate
check and each has to be run.

### 1.1 Every quoted number traces to a generator

Extract every `\Stat*` and `\Preproc*` macro the thesis quotes and, for each, name the
script that writes it and the data it reads. `check_generated_macros.py` proves the macro
exists; it does not prove the macro means what the sentence around it says. Read each
quoted number **in its sentence** and ask whether the sentence is a true statement about
the quantity the generator computes. Two known failure modes, both of which have already
happened here:

- a macro that measures a share **of all steps** quoted as a share **of steps over a
  bound**;
- a macro that measures a **per-flight incidence** quoted as a **volume of data**.

### 1.2 Independent recomputation of the headline numbers

For every number the abstract, the conclusions or a section heading rests on, recompute it
by a **different route** than the generator uses — a different script, a different library
call, a hand computation on a sample. Agreement to the quoted precision is the pass
condition; disagreement anywhere is a stop.

### 1.3 Statistical claims

For each fitted exponent, crossover, ratio or rate in the thesis:

- Is the uncertainty the right *kind* — sampling, or goodness of fit? They answer different
  questions and this thesis has already confused them once.
- Is the denominator right? Flights cluster by day and site; a bootstrap over flights
  reports an error bar that is too small, and by one to two orders of magnitude.
- Is the number of independent points what the fit assumed? A curve of eighty lags whose
  residuals are correlated carries a handful.
- Is the precision claimed defensible? Any exponent quoted tighter than the resolution
  budget allows is a reporting error, however honestly it was computed.
- Does a *null* exist for it, and is that null non-circular? A surrogate built from the
  residuals of a bent curve tests the curve against its own structure.

### 1.4 Reproducibility, end to end

`regenerate.sh` from a clean state, then confirm every regenerated macro is byte-identical
to the committed one. `check_reproducible.py` on a fresh sample. `pytest` in full. A clean
`git status` afterwards, so that nothing quoted depends on an uncommitted local file.

### 1.5 The provenance of every figure

For each figure: which script drew it, from which data, and does its caption describe what
the axes actually show? Render every figure **from the PDF** — a `savefig` PNG is not what
the reader sees, and at least one figure in this repository was correct as a PNG and empty
as a PDF.

---

## 2. Verification of the argument

Numbers can each be right while the argument built on them is wrong.

### 2.1 Claim inventory

Build a list of every claim the thesis makes — one line each, with its section. For each:
what evidence supports it, is that evidence in the document, and is the claim *no stronger
than* the evidence. Mark every claim as **measured**, **argued** or **assumed**, and check
that the text's language matches the mark. "Shows", "establishes" and "suggests" are not
interchangeable.

### 2.2 The chain from raw data to conclusion

Follow one flight from the `.igc` file to every number it contributes to. At each stage ask
what could make the output wrong and whether anything in the document would catch it.
Anywhere the answer is "nothing would catch it", either add the check or say so in the
text.

### 2.3 Adversarial reading

Read the thesis as a hostile examiner whose job is to find the weakest claim and break it.
Write down the three questions you would ask that the document does not answer, and then
answer them — in the document, not in the report.

### 2.4 Internal consistency

Every number that appears twice must be the same number. Every cross-reference must point
where the sentence says it points. Every forward reference must be to something that
exists. Every claim in an abstract or conclusion must be supported by the section it
summarises. Every "as shown in Sec. X" must actually be shown there.

---

## 3. Verification of the writing

The target: scientific, clean, minimal, effective, clear, rigorous, pleasant to read. Dry
but not obscure.

### 3.1 Register

Sweep the whole document for AI-flavoured prose and remove it: narrativized or question
headings, aphorism set-ups, meta-commentary about what the text is doing, sustained
metaphors, antithesis density (`X, not Y` in successive paragraphs), triads, em-dash
chains, throat-clearing openings, and any sentence whose work is rhetorical rather than
informational.

**Compactness comes from moving material, not from compressing explanations.** A concept
that needs three paragraphs gets three. A concept that needed three because it was written
loosely gets one. If cutting a sentence loses a reader, it stays.

### 3.2 Every sentence earns its place

Read the thesis sentence by sentence. For each: does it say something the reader needs at
this point? Would the paragraph be worse without it? Delete what fails, and be willing to
delete a sentence you like.

### 3.3 Structure and page density

No page should be an undivided block of text. Paragraphs carry one idea. Headings mark
where the argument turns. A sentence that enumerates becomes a list or a table. White space
corresponds to a break in the reasoning, not to a float landing.

### 3.4 Typesetting

Every float within the text block and near its reference. No overfull or underfull boxes,
no orphans or widows, no table wider than the text block, no verbatim run breaking the
margin. **Check by looking at rendered pages, not only at the log** — a `table` float
taller than the page overflows silently and `pdflatex` reports nothing.

### 3.5 What belongs where

The body carries the argument and the numbers; the implementation appendix carries module
names, parameter derivations, numerical procedures and failure modes; a derivation long
enough to interrupt the body gets its own appendix. Decide each case by what a reader
following the argument needs *at that point*. If the answer is a pointer, make it a pointer.

---

## 4. Verification of the code

### 4.1 Correctness

- Every estimator validated against a process whose answer is known — and the generator of
  that process validated too. A generator with a scale error is invisible to an exponent
  test.
- Every numerical routine checked at its boundaries: empty input, one sample, all-NaN, a
  single cluster, a degenerate fit.
- Every place the code assumes something about the data — sortedness, uniformity,
  positivity, independence — either asserted or documented as a precondition.
- Every `except` that swallows an error justified in a comment or removed.

### 4.2 Comprehensibility

A module docstring says what the module is for and why it exists as a separate module. A
function docstring says what it returns and what it assumes. A comment explains *why*, not
*what* — the code says what. Delete comments that restate the line below them.

Names say what the thing is. A reader should not have to trace a variable to learn its
units; where units matter, they are in the name or stated in the docstring.

### 4.3 Structure

No module doing three unrelated things. Computation separated from drawing. No duplicated
logic between a script and a module. No dead code, no unused macro, no script with no
caller that is not documented as a standalone tool.

### 4.4 The tests

Do the tests test behaviour or implementation? Would each test fail if the thing it names
were broken? Is there a test for each failure this project has actually had? A bug found
once and not pinned by a test will return.

---

## 5. Verification of the documentation

Every claim in `docs/` true of the code as it is now. The three-place contract aligned.
Every command in a guide actually runs. Every file described in `data-on-disk.md` present
with the columns claimed. The logbook's Next-steps section in step with the thesis, which a
hook checks and which has drifted twice.

---

## 6. Deletion

Delete: superseded documents, dead code, unused macros, figures nothing references,
scripts nothing calls and nothing documents, stale comments, obsolete TODOs, and any file
whose only reason to exist is that it once did.

Keep: anything unique and unreproducible — supervision records, raw inputs, the analysis
plans. When in doubt, keep it and say why in the report.

---

## 7. How to work

**Slowly.** This pass is worth nothing done quickly. Read, check, question, check again.

**Techniques, all of them.** Independent recomputation. Adversarial reading. Boundary
testing. Surrogate and null testing. Cross-validation between methods that should agree.
Rendering and looking. Reading the code as a stranger. Asking what would have to be true
for a claim to be false, and then testing that.

**Question your own corrections.** A fix made in this pass is as capable of being wrong as
the thing it fixed, and it has had less scrutiny. Verify the fix by the same standard.

## 8. Reporting

One report, organised by the sections above. For each finding: what it is, how it was
found, what it changes, and whether it is fixed. Separate **confirmed** (checked here) from
**suspected** (argued but not checked) and never present the second as the first. List
explicitly what could not be verified and why.

End with the single most likely remaining way the thesis is wrong, and say what would be
needed to rule it out.

Then: `pytest`, `check_generated_macros.py`, `check_reproducible.py`, a full
`regenerate.sh`, a clean thesis and logbook build, and a clean `git status`.
