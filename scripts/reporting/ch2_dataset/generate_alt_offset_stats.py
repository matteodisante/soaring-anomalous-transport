#!/usr/bin/env python3
r"""Regenerate the barometric-against-GNSS *offset* statistics for the thesis.

Writes ``thesis/generated/alt_offset.tex``: the ``\StatAltOff*`` family quoted by
``sec:altchannel`` and ``impl:altchannel``, which is what turns the mixed-source
argument from a plausibility into a measurement. Where
``generate_altitude_noise_figure.py`` measures how *noisy* each channel is, this
measures how far apart they *sit*, flight by flight, and what the distance is made of
(:mod:`soaring.analysis.alt_offset`).

Five families of number come out of one pass:

* **the offset itself** -- its median, spread and quantiles per discipline, at flight
  altitude and inside a fixed altitude band so the two disciplines are compared at the
  same height;
* **its decomposition** -- the part independent of height (the reference surfaces: a
  pressure altitude against an ellipsoidal one) and the part proportional to it, which
  is the day's departure from the standard temperature profile and is reported in
  kelvin;
* **weather against instrument** -- the spread of the offset between flights from the
  same site on the same day (an air mass and a pressure setting in common, so what is
  left is the recorders) against its spread between flights from the same site on
  different days (the atmosphere);
* **the two decades** -- barometer prevalence and within-flight scatter in the earliest
  and latest seasons the sample supports, since a 20-year archive is not one fleet;
* **the fallback check** -- how often a flight without a barometric channel carries a
  complete GNSS one. ``impl:altchannel`` records this as untested, because the cached
  track scan has no GNSS-completeness column. This scan does.

**Sampling.** The paraglider archive is too large to census here (a parse of every file,
not a cached column), so a seeded random subsample of ``SAMPLE_PER_DISCIPLINE`` files is
measured; the hang-glider archive falls under that size and is censused. The size is set
by the *finest* cut rather than by the headline. Location and scale of the offset are
stable on a few thousand flights, but the same-site-same-day grouping needs three
flights of one site and day to land in the sample together, and at 6000 paraglider files
that yields a few dozen groups. At 20000 it yields a few hundred, which is what the
instrument-scatter number rests on. Everything coarser than that grouping is
over-sampled at this size, which is the right way round.

**Caching.** The per-flight table is written to ``<data_root>/derived/alt_offset_scan
.parquet`` and reused on the next run, exactly as the track scan is: the macros then
recompute in a second when a definition changes, with no reparse. ``--rescan`` forces
the parse.

Best-effort like every reporting script: if the SSD, a config or a dependency is
missing, the committed ``alt_offset.tex`` is left untouched and the script exits
cleanly. Macros for *both* disciplines are required -- a file written for one would
fail the build on the other's macros. Run it with::

    uv run python scripts/reporting/ch2_dataset/generate_alt_offset_stats.py [--rescan]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "thesis" / "generated" / "alt_offset.tex"

#: Files measured per discipline (see the docstring: sized by the same-site-same-day
#: grouping, not by the headline statistics). A smaller archive is censused whole.
SAMPLE_PER_DISCIPLINE = 20_000
#: Seasons pooled at each end of the archive for the two-decade comparison, and the
#: smallest measured population a season needs to enter it. A single season is noisy and
#: the earliest ones are thin, so the eras are blocks rather than endpoints.
ERA_SEASONS = 5
ERA_MIN_FLIGHTS = 40
#: Flights a site-day group needs, and distinct recorders it must span, before its
#: internal spread is read as an instrument-to-instrument scatter.
SAME_DAY_MIN_FLIGHTS = 3
SAME_DAY_MIN_LOGGERS = 3
#: Flights a recorder make needs before its median enters the between-make spread.
MAKE_MIN_FLIGHTS = 50
#: Absolute accuracy a current MEMS barometric sensor is specified to, hPa: the MS5611
#: (the part behind a large share of free-flight variometers) states +/-1.5 hPa at
#: 25 C and +/-2.5 hPa over its full temperature band. Quoted here rather than typed in
#: the thesis so that the metres it becomes are arithmetic on the datasheet figure and
#: the same conversion the rest of the section uses.
SENSOR_ACCURACY_HPA = 1.5
SENSOR_ACCURACY_WIDE_HPA = 2.5

N_JOBS = min(8, os.cpu_count() or 1)

_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# The sys.path line above is what makes this resolvable when the script is run
# directly, so the import cannot move to the top of the file.
from soaring.reporting import (  # noqa: E402
    DISCIPLINES,
    MacroWriter,
    bare_cli,
    pct_of,
    write_macros,
)


def _fmt(value: float, decimals: int = 1) -> str:
    """Format to ``decimals`` places, dropping a trailing all-zero fraction."""
    text = f"{value:.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _load_or_scan(discipline, cache: Path, rescan: bool):
    """One discipline's per-flight offset table, from the cache or from a parse."""
    import pandas as pd

    from soaring.analysis.alt_offset import COLUMNS, scan_offsets
    from soaring.analysis.altitude_noise import sample_igc_paths

    if cache.is_file() and not rescan:
        table = pd.read_parquet(cache)
        if list(table.columns) == COLUMNS:
            print(f"[{discipline.name}] cached scan: {len(table)} flights ({cache}).")
            return table
        print(f"[{discipline.name}] cached scan has an old schema; re-scanning.")

    cfg = discipline.config()
    paths = sample_igc_paths(cfg.igc_dir, SAMPLE_PER_DISCIPLINE)
    if not paths:
        return None
    print(f"[{discipline.name}] parsing {len(paths)} files on {N_JOBS} workers...")
    table = scan_offsets(paths, n_jobs=N_JOBS)
    cache.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(cache)
    print(f"[{discipline.name}] wrote {cache} ({len(table)} flights).")
    return table


