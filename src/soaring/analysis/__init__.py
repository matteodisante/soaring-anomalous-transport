"""Analysis sub-package: turning the acquired dataset into transport statistics.

Today it holds the pre-processing diagnostics that set the cleaning and flight-level
filtering thresholds (:mod:`soaring.analysis.preprocessing`). Heavier analyses
(segmentation, transport observables) will be added here as the work proceeds.

The numeric helpers depend only on the core dependencies (``pandas``/``numpy``);
figure generation additionally needs ``matplotlib``, installed via the optional
``analysis`` extra (``pip install -e .[analysis]``).
"""
