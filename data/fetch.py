from pathlib import Path

_SEARCH_DIRS = [
    Path("data/raw"),
    Path("data"),
    Path("."),
]

_STRIKE_KEYWORDS = ["strike", "wildlife", "bird"]
_AIRPORT_KEYWORDS = ["airport", "ourairport"]


def find_strikes_dataset() -> Path:
    """Search common locations for the FAA Wildlife Strike CSV."""
    for directory in _SEARCH_DIRS:
        if not directory.exists():
            continue
        for csv_file in sorted(directory.glob("*.csv")):
            name = csv_file.stem.lower()
            if any(kw in name for kw in _STRIKE_KEYWORDS):
                return csv_file
        # Also accept .xlsx
        for xlsx_file in sorted(directory.glob("*.xlsx")):
            name = xlsx_file.stem.lower()
            if any(kw in name for kw in _STRIKE_KEYWORDS):
                return xlsx_file

    raise FileNotFoundError(
        "FAA Wildlife Strike dataset not found.\n"
        "Download the CSV export from https://wildlife.faa.gov/home (Database -> Download)\n"
        "and place it in data/raw/."
    )


def find_airports_dataset() -> Path | None:
    """Search for an airports CSV (OurAirports format) with lat/lon data."""
    for directory in _SEARCH_DIRS:
        if not directory.exists():
            continue
        for csv_file in sorted(directory.glob("*.csv")):
            name = csv_file.stem.lower()
            if any(kw in name for kw in _AIRPORT_KEYWORDS):
                return csv_file
    return None


def find_preprocessed() -> tuple[Path, Path] | None:
    """Return paths to preprocessed summary parquets if both exist."""
    base = Path("data/preprocessed")
    airport_path = base / "airport_stats.parquet"
    seasonal_path = base / "seasonal_stats.parquet"
    if airport_path.exists() and seasonal_path.exists():
        return airport_path, seasonal_path
    return None
