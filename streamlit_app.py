"""
FAA Bird Strike Analyzer — Streamlit showcase app.

Reads from preprocessed Parquet files in data/preprocessed/.
Run with:  streamlit run streamlit_app.py
"""

from pathlib import Path

import polars as pl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import streamlit as st

# ── Paths ──────────────────────────────────────────────────────────────────────
AIRPORT_PARQUET  = Path("data/preprocessed/airport_stats.parquet")
SEASONAL_PARQUET = Path("data/preprocessed/seasonal_stats.parquet")
ANNUAL_PARQUET   = Path("data/preprocessed/annual_stats.parquet")
SPECIES_PARQUET  = Path("data/preprocessed/species_stats.parquet")

FLYWAY_COLORS = {
    "Pacific":     "#2196F3",
    "Central":     "#4CAF50",
    "Mississippi": "#FF9800",
    "Atlantic":    "#9C27B0",
    "Unknown":     "#9E9E9E",
}

SEASON_ORDER = ["Spring", "Summer", "Fall", "Winter"]
SEASON_COLORS = {"Spring": "#66BB6A", "Summer": "#FFA726", "Fall": "#EF5350", "Winter": "#42A5F5"}


# ── Data loading ───────────────────────────────────────────────────────────────
@st.cache_data
def load_airports() -> pl.DataFrame:
    return pl.read_parquet(AIRPORT_PARQUET)


@st.cache_data
def load_annual() -> pl.DataFrame:
    return pl.read_parquet(ANNUAL_PARQUET)


@st.cache_data
def load_species() -> pl.DataFrame:
    return pl.read_parquet(SPECIES_PARQUET)


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FAA Bird Strike Analyzer",
    page_icon="✈️",
    layout="wide",
)

st.title("FAA Wildlife Strike Analyzer")
st.caption(
    "Explore 30+ years of FAA wildlife strike data across US airports. "
    "Data: [FAA Wildlife Strike Database](https://wildlife.faa.gov) · "
    "[OurAirports](https://ourairports.com/data/)"
)

# ── Load data ──────────────────────────────────────────────────────────────────
if not AIRPORT_PARQUET.exists():
    st.error("Preprocessed data not found. Run `python cli.py preprocess` first.")
    st.stop()

airports = load_airports()
annual   = load_annual()   if ANNUAL_PARQUET.exists()  else None
species  = load_species()  if SPECIES_PARQUET.exists() else None

total_strikes = int(airports["total_strikes"].sum())
total_airports = len(airports)
avg_damage = float(
    (airports["damage_rate"] * airports["total_strikes"]).sum() / total_strikes
) if total_strikes > 0 else 0.0

# ── Top KPI strip ──────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Strikes (all time)", f"{total_strikes:,}")
k2.metric("Airports in database", f"{total_airports:,}")
k3.metric("Overall damage rate", f"{avg_damage:.1%}")
if annual is not None and "year" in annual.columns:
    latest_year = int(annual["year"].max())
    k4.metric("Data through", str(latest_year))

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_map, tab_trend, tab_airport, tab_species = st.tabs(
    ["🗺️ Airport Map", "📈 Annual Trend", "🔍 Airport Profile", "🦅 Species Risk"]
)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — National bubble map
# ══════════════════════════════════════════════════════════════════════════════
with tab_map:
    st.subheader("Wildlife Strikes by Airport")
    st.caption("Bubble size = total strikes · Color = flyway · Opacity = damage rate")

    mapped = airports.filter(
        (pl.col("latitude") != 0.0) & (pl.col("longitude") != 0.0)
    )

    col_ctrl, col_map = st.columns([1, 3])
    with col_ctrl:
        flyway_opts = ["All"] + sorted(mapped["flyway"].unique().to_list())
        selected_flyway = st.selectbox("Filter by flyway", flyway_opts)
        min_strikes = st.slider("Minimum strikes", 0, 500, 50, step=10)

    subset = mapped.filter(pl.col("total_strikes") >= min_strikes)
    if selected_flyway != "All":
        subset = subset.filter(pl.col("flyway") == selected_flyway)

    with col_map:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.set_facecolor("#f5f5f5")
        fig.patch.set_facecolor("#f5f5f5")

        # Contiguous US bounds
        ax.set_xlim(-125, -65)
        ax.set_ylim(24, 50)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(True, alpha=0.3, linewidth=0.5)

        max_strikes = float(subset["total_strikes"].max() or 1)
        for row in subset.iter_rows(named=True):
            color = FLYWAY_COLORS.get(row["flyway"], "#9E9E9E")
            size  = (row["total_strikes"] / max_strikes) * 800 + 5
            alpha = 0.3 + 0.6 * float(row.get("damage_rate") or 0.0)
            ax.scatter(row["longitude"], row["latitude"],
                       s=size, color=color, alpha=min(alpha, 0.95),
                       linewidths=0.3, edgecolors="white")

        patches = [
            mpatches.Patch(color=c, label=fw)
            for fw, c in FLYWAY_COLORS.items() if fw != "Unknown"
        ]
        ax.legend(handles=patches, loc="lower left", fontsize=8, title="Flyway")
        ax.set_title(
            f"FAA Wildlife Strikes — {len(subset):,} airports shown",
            fontsize=12, pad=10,
        )
        st.pyplot(fig)
        plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Annual trend
