#!/usr/bin/env python3
"""Decode flight phases with the transcribed Vilpellet segmenter.

Examples::

    uv run python scripts/segment_flights_vilpellet.py flight \
        --igc /Volumes/SSD_DISANTE/paragliders/ffvl_cfd_igc/raw/igc/2021-2022/\
2021-09-01_20308851.igc
    uv run python scripts/segment_flights_vilpellet.py apply \
        --discipline paragliders --limit 20
    uv run python scripts/segment_flights_vilpellet.py coverage --discipline paragliders

Nothing here fits anything.  The parameters come from
``configs/segmentation_vilpellet.yaml`` and are applied unchanged, so the command has
one job: run the decoder over a flight or an archive and record what it decided.

By default ``apply`` writes the run-interval table and the coverage summary, and not
the fix-level table.  The labels are piecewise constant, so the intervals reconstruct
every per-fix label exactly, and the fix-level table costs about 130 times more on
disk: measured on this archive, 0.18 byte per fix against 24 byte per fix, which is
0.22 GB against 30 GB for the paraglider archive.  Pass ``--with-points`` to write it
anyway, after checking there is room for it.

The ``apply`` and ``coverage`` actions write only below the chosen archive's
``derived/segmentation/vilpellet/`` directory.  They never change the preprocessed
``fixes.parquet`` input, and they never touch the Chapter 4 segmenter's own tables one
directory up.  ``apply`` streams the fix table one flight at a time and flushes its
Parquet writers in bounded batches, so interrupting it leaves a readable prefix of the
archive rather than nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque
from collections.abc import Iterator
from concurrent.futures import Future
from dataclasses import dataclass, field, replace
from itertools import islice
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from soaring.analysis.derived import stream_flights  # noqa: E402
from soaring.analysis.segmentation.pipeline import _append_parquet  # noqa: E402
from soaring.analysis.segmentation.vilpellet import (  # noqa: E402
    UNCLASSIFIED,
    VilpelletConfig,
    VilpelletTrack,
    load_vilpellet_config,
    phase_runs,
    segment_flight,
)
from soaring.analysis.segmentation.vilpellet.features import (  # noqa: E402
    geodetic_to_local_enu,
)
from soaring.reporting import DISCIPLINES  # noqa: E402

# The fix-level table stays small on purpose: it carries the identity of the fix, its
# geometry and its label, and nothing that can be recomputed from the cleaned archive.
POINT_COLUMNS = [
    "source",
    "flight_id",
    "segment_id",
    "t",
    "E",
    "N",
    "z",
    "phase",
    "phase_component",
    "phase_reason",
]
# What the decoder needs to read out of derived/fixes.parquet, and nothing more.
INPUT_COLUMNS = ["source", "flight_id", "segment_id", "t", "E", "N", "z"]

# Flights allowed to sit in the submission window per worker. Two keeps every worker
# fed while one result is being written, without holding much of the archive in memory.
_PENDING_PER_WORKER = 2

# Rows buffered before a Parquet flush.  It bounds memory and it bounds how much work
# an interrupt can throw away.
_PARQUET_BATCH_ROWS = 400_000


@dataclass
class Coverage:
    """Running totals of one ``apply`` pass, or of one re-read of its output.

    Attributes:
        n_flights: Flights decoded.
        n_eligible_flights: Flights in which at least one fix received a phase.
        n_fixes: Fixes seen.
        phase_fixes: Fix count per phase name, including ``unclassified``.
        phase_seconds: Summed run duration per phase name.
        phase_runs: Number of uninterrupted runs per phase name.
        reasons: Fix count per ``phase_reason`` value.
    """

    n_flights: int = 0
    n_eligible_flights: int = 0
    n_fixes: int = 0
    phase_fixes: dict[str, int] = field(default_factory=dict)
    phase_seconds: dict[str, float] = field(default_factory=dict)
    phase_runs: dict[str, int] = field(default_factory=dict)
    reasons: dict[str, int] = field(default_factory=dict)

    def add_points(self, points: pd.DataFrame) -> None:
        """Fold one labelled fix table into the totals.

        Args:
            points: A labelled fix table with ``phase`` and ``phase_reason``.
        """
        self.n_fixes += len(points)
        for phase, count in points["phase"].value_counts().items():
            self.phase_fixes[str(phase)] = self.phase_fixes.get(str(phase), 0) + int(
                count
            )
        if "phase_reason" in points.columns:
            for reason, count in points["phase_reason"].value_counts().items():
                self.reasons[str(reason)] = self.reasons.get(str(reason), 0) + int(
                    count
                )

    def add_counts(
        self,
        n_fixes: int,
        phase_counts: dict[str, int],
        reason_counts: dict[str, int],
    ) -> None:
        """Fold one flight's already-counted fixes into the totals.

        A worker process reduces its flight to these three numbers before returning,
        so the parent never receives a fix table it would only count and discard.

        Args:
            n_fixes: Fixes seen in that flight.
            phase_counts: Fix count per phase name.
            reason_counts: Fix count per ``phase_reason`` value.
        """
        self.n_fixes += n_fixes
        for phase, count in phase_counts.items():
            self.phase_fixes[phase] = self.phase_fixes.get(phase, 0) + count
        for reason, count in reason_counts.items():
            self.reasons[reason] = self.reasons.get(reason, 0) + count

    def add_runs(self, runs: pd.DataFrame) -> None:
        """Fold one run table into the per-phase duration and run totals.

        Args:
            runs: A table with ``phase`` and ``duration_s``.
        """
        if runs.empty:
            return
        grouped = runs.groupby("phase")["duration_s"]
        for phase, seconds in grouped.sum().items():
            self.phase_seconds[str(phase)] = self.phase_seconds.get(
                str(phase), 0.0
            ) + float(seconds)
        for phase, count in grouped.count().items():
            self.phase_runs[str(phase)] = self.phase_runs.get(str(phase), 0) + int(
                count
            )

    def summary(self) -> dict[str, Any]:
        """The coverage record written to ``coverage.json`` and printed.

        Returns:
            A JSON-serialisable summary.  ``fix_fraction`` divides by every fix seen.
            ``time_fraction`` divides by the summed run duration, where a run's
            duration spans its first fix to its last one, so it counts one logging step
            less than the time the run occupies.
        """
        total_seconds = sum(self.phase_seconds.values())
        phases = {}
        for phase in sorted(set(self.phase_fixes) | set(self.phase_seconds)):
            fixes = self.phase_fixes.get(phase, 0)
            seconds = self.phase_seconds.get(phase, 0.0)
            phases[phase] = {
                "n_fixes": fixes,
                "fix_fraction": (fixes / self.n_fixes) if self.n_fixes else 0.0,
                "duration_s": seconds,
                "time_fraction": (seconds / total_seconds) if total_seconds else 0.0,
                "n_runs": self.phase_runs.get(phase, 0),
            }
        return {
            "n_flights": self.n_flights,
            "n_eligible_flights": self.n_eligible_flights,
            "n_fixes": self.n_fixes,
            "labelled_duration_s": total_seconds,
            "phases": phases,
            "reasons": dict(sorted(self.reasons.items())),
        }


_POINT_DTYPES = {
    "source": "string",
    "flight_id": "string",
    "segment_id": "int64",
    "t": "float64",
    "E": "float64",
    "N": "float64",
    "z": "float64",
    "phase": "string",
    "phase_component": "Int64",
    "phase_reason": "string",
}
_SEGMENT_DTYPES = {
    "source": "string",
    "flight_id": "string",
    "segment_id": "int64",
    "phase": "string",
    "t_start": "float64",
    "t_end": "float64",
    "duration_s": "float64",
    "n_fixes": "int64",
    "left_censored": "bool",
    "right_censored": "bool",
}


_COVERAGE_DTYPES = {
    "source": "string",
    "flight_id": "string",
    "segment_id": "int64",
    "t_start": "float64",
    "t_end": "float64",
    "n_native_fixes": "int64",
    "native_cadence_s": "float64",
    "n_classified_fixes": "int64",
    "status": "string",
}


def _coverage_frame(fixes: pd.DataFrame) -> pd.DataFrame:
    """One row per preprocessing segment: its extent, its cadence and its outcome.

    This is what makes the unclassified time auditable. Without it the coverage
    summary says how much time carries no phase but not which segments it came from,
    and a cadence the method cannot serve looks the same as a decoding that failed.

    Args:
        fixes: One flight's labelled fix table.

    Returns:
        A table holding :data:`_COVERAGE_DTYPES`.
    """
    rows: list[dict[str, Any]] = []
    for segment_id, group in fixes.groupby("segment_id", sort=True):
        t = group["t"].to_numpy(dtype=float)
        steps = np.diff(t)
        classified = group["phase"].ne(UNCLASSIFIED)
        rows.append(
            {
                "source": group["source"].iloc[0] if "source" in group else pd.NA,
                "flight_id": (
                    group["flight_id"].iloc[0] if "flight_id" in group else pd.NA
                ),
                "segment_id": int(segment_id),
                "t_start": float(t[0]),
                "t_end": float(t[-1]),
                "n_native_fixes": len(group),
                "native_cadence_s": (
                    float(np.median(steps)) if steps.size else float("nan")
                ),
                "n_classified_fixes": int(classified.sum()),
                # A fully classified segment records that; otherwise the reason the
                # first unlabelled fix carries, which is the segment's own verdict.
                "status": (
                    "classified"
                    if bool(classified.all())
                    else str(group.loc[~classified, "phase_reason"].iloc[0])
                ),
            }
        )
    return pd.DataFrame(rows, columns=list(_COVERAGE_DTYPES)).astype(_COVERAGE_DTYPES)


def _write_parameters(
    output_dir: Path, config: VilpelletConfig, discipline: str
) -> Path:
    """Record the exact parameters this export was produced with.

    The Chapter 4 segmenter saves its fitted model beside its tables. Nothing is
    fitted here, so the equivalent record is the parameter set that was applied, which
    makes the export self-describing and lets a later reader tell whether a change to
    the configuration invalidated it.

    Args:
        output_dir: The Vilpellet output directory.
        config: The loaded protocol.
        discipline: The discipline the export covers.

    Returns:
        The path written.
    """
    model_dir = output_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "provenance": (
            "Fitted once by Vilpellet with Baum-Welch on 2019 paraglider flights from "
            "four Alpine take-off sites, and applied here unchanged. Nothing in this "
            "repository re-estimates any of it."
        ),
        "discipline": discipline,
        "alpha_straight_rad": config.alpha_for(discipline),
        "state_names": list(config.state_names),
        "features": {
            "position_smoothing_fixes": config.features.position_smoothing_fixes,
            "turn_smoothing_fixes": config.features.turn_smoothing_fixes,
            "persistence_fixes": config.features.persistence_fixes,
            "beta_persistence": config.features.beta_persistence,
        },
        "majority_fixes": config.majority_fixes,
        "eligibility": {
            "max_mean_dt_s": config.eligibility.max_mean_dt_s,
            "min_fixes": config.eligibility.min_fixes,
        },
        "input": {
            "source": config.input_policy.source,
            "pre_smooth": config.input_policy.pre_smooth,
        },
        "recommendations_active": config.recommendations.active,
        "parameters": {
            "emission": config.parameters.emission.tolist(),
            "transition": config.parameters.transition.tolist(),
            "initial": config.parameters.initial.tolist(),
        },
    }
    path = model_dir / "parameters.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", "utf-8")
    return path


def _empty(dtypes: dict[str, str]) -> pd.DataFrame:
    """An empty table carrying the dtypes a reader of the written file expects.

    A pass that decodes nothing still has to leave a readable table behind, so that a
    later read fails on the absence of rows rather than on the absence of a schema.

    Args:
        dtypes: Column name to dtype.

    Returns:
        The empty table.
    """
    return pd.DataFrame(
        {name: pd.Series(dtype=dtype) for name, dtype in dtypes.items()}
    )


def _paths(discipline: str) -> tuple[Path, Path]:
    """Resolve the fix table and the Vilpellet output directory of one discipline.

    Args:
        discipline: A key of :data:`soaring.reporting.DISCIPLINES`.

    Returns:
        The ``derived/fixes.parquet`` path and the ``derived/segmentation/vilpellet``
        directory.

    Raises:
        FileNotFoundError: If the archive is not currently reachable.
    """
    derived = DISCIPLINES[discipline].derived_dir()
    if derived is None:
        raise FileNotFoundError(f"{discipline}: derived/fixes.parquet is not reachable")
    return derived / "fixes.parquet", derived / "segmentation" / "vilpellet"


def _point_frame(fixes: pd.DataFrame) -> pd.DataFrame:
    """Reduce a labelled fix table to the stored columns, with stable dtypes.

    A Parquet writer opened on the first flight's schema rejects a later flight whose
    columns differ in type, so the dtypes are pinned here rather than inherited from
    whatever the first flight happened to hold.

    Args:
        fixes: The labelled fix table of one flight.

    Returns:
        A new table holding :data:`POINT_COLUMNS`.
    """
    out = pd.DataFrame(index=pd.RangeIndex(len(fixes)))
    source = fixes.reset_index(drop=True)
    for column in ("source", "flight_id", "phase", "phase_reason"):
        out[column] = (
            source[column].astype("string")
            if column in source.columns
            else pd.Series(pd.NA, index=out.index, dtype="string")
        )
    out["segment_id"] = source["segment_id"].astype("int64")
    for column in ("t", "E", "N", "z"):
        out[column] = (
            source[column].astype("float64")
            if column in source.columns
            else pd.Series(np.nan, index=out.index, dtype="float64")
        )
    out["phase_component"] = source["phase_component"].astype("Int64")
    return out.loc[:, POINT_COLUMNS]


def _segment_frame(runs: pd.DataFrame) -> pd.DataFrame:
    """Pin the run table's dtypes for the same reason :func:`_point_frame` does.

    Args:
        runs: The output of
            :func:`soaring.analysis.segmentation.vilpellet.phase_runs`.

    Returns:
        The same rows with stable dtypes.
    """
    out = runs.reset_index(drop=True).copy()
    for column in ("source", "flight_id", "phase"):
        out[column] = out[column].astype("string")
    out["segment_id"] = out["segment_id"].astype("int64")
    for column in ("t_start", "t_end", "duration_s"):
        out[column] = out[column].astype("float64")
    out["n_fixes"] = out["n_fixes"].astype("int64")
    for column in ("left_censored", "right_censored"):
        out[column] = out[column].astype("bool")
    return out


def _raw_gnss_track(
    igc_path: Path, discipline_source: str, flight_id: str
) -> pd.DataFrame:
    """Build a decodable table from the GNSS channel of one IGC file.

    This is the input the reference implementation consumes: latitude, longitude and
    GNSS altitude straight out of the file, with none of this repository's cleaning.
    Fixes without a usable coordinate triple are dropped, because the geodetic
    projection has nothing to place them at.  The whole file becomes one segment, so
    the eligibility gate sees the recording exactly as it was logged.

    Args:
        igc_path: The ``.igc`` file.
        discipline_source: The value the ``source`` column takes.
        flight_id: The identifier to label the rows with.

    Returns:
        A table with the identity columns, ``t``, ``E``, ``N`` and ``z``.

    Raises:
        ValueError: If no fix carries a complete coordinate triple.
    """
    from soaring.viewer.data import load_raw

    raw = load_raw(igc_path).fixes
    usable = raw.loc[
        np.isfinite(raw["lat"].to_numpy(dtype=float))
        & np.isfinite(raw["lon"].to_numpy(dtype=float))
        & np.isfinite(raw["alt"].to_numpy(dtype=float))
    ].reset_index(drop=True)
    if usable.empty:
        raise ValueError(f"{igc_path}: no fix carries latitude, longitude and altitude")
    enu = geodetic_to_local_enu(
        usable["lat"].to_numpy(dtype=float),
        usable["lon"].to_numpy(dtype=float),
        usable["alt"].to_numpy(dtype=float),
    )
    return pd.DataFrame(
        {
            "source": discipline_source,
            "flight_id": flight_id,
            "segment_id": 0,
            "t": usable["t"].to_numpy(dtype=float),
            "E": enu[:, 0],
            "N": enu[:, 1],
            "z": enu[:, 2],
        }
    )


def _cleaned_track(
    igc_path: Path, discipline_source: str, discipline_name: str, flight_id: str
) -> pd.DataFrame:
    """Run the preprocessing pipeline over one IGC file and return its cleaned fixes.

    Args:
        igc_path: The ``.igc`` file.
        discipline_source: The value the ``source`` column takes.
        discipline_name: The discipline key the speed bound is stored under.
        flight_id: The identifier to label the rows with.

    Returns:
        The retained cleaned fixes.

    Raises:
        ValueError: If a cleaning gate dropped the flight, so there is no trajectory.
    """
    from soaring.viewer.data import load_cleaned

    result = load_cleaned(
        igc_path,
        source=discipline_source,
        flight_id=flight_id,
        discipline=discipline_name,
    )
    if not result.kept:
        raise ValueError(
            f"{igc_path.name}: dropped at cleaning stage {result.meta.drop_stage} "
            f"({result.meta.drop_reason}), so there is no cleaned trajectory to decode"
        )
    return result.fixes


def _print_flight_summary(
    track: VilpelletTrack, runs: pd.DataFrame, *, label: str
) -> dict[str, Any]:
    """Print one flight's phase composition and return the same numbers.

    Args:
        track: The decoded flight.
        runs: Its run table.
        label: What to call the flight in the printed heading.

    Returns:
        The coverage summary of this one flight.
    """
    coverage = Coverage()
    coverage.n_flights = 1
    coverage.n_eligible_flights = int(track.eligible)
    coverage.add_points(track.fixes)
    coverage.add_runs(runs)
    summary = coverage.summary()
    span = float(track.fixes["t"].max() - track.fixes["t"].min())
    print(f"{label}: {summary['n_fixes']} fixes over {span / 60.0:.1f} min")
    print(
        f"  discipline {track.discipline}, "
        f"alpha = {track.alpha_straight_rad:.8f} rad/fix, "
        f"eligible = {track.eligible}"
    )
    print(f"  {'phase':<14}{'fixes':>9}{'fix frac':>10}{'time frac':>11}{'runs':>7}")
    for phase, record in summary["phases"].items():
        print(
            f"  {phase:<14}{record['n_fixes']:>9}"
            f"{record['fix_fraction']:>10.3f}{record['time_fraction']:>11.3f}"
            f"{record['n_runs']:>7}"
        )
    print("  reasons: " + ", ".join(f"{k}={v}" for k, v in summary["reasons"].items()))
    return summary


def _write_tables(
    output_dir: Path, points: pd.DataFrame, runs: pd.DataFrame
) -> tuple[Path, Path]:
    """Write one flight's tables into a directory, replacing whatever was there.

    Args:
        output_dir: Destination directory.
        points: The labelled fix table.
        runs: The run table.

    Returns:
        The two paths written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    points_path = output_dir / "phase_points.parquet"
    runs_path = output_dir / "phase_segments.parquet"
    _point_frame(points).to_parquet(points_path, index=False)
    _segment_frame(runs).to_parquet(runs_path, index=False)
    return points_path, runs_path


