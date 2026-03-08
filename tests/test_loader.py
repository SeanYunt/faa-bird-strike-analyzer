"""Tests for data loading and normalization."""

import polars as pl
import pytest

from data.loader import (
    SEASONS,
    _add_damage_flag,
    _assign_flyway,
    _coerce_numeric_types,
    _normalize_columns,
    _parse_dates_and_season,
)


def test_normalize_columns_renames_faa_variants():
    df = pl.DataFrame({
        "AIRPORT_ID": ["JFK"],
        "AIRPORT": ["Kennedy"],
        "PHASE_OF_FLT": ["Approach"],
        "DAMAGE_LEVEL": ["S"],
    })
    result = _normalize_columns(df)
    assert "airport_id" in result.columns
    assert "airport_name" in result.columns
    assert "phase" in result.columns
    assert "damage_level" in result.columns


def test_normalize_columns_case_insensitive():
    df = pl.DataFrame({"airport_id": ["BOS"], "species": ["Gull"]})
    result = _normalize_columns(df)
    assert "airport_id" in result.columns
    assert "species" in result.columns


def test_normalize_columns_preserves_unknown_cols():
    df = pl.DataFrame({"AIRPORT_ID": ["ORD"], "MY_CUSTOM_COL": [42]})
    result = _normalize_columns(df)
    assert "airport_id" in result.columns
    assert "MY_CUSTOM_COL" in result.columns


def test_coerce_numeric_types_handles_strings():
    df = pl.DataFrame({
        "num_struck": ["2", "N/A", None, "5"],
        "cost_repairs": ["1500.0", "", None, "3000"],
    })
    result = _coerce_numeric_types(df)
    assert result["num_struck"].dtype == pl.Int32
    assert result["cost_repairs"].dtype == pl.Float64
    assert result["num_struck"][1] == 1   # null filled with 1
    assert result["cost_repairs"][1] == 0.0


def test_parse_dates_mm_dd_yyyy():
    df = pl.DataFrame({"date": ["06/15/2020", "12/01/2019", "03/22/2021"]})
    result = _parse_dates_and_season(df)
    assert "season" in result.columns
    assert result["season"][0] == "Summer"
    assert result["season"][1] == "Winter"
    assert result["season"][2] == "Spring"


def test_parse_dates_yyyy_mm_dd():
    df = pl.DataFrame({"date": ["2020-09-10", "2021-04-05"]})
    result = _parse_dates_and_season(df)
    assert result["season"][0] == "Fall"
    assert result["season"][1] == "Spring"


def test_parse_dates_no_date_column():
    df = pl.DataFrame({"airport_id": ["JFK"]})
    result = _parse_dates_and_season(df)
    assert result["season"][0] == "Unknown"


def test_add_damage_flag_from_damage_level():
    df = pl.DataFrame({"damage_level": ["N", "M", "S", "D", "N/A"]})
    result = _add_damage_flag(df)
    assert result["has_damage"].to_list() == [False, True, True, True, False]


def test_add_damage_flag_from_indicated_damage():
    df = pl.DataFrame({"indicated_damage": ["Y", "N", "Y", None]})
    result = _add_damage_flag(df)
    assert result["has_damage"][0] is True
    assert result["has_damage"][1] is False


def test_add_damage_flag_fallback():
    df = pl.DataFrame({"airport_id": ["JFK", "BOS"]})
    result = _add_damage_flag(df)
    assert result["has_damage"].to_list() == [False, False]


def test_assign_flyway_boundaries():
    assert _assign_flyway(-120.0, 45.0) == "Pacific"
    assert _assign_flyway(-107.0, 40.0) == "Central"
    assert _assign_flyway(-90.0, 38.0) == "Mississippi"
    assert _assign_flyway(-75.0, 40.0) == "Atlantic"
    assert _assign_flyway(None, None) == "Unknown"


def test_seasons_dict_covers_all_months():
    for month in range(1, 13):
        assert month in SEASONS
        assert SEASONS[month] in ("Spring", "Summer", "Fall", "Winter")
