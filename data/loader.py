from pathlib import Path
from typing import Optional

import polars as pl

# Maps internal standard names -> known FAA column name variants (uppercase for matching)
COLUMN_ALIASES: dict[str, list[str]] = {
    "airport_id":       ["AIRPORT_ID", "SITE_ID", "LOC_ID"],
    "airport_name":     ["AIRPORT", "AIRPORTNAME", "AIRPORT_NAME"],
    "state":            ["STATE", "ST"],
    "date":             ["INCIDENT_DATE", "DATE", "STRIKE_DATE"],
    "time_of_day":      ["TIME_OF_DAY", "TIMEOFDAY"],
    "phase":            ["PHASE_OF_FLT", "PHASE", "FLT_PHASE"],
    "species":          ["SPECIES", "SPECIES_NAME", "WILDLIFE_SPECIES"],
    "size":             ["SIZE", "WILDLIFE_SIZE"],
    "num_struck":       ["NUM_STRUCK", "NUM_STRUCK_ACTUAL", "NUMSTRK"],
    "damage_level":     ["DAMAGE_LEVEL", "DAM_LEVEL"],
    "cost_repairs":     ["COST_REPAIRS", "COST_REPAIRS_INFL_ADJ", "COST"],
    "height":           ["HEIGHT", "HEIGHT_AGL", "AGL"],
    "indicated_damage": ["INDICATED_DAMAGE", "IND_DAMAGE"],
    "warned":           ["WARNED"],
    "operator":         ["OPERATOR", "AIRLINE", "OPID"],
    "aircraft_type":    ["ATYPE", "AIRCRAFT_TYPE", "AC_TYPE"],
}

SEASONS: dict[int, str] = {
    1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Fall",  10: "Fall",  11: "Fall",
    12: "Winter",
}

FLYWAY_BOUNDS = [
    ("Pacific",     None,   -114.0),
    ("Central",   -114.0,   -100.0),
    ("Mississippi",-100.0,   -83.0),
    ("Atlantic",   -83.0,    None),
]


def load_strikes(filepath: Path) -> pl.DataFrame:
    """Load and normalize FAA Wildlife Strike CSV or Excel file into a standard schema."""
    if Path(filepath).suffix.lower() in (".xlsx", ".xls"):
        df = pl.read_excel(filepath)
    else:
        df = pl.read_csv(
            filepath,
            infer_schema_length=10_000,
            ignore_errors=True,
            null_values=["", "N/A", "NA", "UNK", "Unknown", "UNKNOWN"],
        )
    df = _normalize_columns(df)
    df = _coerce_numeric_types(df)
    df = _parse_dates_and_season(df)
    df = _add_damage_flag(df)
    return df


def load_airports(filepath: Path) -> pl.DataFrame:
    """Load airports CSV (OurAirports format) and return ident/lat/lon."""
    df = pl.read_csv(filepath, ignore_errors=True)
    cols = set(df.columns)

    rename: dict[str, str] = {}
    for std, variants in [
        ("ident",     ["ident", "ICAO", "icao_code", "faa_code"]),
        ("iata",      ["iata_code", "iata", "IATA"]),
        ("name",      ["name", "airport_name"]),
        ("latitude",  ["latitude_deg", "lat", "latitude", "LATITUDE"]),
        ("longitude", ["longitude_deg", "lon", "longitude", "LONGITUDE"]),
    ]:
        if std in cols:
            continue
        for v in variants:
            if v in cols and v != std:
                rename[v] = std
                break

    df = df.rename(rename)
    keep = [c for c in ["ident", "iata", "name", "latitude", "longitude"] if c in df.columns]
    return df.select(keep)