def _with_catalog(table, discipline):
    """Attach the take-off site and the date, for the two groupings and the seasons."""
    import pandas as pd

    catalog_path = discipline.catalog_path()
    if catalog_path is None or not catalog_path.is_file():
        table["site"] = pd.NA
        table["date"] = pd.NaT
        return table
    catalog = pd.read_csv(
        catalog_path,
        usecols=["flight_id", "date", "takeoff"],
        dtype={"flight_id": str},
        low_memory=False,
    ).rename(columns={"takeoff": "site"})
    # An explicit format, not dateutil: the column carries a 0000-00-00 sentinel
    # (sec:dataquality) and 200 000 rows of per-element fallback parsing take minutes.
    catalog["date"] = pd.to_datetime(
        catalog["date"], format="%Y-%m-%d", errors="coerce"
    )
    return table.merge(catalog, on="flight_id", how="left")


def _offset_macros(table, tag: str) -> dict[str, str]:
    r"""Every ``\StatAltOff<tag>*`` macro for one discipline."""
    from soaring.analysis.alt_offset import (
        FIXED_BAND_M,
        PRESENT_MIN,
        between_group_spread,
        borderline_gnss_advantage,
        fallback_completeness,
        group_scatter,
        independent,
        metres_per_hpa,
        recorder_make,
        sigma_mad,
        temperature_departure_k,
    )

    writer = MacroWriter(f"StatAltOff{tag}")
    n_measured = len(table)
    both = table["both"].fillna(False).astype(bool)
    keep = independent(table)
    flights = table[keep]
    offset = flights["med_offset"]

    writer.put("Measured", n_measured)
    writer.put("BothPct", _fmt(pct_of(int(both.sum()), n_measured)))
    writer.put("Flights", len(flights))
    # The two exclusions, both reported: a duplicated channel is a property of the
    # fleet worth quoting, and a broken one bounds what the tail could be hiding.
    dup = both & (table["frac_equal"] > 0.99)
    writer.put("DuplicatePct", _fmt(pct_of(int(dup.sum()), int(both.sum()))))
    broken = both & table["med_offset"].notna() & ~keep & ~dup
    writer.put("BrokenPct", _fmt(pct_of(int(broken.sum()), int(both.sum())), 2))

    # --- the offset, and its spread across flights
    writer.put("MedianM", _fmt(offset.median(), 0))
    writer.put("SigmaM", _fmt(sigma_mad(offset), 0))
    writer.put("IqrM", _fmt(offset.quantile(0.75) - offset.quantile(0.25), 0))
    writer.put("PFiveM", _fmt(offset.quantile(0.05), 0))
    writer.put("PNinetyFiveM", _fmt(offset.quantile(0.95), 0))

    # --- decomposition: the part proportional to height is the temperature departure
    sloped = flights[flights["slope"].notna()]
    slope = float(sloped["slope"].median())
    alt = float(sloped["alt_med"].median())
    writer.put("SlopePct", _fmt(-100.0 * slope, 1))
    writer.put("DeltaTK", _fmt(temperature_departure_k(slope, alt), 1))
    writer.put("SlopeAltM", _fmt(alt, 0))
    writer.put("HeightTermM", _fmt((sloped["slope"] * sloped["alt_med"]).median(), 0))
    intercept = sloped["med_offset"] - sloped["slope"] * sloped["alt_med"]
    writer.put("InterceptM", _fmt(intercept.median(), 0))

    # --- at one height, so the two disciplines are comparable
    lo, hi = FIXED_BAND_M
    band = flights[flights["alt_med"].between(lo, hi)]
    writer.put("BandFlights", len(band))
    writer.put("BandMedianM", _fmt(band["med_offset"].median(), 0))
    writer.put("BandSigmaM", _fmt(sigma_mad(band["med_offset"]), 0))

    # --- what survives a difference: the within-flight part
    writer.put("WithinIqrM", _fmt(flights["iqr_offset"].median(), 0))
    writer.put("DriftSigmaM", _fmt(sigma_mad(flights["drift"]), 0))
    writer.put("DriftPFiveM", _fmt(flights["drift"].quantile(0.05), 0))
    writer.put("DriftPNinetyFiveM", _fmt(flights["drift"].quantile(0.95), 0))
    writer.put("DurationMin", _fmt(flights["dur_s"].median() / 60.0, 0))

    # --- weather against instrument
    same_day = group_scatter(
        flights,
        ["site", "date"],
        min_flights=SAME_DAY_MIN_FLIGHTS,
        min_loggers=SAME_DAY_MIN_LOGGERS,
    )
    per_site = group_scatter(flights, ["site"], min_flights=SAME_DAY_MIN_FLIGHTS)
    writer.put("SameDayGroups", len(same_day))
    writer.put("SameDayFlights", int(same_day["n"].sum()) if len(same_day) else 0)
    writer.put("SameDaySigmaM", _fmt(same_day["sigma"].median(), 0))
    writer.put("SiteGroups", len(per_site))
    writer.put("SiteFlights", int(per_site["n"].sum()) if len(per_site) else 0)
    site_sigma = float(per_site["sigma"].median())
    writer.put("SiteSigmaM", _fmt(site_sigma, 0))
    writer.put("SiteHpa", _fmt(site_sigma / metres_per_hpa(), 1))
    # And between recorder models, which is an upper bound on the instrument family's
    # own contribution: the same model is also a period and a set of sites.
    makes = flights.assign(make=recorder_make(flights["logger"]))
    families, family_sigma, family_span = between_group_spread(
        makes, "make", min_flights=MAKE_MIN_FLIGHTS
    )
    writer.put("LoggerFamilies", families)
    writer.put("LoggerSigmaM", _fmt(family_sigma, 0))
    writer.put("LoggerSpanM", _fmt(family_span, 0))

    # --- the two decades: fleet prevalence and within-flight scatter, end to end
    seasons = table.dropna(subset=["season"])
    counts = flights.dropna(subset=["season"]).groupby("season").size()
    usable = sorted(counts[counts >= ERA_MIN_FLIGHTS].index)
    if len(usable) >= 2 * ERA_SEASONS:
        blocks = {"Early": usable[:ERA_SEASONS], "Late": usable[-ERA_SEASONS:]}
        for label, block in blocks.items():
            rows = seasons[seasons["season"].isin(block)]
            writer.put(f"Era{label}Label", f"{block[0][:4]}--{block[-1][-4:]}")
            writer.put(
                f"Era{label}BaroPct",
                _fmt(pct_of(int((rows["baro_frac"] >= PRESENT_MIN).sum()), len(rows))),
            )
            measured = rows[independent(rows)]
            iqr = measured["iqr_offset"].median()
            writer.put(f"Era{label}WithinIqrM", _fmt(iqr, 0))
            writer.put(f"Era{label}DriftSigmaM", _fmt(sigma_mad(measured["drift"]), 0))

    # --- the fallback the pipeline never checked
    complete, fallback = fallback_completeness(table)
    writer.put("FallbackCount", fallback)
    writer.put("FallbackPct", _fmt(pct_of(fallback, n_measured)))
    writer.put("FallbackGnssPct", _fmt(pct_of(complete, fallback)))
    better, borderline = borderline_gnss_advantage(table)
    writer.put("BorderlineCount", borderline)
    writer.put("BorderlineBetterPct", _fmt(pct_of(better, borderline)))
    return writer.macros


