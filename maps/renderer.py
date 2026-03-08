"""
Static map rendering using GeoPandas + Matplotlib.

Three map types:
  national  — bubble map of all airports colored by damage rate
  seasonal  — 2x2 grid showing strike hotspots per season
  flyways   — national map with migration flyway corridors overlaid
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for file output

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import numpy as np

from data.models import AirportStats
from analysis.seasonal import SEASON_ORDER, FLYWAY_COLORS

# US continental bounding box
US_XLIM = (-127, -65)
US_YLIM = (23, 50)

# Approximate flyway corridor polygons [lon_min, lon_max, lat_min, lat_max]
FLYWAY_BOXES = {
    "Pacific":      (-127.0, -114.0, 23.0, 50.0),
    "Central":      (-114.0, -100.0, 23.0, 50.0),
    "Mississippi":  (-100.0,  -83.0, 23.0, 50.0),
    "Atlantic":     ( -83.0,  -65.0, 23.0, 50.0),
}


def render_national_map(airport_stats: list[AirportStats], output_path: Path) -> Path:
    """
    Bubble map of the US. Bubble size = total strikes, color = damage rate.
    """
    airports = _with_coords(airport_stats)
    if not airports:
        raise ValueError("No airports with coordinates available.")

    fig, ax = plt.subplots(figsize=(16, 9))
    _draw_basemap(ax)

    lons = [a.longitude for a in airports]
    lats = [a.latitude for a in airports]
    sizes = [max(8, a.total_strikes * 0.4) for a in airports]
    colors = [a.damage_rate for a in airports]

    sc = ax.scatter(
        lons, lats,
        s=sizes, c=colors,
        cmap="RdYlGn_r", vmin=0.0, vmax=0.6,
        alpha=0.75, linewidths=0.3, edgecolors="white", zorder=5,
    )
    cbar = plt.colorbar(sc, ax=ax, shrink=0.55, pad=0.02)
    cbar.set_label("Damage Rate", fontsize=10)
    cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))

    # Label top 10 airports by total strikes
    top10 = sorted(airports, key=lambda a: -a.total_strikes)[:10]
    for a in top10:
        ax.annotate(
            a.airport_id,
            (a.longitude, a.latitude),
            fontsize=6.5, ha="center", va="bottom",
            xytext=(0, 5), textcoords="offset points",
            color="#222222",
        )

    # Size legend
    for strikes, label in [(50, "50"), (200, "200"), (500, "500+")]:
        ax.scatter([], [], s=max(8, strikes * 0.4), c="gray", alpha=0.6, label=f"{label} strikes")
    ax.legend(title="Strike Volume", loc="lower left", fontsize=8, title_fontsize=9)

    ax.set_xlim(*US_XLIM)
    ax.set_ylim(*US_YLIM)
    ax.set_title(
        "FAA Wildlife Strikes by Airport\n"
        "Bubble size = total strikes  |  Color = damage rate",
        fontsize=14, fontweight="bold", pad=12,
    )
    ax.set_xlabel("Longitude", fontsize=9)
    ax.set_ylabel("Latitude", fontsize=9)
    ax.tick_params(labelsize=8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def render_seasonal_map(airport_stats: list[AirportStats], output_path: Path) -> Path:
    """
    2x2 grid — one panel per season. Shows how strike hotspots shift with migration.
    """
    airports = _with_coords(airport_stats)
    if not airports:
        raise ValueError("No airports with coordinates available.")

    fig, axes = plt.subplots(2, 2, figsize=(18, 11))
    fig.suptitle(
        "FAA Wildlife Strikes — Seasonal Migration Patterns\n"
        "Bubble size = seasonal strikes  |  Color = damage rate",
        fontsize=14, fontweight="bold", y=1.01,
    )

    cmap = plt.get_cmap("RdYlGn_r")
    norm = mcolors.Normalize(vmin=0.0, vmax=0.6)

    for ax, season in zip(axes.flat, SEASON_ORDER):
        _draw_basemap(ax)

        season_airports = [a for a in airports if a.seasonal_counts.get(season, 0) > 0]
        if season_airports:
            lons = [a.longitude for a in season_airports]
            lats = [a.latitude for a in season_airports]
            sizes = [max(6, a.seasonal_counts[season] * 0.6) for a in season_airports]
            colors = [cmap(norm(a.damage_rate)) for a in season_airports]

            ax.scatter(lons, lats, s=sizes, c=colors, alpha=0.75,
                       linewidths=0.2, edgecolors="white", zorder=5)

        total = sum(a.seasonal_counts.get(season, 0) for a in airports)
        ax.set_xlim(*US_XLIM)
        ax.set_ylim(*US_YLIM)
        ax.set_title(f"{season}  ({total:,} strikes)", fontsize=12, fontweight="bold")
        ax.tick_params(labelsize=7)

    # Shared colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes, shrink=0.4, pad=0.02, location="right")
    cbar.set_label("Damage Rate", fontsize=10)
    cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def render_flyway_map(airport_stats: list[AirportStats], output_path: Path) -> Path:
    """
    National map with the 4 major North American migration flyway corridors shaded,
    strikes overlaid as bubbles colored by flyway.
    """
    airports = _with_coords(airport_stats)
    if not airports:
        raise ValueError("No airports with coordinates available.")

    fig, ax = plt.subplots(figsize=(16, 9))
    _draw_basemap(ax)

    # Draw flyway corridor shading
    for flyway, (x0, x1, y0, y1) in FLYWAY_BOXES.items():
        color = FLYWAY_COLORS.get(flyway, "#9E9E9E")
        rect = mpatches.FancyArrowPatch(
            posA=(x0 + (x1 - x0) / 2, y0),
            posB=(x0 + (x1 - x0) / 2, y1),
            arrowstyle=mpatches.ArrowStyle.Simple(
                head_width=abs(x1 - x0) * 0.5,
                tail_width=abs(x1 - x0) * 0.9,
                head_length=2.0,
            ),
            color=color, alpha=0.12, zorder=2,
        )
        ax.add_patch(rect)

        # Flyway label at top
        ax.text(
            (x0 + x1) / 2, y1 - 0.8,
            f"{flyway}\nFlyway",
            ha="center", va="top", fontsize=8, color=color,
            fontweight="bold", alpha=0.9, zorder=3,
        )

    # Plot strikes colored by flyway
    for flyway, color in FLYWAY_COLORS.items():
        fw_airports = [a for a in airports if a.flyway == flyway]
        if not fw_airports:
            continue
        lons = [a.longitude for a in fw_airports]
        lats = [a.latitude for a in fw_airports]
        sizes = [max(8, a.total_strikes * 0.35) for a in fw_airports]
        ax.scatter(lons, lats, s=sizes, c=color, alpha=0.7,
                   linewidths=0.2, edgecolors="white",
                   label=f"{flyway} ({len(fw_airports):,} airports)", zorder=5)

    ax.legend(title="Flyway", loc="lower left", fontsize=8, title_fontsize=9)
    ax.set_xlim(*US_XLIM)
    ax.set_ylim(*US_YLIM)
    ax.set_title(
        "FAA Wildlife Strikes by Migration Flyway\n"
        "Bubble size = total strikes per airport",
        fontsize=14, fontweight="bold", pad=12,
    )
    ax.set_xlabel("Longitude", fontsize=9)
    ax.set_ylabel("Latitude", fontsize=9)
    ax.tick_params(labelsize=8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def render_trend_map(
    airport_stats: list[AirportStats],
    annual_parquet: "Path | None",
    output_path: Path,
) -> Path:
    """
    Two-panel figure:
      Left  — bubble map colored by damage-rate trend (green=improving, red=worsening)
      Right — national annual damage rate line chart
    """
    airports = _with_coords(airport_stats)
    if not airports:
        raise ValueError("No airports with coordinates available.")

    # Only include airports with enough history to have a meaningful trend
    trend_airports = [a for a in airports if a.damage_trend != 0.0]

    fig = plt.figure(figsize=(20, 9))
    gs = fig.add_gridspec(1, 2, width_ratios=[2.2, 1], wspace=0.08)
    ax_map = fig.add_subplot(gs[0])
    ax_line = fig.add_subplot(gs[1])

    # --- Left panel: trend bubble map ---
    _draw_basemap(ax_map)

    # Airports with no trend data — plot in gray first
    no_trend = [a for a in airports if a.damage_trend == 0.0]
    if no_trend:
        ax_map.scatter(
            [a.longitude for a in no_trend],
            [a.latitude for a in no_trend],
            s=[max(5, a.total_strikes * 0.25) for a in no_trend],
            c="#cccccc", alpha=0.4, linewidths=0, zorder=4,
        )

    if trend_airports:
        lons   = [a.longitude for a in trend_airports]
        lats   = [a.latitude  for a in trend_airports]
        sizes  = [max(8, a.total_strikes * 0.35) for a in trend_airports]
        trends = [a.damage_trend for a in trend_airports]

        clamp = 0.015  # ±1.5 pp/year
        sc = ax_map.scatter(
            lons, lats, s=sizes, c=trends,
            cmap="RdYlGn_r", vmin=-clamp, vmax=clamp,
            alpha=0.8, linewidths=0.3, edgecolors="white", zorder=5,
        )
        cbar = plt.colorbar(sc, ax=ax_map, shrink=0.55, pad=0.02)
        cbar.set_label("Damage Rate Trend (pp/year)", fontsize=9)
        cbar.ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{v*100:+.1f}%")
        )

        # Label top 4 worsening and top 4 improving (min 50 total strikes)
        notable = [a for a in trend_airports if a.total_strikes >= 50]
        worst   = sorted(notable, key=lambda a: -a.damage_trend)[:4]
        best    = sorted(notable, key=lambda a:  a.damage_trend)[:4]
        for a in worst + best:
            ax_map.annotate(
                a.airport_id,
                (a.longitude, a.latitude),
                fontsize=6.5, ha="center", va="bottom",
                xytext=(0, 5), textcoords="offset points",
                color="#333333",
            )

    # Size legend
    for strikes, label in [(100, "100"), (500, "500"), (2000, "2000+")]:
        ax_map.scatter([], [], s=max(8, strikes * 0.35), c="gray", alpha=0.6,
                       label=f"{label} strikes")
    ax_map.legend(title="Strike Volume", loc="lower left", fontsize=8, title_fontsize=9)

    ax_map.set_xlim(*US_XLIM)
    ax_map.set_ylim(*US_YLIM)
    ax_map.set_title(
        "FAA Wildlife Strike Trend — Is It Getting Better or Worse?\n"
        "Color = annual change in damage rate  |  Bubble size = total strikes",
        fontsize=13, fontweight="bold", pad=10,
    )
    ax_map.tick_params(labelsize=8)

    # --- Right panel: national annual damage rate ---
    _draw_national_trend(ax_line, annual_parquet)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def render_species_danger_matrix(species_parquet: Path, output_path: Path) -> Path:
    """
    Scatter plot: X = total strikes (log scale), Y = damage rate.
    Bubble size = avg repair cost. Four quadrants colour-coded by risk profile.
    """
    import polars as pl
    import numpy as np
    from matplotlib.patches import Patch

    df = pl.read_parquet(species_parquet).filter(pl.col("total_strikes") >= 20)
    if df.height < 5:
        raise ValueError("Insufficient species data — re-run preprocess.")

    strikes = df["total_strikes"].to_numpy().astype(float)
    damage  = df["damage_rate"].to_numpy().astype(float)
    costs   = df["avg_cost"].to_numpy().astype(float)
    names   = df["species"].to_list()

    # Quadrant thresholds
    med_strikes = float(np.median(strikes))
    med_damage  = float(np.median(damage))

    COLORS = {
        "critical":   "#e74c3c",   # high volume, high damage  — red
        "dangerous":  "#8e44ad",   # low volume,  high damage  — purple
        "nuisance":   "#2980b9",   # high volume, low damage   — blue
        "minor":      "#27ae60",   # low volume,  low damage   — green
    }

    point_colors = []
    for s, d in zip(strikes, damage):
        if s >= med_strikes and d >= med_damage:
            point_colors.append(COLORS["critical"])
        elif s < med_strikes and d >= med_damage:
            point_colors.append(COLORS["dangerous"])
        elif s >= med_strikes and d < med_damage:
            point_colors.append(COLORS["nuisance"])
        else:
            point_colors.append(COLORS["minor"])

    max_cost = max(costs.max(), 1.0)
    sizes = np.clip(costs / max_cost * 600 + 40, 40, 650)

    fig, ax = plt.subplots(figsize=(15, 9))

    ax.scatter(strikes, damage, s=sizes, c=point_colors,
               alpha=0.75, linewidths=0.5, edgecolors="white", zorder=5)

    ax.set_xscale("log")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))

    # Quadrant dividers
    ax.axvline(x=med_strikes, color="#888", linewidth=1.0, linestyle="--", alpha=0.6, zorder=3)
    ax.axhline(y=med_damage,  color="#888", linewidth=1.0, linestyle="--", alpha=0.6, zorder=3)

    # Annotate divider lines with their actual threshold values
    # get_xaxis_transform: x=data, y=axes fraction (0-1)
    ax.text(med_strikes, 0.99, f" median: {int(med_strikes):,} strikes",
            fontsize=7, color="#555", va="top", ha="left",
            transform=ax.get_xaxis_transform(),
            bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=1))
    # get_yaxis_transform: x=axes fraction (0-1), y=data
    ax.text(0.99, med_damage, f"median: {med_damage:.1%} ",
            fontsize=7, color="#555", va="bottom", ha="right",
            transform=ax.get_yaxis_transform(),
            bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=1))


    # Label notable species: top by volume + top by damage rate + top by cost
    notable = set(np.argsort(strikes)[-18:].tolist())
    notable |= set(np.argsort(damage)[-12:].tolist())
    notable |= set(np.argsort(costs)[-8:].tolist())

    texts = []
    for i in notable:
        texts.append(ax.text(
            strikes[i], damage[i], names[i],
            fontsize=6.2, color="#222222",
        ))

    try:
        from adjustText import adjust_text
        adjust_text(
            texts,
            x=strikes, y=damage,
            ax=ax,
            arrowprops=dict(arrowstyle="-", color="#aaaaaa", lw=0.6),
            expand=(1.3, 1.5),
            force_text=(0.4, 0.6),
        )
    except ImportError:
        pass  # fall back to overlapping labels if library not installed

    # Quadrant colour legend — placed below the axes to stay out of the data area
    legend_elements = [
        Patch(facecolor=COLORS["critical"],  alpha=0.75, label="Critical  — high volume + high damage"),
        Patch(facecolor=COLORS["dangerous"], alpha=0.75, label="Dangerous — low volume + high damage"),
        Patch(facecolor=COLORS["nuisance"],  alpha=0.75, label="Nuisance  — high volume + low damage"),
        Patch(facecolor=COLORS["minor"],     alpha=0.75, label="Minor     — low volume + low damage"),
    ]
    fig.legend(handles=legend_elements, fontsize=8, loc="lower center",
               bbox_to_anchor=(0.5, -0.04), ncol=2,
               title="Risk Profile", title_fontsize=9, framealpha=0.9)

    ax.set_xlabel("Total Strikes  (log scale)", fontsize=11)
    ax.set_ylabel("Damage Rate", fontsize=11)
    ax.set_title(
        "Wildlife Species Danger Matrix\n"
        "X = strike frequency  |  Y = damage rate  |  Bubble size = avg repair cost",
        fontsize=13, fontweight="bold", pad=12,
    )
    ax.grid(True, which="major", alpha=0.15)
    ax.grid(True, which="minor", alpha=0.07)
    ax.tick_params(labelsize=9)
    # Reduce x-axis tick density on log scale to avoid label crowding
    from matplotlib.ticker import LogLocator, LogFormatterSciNotation
    ax.xaxis.set_major_locator(LogLocator(base=10, numticks=7))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.tick_params(axis="x", labelrotation=30)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def _draw_national_trend(ax: plt.Axes, annual_parquet: "Path | None") -> None:
    """Line chart of national annual damage rate with a trend line."""
    import numpy as np

    ax.set_title("National Damage Rate Over Time", fontsize=11, fontweight="bold")
    ax.set_xlabel("Year", fontsize=9)
    ax.set_ylabel("Damage Rate", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))

    if annual_parquet is None or not Path(annual_parquet).exists():
        ax.text(0.5, 0.5, "No annual data\n(re-run preprocess)",
                ha="center", va="center", transform=ax.transAxes, color="gray")
        return

    import polars as pl
    from datetime import date
    current_year = date.today().year
    df = pl.read_parquet(annual_parquet).filter(
        pl.col("year").is_not_null()
        & (pl.col("year") >= 1990)
        & (pl.col("year") < current_year)  # exclude incomplete current year
    ).sort("year")

    if df.height < 3:
        ax.text(0.5, 0.5, "Insufficient data", ha="center", va="center",
                transform=ax.transAxes, color="gray")
        return

    years  = df["year"].to_numpy()
    rates  = df["damage_rate"].to_numpy()
    counts = df["total_strikes"].to_numpy()

    # Bar chart of strike volume in the background (secondary feel)
    ax2 = ax.twinx()
    ax2.bar(years, counts, color="#b0c4de", alpha=0.35, zorder=1, label="Strike count")
    ax2.set_ylabel("Annual Strikes", fontsize=8, color="#7a9abf")
    ax2.tick_params(labelsize=7, colors="#7a9abf")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))

    # Damage rate line
    ax.plot(years, rates, color="#c0392b", linewidth=2, zorder=3, label="Damage rate")
    ax.scatter(years, rates, color="#c0392b", s=18, zorder=4)

    # Linear trend overlay
    slope, intercept = np.polyfit(years, rates, 1)
    trend_line = slope * years + intercept
    ax.plot(years, trend_line, "--", color="#333333", linewidth=1.2, alpha=0.7,
            label=f"Trend ({slope*100:+.2f}%/yr)")

    ax.set_xlim(years[0] - 0.5, years[-1] + 0.5)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    ax.legend(fontsize=7, loc="upper left")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _draw_basemap(ax: plt.Axes) -> None:
    """Draw a minimal US basemap using GeoPandas naturalearth data."""
    try:
        import geopandas as gpd
        world = _load_world()
        if world is not None and not world.empty:
            world.plot(ax=ax, color="#e8e8e8", edgecolor="#aaaaaa", linewidth=0.4, zorder=1)
            return
    except Exception:
        pass
    # Fallback: plain light background
    ax.set_facecolor("#dce9f5")
    ax.axhline(y=0, color="#aaaaaa", linewidth=0.3)


def _load_world():
    """Load world/land polygons, trying multiple GeoPandas API versions."""
    import geopandas as gpd

    # Modern GeoPandas (>=0.14) with geodatasets
    try:
        import geodatasets
        return gpd.read_file(geodatasets.get_path("naturalearth.land"))
    except Exception:
        pass

    # Older GeoPandas bundled datasets
    try:
        return gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
    except Exception:
        pass

    return None


def _with_coords(airport_stats: list[AirportStats]) -> list[AirportStats]:
    """Filter to airports that have non-zero lat/lon."""
    return [a for a in airport_stats if a.latitude != 0.0 and a.longitude != 0.0]
