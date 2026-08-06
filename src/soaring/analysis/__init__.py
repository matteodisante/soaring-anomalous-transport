"""Analysis sub-package: turning the acquired dataset into transport statistics.

It holds the pre-processing diagnostics that set the cleaning and flight-level filtering
thresholds (:mod:`soaring.analysis.census`), the seven-stage pipeline that applies them
(:mod:`soaring.analysis.preproc`), the streaming reader over the written tables
(:mod:`soaring.analysis.derived`), the transport estimators
(:mod:`soaring.analysis.observables`) and the clustered bootstrap
(:mod:`soaring.analysis.stats`). Segmentation into flight phases is the work that follows.

The numeric helpers depend only on the core dependencies (``pandas``/``numpy``);
figure generation additionally needs ``matplotlib``/``scipy``/``pyarrow``, installed via
the ``analysis`` uv dependency group (on by default -- see ``[tool.uv] default-groups``
in ``pyproject.toml``; a plain pip install needs them added explicitly, e.g.
``pip install --group analysis``).
"""
