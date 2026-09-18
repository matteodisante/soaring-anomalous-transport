"""Block geometry, pooling identity and known origin-dependence controls."""

import numpy as np
import pytest

from soaring.analysis.observables.origin_dependence import (
    BLOCKS,
    STATISTICS,
    flight_statistics,
    interval,
    origin_blocks,
    ratio_statistics,
    segment_sums,
)


@pytest.mark.parametrize("count", [3, 4, 5, 9, 10, 251, 1250])
def test_blocks_partition_the_origins_and_balance_the_ends(count):
    blocks = origin_blocks(count)
    assert len(blocks) == len(BLOCKS)
    (a0, z0), (a1, z1), (a2, z2) = blocks
    # The three blocks tile the admissible range exactly once.
    assert a0 == 0 and z2 == count
    assert z0 == a1 and z1 == a2
    # The paired contrast needs identical counts at the two ends.
    assert z0 - a0 == z2 - a2 == count // 3
    assert z1 - a1 == count - 2 * (count // 3)


@pytest.mark.parametrize("count", [0, 1, 2, -5])
def test_too_few_origins_give_no_support(count):
    assert origin_blocks(count) is None


def test_segment_sums_reproduce_the_pooled_moments():
    rng = np.random.default_rng(11)
    positions = rng.normal(size=(400, 2)).cumsum(axis=0)
    counts, sums, times = segment_sums(positions, 0, 400, 7)
    step = positions[7:400] - positions[:393]
    radial = np.hypot(step[:, 0], step[:, 1])
    assert counts.sum() == len(radial)
    np.testing.assert_allclose(sums[:, 0].sum(), radial.sum())
    np.testing.assert_allclose(sums[:, 1].sum(), (radial**2).sum())
    # Mean origin index of the whole admissible range, recovered from the blocks.
    np.testing.assert_allclose((counts * times).sum() / counts.sum(), 196.0)


def test_flight_pooling_matches_an_unsplit_measurement():
    rng = np.random.default_rng(5)
    positions = rng.normal(size=(1000, 2)).cumsum(axis=0)
    spans = [(0, 400), (450, 1000)]
    means, counts, _ = flight_statistics(positions, spans, 13)
    pooled = np.einsum("bs,b->s", means, counts) / counts.sum()
    step = np.concatenate(
        [positions[a + 13 : b] - positions[a : b - 13] for a, b in spans]
    )
    radial = np.hypot(step[:, 0], step[:, 1])
    np.testing.assert_allclose(pooled, [radial.mean(), (radial**2).mean()])


def test_segments_shorter_than_the_lag_are_skipped_without_joining():
    rng = np.random.default_rng(3)
    positions = rng.normal(size=(200, 2)).cumsum(axis=0)
    spans = [(0, 150), (150, 155)]
    means, counts, _ = flight_statistics(positions, spans, 20)
    alone, alone_counts, _ = flight_statistics(positions, [(0, 150)], 20)
    np.testing.assert_allclose(means, alone)
    np.testing.assert_array_equal(counts, alone_counts)
    assert flight_statistics(positions, [(150, 155)], 20) is None


def test_stationary_increments_give_unit_ratios():
    rng = np.random.default_rng(2026)
    ratios = []
    for _ in range(800):
        positions = rng.normal(size=(2000, 2)).cumsum(axis=0)
        means, _, _ = flight_statistics(positions, [(0, 2000)], 40)
        ratios.append(means[BLOCKS.index("late")] / means[BLOCKS.index("early")])
    # Overlapping origins leave few independent displacements per block, so the
    # tolerance is Monte Carlo error rather than an accuracy claim.
    np.testing.assert_allclose(np.mean(ratios, axis=0), 1, atol=0.05)


def test_a_growing_increment_scale_is_detected_in_the_late_block():
    rng = np.random.default_rng(7)
    length = 3000
    # Increment scale doubles along the segment; the position law ages by design.
    scale = np.linspace(1.0, 2.0, length)[:, None]
    positions = (rng.normal(size=(length, 2)) * scale).cumsum(axis=0)
    means, _, _ = flight_statistics(positions, [(0, length)], 40)
    ratio = means[BLOCKS.index("late")] / means[BLOCKS.index("early")]
    assert (ratio > 1.2).all()
    # The second moment responds to a scale change more strongly than the first.
    assert ratio[STATISTICS.index("m2")] > ratio[STATISTICS.index("m1")]


def test_ratio_statistics_select_the_paired_blocks():
    means = 1.0 + np.arange(2 * len(BLOCKS) * len(STATISTICS) * 4, dtype=float)
    means = means.reshape(2, len(BLOCKS), len(STATISTICS), 4)
    ratios = ratio_statistics(means)
    expected = means[:, BLOCKS.index("late")] / means[:, BLOCKS.index("early")]
    np.testing.assert_allclose(ratios, expected)
    assert ratios.shape == (2, len(STATISTICS), 4)


def test_nonpositive_early_means_give_missing_ratios():
    means = np.ones((1, len(BLOCKS), 1, 2))
    means[0, BLOCKS.index("early"), 0, 0] = 0.0
    ratios = ratio_statistics(means)
    assert np.isnan(ratios[0, 0, 0]) and ratios[0, 0, 1] == 1


def test_interval_uses_replicates_and_keeps_the_observed_row():
    samples = np.vstack(
        [np.full(2, 1.5), np.linspace(0.6, 1.4, 1000)[:, None] * [1, 1]]
    )
    summary = interval(samples)
    # The observed row is reported as the point estimate and never resampled.
    np.testing.assert_allclose(summary["point"], 1.5)
    assert (summary["lower"] < 0.65).all() and (summary["upper"] > 1.35).all()
    # An interval straddling one cannot report a resolved departure.
    assert not summary["excludes_one"].any()
    assert interval(samples + 1)["excludes_one"].all()
    assert interval(samples - 1)["excludes_one"].all()
