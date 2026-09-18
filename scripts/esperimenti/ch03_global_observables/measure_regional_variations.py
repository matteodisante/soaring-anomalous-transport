"""Measure regional V1/V2/V3 from verified coordinates, then summarise saved moments."""

from __future__ import annotations

# ruff: noqa: E402 -- entry point supports direct execution from this checkout
import argparse
import gzip
import hashlib
import json
import sys
import time
import warnings
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from soaring.analysis.observables.archive_diagnostics import DiskFrames
from soaring.analysis.observables.regional_variations import (
    CHANGE_EDGES,
    DISTRIBUTION_LAGS_S,
    LAGS_S,
    REGIONS,
    VARIANTS,
    bootstrap_moments,
    common_stratum_weights,
    measure_regional_variations,
    mixture_moments,
    moment_diagnostics,
)
from soaring.analysis.stats.bootstrap import cluster_labels
from soaring.reporting import DISCIPLINES, canonical_wing_class
from soaring.reporting.glider_class import equipment_group


def digest(path):
    """Identify file bytes without reading the full coordinate store into memory."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def serialise(value):
    """Use JSON null for unsupported values; never emit nonstandard NaN tokens."""
    if isinstance(value, np.ndarray):
        return serialise(value.tolist())
    if isinstance(value, dict):
        return {str(k): serialise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialise(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def write_json(path, value):
    """Write a readable finite JSON record."""
    Path(path).write_text(
        json.dumps(serialise(value), indent=2, allow_nan=False) + "\n"
    )


def interval(replicates, supported):
    """Pointwise percentile bounds, only with adequate cluster and replicate support."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        bounds = np.nanquantile(replicates, [0.025, 0.975], axis=0)
    enough = np.isfinite(replicates).sum(axis=0) >= 0.9 * len(replicates)
    return np.where(np.asarray(supported) & enough, bounds, np.nan)


def local_slope(curve, lags):
    """Describe the local log slope without identifying it with H."""
    output = np.full_like(curve, np.nan)
    good = np.isfinite(curve) & (curve > 0)
    if good.sum() >= 3:
        output[good] = np.gradient(np.log(curve[good]), np.log(lags[good]))
    return output


def describe(point, replicates, lags, cluster_counts):
    """Retain vector moments, order contrasts and paired uncertainty."""
    result = moment_diagnostics(point)
    result["moments"] = point
    variation = result["variation"]
    result["rms_velocity_change_m_s"] = np.sqrt(np.maximum(variation[:, 1], 0)) / lags
    result["local_b2"] = local_slope(variation[:, 1], lags)
    with np.errstate(invalid="ignore", divide="ignore"):
        result["v3_over_v2"] = variation[:, 2] / variation[:, 1]
    if replicates is None:
        return result, None
    boot = moment_diagnostics(replicates)
    boot["rms_velocity_change_m_s"] = (
        np.sqrt(np.maximum(boot["variation"][:, :, 1], 0)) / lags
    )
    boot["v3_over_v2"] = np.divide(
        boot["variation"][:, :, 2],
        boot["variation"][:, :, 1],
        out=np.full(boot["variation"].shape[:2], np.nan),
        where=boot["variation"][:, :, 1] > 0,
    )
    supported = cluster_counts >= 20
    result["pointwise_95"] = {
        key: interval(boot[key], supported if boot[key].ndim == 3 else supported[:, 1])
        for key in ("variation", "anisotropy", "rms_velocity_change_m_s", "v3_over_v2")
    }
    return result, boot["rms_velocity_change_m_s"]


