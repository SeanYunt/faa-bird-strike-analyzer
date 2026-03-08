# FAA Bird Strike Analyzer

A CLI tool that maps wildlife strike patterns across US airports using public FAA data, with a focus on seasonal migration corridors. Generates publication-quality static maps and per-airport PDF investigation dossiers.

## Quick Start

```bash
pip install -r requirements.txt

# Download FAA Wildlife Strike database (Excel) from wildlife.faa.gov -> Database -> Download
# Download airports.csv from ourairports.com/data/
# Place both in data/raw/  (rename the strike file so it contains the word "bird", e.g. bird_strikes.xlsx)

# One-time preprocessing
python cli.py preprocess

# Generate all maps
python cli.py map --output all

# Generate the species danger matrix chart
python cli.py chart --output danger-matrix

# Print top 20 riskiest airports
python cli.py top --top 20

# Generate a PDF dossier for a specific airport
python cli.py profile JFK
```

## Data Sources

- **FAA Wildlife Strike Database** — public CSV export from [wildlife.faa.gov](https://wildlife.faa.gov). Every reported wildlife strike since 1990 (~280,000 records).
- **OurAirports** — free airports CSV with ICAO codes and lat/lon coordinates from [ourairports.com/data/](https://ourairports.com/data/).

## Pipeline Commands

### `preprocess`

Reads the raw FAA strike file (CSV or Excel), joins airport coordinates, assigns migration flyways, and writes four small summary parquets to `data/preprocessed/`. Run once before using any other command.

| Parquet | Contents |
|---|---|
| `airport_stats.parquet` | Per-airport risk scores, damage rates, seasonal counts, top species |
| `seasonal_stats.parquet` | Strike counts and damage rates by season |
| `annual_stats.parquet` | National year-by-year strike volume and damage rate |
| `species_stats.parquet` | Per-species strike count, damage rate, and avg repair cost |

### `map`

Generates static PNG maps from preprocessed data.

| Output | File | Description |
|---|---|---|
| `national` | `output/maps/map_national.png` | Bubble map — all airports, size=strikes, color=damage rate |
| `seasonal` | `output/maps/map_seasonal.png` | 2×2 grid showing strike hotspots per season |
| `flyways` | `output/maps/map_flyways.png` | Strike density overlaid on the 4 major migration flyway corridors |
| `trend` | `output/maps/map_trend.png` | 2-panel: per-airport damage trend slope map + national annual damage rate chart |
| `all` | all four | Default |

### `top`

Prints the top N highest-risk airports and a flyway summary to the terminal.

### `chart`

Generates analytical charts from preprocessed species data.

| Output | File | Description |
|---|---|---|
| `danger-matrix` | `output/charts/chart_danger_matrix.png` | Scatter plot of all wildlife species: X = strike frequency (log scale), Y = damage rate, bubble size = avg repair cost. Four color-coded quadrants classify species by risk profile. |

```bash
python cli.py chart --output danger-matrix
```

The four quadrants:

| Color | Quadrant | Meaning |
|---|---|---|
| Red | Critical | Common strikes AND high damage — highest priority |
| Purple | Dangerous | Rare strikes but high damage rate — monitor closely |
| Blue | Nuisance | Common strikes but rarely damaging — operational annoyance |
| Green | Minor | Rare and rarely damaging — lowest concern |

### `profile <AIRPORT_ID>`

Generates a PDF dossier for a specific airport (use FAA 3-letter code, e.g. `JFK`, `ORD`, `LAX`):

- Strike summary and peer comparison
- Risk score and damage rate
- Seasonal breakdown
- Top struck species
- Flyway assignment

Output: `output/dossiers/dossier_<ID>_<timestamp>.pdf`

## Migration Flyways

US airports are assigned to one of four major North American migration corridors:

| Flyway | Approximate Coverage |
|---|---|
| **Pacific** | West of –114° longitude |
| **Central** | –114° to –100° |
| **Mississippi** | –100° to –83° |
| **Atlantic** | East of –83° |

## Risk Scoring

Each airport's risk score combines:
- **Damage rate** (50%) — fraction of strikes causing aircraft damage
- **Strike volume** (30%) — total strikes normalized to the busiest airport
- **Average repair cost** (20%) — normalized to the most expensive airport

## Tech Stack

- **Polars** — fast data pipeline and aggregation (supports CSV and Excel input via fastexcel)
- **GeoPandas + Matplotlib** — geospatial map rendering
- **adjustText** — automatic label deconfliction on scatter plots
- **NumPy** — linear regression for per-airport damage trend slopes
- **Click** — CLI framework
- **ReportLab** — PDF generation
- **Pytest** — tests covering loaders, analysis, rendering, and PDF output

## Testing

```bash
python -m pytest tests/ -v
```
