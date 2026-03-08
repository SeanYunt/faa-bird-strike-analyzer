"""
Compute seasonal, flyway, and airport-level statistics from preprocessed parquets.
All functions accept Polars DataFrames and return structured results.
"""

from pathlib import Path

import polars as pl

from data.models import AirportStats, FlywaySummary, SeasonalStats

SEASON_ORDER = ["Spring", "Summer", "Fall", "Winter"]
FLYWAY_COLORS = {
    "Pacific":     "#2196F3",
    "Central":     "#4CAF50",
    "Mississippi": "#FF9800",
    "Atlantic":    "#9C27B0",
    "Unknown":     "#9E9E9E",
}


def load_airport_stats(airport_parquet: Path) -> list[AirportStats]:
    """Convert airport summary parquet into AirportStats dataclass list."""
    df = pl.read_parquet(airport_parquet)
    results = []
    for row in df.iter_rows(named=True):
        seasonal = {
            s: int(row.get(f"strikes_{s.lower()}", 0) or 0)
            for s in SEASON_ORDER
        }
        top_sp = str(row.get("top_species") or "").split(", ")
        top_sp = [s for s in top_sp if s]

        results.append(AirportStats(
            airport_id=str(row.get("airport_id") or ""),
            airport_name=str(row.get("airport_name") or row.get("airport_id") or ""),
            state=str(row.get("state") or ""),
            latitude=float(row["latitude"]) if row.get("latitude") is not None else 0.0,
            longitude=float(row["longitude"]) if row.get("longitude") is not None else 0.0,
            total_strikes=int(row.get("total_strikes") or 0),
            damage_rate=float(row.get("damage_rate") or 0.0),
            avg_cost_per_strike=float(row.get("avg_cost") or 0.0),
            top_species=top_sp,
            seasonal_counts=seasonal,
            flyway=str(row.get("flyway") or "Unknown"),
            risk_score=float(row.get("risk_score") or 0.0),
            damage_trend=float(row.get("damage_trend") or 0.0),
        ))
    return results


def load_seasonal_stats(seasonal_parquet: Path) -> list[SeasonalStats]:
    """Convert seasonal summary parquet into SeasonalStats list."""
    df = pl.read_parquet(seasonal_parquet)
    results = []
    for row in df.iter_rows(named=True):
        results.append(SeasonalStats(
            season=str(row["season"]),
            total_strikes=int(row.get("total_strikes") or 0),
            damage_rate=float(row.get("damage_rate") or 0.0),
            top_airports=[],
            top_species=[],
        ))
    return results


def compute_flyway_summaries(airport_stats: list[AirportStats]) -> list[FlywaySummary]:
    """Aggregate airport stats by flyway."""
    flyways: dict[str, dict] = {}
    for a in airport_stats:
        fw = a.flyway or "Unknown"
        if fw not in flyways:
            flyways[fw] = {"strikes": 0, "damage_sum": 0.0, "airports": []}
        flyways[fw]["strikes"] += a.total_strikes
        flyways[fw]["damage_sum"] += a.damage_rate * a.total_strikes
        flyways[fw]["airports"].append((a.airport_id, a.total_strikes))

    results = []
    for name, data in sorted(flyways.items(), key=lambda x: -x[1]["strikes"]):
        total = data["strikes"]
        damage_rate = data["damage_sum"] / total if total > 0 else 0.0
        top_airports = sorted(data["airports"], key=lambda x: -x[1])[:5]
        results.append(FlywaySummary(
            name=name,
            total_strikes=total,
            damage_rate=damage_rate,
            top_airports=top_airports,
            peak_season="",  # filled in below if seasonal data available
        ))
    return results


def get_peak_season(airport_stats: list[AirportStats]) -> dict[str, str]:
    """Return peak season (highest strike count) per flyway."""
    flyway_season: dict[str, dict[str, int]] = {}
    for a in airport_stats:
        fw = a.flyway or "Unknown"
        if fw not in flyway_season:
            flyway_season[fw] = {s: 0 for s in SEASON_ORDER}
        for season, count in a.seasonal_counts.items():
            flyway_season[fw][season] = flyway_season[fw].get(season, 0) + count

    return {
        fw: max(seasons, key=seasons.get)
        for fw, seasons in flyway_season.items()
        if seasons
    }


def top_airports_by_risk(airport_stats: list[AirportStats], n: int = 20) -> list[AirportStats]:
    return sorted(airport_stats, key=lambda a: -a.risk_score)[:n]


def filter_with_coordinates(airport_stats: list[AirportStats]) -> list[AirportStats]:
    """Return only airports that have valid lat/lon (needed for map plotting)."""
    return [a for a in airport_stats if a.latitude != 0.0 and a.longitude != 0.0]
