"""Prepare, but do not apply, the requested section split during numerical recovery."""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'thesis/sections/04-global-transport.tex'
original = SOURCE.read_text()
old_heading = r'''\section{Anisotropy, dependence and the environment}
\label{sec:transport-axisroutes}
\label{sec:transport-anisotropy}

'''
assert original.count(old_heading) == 1
start = original.index(r'\subsection{East--north balance in the retained archive}')
end = original.index(r'\subsection{Testing east, north and radial scaling}')
balance = original[start:end]
draft = original[:start] + original[end:]
draft = draft.replace(old_heading, r'''\section{Vector scaling and dependence}
\label{sec:transport-vector-scaling}

The radial quantiles describe displacement magnitude. We now ask whether the
same rescaling describes the signed east--north vector, including its dependence
structure. The population and origin controls of
Sec.~\ref{sec:quantile-population} remain fixed throughout this comparison.
An anisotropic distribution can obey a common scalar rescaling; isotropy is not
an assumption of the test.

''', 1)
pca = r'\subsection{Regional principal axes}'
assert draft.count(pca) == 1
environment = r'''\FloatBarrier
\section{Directional structure, terrain and equipment}
\label{sec:transport-axisroutes}
\label{sec:transport-anisotropy}
\label{sec:transport-environment}

We next ask how directional structure varies across take-off regions and equipment
groups, and which environmental interpretations these contrasts can support.
The quantities differ from the fixed-population collapse test: launch-time
second moments describe mean motion and spread together, whereas regional
increment covariances describe centred spread over a lag. Their clocks, weighting
and contributing flights must therefore be specified before comparing them.

'''
draft = draft.replace(pca, environment + balance + pca, 1)
# Population composition is evidence needed by the subsequent model comparison.
# Move the complete block intact so the argument does not return to a prerequisite
# after giving its model verdict.
duration_start = draft.index('\\FloatBarrier\n\\section{Flight duration and equipment composition}')
duration_end = draft.index('\\FloatBarrier\n\\section{Constraints for the phase analysis}')
duration = draft[duration_start:duration_end]
draft = draft[:duration_start] + draft[duration_end:]
model_start = draft.index('\\FloatBarrier\n\\section{Comparison with stochastic models}')
draft = draft[:model_start] + duration + draft[model_start:]
roadmap = r'''The chapter first defines displacement growth and drift-removing variations.
Quantiles then test scalar rescaling, with a fixed-population control, before the
component and joint laws address vector scaling and dependence. A separate section
examines regional geometry and equipment contrasts. Duration and equipment
composition then check how the observed growth depends on the selected flights.
With those population effects established, moment spectra and velocity memory
provide further constraints for the model comparison.

'''
insert = draft.index(r'\FloatBarrier')
draft = draft[:insert] + roadmap + draft[insert:]
old_labels = Counter(re.findall(r'\\label\{([^}]+)\}', original))
new_labels = Counter(re.findall(r'\\label\{([^}]+)\}', draft))
assert all(new_labels[label] == count for label, count in old_labels.items())
assert new_labels - old_labels == Counter({
    'sec:transport-vector-scaling': 1, 'sec:transport-environment': 1,
})
for environment_name in ('figure', 'equation', 'align'):
    pattern = rf'\\begin\{{{environment_name}\}}.*?\\end\{{{environment_name}\}}'
    assert Counter(re.findall(pattern, original, flags=re.S)) == Counter(
        re.findall(pattern, draft, flags=re.S)
    )
(HERE / 'chapter3-structure-draft.tex').write_text(draft)
patch = ''.join(difflib.unified_diff(
    original.splitlines(keepends=True), draft.splitlines(keepends=True),
    fromfile='a/thesis/sections/04-global-transport.tex',
    tofile='b/thesis/sections/04-global-transport.tex',
))
(HERE / 'chapter3-structure.patch').write_text(patch)
(HERE / 'chapter3-structure-check.json').write_text(json.dumps({
    'status': 'prepared_not_applied',
    'original_source_sha256': hashlib.sha256(original.encode()).hexdigest(),
    'draft_sha256': hashlib.sha256(draft.encode()).hexdigest(),
    'all_existing_labels_preserved': True,
    'all_figure_equation_align_blocks_preserved': True,
    'new_sections': [
        '3.3 Vector scaling and dependence',
        '3.4 Directional structure, terrain and equipment',
    ],
    'additional_reordering': 'Flight duration and equipment composition now precedes Comparison with stochastic models; complete existing blocks and labels preserved.',
    'pending': 'Apply only after numerical completion; reconcile numerical claims, add low-relief results and the hypothesis/criticism discussion, then compile and inspect.',
}, indent=2) + '\n')
print('Prepared section split; canonical manuscript unchanged.')
