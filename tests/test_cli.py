"""Tests for the CLI commands in cli.py using Click's CliRunner."""

from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest
from click.testing import CliRunner

from cli import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_airport_parquet(tmp_path: Path) -> Path:
    """Write a minimal airport_stats parquet that load_airport_stats can read."""
    df = pl.DataFrame({
        "airport_id":    ["JFK", "ORD", "SEA"],
        "airport_name":  ["John F Kennedy Intl", "Chicago O'Hare", "Seattle-Tacoma"],
        "state":         ["NY", "IL", "WA"],
        "latitude":      [40.6, 41.9, 47.4],
        "longitude":     [-73.8, -87.9, -122.3],
        "total_strikes": [120, 85, 60],
        "damage_rate":   [0.35, 0.22, 0.18],
        "avg_cost":      [4500.0, 2100.0, 1800.0],
        "top_species":   ["Canada Goose, Starling", "Starling, Pigeon", "Gull, Canada Goose"],
        "flyway":        ["Atlantic", "Mississippi", "Pacific"],
        "risk_score":    [0.72, 0.48, 0.31],
        "damage_trend":  [0.0, 0.0, 0.0],
        "strikes_spring": [20, 30, 25],
        "strikes_summer": [45, 28, 15],
        "strikes_fall":   [35, 20, 12],
        "strikes_winter": [20,  7,  8],
    })
    path = tmp_path / "airport_stats.parquet"
    df.write_parquet(path)
    return path


def _make_seasonal_parquet(tmp_path: Path) -> Path:
    df = pl.DataFrame({
        "season":        ["Spring", "Summer", "Fall", "Winter"],
        "total_strikes": [100, 150, 110, 70],
        "damage_rate":   [0.20, 0.25, 0.22, 0.18],
    })
    path = tmp_path / "seasonal_stats.parquet"
    df.write_parquet(path)
    return path


# ---------------------------------------------------------------------------
# top command
# ---------------------------------------------------------------------------

def test_top_no_preprocessed_data_exits_1(monkeypatch):
    monkeypatch.setattr("cli.find_preprocessed", lambda: None)
    runner = CliRunner()
    result = runner.invoke(cli, ["top"])
    assert result.exit_code == 1
    assert "No preprocessed data found" in result.output


def test_top_with_data_exits_0_and_shows_highest_risk(monkeypatch, tmp_path):
    airport_path = _make_airport_parquet(tmp_path)
    seasonal_path = _make_seasonal_parquet(tmp_path)
    monkeypatch.setattr("cli.find_preprocessed", lambda: (airport_path, seasonal_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["top"])
    assert result.exit_code == 0
    assert "Highest-Risk" in result.output


def test_top_with_data_lists_airport_ids(monkeypatch, tmp_path):
    airport_path = _make_airport_parquet(tmp_path)
    seasonal_path = _make_seasonal_parquet(tmp_path)
    monkeypatch.setattr("cli.find_preprocessed", lambda: (airport_path, seasonal_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["top", "--min-strikes", "50"])
    assert result.exit_code == 0
    # JFK and ORD both have >= 50 strikes
    assert "JFK" in result.output
    assert "ORD" in result.output


# ---------------------------------------------------------------------------
# profile command
# ---------------------------------------------------------------------------

def test_profile_no_preprocessed_data_exits_1(monkeypatch):
    monkeypatch.setattr("cli.find_preprocessed", lambda: None)
    runner = CliRunner()
    result = runner.invoke(cli, ["profile", "JFK"])
    assert result.exit_code == 1
    assert "No preprocessed data found" in result.output


def test_profile_airport_not_found_exits_1(monkeypatch, tmp_path):
    airport_path = _make_airport_parquet(tmp_path)
    seasonal_path = _make_seasonal_parquet(tmp_path)
    monkeypatch.setattr("cli.find_preprocessed", lambda: (airport_path, seasonal_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["profile", "ZZZZ"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_profile_airport_id_case_insensitive(monkeypatch, tmp_path):
    airport_path = _make_airport_parquet(tmp_path)
    seasonal_path = _make_seasonal_parquet(tmp_path)
    monkeypatch.setattr("cli.find_preprocessed", lambda: (airport_path, seasonal_path))
    # Provide a lowercase id — the CLI uppercases it internally
    runner = CliRunner()
    with patch("cli.generate_airport_dossier") as mock_dossier:
        mock_dossier.return_value = Path(tmp_path / "dossier.pdf")
        result = runner.invoke(cli, ["profile", "jfk"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# map command
# ---------------------------------------------------------------------------

def test_map_no_preprocessed_data_exits_1(monkeypatch):
    monkeypatch.setattr("cli.find_preprocessed", lambda: None)
    runner = CliRunner()
    result = runner.invoke(cli, ["map"])
    assert result.exit_code == 1
    assert "No preprocessed data found" in result.output


def test_map_national_calls_render_national_map(monkeypatch, tmp_path):
    airport_path = _make_airport_parquet(tmp_path)
    seasonal_path = _make_seasonal_parquet(tmp_path)
    monkeypatch.setattr("cli.find_preprocessed", lambda: (airport_path, seasonal_path))
    # Redirect MAPS_DIR output into tmp_path to avoid polluting the repo
    monkeypatch.setattr("cli.MAPS_DIR", tmp_path)

    called_with = {}

    def fake_render(airport_stats, output_path):
        called_with["airport_stats"] = airport_stats
        called_with["output_path"] = output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"PNG")
        return output_path

    with patch("cli.render_national_map", side_effect=fake_render):
        runner = CliRunner()
        result = runner.invoke(cli, ["map", "--output", "national"])

    assert result.exit_code == 0
    assert "airport_stats" in called_with


# ---------------------------------------------------------------------------
# chart command
# ---------------------------------------------------------------------------

def test_chart_no_species_parquet_exits_1(monkeypatch, tmp_path):
    # Ensure the species parquet does NOT exist by pointing at a nonexistent path
    nonexistent = tmp_path / "data" / "preprocessed" / "species_stats.parquet"
    with patch("cli.Path") as MockPath:
        # We patch just enough: make the species_parquet Path instance report not existing
        real_path = Path.__new__(Path)

        def fake_path(arg):
            p = Path(arg)
            return p

        # Instead of patching Path globally (which breaks everything), patch
        # the specific attribute on the module after import
        import cli as cli_module
        original = cli_module.Path

        class _FakePath(type(Path())):
            pass

        monkeypatch.setattr(cli_module, "Path", lambda x: _nonexistent_if_species(x, tmp_path))
        runner = CliRunner()
        result = runner.invoke(cli, ["chart"])

    assert result.exit_code == 1
    assert "No species data found" in result.output


def _nonexistent_if_species(arg, tmp_path):
    """Return a path that doesn't exist when it's the species parquet."""
    p = Path(arg)
    if "species_stats" in str(p):
        return tmp_path / "nonexistent" / "species_stats.parquet"
    return p


def test_chart_no_species_parquet_simple(monkeypatch):
    """Simpler test: monkeypatch find_preprocessed is irrelevant; species parquet path is the guard."""
    import cli as cli_module
    # Patch Path so species_stats.parquet appears to not exist
    original_path_cls = cli_module.Path

    class PatchedPath(type(Path())):
        def exists(self):
            if "species_stats" in str(self):
                return False
            return super().exists()

    monkeypatch.setattr(cli_module, "Path", lambda x: PatchedPath(x))
    runner = CliRunner()
    result = runner.invoke(cli, ["chart"])
    assert result.exit_code == 1
    assert "No species data found" in result.output