def run_flight(args: argparse.Namespace, config: VilpelletConfig) -> int:
    """Decode one IGC file and report what the segmenter made of it.

    Args:
        args: The parsed command line.
        config: The loaded protocol.

    Returns:
        The process exit status.

    Raises:
        SystemExit: If no discipline can be resolved for the given path.
    """
    from soaring.viewer.data import resolve_discipline

    igc_path = Path(args.igc).expanduser()
    discipline = (
        DISCIPLINES[args.discipline]
        if args.discipline
        else resolve_discipline(igc_path)
    )
    if discipline is None:
        raise SystemExit(
            f"{igc_path}: outside both configured archives, so pass --discipline"
        )
    flight_id = igc_path.stem
    source = args.input or config.input_policy.source
    if source == "raw_gnss":
        fixes = _raw_gnss_track(igc_path, discipline.source, flight_id)
    else:
        fixes = _cleaned_track(
            igc_path, discipline.source, discipline.name, flight_id
        )
    track = segment_flight(fixes, config, discipline=discipline.name)
    runs = phase_runs(track.fixes, config)
    _print_flight_summary(track, runs, label=f"{flight_id} [{source}]")
    if args.out is not None:
        points_path, runs_path = _write_tables(
            Path(args.out).expanduser(), track.fixes, runs
        )
        print(f"  wrote {points_path}")
        print(f"  wrote {runs_path}")
    return 0