def preprocess(
    strikes_path: Path,
    airports_path: Path | None = None,
) -> tuple[Path, Path]:
    """Aggregate raw strike data into two small summary parquets."""
    import click

    click.echo("Loading strike records...")
    strikes = load_strikes(strikes_path)
    click.echo(f"  {len(strikes):,} records loaded")

    if airports_path:
        click.echo("Joining airport coordinates...")
        airports = load_airports(airports_path)
        strikes = _join_coordinates(strikes, airports)

    if "longitude" in strikes.columns:
        click.echo("Assigning migration flyways...")
        strikes = strikes.with_columns(
            pl.when(pl.col("longitude").is_null())
            .then(pl.lit("Unknown"))
            .when(pl.col("longitude") <= -114.0)
            .then(pl.lit("Pacific"))
            .when(pl.col("longitude") <= -100.0)
            .then(pl.lit("Central"))
            .when(pl.col("longitude") <= -83.0)
            .then(pl.lit("Mississippi"))
            .otherwise(pl.lit("Atlantic"))
            .alias("flyway")
        )
    else:
        strikes = strikes.with_columns(pl.lit("Unknown").alias("flyway"))

    out_dir = Path("data/preprocessed")
    out_dir.mkdir(parents=True, exist_ok=True)

    click.echo("Building airport summary...")
    airport_summary = _build_airport_summary(strikes)
    airport_path = out_dir / "airport_stats.parquet"
    airport_summary.write_parquet(airport_path)
    click.echo(f"  {airport_summary.height:,} airports summarized -> {airport_path}")

    click.echo("Building seasonal summary...")
    seasonal_summary = _build_seasonal_summary(strikes)
    seasonal_path = out_dir / "seasonal_stats.parquet"
    seasonal_summary.write_parquet(seasonal_path)
    click.echo(f"  Seasonal summary -> {seasonal_path}")

    click.echo("Building annual trend summary...")
    annual_summary = _build_annual_summary(strikes)
    annual_path = out_dir / "annual_stats.parquet"
    annual_summary.write_parquet(annual_path)
    click.echo(f"  Annual summary -> {annual_path}")

    click.echo("Building species summary...")
    species_summary = _build_species_summary(strikes)
    species_path = out_dir / "species_stats.parquet"
    species_summary.write_parquet(species_path)
    click.echo(f"  {species_summary.height:,} species summarized -> {species_path}")

    return airport_path, seasonal_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    upper_to_original = {c.upper(): c for c in df.columns}
    rename_map: dict[str, str] = {}
    for standard, aliases in COLUMN_ALIASES.items():
        if standard in df.columns:
            continue
        for alias in aliases:
            if alias in upper_to_original:
                rename_map[upper_to_original[alias]] = standard
                break
    return df.rename(rename_map)


def _coerce_numeric_types(df: pl.DataFrame) -> pl.DataFrame:
    exprs = []
    if "num_struck" in df.columns:
        exprs.append(pl.col("num_struck").cast(pl.Int32, strict=False).fill_null(1))
    if "cost_repairs" in df.columns:
        exprs.append(pl.col("cost_repairs").cast(pl.Float64, strict=False).fill_null(0.0))
    if "height" in df.columns:
        exprs.append(pl.col("height").cast(pl.Float64, strict=False).fill_null(0.0))
    if exprs:
        df = df.with_columns(exprs)
    return df


def _parse_dates_and_season(df: pl.DataFrame) -> pl.DataFrame:
    if "date" not in df.columns:
        return df.with_columns(pl.lit("Unknown").alias("season"))

    date_str = pl.col("date").cast(pl.String)
    parsed = (
        date_str.str.strptime(pl.Date, "%m/%d/%Y", strict=False)
        .fill_null(date_str.str.strptime(pl.Date, "%Y-%m-%d", strict=False))
        .fill_null(date_str.str.strptime(pl.Date, "%d/%m/%Y", strict=False))
    )

    df = df.with_columns(parsed.alias("date_parsed"))
    df = df.with_columns([
        pl.col("date_parsed").dt.month().alias("month"),
        pl.col("date_parsed").dt.year().alias("year"),
    ])
    df = df.with_columns(
        pl.when(pl.col("month").is_in([12, 1, 2])).then(pl.lit("Winter"))
        .when(pl.col("month").is_in([3, 4, 5])).then(pl.lit("Spring"))
        .when(pl.col("month").is_in([6, 7, 8])).then(pl.lit("Summer"))
        .when(pl.col("month").is_in([9, 10, 11])).then(pl.lit("Fall"))
        .otherwise(pl.lit("Unknown"))
        .alias("season")
    )
    return df


