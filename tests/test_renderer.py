"""Tests for map rendering — verifies output files are created."""

import pytest
from pathlib import Path

from maps.renderer import render_flyway_map, render_national_map, render_seasonal_map


def test_render_national_map_creates_file(sample_airport_stats, tmp_path):
    output = tmp_path / "national.png"
    result = render_national_map(sample_airport_stats, output)
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_render_seasonal_map_creates_file(sample_airport_stats, tmp_path):
    output = tmp_path / "seasonal.png"
    result = render_seasonal_map(sample_airport_stats, output)
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_render_flyway_map_creates_file(sample_airport_stats, tmp_path):
    output = tmp_path / "flyways.png"
    result = render_flyway_map(sample_airport_stats, output)
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_render_national_map_creates_parent_dir(sample_airport_stats, tmp_path):
    output = tmp_path / "nested" / "subdir" / "map.png"
    render_national_map(sample_airport_stats, output)
    assert output.exists()


def test_render_national_map_no_coords_raises():
    from data.models import AirportStats
    no_coord = [AirportStats(
        airport_id="X", airport_name="X", state="", latitude=0.0, longitude=0.0,
        total_strikes=10, damage_rate=0.1, avg_cost_per_strike=0.0,
        top_species=[], seasonal_counts={}, flyway="Unknown", risk_score=0.0,
    )]
    with pytest.raises(ValueError, match="No airports with coordinates"):
        render_national_map(no_coord, Path("/tmp/should_not_exist.png"))
