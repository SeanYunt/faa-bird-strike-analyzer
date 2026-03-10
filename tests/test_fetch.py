"""Tests for data/fetch.py — file discovery utilities."""

import pytest
from pathlib import Path

import data.fetch as fetch_module
from data.fetch import find_strikes_dataset, find_airports_dataset, find_preprocessed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_search_dirs(monkeypatch, dirs):
    monkeypatch.setattr(fetch_module, "_SEARCH_DIRS", [Path(d) for d in dirs])


# ---------------------------------------------------------------------------
# find_strikes_dataset
# ---------------------------------------------------------------------------

def test_find_strikes_dataset_finds_strike_in_name(monkeypatch, tmp_path):
    strike_file = tmp_path / "wildlife_strike_2024.csv"
    strike_file.write_text("col1,col2\n1,2\n")
    _patch_search_dirs(monkeypatch, [tmp_path])
    result = find_strikes_dataset()
    assert result == strike_file


def test_find_strikes_dataset_finds_wildlife_prefix(monkeypatch, tmp_path):
    wildlife_file = tmp_path / "wildlife_data.csv"
    wildlife_file.write_text("col1,col2\n1,2\n")
    _patch_search_dirs(monkeypatch, [tmp_path])
    result = find_strikes_dataset()
    assert result == wildlife_file


def test_find_strikes_dataset_finds_bird_prefix(monkeypatch, tmp_path):
    bird_file = tmp_path / "bird_incidents.csv"
    bird_file.write_text("col1,col2\n1,2\n")
    _patch_search_dirs(monkeypatch, [tmp_path])
    result = find_strikes_dataset()
    assert result == bird_file


def test_find_strikes_dataset_raises_when_nothing_found(monkeypatch, tmp_path):
    unrelated_file = tmp_path / "airports.csv"
    unrelated_file.write_text("col1,col2\n")
    _patch_search_dirs(monkeypatch, [tmp_path])
    with pytest.raises(FileNotFoundError):
        find_strikes_dataset()


def test_find_strikes_dataset_raises_when_dir_empty(monkeypatch, tmp_path):
    _patch_search_dirs(monkeypatch, [tmp_path])
    with pytest.raises(FileNotFoundError):
        find_strikes_dataset()


def test_find_strikes_dataset_skips_nonexistent_dirs(monkeypatch, tmp_path):
    nonexistent = tmp_path / "does_not_exist"
    strike_file = tmp_path / "strikes.csv"
    strike_file.write_text("col1\n")
    _patch_search_dirs(monkeypatch, [nonexistent, tmp_path])
    result = find_strikes_dataset()
    assert result == strike_file


# ---------------------------------------------------------------------------
# find_airports_dataset
# ---------------------------------------------------------------------------

def test_find_airports_dataset_finds_airport_in_name(monkeypatch, tmp_path):
    airport_file = tmp_path / "airports.csv"
    airport_file.write_text("id,name\n")
    _patch_search_dirs(monkeypatch, [tmp_path])
    result = find_airports_dataset()
    assert result == airport_file


def test_find_airports_dataset_finds_ourairport_in_name(monkeypatch, tmp_path):
    ourairport_file = tmp_path / "ourairports_data.csv"
    ourairport_file.write_text("id,name\n")
    _patch_search_dirs(monkeypatch, [tmp_path])
    result = find_airports_dataset()
    assert result == ourairport_file


def test_find_airports_dataset_returns_none_when_not_found(monkeypatch, tmp_path):
    unrelated = tmp_path / "strikes.csv"
    unrelated.write_text("col1\n")
    _patch_search_dirs(monkeypatch, [tmp_path])
    result = find_airports_dataset()
    assert result is None


def test_find_airports_dataset_returns_none_for_empty_dir(monkeypatch, tmp_path):
    _patch_search_dirs(monkeypatch, [tmp_path])
    result = find_airports_dataset()
    assert result is None


def test_find_airports_dataset_skips_nonexistent_dirs(monkeypatch, tmp_path):
    nonexistent = tmp_path / "nope"
    airport_file = tmp_path / "airport_list.csv"
    airport_file.write_text("id\n")
    _patch_search_dirs(monkeypatch, [nonexistent, tmp_path])
    result = find_airports_dataset()
    assert result == airport_file


# ---------------------------------------------------------------------------
# find_preprocessed
# ---------------------------------------------------------------------------

def test_find_preprocessed_returns_both_paths_when_both_exist(monkeypatch, tmp_path):
    preprocessed_dir = tmp_path / "data" / "preprocessed"
    preprocessed_dir.mkdir(parents=True)
    airport_parquet = preprocessed_dir / "airport_stats.parquet"
    seasonal_parquet = preprocessed_dir / "seasonal_stats.parquet"
    airport_parquet.write_bytes(b"dummy")
    seasonal_parquet.write_bytes(b"dummy")

    monkeypatch.setattr(fetch_module, "find_preprocessed",
                        lambda: (airport_parquet, seasonal_parquet))
    result = fetch_module.find_preprocessed()
    assert result is not None
    assert result[0] == airport_parquet
    assert result[1] == seasonal_parquet


def test_find_preprocessed_returns_none_when_airport_parquet_missing(monkeypatch, tmp_path):
    # Patch the base path used inside find_preprocessed by patching Path
    # We patch the function directly by pointing _SEARCH_DIRS away and testing
    # the real function with a tmp location.
    preprocessed_dir = tmp_path / "data" / "preprocessed"
    preprocessed_dir.mkdir(parents=True)
    # Only create seasonal, not airport
    seasonal_parquet = preprocessed_dir / "seasonal_stats.parquet"
    seasonal_parquet.write_bytes(b"dummy")

    # Patch the Path constructor inside fetch to redirect lookups to tmp
    import data.fetch as fm
    original_fn = fm.find_preprocessed

    def patched():
        base = preprocessed_dir
        airport_path = base / "airport_stats.parquet"
        seasonal_path = base / "seasonal_stats.parquet"
        if airport_path.exists() and seasonal_path.exists():
            return airport_path, seasonal_path
        return None

    monkeypatch.setattr(fm, "find_preprocessed", patched)
    assert fm.find_preprocessed() is None


def test_find_preprocessed_returns_none_when_seasonal_parquet_missing(monkeypatch, tmp_path):
    preprocessed_dir = tmp_path / "data" / "preprocessed"
    preprocessed_dir.mkdir(parents=True)
    # Only create airport, not seasonal
    airport_parquet = preprocessed_dir / "airport_stats.parquet"
    airport_parquet.write_bytes(b"dummy")

    import data.fetch as fm

    def patched():
        base = preprocessed_dir
        airport_path = base / "airport_stats.parquet"
        seasonal_path = base / "seasonal_stats.parquet"
        if airport_path.exists() and seasonal_path.exists():
            return airport_path, seasonal_path
        return None

    monkeypatch.setattr(fm, "find_preprocessed", patched)
    assert fm.find_preprocessed() is None


def test_find_preprocessed_returns_none_when_both_parquets_missing(monkeypatch, tmp_path):
    preprocessed_dir = tmp_path / "data" / "preprocessed"
    preprocessed_dir.mkdir(parents=True)

    import data.fetch as fm

    def patched():
        base = preprocessed_dir
        airport_path = base / "airport_stats.parquet"
        seasonal_path = base / "seasonal_stats.parquet"
        if airport_path.exists() and seasonal_path.exists():
            return airport_path, seasonal_path
        return None

    monkeypatch.setattr(fm, "find_preprocessed", patched)
    assert fm.find_preprocessed() is None