def _add_damage_flag(df: pl.DataFrame) -> pl.DataFrame:
    if "damage_level" in df.columns:
        no_damage = (
            pl.col("damage_level").cast(pl.String).str.to_uppercase()
            .is_in(["N", "NONE", "N/A", ""])
        )
        # Nulls mean damage is unknown — treat as no damage rather than inflating rates
        return df.with_columns(
            pl.when(pl.col("damage_level").is_null())
            .then(pl.lit(False))
            .otherwise(~no_damage)
            .alias("has_damage")
        )
    if "indicated_damage" in df.columns:
        return df.with_columns(
            pl.col("indicated_damage").cast(pl.String).str.to_uppercase()
            .is_in(["Y", "YES", "1", "TRUE"]).alias("has_damage")
        )
    return df.with_columns(pl.lit(False).alias("has_damage"))


def _join_coordinates(strikes: pl.DataFrame, airports: pl.DataFrame) -> pl.DataFrame:
    if "airport_id" not in strikes.columns:
        return strikes
    if "ident" not in airports.columns or "latitude" not in airports.columns:
        return strikes

    # FAA uses 3-char codes (JFK); OurAirports ICAO uses K+code (KJFK)
    # Build lookup table with both 4-char and stripped 3-char keys — all vectorized
    coords = (
        airports.select(["ident", "latitude", "longitude"])
        .drop_nulls()
        .with_columns(pl.col("ident").cast(pl.String).str.to_uppercase())
    )

    # 3-char version for US airports: strip leading "K" from 4-char ICAO codes
    us_3char = (
        coords
        .filter(
            (pl.col("ident").str.len_chars() == 4) & pl.col("ident").str.starts_with("K")
        )
        .with_columns(pl.col("ident").str.slice(1))
    )

    coord_df = pl.concat([coords, us_3char]).unique(subset=["ident"])

    strikes = strikes.with_columns(
        pl.col("airport_id").cast(pl.String).str.to_uppercase().alias("_join_key")
    )
    result = strikes.join(
        coord_df.rename({"ident": "_join_key"}),
        on="_join_key",
        how="left",
    ).drop("_join_key")
    return result


def _assign_flyway(lon: float | None, lat: float | None) -> str:
    if lon is None:
        return "Unknown"
    if lon <= -114.0:
        return "Pacific"
    elif lon <= -100.0:
        return "Central"
    elif lon <= -83.0:
        return "Mississippi"
    else:
        return "Atlantic"


def _build_airport_summary(df: pl.DataFrame) -> pl.DataFrame:
    if "airport_id" not in df.columns:
        return pl.DataFrame()

    agg_exprs = [
        pl.len().alias("total_strikes"),
        pl.col("has_damage").cast(pl.Float64).mean().alias("damage_rate"),
    ]
    if "cost_repairs" in df.columns:
        agg_exprs.append(pl.col("cost_repairs").mean().alias("avg_cost"))
    else:
        agg_exprs.append(pl.lit(0.0).alias("avg_cost"))

    for col, alias in [
        ("latitude",     "latitude"),
        ("longitude",    "longitude"),
        ("flyway",       "flyway"),
        ("state",        "state"),
        ("airport_name", "airport_name"),
    ]:
        if col in df.columns:
            agg_exprs.append(pl.col(col).first().alias(alias))
        else:
            agg_exprs.append(pl.lit(None).alias(alias))

    # Top species per airport (comma-separated string)
    if "species" in df.columns:
        agg_exprs.append(
            pl.col("species")
            .drop_nulls()
            .value_counts(sort=True)
            .head(5)
            .struct.field("species")
            .implode()
            .list.join(", ")
            .alias("top_species")
        )
    else:
        agg_exprs.append(pl.lit("").alias("top_species"))

    summary = df.group_by("airport_id").agg(agg_exprs)

    # Seasonal counts as separate columns
    if "season" in df.columns:
        for season in ["Spring", "Summer", "Fall", "Winter"]:
            season_counts = (
                df.filter(pl.col("season") == season)
                .group_by("airport_id")
                .agg(pl.len().alias(f"strikes_{season.lower()}"))
            )
            summary = summary.join(season_counts, on="airport_id", how="left").with_columns(
                pl.col(f"strikes_{season.lower()}").fill_null(0)
            )

    # Risk score: weighted combination of damage rate, volume, and cost
    max_strikes = summary["total_strikes"].max() or 1
    max_cost = summary["avg_cost"].max() or 1
    summary = summary.with_columns(
        (
            pl.col("damage_rate").fill_null(0.0) * 0.5
            + (pl.col("total_strikes") / max_strikes) * 0.3
            + (pl.col("avg_cost") / max_cost) * 0.2
        ).clip(0.0, 1.0).alias("risk_score")
    )

    # Join per-airport damage trend slopes
    trend_df = _compute_trend_slopes(df)
    if trend_df.height > 0:
        summary = summary.join(trend_df, on="airport_id", how="left").with_columns(
            pl.col("damage_trend").fill_null(0.0)
        )
    else:
        summary = summary.with_columns(pl.lit(0.0).alias("damage_trend"))

    return summary.sort("risk_score", descending=True)


