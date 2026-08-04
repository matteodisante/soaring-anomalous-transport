"""Figure drawing, kept apart from the modules that compute.

A figure module imports from an observable module and never the other way round. That
keeps Matplotlib out of the import path of anything that only needs a number, and it means
a change to a panel cannot silently change an estimator -- which matters here, because the
estimators are what the thesis quotes.
"""
