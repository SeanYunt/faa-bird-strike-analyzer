"""Shared test fixtures."""

import polars as pl
import pytest

from data.models import AirportStats


@pytest.fixture
def sample_strikes_df() -> pl.DataFrame:
    """Synthetic normalized strike DataFrame."""
    return pl.DataFrame({
        "airport_id":    ["JFK", "JFK", "JFK", "BOS", "BOS", "ORD", "LAX", "LAX", "LAX", "LAX",
                          "DFW", "DFW", "SEA", "SEA", "SEA", "ATL", "ATL", "MIA", "DEN", "DEN"],
        "airport_name":  ["John F Kennedy Intl"] * 3 + ["Boston Logan"] * 2 +
                         ["Chicago O'Hare"] * 1 + ["Los Angeles Intl"] * 4 +
                         ["Dallas Ft Worth"] * 2 + ["Seattle-Tacoma"] * 3 +
                         ["Atlanta Hartsfield"] * 2 + ["Miami Intl"] * 1 +
                         ["Denver Intl"] * 2,
        "state":         ["NY"] * 3 + ["MA"] * 2 + ["IL"] * 1 + ["CA"] * 4 +
                         ["TX"] * 2 + ["WA"] * 3 + ["GA"] * 2 + ["FL"] * 1 + ["CO"] * 2,
        "date":          ["01/15/2020", "06/20/2020", "09/10/2020",
                          "04/05/2019", "08/22/2019",
                          "07/01/2021",
                          "03/14/2020", "05/30/2020", "10/15/2020", "12/01/2020",
                          "02/14/2019", "11/20/2019",
                          "04/10/2021", "06/25/2021", "09/05/2021",
                          "07/04/2020", "08/15/2020",
                          "05/20/2019",
                          "01/10/2021", "03/22/2021"],
        "season":        ["Winter", "Summer", "Fall",
                          "Spring", "Summer",
                          "Summer",
                          "Spring", "Spring", "Fall", "Winter",
                          "Winter", "Fall",
                          "Spring", "Summer", "Fall",
                          "Summer", "Summer",
                          "Spring",
                          "Winter", "Spring"],
        "species":       ["Canada Goose", "Starling", "Canada Goose",
                          "Gull", "Pigeon",
                          "Starling",
                          "Gull", "Canada Goose", "Hawk", "Starling",
                          "Dove", "Hawk",
                          "Gull", "Canada Goose", "Starling",
                          "Vulture", "Vulture",
                          "Pelican",
                          "Hawk", "Canada Goose"],
        "size":          ["Large", "Small", "Large",
                          "Medium", "Small",
                          "Small",
                          "Medium", "Large", "Medium", "Small",
                          "Small", "Medium",
                          "Medium", "Large", "Small",
                          "Large", "Large",
                          "Large",
                          "Medium", "Large"],
        "has_damage":    [True, False, True,
                          False, False,
                          False,
                          True, True, False, False,
                          False, True,
                          False, True, False,
                          True, False,
                          True,
                          False, True],
        "cost_repairs":  [12000.0, 0.0, 8500.0,
                          0.0, 0.0,
                          0.0,
                          5000.0, 22000.0, 0.0, 0.0,
                          0.0, 3500.0,
                          0.0, 18000.0, 0.0,
                          45000.0, 0.0,
                          9000.0,
                          0.0, 6000.0],
        "num_struck":    [1, 3, 1, 1, 2, 5, 1, 1, 1, 2, 1, 1, 1, 1, 3, 1, 1, 1, 1, 1],
        "latitude":      [40.6, 40.6, 40.6, 42.4, 42.4, 41.9, 33.9, 33.9, 33.9, 33.9,
                          32.9, 32.9, 47.4, 47.4, 47.4, 33.6, 33.6, 25.8, 39.9, 39.9],
        "longitude":     [-73.8, -73.8, -73.8, -71.0, -71.0, -87.9, -118.4, -118.4, -118.4, -118.4,
                          -97.0, -97.0, -122.3, -122.3, -122.3, -84.4, -84.4, -80.3, -104.7, -104.7],
        "flyway":        ["Atlantic"] * 5 + ["Mississippi"] * 1 + ["Pacific"] * 4 +
                         ["Central"] * 2 + ["Pacific"] * 3 + ["Atlantic"] * 2 +
                         ["Atlantic"] * 1 + ["Central"] * 2,
        "damage_level":  ["S", "N", "M", "N", "N", "N", "M", "S", "N", "N",
                          "N", "M", "N", "S", "N", "S", "N", "M", "N", "M"],
    })


@pytest.fixture
def sample_airport_stats() -> list[AirportStats]:
    return [
        AirportStats(
            airport_id="JFK",
            airport_name="John F Kennedy Intl",
            state="NY",
            latitude=40.6,
            longitude=-73.8,
            total_strikes=120,
            damage_rate=0.35,
            avg_cost_per_strike=4500.0,
            top_species=["Canada Goose", "Starling", "Gull"],
            seasonal_counts={"Spring": 20, "Summer": 45, "Fall": 35, "Winter": 20},
            flyway="Atlantic",
            risk_score=0.72,
        ),
        AirportStats(
            airport_id="ORD",
            airport_name="Chicago O'Hare",
            state="IL",
            latitude=41.9,
            longitude=-87.9,
            total_strikes=85,
            damage_rate=0.22,
            avg_cost_per_strike=2100.0,
            top_species=["Starling", "Pigeon"],
            seasonal_counts={"Spring": 30, "Summer": 28, "Fall": 20, "Winter": 7},
            flyway="Mississippi",
            risk_score=0.48,
        ),
        AirportStats(
            airport_id="SEA",
            airport_name="Seattle-Tacoma",
            state="WA",
            latitude=47.4,
            longitude=-122.3,
            total_strikes=60,
            damage_rate=0.18,
            avg_cost_per_strike=1800.0,
            top_species=["Gull", "Canada Goose"],
            seasonal_counts={"Spring": 25, "Summer": 15, "Fall": 12, "Winter": 8},
            flyway="Pacific",
            risk_score=0.31,
        ),
        AirportStats(
            airport_id="DFW",
            airport_name="Dallas Ft Worth",
            state="TX",
            latitude=32.9,
            longitude=-97.0,
            total_strikes=40,
            damage_rate=0.10,
            avg_cost_per_strike=800.0,
            top_species=["Dove", "Hawk"],
            seasonal_counts={"Spring": 12, "Summer": 14, "Fall": 10, "Winter": 4},
            flyway="Central",
            risk_score=0.18,
        ),
    ]