def _compute_trend_slopes(df: pl.DataFrame) -> pl.DataFrame:
    """Compute linear slope of damage_rate per year per airport (percentage points/year)."""
    import numpy as np
    from collections import defaultdict

    if "year" not in df.columns or "airport_id" not in df.columns:
        return pl.DataFrame({"airport_id": pl.Series([], dtype=pl.String),
                             "damage_trend": pl.Series([], dtype=pl.Float64)})

    yearly = (
        df.filter(pl.col("year").is_not_null())
        .group_by(["airport_id", "year"])
        .agg([
            pl.len().alias("n_strikes"),
            pl.col("has_damage").cast(pl.Float64).mean().alias("yearly_damage_rate"),
        ])
        .filter(pl.col("n_strikes") >= 3)
        .sort(["airport_id", "year"])
    )

    airport_data: dict[str, list[tuple]] = defaultdict(list)
    for aid, yr, rate in zip(
        yearly["airport_id"].to_list(),
        yearly["year"].to_list(),
        yearly["yearly_damage_rate"].to_list(),
    ):
        airport_data[str(aid)].append((int(yr), float(rate)))

    slopes = []
    for aid, data in airport_data.items():
        if len(data) >= 3:
            years_arr = np.array([d[0] for d in data], dtype=float)
            rates_arr = np.array([d[1] for d in data], dtype=float)
            slope = float(np.polyfit(years_arr, rates_arr, 1)[0])
        else:
            slope = 0.0
        slopes.append({"airport_id": aid, "damage_trend": slope})

    return pl.DataFrame(slopes)


def _build_annual_summary(df: pl.DataFrame) -> pl.DataFrame:
    """National year-by-year strike count and damage rate."""
    if "year" not in df.columns:
        return pl.DataFrame()
    return (
        df.filter(pl.col("year").is_not_null())
        .group_by("year")
        .agg([
            pl.len().alias("total_strikes"),
            pl.col("has_damage").cast(pl.Float64).mean().alias("damage_rate"),
        ])
        .sort("year")
    )


def _build_species_summary(df: pl.DataFrame) -> pl.DataFrame:
    """Per-species strike count, damage rate, and average repair cost."""
    if "species" not in df.columns:
        return pl.DataFrame()

    agg_exprs = [
        pl.len().alias("total_strikes"),
        pl.col("has_damage").cast(pl.Float64).mean().alias("damage_rate"),
    ]
    if "cost_repairs" in df.columns:
        agg_exprs.append(
            pl.col("cost_repairs").filter(pl.col("cost_repairs") > 0).mean().fill_null(0.0).alias("avg_cost")
        )
    else:
        agg_exprs.append(pl.lit(0.0).alias("avg_cost"))

    return (
        df.filter(pl.col("species").is_not_null())
        .group_by("species")
        .agg(agg_exprs)
        .filter(pl.col("total_strikes") >= 10)
        .sort("total_strikes", descending=True)
    )


def _build_seasonal_summary(df: pl.DataFrame) -> pl.DataFrame:
    if "season" not in df.columns:
        return pl.DataFrame()

    agg_exprs = [
        pl.len().alias("total_strikes"),
        pl.col("has_damage").cast(pl.Float64).mean().alias("damage_rate"),
    ]
    return df.group_by("season").agg(agg_exprs).sort("total_strikes", descending=True)
