"""Tests for analysis/seasonal.py."""

import pytest

from analysis.seasonal import (
    compute_flyway_summaries,
    filter_with_coordinates,
    get_peak_season,
    top_airports_by_risk,
)
from data.models import AirportStats


def test_compute_flyway_summaries_aggregates_correctly(sample_airport_stats):
    summaries = compute_flyway_summaries(sample_airport_stats)
    flyway_names = {s.name for s in summaries}
    assert "Atlantic" in flyway_names
    assert "Pacific" in flyway_names
    assert "Mississippi" in flyway_names
    assert "Central" in flyway_names


def test_compute_flyway_summaries_strike_totals(sample_airport_stats):
    summaries = compute_flyway_summaries(sample_airport_stats)
    atlantic = next(s for s in summaries if s.name == "Atlantic")
    assert atlantic.total_strikes == 120


def test_compute_flyway_summaries_damage_rate(sample_airport_stats):
    summaries = compute_flyway_summaries(sample_airport_stats)
    atlantic = next(s for s in summaries if s.name == "Atlantic")
    assert 0.0 < atlantic.damage_rate <= 1.0


def test_top_airports_by_risk_ordered(sample_airport_stats):
    top = top_airports_by_risk(sample_airport_stats, n=4)
    scores = [a.risk_score for a in top]
    assert scores == sorted(scores, reverse=True)


def test_top_airports_by_risk_limit(sample_airport_stats):
    top = top_airports_by_risk(sample_airport_stats, n=2)
    assert len(top) == 2
    assert top[0].airport_id == "JFK"


def test_get_peak_season(sample_airport_stats):
    peaks = get_peak_season(sample_airport_stats)
    assert "Atlantic" in peaks
    assert peaks["Atlantic"] in ("Spring", "Summer", "Fall", "Winter")


def test_filter_with_coordinates_excludes_zero(sample_airport_stats):
    # Add an airport with no coordinates
    no_coord = AirportStats(
        airport_id="???",
        airport_name="Unknown",
        state="",
        latitude=0.0,
        longitude=0.0,
        total_strikes=10,
        damage_rate=0.2,
        avg_cost_per_strike=0.0,
        top_species=[],
        seasonal_counts={},
        flyway="Unknown",
        risk_score=0.1,
    )
    result = filter_with_coordinates(sample_airport_stats + [no_coord])
    ids = [a.airport_id for a in result]
    assert "???" not in ids
    assert "JFK" in ids


def test_flyway_summaries_sorted_by_volume(sample_airport_stats):
    summaries = compute_flyway_summaries(sample_airport_stats)
    volumes = [s.total_strikes for s in summaries]
    assert volumes == sorted(volumes, reverse=True)
