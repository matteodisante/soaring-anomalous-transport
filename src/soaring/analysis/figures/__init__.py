"""Figure drawing, kept apart from the modules that compute.

A figure module imports from an observable module and never the other way round. That
keeps Matplotlib out of the import path of anything that only needs a number, and it means
a change to a panel cannot silently change an estimator -- which matters here, because the
estimators are what the thesis quotes.

Not every figure lives here. A panel drawn once, by one reduction under
``scripts/reporting/``, stays in that script: the seven ``generate_*_figure.py`` scripts
draw their own, and moving them here would buy an import and no reuse. What this package
holds is the drawing that more than one caller needs, or that a test draws without running
a reduction. The rule above is about the direction of the dependency, not about the
address: no estimator imports Matplotlib, wherever the drawing happens to sit.
"""
