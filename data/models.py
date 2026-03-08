from dataclasses import dataclass, field


@dataclass
class AirportStats:
    airport_id: str
    airport_name: str
    state: str
    latitude: float
    longitude: float
    total_strikes: int
    damage_rate: float           # fraction of strikes with any damage
    avg_cost_per_strike: float   # average repair cost per strike
    top_species: list[str]       # top 5 species by frequency
    seasonal_counts: dict[str, int]  # {"Spring": 42, "Summer": 18, ...}
    flyway: str
    risk_score: float            # 0.0 – 1.0 composite risk
    damage_trend: float = 0.0   # linear slope of damage_rate per year (+ = worsening)


@dataclass
class SeasonalStats:
    season: str
    total_strikes: int
    damage_rate: float
    top_airports: list[tuple[str, int]]   # (airport_id, strike_count)
    top_species: list[tuple[str, int]]    # (species_name, strike_count)


@dataclass
class FlywaySummary:
    name: str
    total_strikes: int
    damage_rate: float
    top_airports: list[tuple[str, int]]
    peak_season: str