def _shared_macros() -> dict[str, str]:
    """The standard-atmosphere arithmetic every statement above is read against."""
    from soaring.analysis.alt_offset import (
        EDGE_TRIM,
        FIXED_BAND_M,
        ISA_T0,
        MIN_FIX,
        PLAUSIBLE_MAX_M,
        SLOPE_MIN_RANGE_M,
        metres_per_hpa,
        scale_height_m,
    )

    writer = MacroWriter("StatAltOff")
    writer.put("ScaleHeightKm", _fmt(scale_height_m() / 1000.0, 1))
    writer.put("ScaleHeightTempK", _fmt(ISA_T0, 2))
    writer.put("MetrePerHpa", _fmt(metres_per_hpa(), 1))
    writer.put("TenHpaM", _fmt(10.0 * metres_per_hpa(), 0))
    writer.put("BandLoM", _fmt(FIXED_BAND_M[0], 0))
    writer.put("BandHiM", _fmt(FIXED_BAND_M[1], 0))
    writer.put("SensorHpa", _fmt(SENSOR_ACCURACY_HPA))
    writer.put("SensorWideHpa", _fmt(SENSOR_ACCURACY_WIDE_HPA))
    writer.put("SensorM", _fmt(SENSOR_ACCURACY_HPA * metres_per_hpa(), 0))
    writer.put("SensorWideM", _fmt(SENSOR_ACCURACY_WIDE_HPA * metres_per_hpa(), 0))
    # The diagnostic's own working values, so the appendix that argues for them and the
    # code that applies them cannot drift apart.
    writer.put("MinFix", MIN_FIX)
    writer.put("WindowPct", _fmt(100.0 * (1.0 - 2.0 * EDGE_TRIM), 0))
    writer.put("SlopeMinRangeM", _fmt(SLOPE_MIN_RANGE_M, 0))
    writer.put("PlausibleMaxKm", _fmt(PLAUSIBLE_MAX_M / 1000.0, 0))
    writer.put("GroupMinFlights", SAME_DAY_MIN_FLIGHTS)
    writer.put("SameDayMinLoggers", SAME_DAY_MIN_LOGGERS)
    writer.put("EraSeasons", ERA_SEASONS)
    writer.put("EraMinFlights", ERA_MIN_FLIGHTS)
    writer.put("MakeMinFlights", MAKE_MIN_FLIGHTS)
    return writer.macros


