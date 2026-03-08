from pathlib import Path

import click

from data.fetch import find_airports_dataset, find_preprocessed, find_strikes_dataset
from data.loader import preprocess
from analysis.seasonal import (
    compute_flyway_summaries,
    filter_with_coordinates,
    get_peak_season,
    load_airport_stats,
    load_seasonal_stats,
    top_airports_by_risk,
)
from maps.renderer import render_flyway_map, render_national_map, render_seasonal_map, render_trend_map, render_species_danger_matrix
from reports.pdf import generate_airport_dossier

OUTPUT_DIR = Path("output")
MAPS_DIR   = OUTPUT_DIR / "maps"


@click.group()
def cli():
    """FAA Bird Strike Analyzer — Map wildlife strike patterns and build airport dossiers."""
    pass


@cli.command()
@click.option("--strikes-path", default=None, type=click.Path(exists=True),
              help="Path to FAA Wildlife Strike CSV (auto-detected if omitted)")
@click.option("--airports-path", default=None, type=click.Path(exists=True),
              help="Path to airports CSV with lat/lon (OurAirports format)")
def preprocess_cmd(strikes_path: str | None, airports_path: str | None):
    """Pre-aggregate raw FAA data into small summary files for fast analysis."""
    strikes = Path(strikes_path) if strikes_path else find_strikes_dataset()
    airports = Path(airports_path) if airports_path else find_airports_dataset()

    if airports is None:
        click.echo(
            "No airports CSV found — maps will lack coordinates.\n"
            "Download airports.csv from ourairports.com/data/ and place in data/raw/."
        )

    airport_path, seasonal_path = preprocess(strikes, airports)
    click.echo(f"\nPreprocessing complete.")
    click.echo(f"  Airport summary : {airport_path}")
    click.echo(f"  Seasonal summary: {seasonal_path}")
    click.echo("\nRun 'python cli.py map --output national' to generate maps.")