# Set once per worker process by :func:`_worker_init`, so the configuration and the
# discipline are shipped across the process boundary once instead of once per flight.
_WORKER: dict[str, Any] = {}


def _worker_init(config: VilpelletConfig, discipline: str, with_points: bool) -> None:
    """Install one worker's decoding context.

    Args:
        config: The loaded protocol.
        discipline: The discipline whose straightness threshold applies.
        with_points: Whether the fix-level frame should be returned as well.
    """
    # Each worker is one flight at a time on one core, so a nested BLAS thread pool on
    # top of that would oversubscribe the machine. On the development machine it does
    # not: NumPy links against Apple's Accelerate framework, whose matrix kernels run
    # from a single thread on the AMX coprocessor, and a 3000x3000 matmul was measured
    # at 99.6% CPU with these variables unset against 92.2% with them set. They are
    # kept because the guarantee should not depend on which BLAS a given checkout
    # happens to link against, and because they cost nothing. The oversubscription
    # this pass actually had to avoid was memory, not threads; see `_decoded_flights`.
    for variable in (
        "VECLIB_MAXIMUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
    ):
        os.environ[variable] = "1"
    _WORKER["config"] = config
    _WORKER["discipline"] = discipline
    _WORKER["with_points"] = with_points


def _decode_one(flight: pd.DataFrame) -> dict[str, Any]:
    """Decode one flight and reduce it to what the writer and the totals need.

    Args:
        flight: One flight's rows of :data:`INPUT_COLUMNS`.

    Returns:
        The frames to append and the counts to fold in.
    """
    config: VilpelletConfig = _WORKER["config"]
    track = segment_flight(flight, config, discipline=_WORKER["discipline"])
    runs = phase_runs(track.fixes, config)
    return {
        "points": _point_frame(track.fixes) if _WORKER["with_points"] else None,
        "runs": runs,
        "coverage": _coverage_frame(track.fixes),
        "n_fixes": len(track.fixes),
        "eligible": bool(track.eligible),
        "phase_counts": {
            str(k): int(v) for k, v in track.fixes["phase"].value_counts().items()
        },
        "reason_counts": {
            str(k): int(v)
            for k, v in track.fixes["phase_reason"].value_counts().items()
        },
    }


