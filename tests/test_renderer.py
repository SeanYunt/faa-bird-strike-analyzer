"""Tests for map rendering — verifies output files are created."""

import pytest
import polars as pl
from pathlib import Path

from maps.renderer import (
    render_flyway_map,
    render_national_map,
    render_seasonal_map,
    render_trend_map,
    render_species_danger_matrix,
)


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


# ---------------------------------------------------------------------------
# render_trend_map
# ---------------------------------------------------------------------------

def test_render_trend_map_with_no_annual_parquet_creates_file(sample_airport_stats, tmp_path):
    output = tmp_path / "trend.png"
    result = render_trend_map(sample_airport_stats, None, output)
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_render_trend_map_creates_parent_dirs(sample_airport_stats, tmp_path):
    output = tmp_path / "nested" / "trend.png"
    render_trend_map(sample_airport_stats, None, output)
    assert output.exists()


# ---------------------------------------------------------------------------
# render_species_danger_matrix
# ---------------------------------------------------------------------------

def _make_species_parquet(tmp_path, n_rows: int, min_strikes: int = 25) -> Path:
    """Write a minimal species parquet with n_rows all exceeding the >= 20 filter."""
    species_names = [f"Species_{i}" for i in range(n_rows)]
    df = pl.DataFrame({
        "species":       species_names,
        "total_strikes": [min_strikes + i for i in range(n_rows)],
        "damage_rate":   [0.05 + (i % 10) * 0.04 for i in range(n_rows)],
        "avg_cost":      [500.0 + i * 200 for i in range(n_rows)],
    })
    parquet_path = tmp_path / "species_stats.parquet"
    df.write_parquet(parquet_path)
    return parquet_path


def test_render_species_danger_matrix_creates_valid_png(tmp_path):
    parquet_path = _make_species_parquet(tmp_path, n_rows=12)
    output = tmp_path / "danger_matrix.png"
    result = render_species_danger_matrix(parquet_path, output)
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_render_species_danger_matrix_insufficient_data_raises(tmp_path):
    # Create parquet where all rows have < 20 strikes so the filter leaves < 5 rows
    df = pl.DataFrame({
        "species":       [f"Sp_{i}" for i in range(4)],
        "total_strikes": [5, 8, 10, 3],   # all below the >= 20 threshold
        "damage_rate":   [0.1, 0.2, 0.15, 0.05],
        "avg_cost":      [100.0, 200.0, 150.0, 50.0],
    })
    parquet_path = tmp_path / "sparse_species.parquet"
    df.write_parquet(parquet_path)
    with pytest.raises(ValueError, match="Insufficient species data"):
        render_species_danger_matrix(parquet_path, tmp_path / "out.png")