def metadata_table(rows, discipline, catalog):
    """Join context and valid site--day labels without inferring missing equipment."""
    table = pd.DataFrame(rows)
    table = table.merge(catalog, on="flight_id", how="left", validate="one_to_one")
    table["date"] = pd.to_datetime(
        table.date,
        format="%Y-%m-%d",
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")
    table["task_group"] = np.where(
        table.task_known, np.where(table.closed, "closed", "open"), None
    )
    table["duration_band"] = pd.cut(
        table.retained_duration_s,
        [0, 7200, 14400, np.inf],
        labels=["0-2h", "2-4h", "4h+"],
    ).astype(object)
    year = pd.to_numeric(table.season_year, errors="coerce")
    table["period"] = pd.cut(
        year,
        [0, 2009, 2019, np.inf],
        labels=["through-2009", "2010-2019", "2020+"],
        right=True,
    ).astype(object)
    wing = canonical_wing_class(discipline, table.wing_class)
    table["equipment_group"] = (
        equipment_group(wing) if discipline == "paragliders" else wing
    )
    table["equipment_group"] = table.equipment_group.replace("", None)
    keys = table[["date", "takeoff"]].astype("string").apply(lambda x: x.str.strip())
    table["missing_cluster_key"] = (keys.isna() | keys.eq("").fillna(False)).any(axis=1)
    table["cluster"] = cluster_labels(table, "day_site")
    return table


def regional_contrasts(summaries, bootstrap_curves, lags):
    """Compare RMS-change curves with pointwise and simultaneous log-ratio bands."""
    output = []
    for variant in VARIANTS:
        for first, second in combinations(REGIONS, 2):
            a, b = summaries[first][variant], summaries[second][variant]
            with np.errstate(invalid="ignore", divide="ignore"):
                ratio = a["rms_velocity_change_m_s"] / b["rms_velocity_change_m_s"]
                boot = (
                    bootstrap_curves[first, variant] / bootstrap_curves[second, variant]
                )
            supported = (a["n_clusters"][:, 1] >= 20) & (b["n_clusters"][:, 1] >= 20)
            bounds = interval(boot, supported)
            valid = (
                supported
                & np.isfinite(boot).all(axis=0)
                & np.all(boot > 0, axis=0)
                & (ratio > 0)
            )
            simultaneous = np.full((2, len(lags)), np.nan)
            if valid.any():
                logboot, logpoint = np.log(boot[:, valid]), np.log(ratio[valid])
                deviation = np.std(logboot, axis=0, ddof=1)
                positive = deviation > 0
                if positive.any():
                    max_t = np.max(
                        np.abs(
                            (logboot[:, positive] - logpoint[positive])
                            / deviation[positive]
                        ),
                        axis=1,
                    )
                    critical = np.quantile(max_t, 0.95)
                    supported_indexes = np.flatnonzero(valid)[positive]
                    simultaneous[:, supported_indexes] = np.exp(
                        logpoint[positive]
                        + np.array([-1, 1])[:, None] * critical * deviation[positive],
                    )
            output.append(
                {
                    "variant": variant,
                    "numerator": first,
                    "denominator": second,
                    "rms_change_ratio": ratio,
                    "pointwise_95": bounds,
                    "simultaneous_95": simultaneous,
                    "simultaneous_lags_s": lags[np.isfinite(simultaneous).all(axis=0)],
                }
            )
    return output


def summarise(rows, moments, counts, metadata, lags, n_resamples):
    """Summarise all regions and a descriptive common-context standardisation."""
    summaries, bootstrap_curves = {}, {}
    for group_index, region in enumerate(REGIONS):
        mask = metadata.region.eq(region).to_numpy()
        labels = metadata.loc[mask, "cluster"].to_numpy()
        summaries[region] = {}
        for k, variant in enumerate(VARIANTS):
            data, support = moments[mask, k], counts[mask, k]
            point, replicates = bootstrap_moments(
                data, labels, n_resamples=n_resamples, seed=20260912 + group_index
            )
            n_clusters = np.array(
                [
                    [len(np.unique(labels[support[:, j, p] > 0])) for p in range(3)]
                    for j in range(len(lags))
                ]
            )
            result, boot = describe(point, replicates, lags, n_clusters)
            result.update(
                {
                    "n_flights": (support > 0).sum(axis=0),
                    "n_origins": support.sum(axis=0),
                    "n_clusters": n_clusters,
                    "missing_cluster_key_flights": int(
                        metadata.loc[mask, "missing_cluster_key"].sum()
                    ),
                }
            )
            # Explicit sensitivity to the weighting used in the existing regional PCA.
            result["pooled_origin_variation"] = np.array(
                [
                    moment_diagnostics(
                        mixture_moments(data[:, j, p], support[:, j, p])
                    )["variation"]
                    for j in range(len(lags))
                    for p in range(3)
                ]
            ).reshape(len(lags), 3)
            summaries[region][variant] = result
            bootstrap_curves[region, variant] = boot
        print(f"Summarised {region}: {mask.sum()} flights", flush=True)
    eligible = counts[:, 2, 0, 0] > 0
    weights, standardisation = common_stratum_weights(metadata, eligible)
    standardisation["uncertainty"] = (
        "descriptive point estimates; no calibrated intervals"
    )
    standardisation["regions"] = {}
    for region in REGIONS:
        mask = metadata.region.eq(region).to_numpy() & (weights > 0)
        if not mask.any():
            continue
        point = mixture_moments(moments[mask, 2], weights[mask])
        result, _ = describe(point, None, lags, None)
        result["n_flights"] = int(mask.sum())
        standardisation["regions"][region] = result
    return (
        summaries,
        standardisation,
        regional_contrasts(summaries, bootstrap_curves, lags),
    )


def main():
    """Create an immutable focused measurement and its complete small report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--coordinate-manifest",
        type=Path,
        default=ROOT / "revisions/regional-pca-lags-2026-09-12/numerical-update.json",
    )
    parser.add_argument("--resamples", type=int, default=500)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--summarise-only", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "report.json").exists():
        raise FileExistsError(
            "Completed report is immutable; use a new output directory"
        )
    started = time.perf_counter()
    source_paths = [
        Path(__file__),
        ROOT / "src/soaring/analysis/observables/regional_variations.py",
        ROOT / "src/soaring/analysis/observables/segment_support.py",
        ROOT / "src/soaring/analysis/stats/bootstrap.py",
        ROOT / "src/soaring/reporting/glider_class.py",
    ]
    sources = {str(p.relative_to(ROOT)): digest(p) for p in source_paths}
    manifest = json.loads(args.coordinate_manifest.read_text())
    if manifest["status"] != "complete":
        raise ValueError("Coordinates must belong to a completed verified run")
    inputs, results = {}, {}
    for name, glider in DISCIPLINES.items():
        input_paths = {
            (ROOT / p).resolve(): record
            for p, record in manifest["coordinate_inputs"].items()
        }
        candidates = [
            p
            for p in input_paths
            if str(p).endswith(f"ch3-full-{glider.slug}/flights.json")
        ]
        if len(candidates) != 1:
            raise ValueError("One verified coordinate store is required per discipline")
        directory = candidates[0].parent
        for filename in ("positions.bin", "flights.json"):
            path = directory / filename
            expected = input_paths[path.resolve()]
            if digest(path) != expected["sha256"]:
                raise ValueError(f"Coordinate input changed: {path}")
            inputs[str(path)] = {
                "sha256": expected["sha256"],
                "bytes": path.stat().st_size,
            }
        catalog_path = Path(glider.catalog_path())
        inputs[str(catalog_path)] = {
            "sha256": digest(catalog_path),
            "bytes": catalog_path.stat().st_size,
        }
        catalog = pd.read_csv(
            catalog_path,
            dtype={"flight_id": str},
            usecols=["flight_id", "date", "takeoff", "season_year", "wing_class"],
        )
        arrays = out / "arrays" / glider.slug
        measurement_contract = {
            "coordinate_sha256": inputs[str(directory / "positions.bin")]["sha256"],
            "index_sha256": inputs[str(directory / "flights.json")]["sha256"],
            "lags_s": LAGS_S.tolist(),
            "common_max_s": 1000,
            "measurement_source_sha256": sources[
                "src/soaring/analysis/observables/regional_variations.py"
            ],
        }
        if args.summarise_only:
            saved = json.loads((arrays / "measurement.json").read_text())
            if saved["contract"] != measurement_contract:
                raise ValueError("Cached moments have a different measurement contract")
            for filename, expected in saved["outputs"].items():
                if digest(arrays / filename) != expected:
                    raise ValueError(f"Cached moments changed: {filename}")
            rows = json.loads((arrays / "flights.json").read_text())
            moments, counts = (
                np.load(arrays / f"{kind}.npy", mmap_mode="r")
                for kind in ("moments", "counts")
            )
            distributions = json.loads((arrays / "distributions.json").read_text())
        else:
            rows, moments, counts, distributions = measure_regional_variations(
                DiskFrames(directory),
                arrays,
                workers=args.workers,
            )
            write_json(arrays / "flights.json", rows)
            write_json(arrays / "distributions.json", distributions)
            write_json(
                arrays / "measurement.json",
                {
                    "contract": measurement_contract,
                    "outputs": {
                        filename: digest(arrays / filename)
                        for filename in (
                            "moments.npy",
                            "counts.npy",
                            "flights.json",
                            "distributions.json",
                        )
                    },
                },
            )
        metadata = metadata_table(rows, name, catalog)
        summaries, standardisation, contrasts = summarise(
            rows, moments, counts, metadata, LAGS_S, args.resamples
        )
        results[name] = {
            "n_regional_flights": len(rows),
            "regions": summaries,
            "standardisation": standardisation,
            "contrasts": contrasts,
            "distributions": distributions,
        }
        print(
            f"Completed {name} in {time.perf_counter() - started:.1f} s elapsed",
            flush=True,
        )
    if sources != {str(p.relative_to(ROOT)): digest(p) for p in source_paths}:
        raise ValueError("Numerical source changed during the run")
    report = {
        "status": "complete",
        "completed_utc": datetime.now(UTC).isoformat(),
        "run_id": out.name,
        "coordinate_manifest_sha256": digest(args.coordinate_manifest),
        "sources": sources,
        "inputs": inputs,
        "elapsed_seconds": time.perf_counter() - started,
        "contract": {
            "lags_s": LAGS_S,
            "display_lags_s": DISTRIBUTION_LAGS_S,
            "grid_s": 10,
            "orders": [1, 2, 3],
            "regions": REGIONS,
            "region_definition": (
                "take-off boxes inherited from the verified PCA coordinate store"
            ),
            "weighting": "equal flight; within-flight eligible origins pooled",
            "variants": {
                "available": (
                    "every supported origin, stride tau, independently by order"
                ),
                "matched": (
                    "same origins and flights for orders 1--3 at each lag, stride tau"
                ),
                "common": (
                    "same origins and flights for all orders and lags <=1000 s; "
                    "stride 10 s; 3000 s continuous stencil support"
                ),
            },
            "bootstrap": {
                "replicates": args.resamples,
                "unit": "site-day",
                "seed": 20260912,
                "interval": (
                    "pointwise percentile 95%; region contrasts also simultaneous "
                    "across supported lags"
                ),
                "minimum_clusters_for_intervals": 20,
                "missing_keys": "singleton flight clusters",
                "assumptions": (
                    "independent exchangeable site-day clusters within each region; "
                    "dependence across clusters remains possible"
                ),
            },
            "distribution_edges_m_s": CHANGE_EDGES,
            "distribution_tail_convention": (
                "last edge null means +infinity; both tails and zeros retained; "
                "quantile bounds refer to histogram bins"
            ),
            "standardisation": (
                "common-origin sample; common task x retained-duration band x "
                "season-period x equipment strata, at least 10 flights in every "
                "region; descriptive only"
            ),
            "interpretation": (
                "ground-trajectory diagnostics; no wind identification, phase "
                "conditioning, or validated Hurst estimates"
            ),
        },
        "results": results,
    }
    write_json(out / "report.json", report)
    (out / "report.json.gz").write_bytes(
        gzip.compress((out / "report.json").read_bytes(), mtime=0)
    )
    print(f"Saved {out / 'report.json'}", flush=True)


if __name__ == "__main__":
    main()