def _decoded_flights(
    fixes_path: Path,
    config: VilpelletConfig,
    discipline: str,
    *,
    with_points: bool,
    limit: int | None,
    jobs: int,
) -> Iterator[dict[str, Any]]:
    """Yield decoded flights in archive order, on one core or on several.

    Order is preserved whichever path runs, so the written tables do not depend on how
    many workers the machine happened to give the pass.

    Args:
        fixes_path: The archive's ``fixes.parquet``.
        config: The loaded protocol.
        discipline: The discipline being decoded.
        with_points: Whether to build the fix-level frame.
        limit: Stop after this many flights, or ``None`` for the whole archive.
        jobs: Worker processes; one runs everything in this process.

    Yields:
        One :func:`_decode_one` result per flight.
    """
    flights = stream_flights(fixes_path, INPUT_COLUMNS)
    if limit is not None:
        flights = islice(flights, limit)
    if jobs <= 1:
        _worker_init(config, discipline, with_points)
        yield from map(_decode_one, flights)
        return
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(
        max_workers=jobs,
        initializer=_worker_init,
        initargs=(config, discipline, with_points),
    ) as pool:
        # Deliberately not `pool.map`. `Executor.map` builds its future list eagerly
        # (`[self.submit(...) for args in ...]` in CPython), so over a 156,000-flight
        # archive it tries to hold every flight's fixes in the parent at once: the
        # paraglider pass was killed by the operating system for it. This window keeps
        # at most `jobs * _PENDING_PER_WORKER` flights resident, which bounds memory by
        # the worker count rather than by the archive, and still hands results back in
        # archive order because the queue is drained from its head.
        pending: deque[Future[dict[str, Any]]] = deque()
        iterator = iter(flights)
        for flight in islice(iterator, jobs * _PENDING_PER_WORKER):
            pending.append(pool.submit(_decode_one, flight))
        while pending:
            result = pending.popleft().result()
            next_flight = next(iterator, None)
            if next_flight is not None:
                pending.append(pool.submit(_decode_one, next_flight))
            yield result