def main(argv: list[str] | None = None) -> int:
    """Rewrite ``alt_offset.tex`` when both archives are reachable."""
    argv = sys.argv[1:] if argv is None else argv
    rescan = "--rescan" in argv
    try:
        import pandas  # noqa: F401
    except ImportError as exc:
        print(f"alt offset: missing dependency ({exc}); keeping the committed file.")
        return 0

    tables = {}
    for discipline in DISCIPLINES.values():
        try:
            cfg = discipline.config()
        except (FileNotFoundError, KeyError):
            print(f"alt offset: no config for {discipline.name}; keeping the file.")
            return 0
        if not cfg.igc_dir.is_dir():
            print(f"alt offset: {cfg.igc_dir} unreachable; keeping the file.")
            return 0
        table = _load_or_scan(discipline, cfg.derived_dir / "alt_offset_scan.parquet",
                              rescan)
        if table is None or table.empty:
            print(f"alt offset: no flights measured for {discipline.name}; keeping it.")
            return 0
        tables[discipline] = _with_catalog(table, discipline)

    macros = MacroWriter()
    macros.update(_shared_macros())
    for discipline, table in tables.items():
        macros.update(_offset_macros(table, discipline.tag))

    n = write_macros(
        OUT,
        macros,
        generator="scripts/reporting/ch2_dataset/generate_alt_offset_stats.py",
        extra_header=[
            "Per-flight barometric-minus-GNSS offset, from a seeded IGC sample",
            "(cache: <data_root>/derived/alt_offset_scan.parquet; --rescan reparses).",
        ],
    )
    counts = ", ".join(f"{d.tag}={len(t)}" for d, t in tables.items())
    print(f"Wrote {OUT}: {n} macros ({counts}).")
    return 0


if __name__ == "__main__":
    bare_cli(__doc__, known=["--rescan"])

    raise SystemExit(main())
