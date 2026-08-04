"""Transport observables measured on the analysis ensemble.

One module per family of observable, each computing and returning numbers -- never
drawing. The figures that read them live in :mod:`soaring.analysis.figures`, so that an
estimator can be imported, tested and quoted without Matplotlib, and so that a change to a
panel cannot reach a number the thesis states.
"""