@cli.command()
@click.option(
    "--output", "output_type",
    type=click.Choice(["national", "seasonal", "flyways", "trend", "all"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Which map(s) to generate.",
)
def map_cmd(output_type: str):
    """Generate static PNG maps of wildlife strike patterns."""
    preprocessed = find_preprocessed()
    if not preprocessed:
        click.echo(
            "No preprocessed data found. Run 'python cli.py preprocess' first.",
            err=True,
        )
        raise SystemExit(1)

    airport_path, seasonal_path = preprocessed
    click.echo("Loading preprocessed data...")
    airport_stats = load_airport_stats(airport_path)
    mapped = filter_with_coordinates(airport_stats)

    if not mapped:
        click.echo(
            "No airports have coordinates — cannot render maps.\n"
            "Re-run preprocess with an airports CSV to add lat/lon data.",
            err=True,
        )
        raise SystemExit(1)

    click.echo(f"  {len(airport_stats):,} airports loaded  |  {len(mapped):,} with coordinates")
    MAPS_DIR.mkdir(parents=True, exist_ok=True)

    generated = []

    if output_type in ("national", "all"):
        path = MAPS_DIR / "map_national.png"
        click.echo("Rendering national heatmap...")
        render_national_map(mapped, path)
        generated.append(path)

    if output_type in ("seasonal", "all"):
        path = MAPS_DIR / "map_seasonal.png"
        click.echo("Rendering seasonal migration map...")
        render_seasonal_map(mapped, path)
        generated.append(path)

    if output_type in ("flyways", "all"):
        path = MAPS_DIR / "map_flyways.png"
        click.echo("Rendering flyway overlay map...")
        render_flyway_map(mapped, path)
        generated.append(path)

    if output_type in ("trend", "all"):
        path = MAPS_DIR / "map_trend.png"
        click.echo("Rendering trend map...")
        annual_parquet = Path("data/preprocessed/annual_stats.parquet")
        render_trend_map(mapped, annual_parquet if annual_parquet.exists() else None, path)
        generated.append(path)

    click.echo(f"\nMaps saved to {MAPS_DIR}/:")
    for p in generated:
        click.echo(f"  {p.name}")


@cli.command()
@click.argument("airport_id")
def profile(airport_id: str):
    """Build a PDF dossier for a specific airport (e.g. JFK, ORD, LAX)."""
    preprocessed = find_preprocessed()
    if not preprocessed:
        click.echo(
            "No preprocessed data found. Run 'python cli.py preprocess' first.",
            err=True,
        )
        raise SystemExit(1)

    airport_path, _ = preprocessed
    airport_stats = load_airport_stats(airport_path)

    airport_id = airport_id.upper()
    match = next((a for a in airport_stats if a.airport_id.upper() == airport_id), None)
    if match is None:
        click.echo(f"Airport '{airport_id}' not found in preprocessed data.", err=True)
        click.echo(f"Available IDs (sample): {', '.join(a.airport_id for a in airport_stats[:10])}")
        raise SystemExit(1)

    click.echo(f"Building dossier for {match.airport_name or match.airport_id}...")
    pdf_path = generate_airport_dossier(match, airport_stats)

    click.echo(f"\nDossier generated: {pdf_path}")
    click.echo(f"\n{'=' * 55}")
    click.echo(f"  Airport : {match.airport_name or match.airport_id} ({match.airport_id})")
    click.echo(f"  State   : {match.state or '—'}")
    click.echo(f"  Flyway  : {match.flyway}")
    click.echo(f"  Strikes : {match.total_strikes:,}")
    click.echo(f"  Damage  : {match.damage_rate:.1%}")
    click.echo(f"  Risk    : {match.risk_score:.0%}")
    if match.top_species:
        click.echo(f"  Top species: {', '.join(match.top_species[:3])}")
    click.echo(f"{'=' * 55}")


@cli.command()
@click.option("--top", default=20, show_default=True, help="Number of airports to list.")
@click.option("--min-strikes", default=50, show_default=True,
              help="Exclude airports with fewer than this many total strikes (avoids small-sample noise).")
def top(top: int, min_strikes: int):
    """Print the top N riskiest airports from preprocessed data."""
    preprocessed = find_preprocessed()
    if not preprocessed:
        click.echo("No preprocessed data found. Run 'python cli.py preprocess' first.", err=True)
        raise SystemExit(1)

    airport_path, seasonal_path = preprocessed
    airport_stats = load_airport_stats(airport_path)
    filtered = [a for a in airport_stats
                if a.total_strikes >= min_strikes and a.airport_id.upper() != "ZZZZ"]
    flyway_summaries = compute_flyway_summaries(airport_stats)
    peak_seasons = get_peak_season(airport_stats)

    click.echo(f"\nTop {top} Highest-Risk Airports (min {min_strikes:,} strikes):")
    click.echo("-" * 75)
    for i, airport in enumerate(top_airports_by_risk(filtered, top), 1):
        click.echo(
            f"  {i:3d}. {airport.airport_id:<6}  {airport.airport_name[:28]:<28}  "
            f"State: {airport.state or '?':2}  "
            f"Strikes: {airport.total_strikes:>5,}  "
            f"Damage: {airport.damage_rate:>5.1%}  "
            f"Risk: {airport.risk_score:.0%}"
        )

    click.echo(f"\nFlyway Summary:")
    click.echo("-" * 55)
    for fw in flyway_summaries:
        peak = peak_seasons.get(fw.name, "—")
        click.echo(
            f"  {fw.name:<14}  Strikes: {fw.total_strikes:>6,}  "
            f"Damage: {fw.damage_rate:>5.1%}  Peak: {peak}"
        )


@cli.command()
@click.option(
    "--output", "output_type",
    type=click.Choice(["danger-matrix"], case_sensitive=False),
    default="danger-matrix",
    show_default=True,
    help="Which chart to generate.",
)
def chart(output_type: str):
    """Generate analytical charts from preprocessed data."""
    charts_dir = OUTPUT_DIR / "charts"
    species_parquet = Path("data/preprocessed/species_stats.parquet")

    if not species_parquet.exists():
        click.echo("No species data found. Run 'python cli.py preprocess' first.", err=True)
        raise SystemExit(1)

    charts_dir.mkdir(parents=True, exist_ok=True)

    if output_type == "danger-matrix":
        path = charts_dir / "chart_danger_matrix.png"
        click.echo("Rendering species danger matrix...")
        render_species_danger_matrix(species_parquet, path)
        click.echo(f"\nChart saved: {path}")


# Rename commands to match README
cli.add_command(preprocess_cmd, name="preprocess")
cli.add_command(map_cmd, name="map")

if __name__ == "__main__":
    cli()
