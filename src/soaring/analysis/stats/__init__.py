"""Statistical machinery shared by the observables.

What lives here is the part of an estimate that is not the estimate: how many independent
things went into it, how far it would move on another draw of the data, and what a null
looks like. Those questions have the same answer for every observable in the package, so
they are answered once here rather than differently in each.
"""