def _default_jobs() -> int:
    """A worker count that leaves headroom for the rest of the machine.

    Two cores are reserved so the interactive session (an editor, a browser, this
    very shell) stays responsive while an archive-wide pass runs in the background.

    Returns:
        At least one worker, however few cores the machine reports.
    """
    total = os.cpu_count() or 1
    return max(1, total - 2)


def _write_coverage(output_dir: Path, record: dict[str, Any]) -> Path:
    """Write ``coverage.json`` and echo it.

    Args:
        output_dir: The Vilpellet output directory.
        record: The summary to write.

    Returns:
        The path written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "coverage.json"
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    print(text)
    return path


def run_apply(args: argparse.Namespace, config: VilpelletConfig) -> int:
    """Decode an archive flight by flight, appending to the two Parquet tables.

    The fix table is read one flight at a time, so peak memory stays bounded by one row
    group plus the flights in flight, whatever the size of the archive. Decoding one
    flight does not depend on any other, so it runs across several worker processes by
    default (see :func:`_default_jobs`); results are still written in archive order, so
    the number of workers changes only how fast the pass runs, never what it writes. An
    interrupt flushes the buffered rows, closes the writers and records how far the
    pass got.

    Args:
        args: The parsed command line.
        config: The loaded protocol.

    Returns:
        The process exit status.
    """
    fixes_path, output_dir = _paths(args.discipline)
    output_dir.mkdir(parents=True, exist_ok=True)
    points_path = output_dir / "phase_points.parquet"
    runs_path = output_dir / "phase_segments.parquet"
    coverage_path = output_dir / "phase_coverage.parquet"
    # A Parquet writer opens its file at the first flush, so a pass that stops before
    # one would otherwise leave the previous run's tables beside this run's coverage.
    # Removing them first keeps the directory telling one story.
    write_points = bool(getattr(args, "with_points", False))
    points_path.unlink(missing_ok=True)
    runs_path.unlink(missing_ok=True)
    coverage_path.unlink(missing_ok=True)
    point_writer: Any | None = None
    run_writer: Any | None = None
    point_schema: Any | None = None
    run_schema: Any | None = None
    segment_writer: Any | None = None
    segment_schema: Any | None = None
    point_buffer: list[pd.DataFrame] = []
    run_buffer: list[pd.DataFrame] = []
    segment_buffer: list[pd.DataFrame] = []
    point_rows = run_rows = segment_rows = 0
    coverage = Coverage()
    interrupted = False
    jobs = getattr(args, "jobs", None) or _default_jobs()
    try:
        for flight_result in _decoded_flights(
            fixes_path,
            config,
            args.discipline,
            with_points=write_points,
            limit=args.limit,
            jobs=jobs,
        ):
            runs = flight_result["runs"]
            coverage.n_flights += 1
            coverage.n_eligible_flights += int(flight_result["eligible"])
            coverage.add_counts(
                flight_result["n_fixes"],
                flight_result["phase_counts"],
                flight_result["reason_counts"],
            )
            coverage.add_runs(runs)
            if write_points and flight_result["points"] is not None:
                point_buffer.append(flight_result["points"])
                point_rows += len(flight_result["points"])
            segment_coverage = flight_result["coverage"]
            if not segment_coverage.empty:
                segment_buffer.append(segment_coverage)
                segment_rows += len(segment_coverage)
            if not runs.empty:
                run_buffer.append(_segment_frame(runs))
                run_rows += len(runs)
            if point_rows >= _PARQUET_BATCH_ROWS:
                point_writer, point_schema = _append_parquet(
                    point_writer,
                    points_path,
                    pd.concat(point_buffer, ignore_index=True),
                    point_schema,
                )
                point_buffer, point_rows = [], 0
            if run_rows >= _PARQUET_BATCH_ROWS:
                run_writer, run_schema = _append_parquet(
                    run_writer,
                    runs_path,
                    pd.concat(run_buffer, ignore_index=True),
                    run_schema,
                )
                run_buffer, run_rows = [], 0
            if segment_rows >= _PARQUET_BATCH_ROWS:
                segment_writer, segment_schema = _append_parquet(
                    segment_writer,
                    coverage_path,
                    pd.concat(segment_buffer, ignore_index=True),
                    segment_schema,
                )
                segment_buffer, segment_rows = [], 0
            if coverage.n_flights % 200 == 0:
                print(
                    f"{args.discipline}: {coverage.n_flights} flights, "
                    f"{coverage.n_fixes} fixes",
                    flush=True,
                )
    except KeyboardInterrupt:
        interrupted = True
        print(
            f"\n{args.discipline}: interrupted after {coverage.n_flights} flights; "
            "flushing what was decoded",
            flush=True,
        )
    if point_buffer:
        point_writer, point_schema = _append_parquet(
            point_writer,
            points_path,
            pd.concat(point_buffer, ignore_index=True),
            point_schema,
        )
    if run_buffer:
        run_writer, run_schema = _append_parquet(
            run_writer,
            runs_path,
            pd.concat(run_buffer, ignore_index=True),
            run_schema,
        )
    if segment_buffer:
        segment_writer, segment_schema = _append_parquet(
            segment_writer,
            coverage_path,
            pd.concat(segment_buffer, ignore_index=True),
            segment_schema,
        )
    if point_writer is not None:
        point_writer.close()
    elif write_points:
        _empty(_POINT_DTYPES).to_parquet(points_path, index=False)
    if run_writer is None:
        _empty(_SEGMENT_DTYPES).to_parquet(runs_path, index=False)
    else:
        run_writer.close()
    if segment_writer is None:
        _empty(_COVERAGE_DTYPES).to_parquet(coverage_path, index=False)
    else:
        segment_writer.close()
    _write_parameters(output_dir, config, args.discipline)
    record = coverage.summary()
    record.update(
        {
            "discipline": args.discipline,
            "fixes_path": str(fixes_path),
            "limit": args.limit,
            "interrupted": interrupted,
            "config_path": (
                str(args.config)
                if args.config
                else "configs/segmentation_vilpellet.yaml"
            ),
            "alpha_straight_rad": config.alpha_for(args.discipline),
            "source": "apply",
        }
    )
    written = (
        f"{runs_path.name}, {coverage_path.name}, model/parameters.json"
        + (f" and {points_path.name}" if write_points else "")
        + ("" if write_points else " (pass --with-points for the fix-level table)")
    )
    print(f"{args.discipline}: wrote {written}")
    _write_coverage(output_dir, record)
    return 0


def _stream_column_counts(path: Path, columns: list[str]) -> Coverage:
    """Re-read a written table row group by row group, folding it into a coverage.

    Args:
        path: The ``phase_points.parquet`` to read.
        columns: The columns to read out of it.

    Returns:
        The accumulated coverage, with the run-derived fields still empty.
    """
    import pyarrow.parquet as pq

    coverage = Coverage()
    parquet = pq.ParquetFile(path)
    flights: set[str] = set()
    eligible: set[str] = set()
    for group in range(parquet.metadata.num_row_groups):
        frame = parquet.read_row_group(group, columns=columns).to_pandas()
        if frame.empty:
            continue
        coverage.add_points(frame)
        flights.update(frame["flight_id"].astype(str).unique().tolist())
        labelled = frame.loc[frame["phase"] != UNCLASSIFIED, "flight_id"]
        eligible.update(labelled.astype(str).unique().tolist())
    coverage.n_flights = len(flights)
    coverage.n_eligible_flights = len(eligible)
    return coverage


def _coverage_from_segment_table(path: Path) -> Coverage:
    """Recover flight and fix totals from ``phase_coverage.parquet`` alone.

    Every fix of one preprocessing segment gets the same ``phase_reason``: the
    segmenter classifies a whole eligible segment or excludes it for one uniform
    reason (:func:`soaring.analysis.segmentation.vilpellet.pipeline.segment_flight`),
    so ``status`` here determines every one of its fixes' fate exactly. That no longer
    holds once the author's optional run-selection recommendations are active
    (``configs/segmentation_vilpellet.yaml``'s ``recommendations`` block), which can
    unclassify part of an otherwise-eligible segment; the classified/unclassified
    split stays exact even then (``n_classified_fixes`` is read after those
    recommendations run), but the breakdown across *why* a fix was excluded can then
    undercount a reason that only applies to part of a segment. Flight and fix totals
    are exact in every case: this table has one row per segment and no fix-level
    detail to lose.

    Args:
        path: The ``phase_coverage.parquet`` to read.

    Returns:
        The accumulated coverage, with the run-derived fields still empty.
    """
    import pyarrow.parquet as pq

    coverage = Coverage()
    parquet = pq.ParquetFile(path)
    flights: set[str] = set()
    eligible: set[str] = set()
    columns = ["flight_id", "n_native_fixes", "n_classified_fixes", "status"]
    for group in range(parquet.metadata.num_row_groups):
        frame = parquet.read_row_group(group, columns=columns).to_pandas()
        if frame.empty:
            continue
        coverage.n_fixes += int(frame["n_native_fixes"].sum())
        classified = int(frame["n_classified_fixes"].sum())
        coverage.phase_fixes[UNCLASSIFIED] = coverage.phase_fixes.get(
            UNCLASSIFIED, 0
        ) + int((frame["n_native_fixes"] - frame["n_classified_fixes"]).sum())
        coverage.reasons["classified"] = coverage.reasons.get("classified", 0) + (
            classified
        )
        unclassified_by_status = frame.loc[frame["status"] != "classified"]
        for status, rows in unclassified_by_status.groupby("status"):
            coverage.reasons[str(status)] = coverage.reasons.get(
                str(status), 0
            ) + int(rows["n_native_fixes"].sum())
        flights.update(frame["flight_id"].astype(str).unique().tolist())
        eligible.update(
            frame.loc[frame["n_classified_fixes"] > 0, "flight_id"]
            .astype(str)
            .unique()
            .tolist()
        )
    coverage.n_flights = len(flights)
    coverage.n_eligible_flights = len(eligible)
    return coverage


def run_coverage(args: argparse.Namespace, config: VilpelletConfig) -> int:
    """Re-read the written tables and rewrite the coverage summary from them.

    Prefers the fix-level table when it is present (exact, including the per-phase
    fix counts), falls back to the per-segment ``phase_coverage.parquet`` otherwise
    (exact for flight and fix totals and for the classified/unclassified split; see
    :func:`_coverage_from_segment_table` for the one case where its reason breakdown
    can undercount). Refuses to replace a richer existing summary with a poorer one:
    an earlier version of this function re-read only the fix-level table, so on an
    archive exported without ``--with-points`` it silently zeroed the flight and fix
    totals that ``apply`` had already written correctly. That regression is now a
    guard, not a possibility: see the comparison below.

    Args:
        args: The parsed command line.
        config: The loaded protocol.

    Returns:
        The process exit status.

    Raises:
        FileNotFoundError: If ``apply`` has not been run for this discipline.
        ValueError: If re-deriving the summary would report fewer flights than the
            existing ``coverage.json`` already does.
    """
    _, output_dir = _paths(args.discipline)
    points_path = output_dir / "phase_points.parquet"
    runs_path = output_dir / "phase_segments.parquet"
    segment_coverage_path = output_dir / "phase_coverage.parquet"
    if not any(p.is_file() for p in (points_path, runs_path, segment_coverage_path)):
        raise FileNotFoundError(
            f"none of {points_path.name}, {runs_path.name} or "
            f"{segment_coverage_path.name} exist in {output_dir}; run apply first"
        )
    if points_path.is_file():
        coverage = _stream_column_counts(
            points_path, ["flight_id", "phase", "phase_reason"]
        )
    elif segment_coverage_path.is_file():
        coverage = _coverage_from_segment_table(segment_coverage_path)
    else:
        coverage = Coverage()
    if runs_path.is_file():
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(runs_path)
        for group in range(parquet.metadata.num_row_groups):
            coverage.add_runs(
                parquet.read_row_group(group, columns=["phase", "duration_s"])
                .to_pandas()
            )
    record = coverage.summary()
    record.update(
        {
            "discipline": args.discipline,
            "points_path": str(points_path) if points_path.is_file() else None,
            "segments_path": str(runs_path),
            "fix_level_counts_available": points_path.is_file(),
            "alpha_straight_rad": config.alpha_for(args.discipline),
            "source": "coverage",
        }
    )
    existing_path = output_dir / "coverage.json"
    if existing_path.is_file():
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        if int(existing.get("n_flights", 0)) > int(record["n_flights"]):
            source = (
                "the fix-level table"
                if points_path.is_file()
                else segment_coverage_path.name
            )
            raise ValueError(
                f"{existing_path} already reports {existing['n_flights']:,} flights; "
                f"this re-derivation only recovered {record['n_flights']:,} from "
                f"{source}. Refusing to overwrite the more complete summary."
            )
    _write_coverage(output_dir, record)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run one action of the Vilpellet segmentation command line.

    Args:
        argv: Argument vector, or ``None`` to read ``sys.argv``.

    Returns:
        The process exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["flight", "apply", "coverage"])
    parser.add_argument("--igc", type=Path, help="One .igc file, for the flight action")
    parser.add_argument("--discipline", choices=list(DISCIPLINES))
    parser.add_argument(
        "--input",
        choices=["cleaned", "raw_gnss"],
        help="Which trajectory to build the features from; defaults to the config",
    )
    parser.add_argument(
        "--out", type=Path, help="Write this flight's two tables into this directory"
    )
    parser.add_argument(
        "--limit", type=int, help="Stop the apply action after this many flights"
    )
    parser.add_argument(
        "--jobs",
        type=int,
        help=(
            "Worker processes for the apply action. Defaults to the machine's core "
            "count minus two, leaving headroom for interactive use; pass 1 to run "
            "single-process"
        ),
    )
    parser.add_argument(
        "--with-points",
        action="store_true",
        help=(
            "Also write the fix-level phase_points.parquet. The run intervals already "
            "reconstruct every per-fix label exactly, and this table is far larger, "
            "so it is off by default"
        ),
    )
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)

    if args.action == "flight" and args.igc is None:
        parser.error("--igc is required for the flight action")
    if args.action in {"apply", "coverage"} and args.discipline is None:
        parser.error(f"--discipline is required for the {args.action} action")
    if args.action != "flight" and args.input is not None:
        parser.error("--input applies to the flight action only")

    config = load_vilpellet_config(args.config)
    if args.input is not None:
        config = replace(
            config, input_policy=replace(config.input_policy, source=args.input)
        )
    if args.action == "flight":
        return run_flight(args, config)
    if args.action == "apply":
        return run_apply(args, config)
    return run_coverage(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