# ══════════════════════════════════════════════════════════════════════════════
with tab_trend:
    st.subheader("National Strike Volume Over Time")

    if annual is None or "year" not in annual.columns:
        st.info("Annual trend data not available.")
    else:
        fig, ax1 = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor("#f5f5f5")
        ax1.set_facecolor("#f5f5f5")

        years  = annual["year"].to_list()
        counts = annual["total_strikes"].to_list()
        damages = annual["damage_rate"].to_list() if "damage_rate" in annual.columns else None

        ax1.bar(years, counts, color="#2196F3", alpha=0.7, label="Total strikes")
        ax1.set_xlabel("Year")
        ax1.set_ylabel("Total Strikes", color="#2196F3")
        ax1.tick_params(axis="y", labelcolor="#2196F3")

        if damages:
            ax2 = ax1.twinx()
            ax2.plot(years, [d * 100 for d in damages], color="#EF5350",
                     linewidth=2, marker="o", markersize=3, label="Damage rate %")
            ax2.set_ylabel("Damage Rate (%)", color="#EF5350")
            ax2.tick_params(axis="y", labelcolor="#EF5350")

        ax1.set_title("US Wildlife Strikes per Year", fontsize=12, pad=10)
        st.pyplot(fig)
        plt.close(fig)

        st.caption(
            "Strike volume has grown significantly since the 1990s, "
            "partly reflecting improved reporting rather than purely increased incidents."
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Airport profile
# ══════════════════════════════════════════════════════════════════════════════
with tab_airport:
    st.subheader("Airport Profile")

    # Build display label: "JFK — John F Kennedy Intl (NY)"
    def label(row) -> str:
        name = row["airport_name"] or row["airport_id"]
        state = f" ({row['state']})" if row.get("state") else ""
        return f"{row['airport_id']} — {name}{state}"

    top_airports_df = (
        airports
        .filter(pl.col("total_strikes") >= 50)
        .filter(pl.col("airport_id") != "ZZZZ")
        .sort("risk_score", descending=True)
    )

    airport_labels = [label(r) for r in top_airports_df.iter_rows(named=True)]

    if not airport_labels:
        st.info("No airports with 50+ strikes found in the data.")
        st.stop()

    selected_label = st.selectbox("Select airport", airport_labels)
    selected_id = selected_label.split(" — ")[0]

    row = top_airports_df.filter(pl.col("airport_id") == selected_id).row(0, named=True)

    # Stats row
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Strikes", f"{row['total_strikes']:,}")
    c2.metric("Damage Rate", f"{float(row['damage_rate']):.1%}")
    c3.metric("Risk Score", f"{float(row['risk_score']):.0%}")
    c4.metric("Flyway", row["flyway"])
    c5.metric("Avg Repair Cost", f"${float(row.get('avg_cost') or 0):,.0f}")

    # Seasonal bar + species list side by side
    left, right = st.columns(2)

    with left:
        st.markdown("**Strikes by Season**")
        season_counts = {
            s: int(row.get(f"strikes_{s.lower()}") or 0) for s in SEASON_ORDER
        }
        if any(season_counts.values()):
            fig, ax = plt.subplots(figsize=(4, 3))
            fig.patch.set_facecolor("#f5f5f5")
            ax.set_facecolor("#f5f5f5")
            colors = [SEASON_COLORS[s] for s in SEASON_ORDER]
            ax.bar(SEASON_ORDER, [season_counts[s] for s in SEASON_ORDER],
                   color=colors, edgecolor="white")
            ax.set_ylabel("Strikes")
            ax.set_title(f"{selected_id} — Seasonal Breakdown", fontsize=10)
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.info("No seasonal breakdown available.")

    with right:
        st.markdown("**Top Species Struck**")
        species_str = str(row.get("top_species") or "")
        top_sp = [s.strip() for s in species_str.split(",") if s.strip()]
        if top_sp:
            for i, sp in enumerate(top_sp[:5], 1):
                st.write(f"{i}. {sp}")
        else:
            st.info("No species data available.")

    # Peer comparison
    st.markdown("**Peer Comparison** — where this airport ranks nationally")
    rank_risk = int(
        (top_airports_df["risk_score"] > float(row["risk_score"])).sum()
    ) + 1
    rank_strikes = int(
        (top_airports_df["total_strikes"] > int(row["total_strikes"])).sum()
    ) + 1
    n_total = len(top_airports_df)
    st.write(
        f"Risk score rank: **#{rank_risk}** of {n_total} airports  ·  "
        f"Strike volume rank: **#{rank_strikes}** of {n_total} airports"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Species risk matrix
# ══════════════════════════════════════════════════════════════════════════════
with tab_species:
    st.subheader("Wildlife Species Danger Matrix")
    st.caption(
        "X = strike frequency (log scale) · Y = damage rate · "
        "Bubble size = avg repair cost"
    )

    if species is None:
        st.info("Species data not available.")
    else:
        min_strikes_sp = st.slider("Min strikes to include species", 5, 200, 20, key="sp_slider")
        sp = species.filter(pl.col("total_strikes") >= min_strikes_sp)

        if len(sp) == 0:
            st.warning("No species meet the minimum strike threshold.")
        else:
            import plotly.graph_objects as go

            med_strikes = float(sp["total_strikes"].median() or 1)
            med_damage  = float(sp["damage_rate"].median() or 0.1)

            QUADRANT_COLORS = {
                "Critical":  "#EF5350",
                "Dangerous": "#9C27B0",
                "Nuisance":  "#2196F3",
                "Minor":     "#4CAF50",
            }

            def quadrant_label(strikes, damage):
                high_s = strikes >= med_strikes
                high_d = damage  >= med_damage
                if high_s and high_d: return "Critical"
                if high_d:            return "Dangerous"
                if high_s:            return "Nuisance"
                return "Minor"

            max_cost = float(sp["avg_cost"].max() or 1) if "avg_cost" in sp.columns else 1

            # Build one trace per quadrant so the legend is clean
            traces = {q: {"x": [], "y": [], "size": [], "text": []} for q in QUADRANT_COLORS}
            for row in sp.iter_rows(named=True):
                s    = row["total_strikes"]
                d    = row["damage_rate"]
                cost = float(row.get("avg_cost") or 0)
                q    = quadrant_label(s, d)
                bubble = 8 + (cost / max_cost) * 40
                hover = (
                    f"<b>{row['species']}</b><br>"
                    f"Strikes: {s:,}<br>"
                    f"Damage rate: {d:.1%}<br>"
                    f"Avg repair cost: ${cost:,.0f}"
                )
                traces[q]["x"].append(s)
                traces[q]["y"].append(d * 100)
                traces[q]["size"].append(bubble)
                traces[q]["text"].append(hover)

            fig = go.Figure()
            for q, color in QUADRANT_COLORS.items():
                t = traces[q]
                fig.add_trace(go.Scatter(
                    x=t["x"], y=t["y"],
                    mode="markers",
                    name=q,
                    marker=dict(
                        size=t["size"],
                        color=color,
                        opacity=0.7,
                        line=dict(color="white", width=0.5),
                        sizemode="area",
                    ),
                    hovertemplate="%{text}<extra></extra>",
                    text=t["text"],
                ))

            fig.add_vline(x=med_strikes, line_dash="dash", line_color="gray", opacity=0.6)
            fig.add_hline(y=med_damage * 100, line_dash="dash", line_color="gray", opacity=0.6)

            max_y = float(sp["damage_rate"].max() or 1) * 100 * 1.1

            # Quadrant corner labels in paper coords (0=left/bottom, 1=right/top)
            quadrant_annotations = [
                dict(text="Critical", x=0.98, y=0.98, xref="paper", yref="paper",
                     showarrow=False, font=dict(color="#EF5350", size=11), xanchor="right", yanchor="top"),
                dict(text="Dangerous", x=0.02, y=0.98, xref="paper", yref="paper",
                     showarrow=False, font=dict(color="#9C27B0", size=11), xanchor="left", yanchor="top"),
                dict(text="Nuisance", x=0.98, y=0.02, xref="paper", yref="paper",
                     showarrow=False, font=dict(color="#2196F3", size=11), xanchor="right", yanchor="bottom"),
                dict(text="Minor", x=0.02, y=0.02, xref="paper", yref="paper",
                     showarrow=False, font=dict(color="#4CAF50", size=11), xanchor="left", yanchor="bottom"),
            ]

            fig.update_layout(
                title="Species Risk Profile",
                xaxis=dict(title="Total Strikes (log scale)", type="log"),
                yaxis=dict(title="Damage Rate (%)", range=[0, max_y]),
                legend=dict(title="Quadrant", orientation="v"),
                annotations=quadrant_annotations,
                plot_bgcolor="#f5f5f5",
                paper_bgcolor="#f5f5f5",
                height=600,
                hovermode="closest",
            )
            st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption("Built with Polars · Matplotlib · Plotly · Streamlit · FAA public data")
