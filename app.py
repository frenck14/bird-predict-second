"""Streamlit dashboard for the Eastern and Atlantic Vagrancy Indices."""

from __future__ import annotations

import json
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.atmospheric_indices import (
    ComponentScore,
    SignalScore,
    calculate_atmospheric_indices,
)
from src.forecast_atlantic_locations import (
    ATLANTIC_LOCATION_FORECAST_FILE,
    LOCATION_MAP_FILE as ATLANTIC_LOCATION_MAP_FILE,
    cell_polygon as atlantic_cell_polygon,
)
from src.forecast_atlantic_species_locations import (
    SPECIES_LAYERS,
    species_output_paths,
)
from src.forecast_eastern_species_locations import (
    EASTERN_GUILD_LAYER,
    EASTERN_SPECIES_LAYERS,
    combine_species_forecasts,
    eastern_species_output_paths,
)
from src.birding_opportunity_index import BOI_JSON
from src.eastern_target_species import (
    EASTERN_TARGET_SPECIES_CSV,
    HORIZON_LABELS as TARGET_HORIZON_LABELS,
    stars_text,
)
from src.forecast_location import cell_polygon
from src.next_dutch_firsts import (
    COUNTRIES,
    COUNTRY_LABELS,
    FILTERS,
    Candidate,
    apply_filter,
    top_rising,
    rising_species,
    summary_counts,
    timeline_label,
    BREAKDOWN_LABELS,
    RARITY_COLORS,
    RARITY_LABELS,
    DATA_PROVENANCE,
    PLANNED_SOURCES,
    load_ranked,
    timeline,
)
from src.predict_yellow_browed import load_weather_forecast, risk_category
from src.run_daily_forecast import RUN_METADATA, run_daily_forecast
from src.seabird_decision_support import (
    DECISION_SUPPORT_FILE,
    confidence_label,
    event_status,
    index_score,
    recommended_coast,
)
from src.seawatch_day_rating import RATING_JSON_OUTPUT, RATING_OUTPUT
from src.seabird_guidance import DUTCH_COAST_REGIONS, build_recommendations
from src.predict_atlantic_vagrancy import risk_level as atlantic_risk_level
from src.predict_eastern_vagrancy import risk_level as eastern_risk_level
from src.predict_seabird import risk_level as seabird_risk_level
from src.rarity_index import RARITY_INDEX_JSON_OUTPUT
from src.goose_module import MODULE_JSON_OUTPUT as GOOSE_JSON_OUTPUT
from src.download_open_meteo_forecast import (
    DEFAULT_FORECAST_FILE as WEATHER_FORECAST_FILE,
)
from src.forecast_seabird_species import (
    species_output_paths as seabird_species_output_paths,
)
from src.train_seabird_species_models import SPECIES_NAMES as SEABIRD_SPECIES_NAMES
from src.build_seabird_dataset import SEABIRD_SPECIES


ROOT = Path(__file__).resolve().parent
FORECAST_FILE = ROOT / "outputs/yellow_browed_forecast.csv"
LOCATION_FORECAST_FILE = ROOT / "outputs/yellow_browed_location_forecast.csv"
PLOT_FILE = ROOT / "outputs/yellow_browed_forecast.png"
REPORT_FILE = ROOT / "outputs/yellow_browed_report.md"
EASTERN_FORECAST_FILE = ROOT / "outputs/eastern_vagrancy_forecast.csv"
EASTERN_PLOT_FILE = ROOT / "outputs/eastern_vagrancy_forecast.png"
EASTERN_LOCATION_FORECAST_FILE = ROOT / "outputs/eastern_vagrancy_location_forecast.csv"
EASTERN_LOCATION_MAP_FILE = ROOT / "outputs/eastern_location_forecast.png"
ATLANTIC_FORECAST_FILE = ROOT / "outputs/atlantic_vagrancy_forecast.csv"
ATLANTIC_PLOT_FILE = ROOT / "outputs/atlantic_vagrancy_forecast.png"
ATLANTIC_EVENTS_FILE = ROOT / "outputs/atlantic_vagrancy_events.csv"
EASTERN_EVENTS_FILE = ROOT / "outputs/eastern_vagrancy_events.csv"
SEABIRD_FORECAST_FILE = ROOT / "outputs/seabird_forecast.csv"
SEABIRD_PLOT_FILE = ROOT / "outputs/seabird_forecast.png"
SEABIRD_LOCATION_FORECAST_FILE = ROOT / "outputs/seabird_location_forecast_detail.csv"
SEABIRD_LOCATION_MAP_FILE = ROOT / "outputs/seabird_location_forecast.png"
EASTERN_VAGRANCY_SPECIES = (
    "Yellow-browed Warbler",
    "Red-flanked Bluetail",
    "Olive-backed Pipit",
    "Pallas's Warbler",
    "Dusky Warbler",
    "Siberian Chiffchaff",
)
ATLANTIC_VAGRANCY_DESCRIPTION = (
    "Nearctic trans-Atlantic passerines recorded in the United Kingdom, "
    "Ireland, Netherlands, Belgium, and Denmark."
)
MODEL_STATUS = {
    "Forecast Model": (
        "✅",
        "Driven by weather forecasts and predictive modelling.",
    ),
    "Statistical Risk Model": (
        "📊",
        "Generated from historical records, trends and environmental predictors.",
    ),
    "Hotspot Prediction Model": (
        "📍",
        "Forecasts where rarity arrivals are most likely.",
    ),
    "Descriptive Analytics": (
        "📚",
        "Historical patterns and observations. No forecast component.",
    ),
}
MODEL_CONFIDENCE = ("High", "Medium", "Low", "Experimental")
FORECAST_HORIZONS = {
    1: "Tomorrow",
    3: "+3 days",
    7: "+7 days",
    14: "+14 days",
}
REFERENCE_TOWNS = (
    ("Alkmaar", 52.6324, 4.7534),
    ("Almere", 52.3508, 5.2647),
    ("Amersfoort", 52.1561, 5.3878),
    ("Amsterdam", 52.3676, 4.9041),
    ("Apeldoorn", 52.2112, 5.9699),
    ("Arnhem", 51.9851, 5.8987),
    ("Assen", 52.9928, 6.5642),
    ("Breda", 51.5719, 4.7683),
    ("Dordrecht", 51.8133, 4.6901),
    ("Eindhoven", 51.4416, 5.4697),
    ("Enschede", 52.2215, 6.8937),
    ("Goes", 51.5042, 3.8883),
    ("Groningen", 53.2194, 6.5665),
    ("Haarlem", 52.3874, 4.6462),
    ("The Hague", 52.0705, 4.3007),
    ("Harlingen", 53.1746, 5.4222),
    ("Heerenveen", 52.9593, 5.9185),
    ("Leeuwarden", 53.2012, 5.7999),
    ("Leiden", 52.1601, 4.4970),
    ("Lelystad", 52.5185, 5.4714),
    ("Maastricht", 50.8514, 5.6910),
    ("Middelburg", 51.4988, 3.6109),
    ("Nijmegen", 51.8126, 5.8372),
    ("Rotterdam", 51.9244, 4.4777),
    ("Roosendaal", 51.5308, 4.4653),
    ("'s-Hertogenbosch", 51.6978, 5.3037),
    ("Sneek", 53.0320, 5.6580),
    ("Terneuzen", 51.3358, 3.8276),
    ("Tilburg", 51.5555, 5.0913),
    ("Utrecht", 52.0907, 5.1214),
    ("Venlo", 51.3704, 6.1724),
    ("Vlissingen", 51.4427, 3.5736),
    ("Zwolle", 52.5168, 6.0830),
)


def nearest_location_name(latitude: float, longitude: float) -> str:
    nearest_town = ""
    nearest_distance = float("inf")
    latitude_radians = radians(latitude)
    for town, town_latitude, town_longitude in REFERENCE_TOWNS:
        latitude_delta = radians(town_latitude - latitude)
        longitude_delta = radians(town_longitude - longitude)
        haversine = (
            sin(latitude_delta / 2) ** 2
            + cos(latitude_radians)
            * cos(radians(town_latitude))
            * sin(longitude_delta / 2) ** 2
        )
        distance = 6371 * 2 * asin(sqrt(haversine))
        if distance < nearest_distance:
            nearest_town = town
            nearest_distance = distance
    return f"Near {nearest_town} ({nearest_distance:.0f} km)"


def read_last_run() -> dict[str, object] | None:
    if not RUN_METADATA.is_file():
        return None
    return json.loads(RUN_METADATA.read_text(encoding="utf-8"))


def build_location_map_data(
    frame: pd.DataFrame, value_column: str
) -> pd.DataFrame:
    map_data = frame.copy()
    map_data["location_name"] = [
        nearest_location_name(float(latitude), float(longitude))
        for latitude, longitude in zip(
            map_data["center_latitude"], map_data["center_longitude"]
        )
    ]
    if value_column == "forecast_probability":
        values = map_data[value_column].clip(0, 1)
        map_data["fill_color"] = [
            [
                int(30 + 225 * value),
                int(220 * (1 - value)),
                int(245 * (1 - value)),
                170,
            ]
            for value in values
        ]
    else:
        values = map_data[value_column]
        scale = max(float(values.abs().max()), 1e-12)
        map_data["fill_color"] = [
            (
                [
                    220,
                    int(220 * (1 - abs(value) / scale)),
                    int(220 * (1 - abs(value) / scale)),
                    175,
                ]
                if value >= 0
                else [
                    int(220 * (1 - abs(value) / scale)),
                    int(220 * (1 - abs(value) / scale)),
                    220,
                    175,
                ]
            )
            for value in values
        ]
    map_data["polygon"] = [
        cell_polygon(int(easting), int(northing))
        for easting, northing in zip(
            map_data["grid_easting"], map_data["grid_northing"]
        )
    ]
    map_data["forecast_percent"] = (
        map_data["forecast_probability"].map(lambda value: f"{value:.1%}")
    )
    map_data["expected_percent"] = (
        map_data["expected_probability"].map(lambda value: f"{value:.1%}")
    )
    map_data["anomaly_percentage_points"] = (
        map_data["anomaly_score"].map(lambda value: f"{value * 100:+.2f} pp")
    )
    return map_data


def render_location_map(
    frame: pd.DataFrame,
    title: str,
    value_column: str,
) -> None:
    map_data = build_location_map_data(frame, value_column)
    layer = pdk.Layer(
        "PolygonLayer",
        data=map_data,
        get_polygon="polygon",
        get_fill_color="fill_color",
        get_line_color=[70, 70, 70, 90],
        line_width_min_pixels=0.4,
        filled=True,
        stroked=True,
        pickable=True,
        auto_highlight=True,
    )
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(
            latitude=52.2,
            longitude=5.3,
            zoom=6,
            pitch=0,
        ),
        tooltip={
            "html": (
                "<b>{location_name}</b><br/>"
                "Forecast probability: {forecast_percent}<br/>"
                "Baseline probability: {expected_percent}<br/>"
                "Anomaly score: {anomaly_percentage_points}"
            )
        },
    )
    st.pydeck_chart(deck, width="stretch", height=480)
    st.caption(title)


def show_location_forecasts() -> None:
    st.subheader("10 km location outlook")
    st.caption(
        "Cell scores are a transparent downscaling of the nationwide model: "
        "each cell's historical GBIF reporting rate for this time of year is "
        "adjusted by the national forecast's seasonal log-odds shift. This is "
        "not an independently trained local-weather forecast or a "
        "detection-corrected occupancy estimate. Maps and rankings include "
        "only 10 km cells with historical, dated GBIF coordinates; blank "
        "cells are unknown, not confirmed absences."
    )
    if not LOCATION_FORECAST_FILE.is_file():
        st.info(
            "No location forecast is available yet. Run the forecast to "
            "retrieve GBIF coordinates and generate the grid-cell outlook."
        )
        return

    location_forecast = pd.read_csv(
        LOCATION_FORECAST_FILE, parse_dates=["date"]
    )
    required = {
        "date",
        "cell_id",
        "grid_easting",
        "grid_northing",
        "center_latitude",
        "center_longitude",
        "expected_probability",
        "forecast_probability",
        "anomaly_score",
        "national_forecast_probability",
    }
    missing = required.difference(location_forecast.columns)
    if missing:
        raise ValueError(
            "Location forecast file is missing columns: "
            f"{sorted(missing)}. Run the forecast again."
        )
    dates = sorted(location_forecast["date"].dropna().dt.date.unique())
    if not dates:
        raise ValueError("Location forecast contains no valid forecast dates.")
    horizon_dates = {
        horizon: dates[0] + timedelta(days=horizon - 1)
        for horizon in FORECAST_HORIZONS
    }
    available_dates = set(dates)
    missing_horizons = {
        horizon: forecast_date
        for horizon, forecast_date in horizon_dates.items()
        if forecast_date not in available_dates
    }
    if missing_horizons:
        raise ValueError(
            "Location forecast is missing dates required for the horizon "
            f"selector: {missing_horizons}."
        )
    selected_horizon = st.radio(
        "Forecast horizon",
        options=list(FORECAST_HORIZONS),
        index=0,
        format_func=lambda horizon: (
            f"{FORECAST_HORIZONS[horizon]} · "
            f"{horizon_dates[horizon]:%b %d, %Y}"
        ),
        horizontal=True,
    )
    selected_date = horizon_dates[selected_horizon]
    selected = location_forecast.loc[
        location_forecast["date"].dt.date.eq(selected_date)
    ].copy()
    if selected.empty:
        raise ValueError(
            f"No location forecasts found for {selected_date:%Y-%m-%d}."
        )

    national_probability = float(
        selected["national_forecast_probability"].iloc[0]
    )
    best_hotspot = selected.loc[selected["forecast_probability"].idxmax()]
    strongest_anomaly = selected.loc[
        selected["anomaly_score"].abs().idxmax()
    ]
    summary = st.columns(5)
    summary[0].metric("National probability", f"{national_probability:.1%}")
    summary[1].metric(
        "National risk class", risk_category(national_probability)
    )
    summary[2].metric(
        "Best hotspot",
        nearest_location_name(
            float(best_hotspot["center_latitude"]),
            float(best_hotspot["center_longitude"]),
        ),
        f"{best_hotspot['forecast_probability']:.1%} forecast",
    )
    summary[3].metric(
        "Strongest anomaly",
        nearest_location_name(
            float(strongest_anomaly["center_latitude"]),
            float(strongest_anomaly["center_longitude"]),
        ),
        f"{strongest_anomaly['anomaly_score'] * 100:+.2f} pp",
    )
    summary[4].metric(
        "Best inland location",
        "Not available",
        help="A coastline dataset is not available to identify inland cells.",
    )

    hotspots = selected.nlargest(10, "forecast_probability")
    coldspots = selected.nsmallest(10, "forecast_probability")
    positive_anomalies = selected.loc[
        selected["anomaly_score"].gt(0)
    ].nlargest(10, "anomaly_score")

    def ranking_table(
        frame: pd.DataFrame, *, include_anomaly: bool
    ) -> pd.DataFrame:
        display = pd.DataFrame(index=frame.index)
        display["Rank"] = range(1, len(frame) + 1)
        display["Location"] = [
            nearest_location_name(float(latitude), float(longitude))
            for latitude, longitude in zip(
                frame["center_latitude"], frame["center_longitude"]
            )
        ]
        display["Forecast probability"] = frame[
            "forecast_probability"
        ].map(lambda value: f"{value:.1%}")
        if include_anomaly:
            display["Anomaly score"] = frame["anomaly_score"].map(
                lambda value: f"{value * 100:+.2f} pp"
            )
        return display

    rankings = st.columns(3)
    ranking_details = (
        (rankings[0], "**Top 10 hotspots**", hotspots, True),
        (
            rankings[1],
            "**Top 10 positive anomalies**",
            positive_anomalies,
            True,
        ),
        (rankings[2], "**Top 10 coldspots**", coldspots, False),
    )
    for column, heading, ranked, include_anomaly in ranking_details:
        with column:
            st.markdown(heading)
            if ranked.empty:
                st.info("No locations match this ranking.")
            else:
                st.dataframe(
                    ranking_table(ranked, include_anomaly=include_anomaly),
                    width="stretch",
                    hide_index=True,
                )

    map_columns = st.columns(2)
    with map_columns[0]:
        render_location_map(
            selected,
            "Forecast probability (low blue to high red).",
            "forecast_probability",
        )
    with map_columns[1]:
        render_location_map(
            selected,
            "Anomaly score (negative blue to positive red).",
            "anomaly_score",
        )


def atlantic_location_label(row: pd.Series) -> str:
    site = str(row["nearest_site"]) if pd.notna(row["nearest_site"]) else ""
    return f"{site} ({row['country']})" if site else (
        f"{row['center_latitude']:.2f}, {row['center_longitude']:.2f} "
        f"({row['country']})"
    )


GUILD_LAYER = "Atlantic passerines"


def atlantic_layer_options() -> dict[str, Path]:
    """Map selector labels to location forecast files for the guild and species."""
    options = {GUILD_LAYER: ATLANTIC_LOCATION_FORECAST_FILE}
    for species in SPECIES_LAYERS:
        options[str(species["species"])] = species_output_paths(
            str(species["slug"])
        )["location"]
    return options


def show_atlantic_location_forecasts(
    path: Path | None = None,
    product: str = "Atlantic",
    map_file: Path = ATLANTIC_LOCATION_MAP_FILE,
    color_scale: float = 0.25,
) -> None:
    title = "Seabird Index Hotspots" if product == "Seabird" else f"{product} Vagrancy Hotspots"
    st.subheader(title)
    key = product.lower()
    options = atlantic_layer_options()
    if path is None:
        layer = st.radio(
            "Hotspot layer",
            list(options),
            horizontal=True,
            help="Guild layer or a species-specific layer.",
            key=f"{key}_layer",
        )
        path = options[layer]
    else:
        layer = GUILD_LAYER
    st.caption(
        f"Cell probability = {product} Index probability "
        + ("x species suitability " if layer != GUILD_LAYER else "")
        + "x coastal suitability x regional suitability. Suitability "
        "weights are expert heuristics (islands, headlands, west-facing "
        "coast, migration traps, landfall exposure and bonuses); species "
        "occupancy and seasonality come from GBIF records. Not trained or "
        "validated. Only 10 km cells with GBIF history or a registered site "
        "are shown."
    )
    if not path.is_file():
        st.info(
            f"No {layer} hotspot forecast is available yet. Run the forecast."
        )
        return
    frame = pd.read_csv(path, parse_dates=["date"])
    available = sorted(frame["date"].dt.date.unique())
    horizon_days = {
        horizon: available[0] + timedelta(days=horizon - 1)
        for horizon in FORECAST_HORIZONS
    }
    missing = [d for d in horizon_days.values() if d not in set(available)]
    if missing:
        raise ValueError(f"{product} hotspot forecast is missing dates: {missing}.")
    horizon = st.radio(
        f"{product} hotspot horizon",
        list(FORECAST_HORIZONS),
        format_func=lambda h: f"{FORECAST_HORIZONS[h]} · {horizon_days[h]:%b %d, %Y}",
        horizontal=True,
        key=f"{key}_horizon",
    )
    selected = frame.loc[frame["date"].dt.date.eq(horizon_days[horizon])].copy()
    if "location" not in selected.columns:
        selected["location"] = selected.apply(atlantic_location_label, axis=1)
    best = selected.loc[selected["forecast_probability"].idxmax()]
    strongest = selected.loc[selected["anomaly_score"].abs().idxmax()]
    metrics = st.columns(4)
    metrics[0].metric("Strongest hotspot", str(best["location"]))
    metrics[1].metric("Probability", f"{best['forecast_probability']:.1%}")
    metrics[2].metric(
        "Strongest anomaly",
        str(strongest["location"]),
        f"{strongest['anomaly_score'] * 100:+.2f} pp",
    )
    metrics[3].metric("Risk level", str(best["risk_level"]))

    def ranking(frame: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Rank": range(1, len(frame) + 1),
                "Location": frame["location"].to_numpy(),
                "Probability": frame["forecast_probability"].map(
                    lambda v: f"{v:.1%}"
                ).to_numpy(),
                "Anomaly": frame["anomaly_score"].map(
                    lambda v: f"{v * 100:+.2f} pp"
                ).to_numpy(),
                "Risk": frame["risk_level"].to_numpy(),
            }
        )

    ranked = selected.sort_values(
        ["forecast_probability", "cell_id"], ascending=[False, True]
    )
    columns = st.columns(2)
    with columns[0]:
        hot_tab, anomaly_tab, cold_tab = st.tabs(
            ["Top 10 hotspots", "Top 20 positive anomalies", "Top 20 coldspots"]
        )
        with hot_tab:
            st.dataframe(ranking(ranked.head(10)), width="stretch", hide_index=True)
        with anomaly_tab:
            positive = selected.loc[selected["anomaly_score"].gt(0)].nlargest(
                20, "anomaly_score"
            )
            if positive.empty:
                st.info("No cell is forecast above its seasonal baseline.")
            else:
                st.dataframe(ranking(positive), width="stretch", hide_index=True)
        with cold_tab:
            st.dataframe(
                ranking(ranked.tail(20).iloc[::-1]),
                width="stretch",
                hide_index=True,
            )
    with columns[1]:
        selected["polygon"] = [
            atlantic_cell_polygon(int(e), int(n))
            for e, n in zip(selected["grid_easting"], selected["grid_northing"])
        ]
        selected["fill_color"] = [
            [int(30 + 225 * v), int(220 * (1 - v)), int(245 * (1 - v)), 170]
            for v in (selected["forecast_probability"] / color_scale).clip(0, 1)
        ]
        selected["forecast_percent"] = selected["forecast_probability"].map(
            lambda v: f"{v:.1%}"
        )
        st.pydeck_chart(
            pdk.Deck(
                layers=[
                    pdk.Layer(
                        "PolygonLayer",
                        data=selected,
                        get_polygon="polygon",
                        get_fill_color="fill_color",
                        pickable=True,
                        filled=True,
                    )
                ],
                initial_view_state=pdk.ViewState(
                    latitude=54.5, longitude=-2.0, zoom=4
                ),
                tooltip={"html": "<b>{location}</b><br/>{forecast_percent}"},
            ),
            width="stretch",
            height=480,
        )
    if layer == GUILD_LAYER and map_file.is_file():
        st.image(
            str(map_file),
            caption=f"{product} hotspots: tomorrow, +3, +7 and +14 days.",
            width="stretch",
        )


def eastern_hotspot_frame(selection: list[str]) -> tuple[pd.DataFrame | None, str]:
    """Load the Eastern guild or combine the selected species by maximum probability."""
    if not selection or EASTERN_GUILD_LAYER in selection:
        if not EASTERN_LOCATION_FORECAST_FILE.is_file():
            return None, EASTERN_GUILD_LAYER
        frame = pd.read_csv(EASTERN_LOCATION_FORECAST_FILE, parse_dates=["date"])
        frame["hotspot_suitability"] = (
            frame["coastal_suitability"] * frame["regional_suitability"]
        )
        frame["historical_occupancy"] = (
            frame["historical_years"] / frame["historical_years"].max()
        )
        frame["driving_species"] = EASTERN_GUILD_LAYER
        return frame, EASTERN_GUILD_LAYER
    by_name = {str(s["species"]): s for s in EASTERN_SPECIES_LAYERS}
    frames: dict[str, pd.DataFrame] = {}
    for name in selection:
        path = eastern_species_output_paths(str(by_name[name]["slug"]))["location"]
        if not path.is_file():
            return None, name
        frames[name] = pd.read_csv(path, parse_dates=["date"])
    combined = combine_species_forecasts(frames)
    combined["hotspot_suitability"] = (
        combined["coastal_suitability"]
        * combined["regional_suitability"]
        * combined["species_suitability"]
    )
    combined["historical_occupancy"] = combined["cell_occupancy"]
    return combined, ", ".join(selection)


def show_eastern_hotspots(color_scale: float = 1.0) -> None:
    st.subheader("Eastern Vagrancy Hotspots")
    names = [str(s["species"]) for s in EASTERN_SPECIES_LAYERS]
    selection = st.multiselect(
        "Species",
        [EASTERN_GUILD_LAYER, *names],
        default=[EASTERN_GUILD_LAYER],
        help=(
            "All Eastern Species shows the guild layer. Several species are "
            "combined using the maximum species probability per cell."
        ),
        key="eastern_species",
    )
    if not selection:
        st.info("Select at least one species.")
        return
    frame, label = eastern_hotspot_frame(selection)
    if frame is None:
        st.info(f"No {label} hotspot forecast is available yet. Run the forecast.")
        return
    st.caption(
        "Cell probability = Eastern Index probability x species suitability "
        "x coastal suitability x regional suitability; multiple species use "
        "the maximum probability per cell. Hotspot suitability is the "
        "suitability product; historical occupancy is the share of years with "
        "GBIF records in the cell. Suitability weights are expert heuristics, "
        "not trained or validated."
    )
    available = sorted(frame["date"].dt.date.unique())
    horizon_days = {
        horizon: available[0] + timedelta(days=horizon - 1)
        for horizon in FORECAST_HORIZONS
    }
    missing = [d for d in horizon_days.values() if d not in set(available)]
    if missing:
        raise ValueError(f"Eastern hotspot forecast is missing dates: {missing}.")
    horizon = st.radio(
        "Eastern hotspot horizon",
        list(FORECAST_HORIZONS),
        format_func=lambda h: f"{FORECAST_HORIZONS[h]} · {horizon_days[h]:%b %d, %Y}",
        horizontal=True,
        key="eastern_horizon",
    )
    selected = frame.loc[frame["date"].dt.date.eq(horizon_days[horizon])].copy()
    ranked = selected.sort_values(
        ["forecast_probability", "cell_id"], ascending=[False, True]
    )
    best = ranked.iloc[0]
    metrics = st.columns(4)
    metrics[0].metric("Selected species", label)
    metrics[1].metric("Predicted probability", f"{best['forecast_probability']:.1%}")
    metrics[2].metric("Hotspot suitability", f"{best['hotspot_suitability']:.2f}")
    metrics[3].metric("Historical occupancy", f"{best['historical_occupancy']:.0%}")
    st.caption(f"Strongest hotspot: {best['location']} ({best['driving_species']}).")

    def ranking(rows: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Rank": range(1, len(rows) + 1),
                "Location": rows["location"].to_numpy(),
                "Species": rows["driving_species"].to_numpy(),
                "Predicted probability": rows["forecast_probability"]
                .map(lambda v: f"{v:.1%}")
                .to_numpy(),
                "Hotspot suitability": rows["hotspot_suitability"]
                .map(lambda v: f"{v:.2f}")
                .to_numpy(),
                "Historical occupancy": rows["historical_occupancy"]
                .map(lambda v: f"{v:.0%}")
                .to_numpy(),
            }
        )

    columns = st.columns(2)
    with columns[0]:
        hot_tab, cold_tab = st.tabs(["Top 10 hotspots", "Top 20 coldspots"])
        with hot_tab:
            st.dataframe(ranking(ranked.head(10)), width="stretch", hide_index=True)
        with cold_tab:
            st.dataframe(
                ranking(ranked.tail(20).iloc[::-1]),
                width="stretch",
                hide_index=True,
            )
    with columns[1]:
        selected["polygon"] = [
            atlantic_cell_polygon(int(e), int(n))
            for e, n in zip(selected["grid_easting"], selected["grid_northing"])
        ]
        selected["fill_color"] = [
            [int(30 + 225 * v), int(220 * (1 - v)), int(245 * (1 - v)), 170]
            for v in (selected["forecast_probability"] / color_scale).clip(0, 1)
        ]
        selected["forecast_percent"] = selected["forecast_probability"].map(
            lambda v: f"{v:.1%}"
        )
        selected["suitability_text"] = selected["hotspot_suitability"].map(
            lambda v: f"{v:.2f}"
        )
        selected["occupancy_text"] = selected["historical_occupancy"].map(
            lambda v: f"{v:.0%}"
        )
        st.pydeck_chart(
            pdk.Deck(
                layers=[
                    pdk.Layer(
                        "PolygonLayer",
                        data=selected,
                        get_polygon="polygon",
                        get_fill_color="fill_color",
                        pickable=True,
                        filled=True,
                    )
                ],
                initial_view_state=pdk.ViewState(
                    latitude=54.5, longitude=-2.0, zoom=4
                ),
                tooltip={
                    "html": "<b>{location}</b><br/>{driving_species}<br/>"
                    "Probability {forecast_percent}<br/>"
                    "Suitability {suitability_text}<br/>"
                    "Occupancy {occupancy_text}"
                },
            ),
            width="stretch",
            height=480,
        )
    if label == EASTERN_GUILD_LAYER and EASTERN_LOCATION_MAP_FILE.is_file():
        st.image(
            str(EASTERN_LOCATION_MAP_FILE),
            caption="Eastern hotspots: tomorrow, +3, +7 and +14 days.",
            width="stretch",
        )


def show_eastern_target_species() -> None:
    st.subheader("🎯 Eastern Target Species")
    if not EASTERN_TARGET_SPECIES_CSV.is_file():
        st.info("No Eastern target species are available yet. Run the forecast.")
        return
    frame = pd.read_csv(EASTERN_TARGET_SPECIES_CSV)
    st.caption(
        "Species ranked by predicted probability (Eastern Index x seasonal "
        "weight x peak cell suitability). Historical percentile is the share "
        "of historical model-output days with a lower probability; stars "
        "follow the percentile bands (95+ = 5, 90-95 = 4, 75-90 = 3, "
        "50-75 = 2, below 50 = 1)."
    )
    horizons = sorted(frame["horizon_days"].unique())
    horizon = st.radio(
        "Eastern target species horizon",
        horizons,
        format_func=lambda h: (
            f"{TARGET_HORIZON_LABELS[h]} · "
            f"{frame.loc[frame['horizon_days'].eq(h), 'date'].iloc[0]}"
        ),
        horizontal=True,
        key="eastern_target_horizon",
    )
    shown = (
        frame.loc[frame["horizon_days"].eq(horizon)]
        .sort_values("rank")
        .head(10)
    )
    st.dataframe(
        pd.DataFrame(
            {
                "Rank": shown["rank"].to_numpy(),
                "Species": shown["species"].to_numpy(),
                "Probability": shown["probability"].map(lambda v: f"{v:.1%}").to_numpy(),
                "Historical percentile": shown["historical_percentile"]
                .map(lambda v: f"{v:.1f}")
                .to_numpy(),
                "Star rating": shown["star_rating"].map(lambda v: stars_text(int(v))).to_numpy(),
            }
        ),
        width="stretch",
        hide_index=True,
    )


def show_birding_opportunity_index() -> None:
    st.header("🎯 Birding Opportunity Index")
    if not BOI_JSON.is_file():
        st.info("No Birding Opportunity Index is available yet. Run the forecast.")
        return
    document = json.loads(BOI_JSON.read_text(encoding="utf-8"))
    horizons = {int(h["horizon_days"]): h for h in document["horizons"]}
    horizon = st.radio(
        "BOI horizon",
        list(horizons),
        format_func=lambda h: f"{horizons[h]['label']} · {horizons[h]['date']}",
        horizontal=True,
        key="boi_horizon",
    )
    item = horizons[horizon]
    metrics = st.columns(4)
    metrics[0].metric("Score", f"{item['boi_score']:.0f} / 100", item["rating_category"], delta_color="off")
    metrics[1].metric("Historical percentile", f"{item['historical_percentile']:.0f}")
    metrics[2].metric("Main contributing module", item["main_module"])
    metrics[3].metric(
        "Modules used", str(len(item["weighted_contributions"])), delta_color="off"
    )
    st.markdown(f"**Recommendation:** {item['recommended_style']}")
    columns = st.columns(2)
    columns[0].markdown(
        "**Best hotspots**\n\n"
        + ("\n".join(f"- {h}" for h in item["best_hotspots"]) or "None available")
    )
    columns[1].markdown(
        "**Most likely target species**\n\n"
        + ("\n".join(f"- {t}" for t in item["target_species"]) or "None available")
    )
    st.caption(
        "BOI = weighted mean of module historical percentiles "
        + ", ".join(f"{k} {v:.0%}" for k, v in document["weights"].items())
        + ". Modules without a forecast (e.g. Goose out of season) are "
        "dropped and the weights renormalised. Hotspots and species come "
        "from the main contributing module."
    )
    st.dataframe(
        pd.DataFrame(
            {
                "Module": list(item["module_percentiles"]),
                "Historical percentile": [
                    "n/a" if v is None else f"{v:.1f}"
                    for v in item["module_percentiles"].values()
                ],
                "Weighted contribution": [
                    f"{item['weighted_contributions'].get(k, 0):.1f}"
                    for k in item["module_percentiles"]
                ],
            }
        ),
        width="stretch",
        hide_index=True,
    )


def trend_text(trend: dict[str, object]) -> str:
    arrows = {"up": "▲", "down": "▼", "steady": "▬"}
    if trend.get("change") is None:
        return "Trend n/a (no earlier forecast)"
    return (
        f"{arrows[str(trend['direction'])]} {float(trend['change']) * 100:+.1f} pp "
        "vs yesterday's forecast"
    )


def marker_color(value: float) -> list[int]:
    """Blue (low) through yellow to red (strongest) for a 0-1 relative score."""
    value = min(max(value, 0.0), 1.0)
    if value < 0.5:
        mix = value / 0.5
        return [int(43 + 204 * mix), int(108 + 116 * mix), int(176 - 100 * mix), 210]
    mix = (value - 0.5) / 0.5
    return [int(247 - 33 * mix), int(224 - 185 * mix), int(76 - 36 * mix), 210]


def show_seabird_decision_support() -> None:
    st.subheader("Seawatching decision support")
    species_names = [str(item["species"]) for item in SEABIRD_SPECIES]
    species = {name: name for name in species_names}
    show_species_leaderboard("Seabirds", species)

    def clear_leaderboard_selection() -> None:
        st.session_state["species_leaderboard_Seabirds"] = {"selection": {"rows": []}}

    selected_product = st.selectbox(
        "Seabird Product:",
        ["General Seabird Index", *sorted(species_names)],
        format_func=lambda name: {
            "European Storm-petrel": "🌀 Storm-petrels · European Storm-petrel",
            "Northern Fulmar": "🌊 Rare seabirds · Northern Fulmar",
            "Sooty Shearwater": "🐦 Shearwaters · Sooty Shearwater",
            "Manx Shearwater": "🐦 Shearwaters · Manx Shearwater",
            "Great Shearwater": "🐦 Shearwaters · Great Shearwater",
        }.get(name, name),
        key="seabird_product_selector",
        on_change=clear_leaderboard_selection,
    )
    support = read_output(DECISION_SUPPORT_FILE)
    if selected_product != "General Seabird Index":
        if selected_product not in SEABIRD_SPECIES_NAMES:
            st.info(
                f"No independent species forecast is available for {selected_product}. "
                "This species is listed in the seabird dataset configuration but has "
                "no species model. The General Seabird Index is a pooled forecast "
                "for the configured core taxa, not a forecast for this species."
            )
        else:
            show_seabird_species_detail(selected_product, support)
        return
    if support is None:
        st.info("No seawatching decision support yet. Run the forecast.")
        return
    horizons = support["horizons"]
    st.caption(
        "Index score: 100 equals a Major Seawatch Day probability (50%). "
        "Status bands: Normal <10%, Good 10-25%, Excellent 25-50%, Major "
        "50%+. Confidence is a lead-time rule, not a calibrated interval. "
        "Wind is the national coastal wind driving the model and applies to "
        "every site."
    )
    tomorrow = horizons[0]
    card = st.columns(4)
    card[0].metric(
        "Seabird probability",
        f"{tomorrow['probability']:.1%}",
        trend_text(tomorrow["trend"]),
        delta_color="off",
    )
    card[1].metric("Event status", tomorrow["status"])
    card[2].metric("Index score", f"{tomorrow['score']}/100")
    card[3].metric("Recommended coast", tomorrow["recommended_coast"]["coast"])

    tabs = st.tabs([h["label"] for h in horizons])
    for tab, horizon in zip(tabs, horizons):
        with tab:
            st.markdown(f"**{horizon['label']} · {horizon['date']}**")
            metrics = st.columns(4)
            metrics[0].metric("Seabird Index score", f"{horizon['score']}/100")
            metrics[1].metric(
                "Event probability",
                f"{horizon['probability']:.1%}",
                trend_text(horizon["trend"]),
                delta_color="off",
            )
            metrics[2].metric("Status", horizon["status"])
            metrics[3].metric("Confidence", horizon["confidence"])
            st.write(f"**Wind:** {horizon['wind']['text']}")
            coast = horizon["recommended_coast"]
            st.write(
                f"**Recommended watch coast:** {coast['coast']}"
                + (f" (best site: {coast['top_site']})" if coast["top_site"] else "")
            )
            columns = st.columns(2)
            with columns[0]:
                st.markdown("**Best seawatch locations**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Rank": site["rank"],
                                "Location": site["location"],
                                "Country": site["country"],
                                "Score": site["score"],
                                "Probability": f"{site['probability']:.1%}",
                            }
                            for site in horizon["best_locations"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                st.markdown("**Best Dutch sites**")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Rank": site["rank"],
                                "Location": site["location"],
                                "Score": site["score"],
                                "Probability": f"{site['probability']:.1%}",
                            }
                            for site in horizon["best_dutch_locations"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            with columns[1]:
                sites = pd.DataFrame(horizon["map_locations"])
                top = max(float(sites["probability"].max()), 1e-9)
                sites["color"] = [marker_color(v / top) for v in sites["probability"]]
                sites["radius"] = 6000 + 14000 * (sites["probability"] / top)
                sites["rank_label"] = sites["rank"].astype(str)
                sites["score_text"] = sites["score"].astype(str) + "/100"
                sites["probability_text"] = sites["probability"].map(
                    lambda v: f"{v:.1%}"
                )
                sites["wind_text"] = horizon["wind"]["text"]
                sites["confidence"] = horizon["confidence"]
                st.pydeck_chart(
                    pdk.Deck(
                        layers=[
                            pdk.Layer(
                                "ScatterplotLayer",
                                data=sites,
                                get_position=["longitude", "latitude"],
                                get_fill_color="color",
                                get_radius="radius",
                                pickable=True,
                            ),
                            pdk.Layer(
                                "TextLayer",
                                data=sites.head(10),
                                get_position=["longitude", "latitude"],
                                get_text="rank_label",
                                get_size=14,
                                get_color=[20, 20, 20, 255],
                            ),
                        ],
                        initial_view_state=pdk.ViewState(
                            latitude=54.5, longitude=1.0, zoom=3.6
                        ),
                        tooltip={
                            "html": (
                                "<b>#{rank_label} {location}</b><br/>"
                                "Score: {score_text} ({probability_text})<br/>"
                                "Wind: {wind_text}<br/>"
                                "Confidence: {confidence}"
                            )
                        },
                    ),
                    width="stretch",
                    height=480,
                )
                st.caption(
                    "Marker colour: blue = low, yellow = moderate, red = "
                    "strongest of the day. Numbers mark the top 10."
                )


def show_seabird_species_detail(
    species: str, support: dict | None
) -> None:
    forecast = read_forecast(seabird_species_output_paths(species)["forecast"])
    if forecast is not None:
        ordered = forecast.sort_values("date")
        scores = st.columns(3)
        scores[0].metric("First forecast day", f"{ordered.iloc[0]['probability']:.1%}")
        scores[1].metric(
            "Change to next forecast day",
            f"{(ordered.iloc[1]['probability'] - ordered.iloc[0]['probability']) * 100:+.1f} pp"
            if len(ordered) > 1 else "Unavailable",
        )
        scores[2].metric(
            "Highest forecast date",
            ordered.loc[ordered["probability"].idxmax(), "date"].strftime("%Y-%m-%d"),
        )
        locations = read_forecast(seabird_species_output_paths(species)["location"])
        if locations is not None:
            first_date = ordered.iloc[0]["date"]
            show_dutch_species_recommendations(
                species, locations.loc[locations["date"].eq(first_date)],
                "probability", "Seabirds", first_date,
            )
        else:
            st.info("Dutch location forecast is unavailable for this species.")
        st.line_chart(
            ordered.set_index("date")["probability"].mul(100).rename("Probability (%)"),
            width="stretch",
        )
        st.caption("Change compares forecast dates, not revisions to an earlier forecast.")
    if support is None:
        st.info("Seabird weather and international site support is unavailable. Run the forecast.")
    else:
        show_seabird_species_product(species, support, dutch_recommendations=True)


def show_seabird_species_product(
    species: str, general_support: dict[str, object], *, dutch_recommendations: bool = False
) -> None:
    paths = seabird_species_output_paths(species)
    forecast_path = paths["forecast"]
    location_path = paths["location"]
    if not forecast_path.is_file() or not location_path.is_file():
        st.info(f"No forecast is available yet for {species}. Run the daily forecast.")
        return
    forecast = pd.read_csv(forecast_path, parse_dates=["date"])
    locations = pd.read_csv(location_path, parse_dates=["date"])
    required_forecast = {"date", "probability", "risk_level"}
    required_locations = {
        "date", "location", "country", "latitude", "longitude",
        "probability", "rank",
    }
    if not required_forecast.issubset(forecast.columns):
        raise ValueError(f"Invalid species forecast schema: {forecast_path}")
    if not required_locations.issubset(locations.columns):
        raise ValueError(f"Invalid species location schema: {location_path}")
    evaluation_path = ROOT / "outputs/seabird_species_evaluation.csv"
    if evaluation_path.is_file():
        evaluation = pd.read_csv(evaluation_path)
        product = f"{species} Seabird Model"
        row = evaluation.loc[evaluation["product"].eq(product)]
        if not row.empty:
            report = row.iloc[0]
            st.caption(
                f"Training P90 threshold: {report['threshold_count']:g} records/day · "
                f"positive days: {int(report['full_period_positive_days']):,} "
                f"({report['full_period_prevalence']:.1%}) · "
                f"forward-chain ROC-AUC: {report['roc_auc']:.3f} · "
                f"PR-AUC: {report['pr_auc']:.3f}."
            )
            if not bool(report["data_sufficient_for_meaningful_prediction"]):
                st.warning(
                    f"Limited data for {species}: the current history does not meet "
                    f"the model's sufficiency rule ({report['sufficiency_rule']}). "
                    "Treat its forecast as exploratory."
                )
    forecast["date"] = forecast["date"].dt.normalize()
    locations["date"] = locations["date"].dt.normalize()
    first_date = forecast["date"].min()
    horizon_dates = {
        horizon: first_date + pd.Timedelta(days=horizon - 1)
        for horizon in FORECAST_HORIZONS
    }
    available_dates = set(forecast["date"])
    if set(horizon_dates.values()) - available_dates:
        raise ValueError(f"{species} forecast does not cover all four horizons.")
    tabs = st.tabs([FORECAST_HORIZONS[h] for h in FORECAST_HORIZONS])
    support_by_horizon = {
        int(item["horizon_days"]): item for item in general_support["horizons"]
    }
    for tab, (horizon, label) in zip(tabs, FORECAST_HORIZONS.items()):
        with tab:
            target_date = horizon_dates[horizon]
            national = forecast.loc[forecast["date"].eq(target_date)]
            day = locations.loc[locations["date"].eq(target_date)].copy()
            if national.empty or day.empty:
                raise ValueError(
                    f"{species} forecast is missing location data for "
                    f"{target_date.date()}."
                )
            probability = float(national.iloc[0]["probability"])
            ordered = day.sort_values(["rank", "location"])
            top10 = ordered.head(10)
            score = index_score(probability)
            metrics = st.columns(4)
            metrics[0].metric(f"{species} probability", f"{probability:.1%}")
            metrics[1].metric("Event status", event_status(probability))
            metrics[2].metric("Index score", f"{score}/100")
            metrics[3].metric("Confidence", confidence_label(horizon))
            if dutch_recommendations and horizon != 1:
                show_dutch_species_recommendations(
                    species, day, "probability", "Seabirds", target_date
                )
            st.write(f"**{label} · {target_date:%b %d, %Y}**")
            st.write(f"**Wind:** {support_by_horizon[horizon]['wind']['text']}")

            coast_input = day.rename(
                columns={"probability": "forecast_probability"}
            )
            coast = recommended_coast(coast_input)
            st.write(
                f"**Recommended watch coast:** {coast['coast']}"
                + (f" (best site: {coast['top_site']})" if coast["top_site"] else "")
            )
            columns = st.columns(2)
            with columns[0]:
                st.markdown("**Top 10 hotspots**")
                display = top10[
                    ["rank", "location", "country", "probability", "anomaly_score"]
                ].copy()
                display["score"] = display["probability"].map(index_score)
                display["probability"] = display["probability"].map(
                    lambda value: f"{value:.1%}"
                )
                display["anomaly_score"] = display["anomaly_score"].map(
                    lambda value: f"{value * 100:+.2f} pp"
                )
                st.dataframe(display, width="stretch", hide_index=True)
            with columns[1]:
                map_data = ordered.head(40).copy()
                max_probability = max(float(map_data["probability"].max()), 1e-9)
                map_data["color"] = [
                    marker_color(float(value) / max_probability)
                    for value in map_data["probability"]
                ]
                map_data["radius"] = [
                    6000 + 14000 * float(value) / max_probability
                    for value in map_data["probability"]
                ]
                map_data["rank_label"] = map_data["rank"].astype(str)
                map_data["score_text"] = map_data["probability"].map(
                    lambda value: f"{index_score(float(value))}/100"
                )
                map_data["probability_text"] = map_data["probability"].map(
                    lambda value: f"{value:.1%}"
                )
                map_data["wind_text"] = support_by_horizon[horizon]["wind"]["text"]
                map_data["confidence"] = confidence_label(horizon)
                st.pydeck_chart(
                    pdk.Deck(
                        layers=[
                            pdk.Layer(
                                "ScatterplotLayer",
                                data=map_data,
                                get_position=["longitude", "latitude"],
                                get_fill_color="color",
                                get_radius="radius",
                                pickable=True,
                            ),
                            pdk.Layer(
                                "TextLayer",
                                data=map_data.head(10),
                                get_position=["longitude", "latitude"],
                                get_text="rank_label",
                                get_size=14,
                                get_color=[20, 20, 20, 255],
                            ),
                        ],
                        initial_view_state=pdk.ViewState(
                            latitude=54.5, longitude=1.0, zoom=3.6
                        ),
                        tooltip={
                            "html": (
                                "<b>#{rank_label} {location}</b><br/>"
                                "Score: {score_text} ({probability_text})<br/>"
                                "Wind: {wind_text}<br/>Confidence: {confidence}"
                            )
                        },
                    ),
                    width="stretch",
                    height=480,
                )


def _driver_lines(drivers: list[dict[str, object]]) -> str:
    return "\n".join(
        f"- {driver['label']} ({float(driver['points']):+.1f}): {driver['detail']}"
        for driver in drivers
    ) or "- None"


def show_score_drivers(horizon: dict[str, object]) -> None:
    if "positive_drivers" not in horizon:
        return
    positive, negative = st.columns(2)
    positive.markdown("**Positive drivers**\n" + _driver_lines(horizon["positive_drivers"]))
    negative.markdown(
        "**Negative drivers** (points forgone)\n"
        + _driver_lines(horizon["negative_drivers"])
    )


def show_coast_ranking_rows(ranking: list[dict[str, object]]) -> None:
    if ranking:
        st.markdown("**Dutch coast ranking**")
        st.dataframe(
            pd.DataFrame(ranking)[["rank", "coast", "score"]],
            width="stretch",
            hide_index=True,
        )


def show_recommendation_banner() -> None:
    if not RATING_JSON_OUTPUT.is_file() or not RARITY_INDEX_JSON_OUTPUT.is_file():
        return
    items = build_recommendations(
        json.loads(RATING_JSON_OUTPUT.read_text(encoding="utf-8")),
        json.loads(RARITY_INDEX_JSON_OUTPUT.read_text(encoding="utf-8")),
    )
    tabs = st.tabs([item["label"] for item in items])
    for tab, item in zip(tabs, items):
        with tab:
            message = (
                f"{item['icon']} **{item['decision']}**\n\n"
                f"Seawatch Day Rating: {item['seawatch_day_rating']:.0f}  \n"
                f"Rarity Index: {item['rarity_index']:.0f}\n\n"
                f"Best coast: {item['best_coast']}  \n"
                f"Best site: {item['best_site']}"
            )
            {"GO": st.success, "MAYBE": st.warning, "STAY HOME": st.error}[
                item["decision"]
            ](message)


def show_percentile_context(item: dict[str, object]) -> None:
    if "historical_rank_text" in item:
        st.markdown(
            f"**{item['historical_label']}**  \n{item['historical_rank_text']}"
        )


def show_seawatch_day_rating() -> None:
    st.subheader("🔥 Seawatch Day Rating")
    if not RATING_JSON_OUTPUT.is_file():
        show_prediction_status("Forecast Model", "Experimental")
        st.info("No Seawatch Day Rating is available yet. Run the daily forecast.")
        return
    document = json.loads(RATING_JSON_OUTPUT.read_text(encoding="utf-8"))
    horizons = document.get("horizons", [])
    if not horizons:
        raise ValueError("Seawatch Day Rating JSON contains no forecast horizons.")
    tomorrow = horizons[0]
    show_prediction_status(
        "Forecast Model", str(tomorrow.get("confidence", "Experimental"))
    )
    metrics = st.columns(4)
    metrics[0].metric("Score", f"{tomorrow['score']}/100")
    metrics[1].metric("Rating", tomorrow["rating"])
    metrics[2].metric("Confidence", tomorrow["confidence"])
    metrics[3].metric("Best Coast", tomorrow["best_coast"]["coast"])
    show_percentile_context(tomorrow)
    dutch = tomorrow.get("top3_dutch_sites", [])
    if dutch:
        st.markdown(
            "**Top 3 Dutch Sites:** "
            + " · ".join(
                f"{site['location']} ({site['score']}/100)"
                for site in dutch
            )
        )
    st.markdown(
        "**Drivers:** "
        + (
            " · ".join(
                f"{driver['name'].replace('_', ' ').title()} "
                f"{float(driver['points']):+.1f}"
                for driver in tomorrow["drivers"]
            )
            if tomorrow["drivers"]
            else "No additional weather bonuses."
        )
    )
    tabs = st.tabs([horizon["label"] for horizon in horizons])
    for tab, horizon in zip(tabs, horizons):
        with tab:
            st.markdown(f"**{horizon['date']}**")
            horizon_metrics = st.columns(4)
            horizon_metrics[0].metric("Score", f"{horizon['score']}/100")
            horizon_metrics[1].metric("Rating", horizon["rating"])
            horizon_metrics[2].metric("Confidence", horizon["confidence"])
            horizon_metrics[3].metric(
                "Best Coast", horizon["best_coast"]["coast"]
            )
            show_percentile_context(horizon)
            st.markdown(
                "**Top 3 Dutch Sites:** "
                + (
                    " · ".join(
                        f"{site['location']} ({site['score']}/100)"
                        for site in horizon.get("top3_dutch_sites", [])
                    )
                    or "No site data"
                )
            )
            st.markdown(
                "**Drivers:** "
                + (
                    " · ".join(
                        f"{driver['name'].replace('_', ' ').title()} "
                        f"{float(driver['points']):+.1f}"
                        for driver in horizon["drivers"]
                    )
                    if horizon["drivers"]
                    else "No additional weather bonuses."
                )
            )
            show_score_drivers(horizon)
            show_coast_ranking_rows(horizon.get("coast_ranking", []))
            hotspot_table = pd.DataFrame(horizon["top10_hotspots"])
            st.dataframe(
                hotspot_table[
                    ["rank", "location", "country", "score", "rating"]
                ],
                width="stretch",
                hide_index=True,
            )


def show_rarity_index() -> None:
    st.subheader("🦅 Rarity Index")
    st.caption(
        "Weighted potential for unusually rare seabird records, scaled against "
        "historical species-model output. Separate from overall seawatching quality."
    )
    if not RARITY_INDEX_JSON_OUTPUT.is_file():
        st.info("No Rarity Index forecast is available yet. Run the daily forecast.")
        return
    document = json.loads(
        RARITY_INDEX_JSON_OUTPUT.read_text(encoding="utf-8")
    )
    insufficient = [
        species
        for species, sufficient in document.get(
            "model_data_sufficiency", {}
        ).items()
        if not sufficient
    ]
    if insufficient:
        st.warning(
            "Limited training data for "
            + ", ".join(insufficient)
            + "; rarity contributions from these species are exploratory."
        )
    horizons = document.get("horizons", [])
    if not horizons:
        raise ValueError("Rarity Index JSON contains no forecast horizons.")
    first = horizons[0]
    st.metric(
        "Tomorrow's Rarity Index",
        f"{first['rarity_index']:.1f}/100",
        f"Leading species: {first['leading_rarity_species']}",
        delta_color="off",
    )
    show_percentile_context(first)
    scaling = document["scaling"]
    st.caption(
        f"Historical raw-score P{scaling['lower_percentile']}: "
        f"{scaling['historical_raw_p5']:.3f}; P{scaling['upper_percentile']}: "
        f"{scaling['historical_raw_p95']:.3f}. Values outside this range are clipped."
    )
    tabs = st.tabs([horizon["label"] for horizon in horizons])
    for tab, horizon in zip(tabs, horizons):
        with tab:
            st.markdown(f"**{horizon['date']}**")
            st.metric(
                "Rarity Index",
                f"{horizon['rarity_index']:.1f}/100",
                f"Leading species: {horizon['leading_rarity_species']}",
                delta_color="off",
            )
            show_percentile_context(horizon)
            contributions = pd.DataFrame(
                [
                    {
                        "Species": species,
                        "Probability": f"{horizon['species_probabilities'][species]:.1%}",
                        "Rarity weight": document["rarity_weights"][species],
                        "Weighted rarity potential": (
                            horizon["rarity_contributions"][species]
                        ),
                    }
                    for species in document["rarity_weights"]
                ]
            ).sort_values("Weighted rarity potential", ascending=False)
            st.dataframe(contributions, width="stretch", hide_index=True)


def goose_hotspot_color(score: float) -> list[int]:
    ratio = min(max(float(score) / 100.0, 0.0), 1.0)
    return [int(40 + 190 * ratio), int(110 + 60 * (1 - ratio)), int(200 * (1 - ratio) + 30), 200]


def show_goose_hotspot_map(hotspots: list[dict[str, object]]) -> None:
    if not hotspots:
        st.info("No goose hotspots available.")
        return
    data = pd.DataFrame(hotspots)
    data["fill_color"] = data["score"].map(goose_hotspot_color)
    data["radius"] = 3000 + data["score"].astype(float) * 150
    layer = pdk.Layer(
        "ScatterplotLayer", data=data, get_position="[longitude, latitude]",
        get_fill_color="fill_color", get_radius="radius", pickable=True,
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(latitude=52.7, longitude=5.4, zoom=6),
            tooltip={"html": "<b>{location}</b><br/>{region}<br/>Score: {score}/100 ({rating})"},
        ),
        width="stretch",
        height=420,
    )


def show_goose_horizon(horizon: dict[str, object], document: dict[str, object]) -> None:
    rating = horizon["goose_day_rating"]
    activity = horizon["goose_activity"]
    rare = horizon["rare_goose_potential"]
    decision = horizon["recommendation"]
    st.markdown(f"**{horizon['date']}**")
    if horizon.get("off_season"):
        st.caption("Outside the Oct-Mar goose season; models were trained on winter days only.")
    {"GO": st.success, "MAYBE": st.warning, "STAY HOME": st.error}[decision["decision"]](
        f"{decision['emoji']} **{decision['decision']}** — {decision['reason']}"
    )

    st.markdown("#### 1. Goose Day Rating")
    st.metric("Goose Day Rating", f"{rating['score']}/100", rating["rating"], delta_color="off")
    st.caption("70% Goose Activity Index + 30% Rare Goose Potential")

    st.markdown("#### 2. Goose Activity Index")
    st.metric("Goose Activity Index", f"{activity['score']}", activity["category"], delta_color="off")
    st.caption(f"Probability of above-normal goose concentrations: {activity['probability']:.1%}")

    st.markdown("#### 3. Rare Goose Potential")
    st.metric("Rare Goose Potential", f"{rare['score']}", rare["category"], delta_color="off")

    st.markdown("#### 4. 🎯 Target Geese")
    st.dataframe(
        pd.DataFrame(
            [
                {"Rank": item["rank"], "Species": item["species"],
                 "Probability": f"{item['probability']:.1%}",
                 "Rarity weight": item["rarity_weight"],
                 "Target score": round(item["target_score"], 3)}
                for item in horizon["target_geese"]
            ]
        ),
        width="stretch", hide_index=True,
    )

    st.markdown("#### 5. Best Goose Regions")
    st.dataframe(
        pd.DataFrame(horizon["best_regions"])[["rank", "region", "score", "top_site"]],
        width="stretch", hide_index=True,
    )

    st.markdown("#### 6. Hotspot Map")
    show_goose_hotspot_map(horizon["top10_hotspots"])
    st.dataframe(
        pd.DataFrame(horizon["top10_hotspots"])[["rank", "location", "region", "score", "rating"]],
        width="stretch", hide_index=True,
    )

    st.markdown("#### 7. Historical Context")
    for title, item in (
        ("Goose Day Rating", {**rating, "value": rating["score"]}),
        ("Goose Activity Index", {**activity, "value": activity["score"]}),
        ("Rare Goose Potential", {**rare, "value": rare["score"]}),
    ):
        st.markdown(
            f"**{title}** {item['value']}  \n{item['historical_rank_text']} · "
            f"**{item['historical_label']}**"
        )

    st.markdown("#### European Goose Influx")
    european = horizon["european_goose_influx"]
    influx_metrics = st.columns(3)
    influx_metrics[0].metric(
        "Rare Goose Europe Index",
        f"{european['score']:.1f}/100",
        f"{european['historical_percentile']:.0f}% of historical forecasts",
        delta_color="off",
    )
    influx_metrics[1].metric(
        "7-day change from Tomorrow",
        f"{european['change_7d_points']:+.1f} points",
        delta_color="off",
    )
    influx_metrics[2].metric(
        "14-day change from Tomorrow",
        f"{european['change_14d_points']:+.1f} points",
        delta_color="off",
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Species": item["species"],
                    "European activity": f"{item['probability']:.1%}",
                    "Activity score": item["activity_score"],
                    "European percentile": item["european_percentile"],
                    "Historical context": item["historical_label"],
                }
                for item in european["species_activity"]
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    conditions = horizon.get("conditions", {})
    if conditions:
        st.caption(
            f"Weather: {conditions.get('temperature_c')} °C · "
            f"frost days in a row: {conditions.get('consecutive_frost_days', 0):.0f} · "
            f"cold outbreak: {'yes' if conditions.get('cold_outbreak') else 'no'} · "
            f"rapid temperature drop: {'yes' if conditions.get('rapid_temp_drop') else 'no'}"
        )


def show_goose_forecast(path: Path | None = None) -> None:
    st.header("🪿 Goose Forecast")
    show_prediction_status("Forecast Model", "Experimental")
    path = path or GOOSE_JSON_OUTPUT
    if not path.is_file():
        st.info(
            "No Goose Forecast is available yet. Train the goose models and run the "
            "daily forecast."
        )
        return
    document = json.loads(path.read_text(encoding="utf-8"))
    horizons = document.get("horizons", [])
    if not horizons:
        raise ValueError("Goose module JSON contains no forecast horizons.")
    weak = [
        row["model"] for row in document.get("model_evaluation", [])
        if row.get("status") == "Experimental"
    ]
    if weak:
        st.warning(
            "Experimental models (limited data or weak validation): " + ", ".join(weak)
            + ". Treat their contribution as exploratory."
        )
    tabs = st.tabs([horizon["label"] for horizon in horizons])
    for tab, horizon in zip(tabs, horizons):
        with tab:
            show_goose_horizon(horizon, document)
    evaluation = document.get("model_evaluation", [])
    if evaluation:
        with st.expander("Model validation"):
            st.dataframe(pd.DataFrame(evaluation), width="stretch", hide_index=True)


FIRSTS_TOP_COLOR = "#1f6f5c"
FIRSTS_REST_COLOR = "#a9c4bd"
FIRSTS_BADGE_COLORS = {
    "corvo": "#2a7f9e",
    "ireland": "#3a9a5b",
    "uk": "#b5483a",
    "france": "#5b6fb5",
    "spain": "#d49a1f",
    "portugal": "#8a5a9e",
}


def firsts_badges(candidate: Candidate) -> str:
    return " ".join(
        f'<span style="background:{FIRSTS_BADGE_COLORS[c]};color:#fff;'
        f'padding:2px 8px;border-radius:10px;font-size:0.8rem;">'
        f"{COUNTRY_LABELS[c]} {candidate.records(c)}</span>"
        for c in COUNTRIES
        if candidate.records(c) > 0
    )


def firsts_timeline_html(candidate: Candidate) -> str:
    steps = []
    for region, year, years_ago in timeline(candidate):
        color = FIRSTS_TOP_COLOR if year else FIRSTS_REST_COLOR
        detail = "never" if not year else f"{year}<br>{years_ago}y ago"
        steps.append(
            f'<div style="text-align:center;min-width:100px;">'
            f'<div style="background:{color};color:#fff;border-radius:12px;padding:8px 6px;'
            f'font-weight:600;line-height:1.3;">{detail}</div>'
            f'<div style="font-size:0.85rem;margin-top:4px;">{region}</div></div>'
        )
    return (
        '<div style="display:flex;align-items:center;gap:8px;">'
        + '<span style="font-size:1.4rem;">→</span>'.join(steps)
        + "</div>"
    )


def firsts_rarity_html(candidate: Candidate) -> str:
    chips = []
    for label, color in zip(RARITY_LABELS, RARITY_COLORS):
        active = label == candidate.dutch_status
        text = "#fff" if RARITY_COLORS.index(color) < 3 else "#14463a"
        style = (
            f"background:{color};color:{text};padding:3px 10px;border-radius:10px;"
            f"font-size:0.8rem;"
            + ("outline:3px solid #f2a900;font-weight:700;" if active else "opacity:0.55;")
        )
        chips.append(f'<span style="{style}">{label}</span>')
    return " ".join(chips)


def show_score_breakdown(candidate: Candidate) -> None:
    st.markdown(f"**Prediction Score: {candidate.prediction_score:.0f}**")
    lines = [
        f"- {BREAKDOWN_LABELS[key]}: +{points}"
        for key, points in candidate.score_breakdown.items()
    ]
    st.markdown("Breakdown:\n" + "\n".join(lines))


def show_next_dutch_firsts() -> None:
    st.subheader("⭐ Next Dutch Firsts")
    show_prediction_status("Statistical Risk Model", "Experimental")
    st.caption(
        "Trend-based candidates for a Dutch first or an exceptionally rare "
        "record, ranked using historical rarity and recent western-European records."
    )
    st.markdown(
        '<span style="background:#d9822b;color:#fff;padding:4px 12px;border-radius:12px;'
        'font-weight:700;letter-spacing:0.05em;">DEMO DATA</span>',
        unsafe_allow_html=True,
    )
    st.warning(DATA_PROVENANCE)
    st.info(
        "Many North American vagrants first appear on Corvo (Azores), then Ireland, "
        "then the UK before reaching northwestern mainland Europe."
    )
    st.caption(
        "This is a historical rarity and momentum ranking, not a calibrated "
        "multi-year probability forecast. The bundled candidate records are "
        "illustrative demo data."
    )
    with st.expander("How the score works and what the filters mean"):
        st.markdown(
            "Score = 30% Corvo, 20% UK, 10% Ireland, 10% France/Iberia, 10% Dutch "
            "rarity (fewer Dutch records = higher), 10% recency, 10% momentum "
            "(0-20 pts: Corvo +8, Ireland +5, UK +5 if seen in the last 2 years, +2 "
            "recent surge).\n\n"
            "- Corvo Pipeline: Corvo records and <10 Dutch records\n"
            "- Long Overdue: last Dutch record 10+ years ago and an Atlantic record in the last 3 years\n"
            "- Rising Fast: momentum 13+/20"
        )
    with st.expander("Data sources (planned live integrations)"):
        for name, status, purpose in PLANNED_SOURCES:
            st.markdown(f"- `{status}` **{name}**: {purpose}")
    ranked = load_ranked()
    counts = summary_counts(ranked)
    for column, (name, count) in zip(st.columns(len(counts)), counts.items()):
        column.metric(name.replace(" (<10 Dutch records)", ""), count)
    rising = top_rising(ranked)
    with st.container(border=True):
        st.markdown("**🚀 Top Rising Species**")
        if not rising:
            st.caption("No species currently have momentum of 13 or more.")
        for i, c in enumerate(rising, 1):
            st.markdown(f"{i}. {c.common_name} · {c.momentum_score}/20 · {c.momentum_label}")
    chosen_filter = st.radio("Filter", FILTERS, horizontal=True, key="avw_filter")
    shown = apply_filter(ranked, chosen_filter)
    if not shown:
        st.info("No species match this filter.")
        return
    order = [c.common_name for c in shown]
    frame = pd.DataFrame(
        {
            "Species": order,
            "Score": [c.prediction_score for c in shown],
            "Label": [
                f"{c.prediction_score:.0f}%" + (" 🌊" if c.corvo_records else "")
                for c in shown
            ],
            "Tier": ["Top 10" if i < 10 else "Watchlist" for i in range(len(shown))],
        }
    )
    select = alt.selection_point(fields=["Species"], name="species")
    bars = (
        alt.Chart(frame)
        .mark_bar()
        .encode(
            y=alt.Y("Species:N", sort=order, title=None),
            x=alt.X("Score:Q", title="Prediction score (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color(
                "Tier:N",
                scale=alt.Scale(domain=["Top 10", "Watchlist"], range=[FIRSTS_TOP_COLOR, FIRSTS_REST_COLOR]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=["Species", "Label"],
        )
        .add_params(select)
    )
    labels = bars.mark_text(align="left", dx=3).encode(text="Label:N")
    event = st.altair_chart(
        (bars + labels).properties(height=26 * len(frame)),
        on_select="rerun",
        selection_mode="species",
        key="next_dutch_firsts_chart",
        width="stretch",
    )
    st.caption("🌊 = Corvo Factor (species recorded on Corvo)")
    clicked = event.selection.get("species", []) if event and event.selection else []
    default = order.index(clicked[0]["Species"]) if clicked and clicked[0].get("Species") in order else 0
    chosen = st.selectbox("Species detail (or click a bar)", order, index=default)
    candidate = next(c for c in shown if c.common_name == chosen)
    rank = order.index(chosen) + 1

    with st.container(border=True):
        st.subheader(f"#{rank} {candidate.common_name}")
        st.markdown(f"*{candidate.scientific_name}* · {candidate.momentum_label}")
        if candidate.corvo_records:
            st.markdown(
                f'<span style="background:{FIRSTS_BADGE_COLORS["corvo"]};color:#fff;'
                'padding:3px 10px;border-radius:12px;font-weight:600;">'
                f"🌊 Corvo Factor · {candidate.corvo_records} records</span>",
                unsafe_allow_html=True,
            )
        score_col, status_col, count_col = st.columns(3)
        score_col.metric("Prediction score", f"{candidate.prediction_score:.0f}")
        status_col.metric("Dutch rarity", candidate.dutch_status)
        count_col.metric("Dutch records", candidate.dutch_record_count)
        st.markdown(firsts_rarity_html(candidate), unsafe_allow_html=True)
        st.metric("Momentum score", f"{candidate.momentum_score}/20")
        last_col, since_col = st.columns(2)
        since = candidate.years_since_last_dutch_record()
        last_col.metric("Last Dutch record", candidate.dutch_latest_year or "—")
        since_col.metric("Years since last record", since if since is not None else "—")
        if candidate.is_long_overdue():
            st.markdown("🚨 **Long Overdue**: no Dutch record for 10+ years, but still arriving on the Atlantic coast.")
        show_score_breakdown(candidate)
        st.markdown("**Atlantic timeline (latest record year)**")
        st.markdown(firsts_timeline_html(candidate), unsafe_allow_html=True)
        st.markdown("**Occurrence by country**")
        st.markdown(firsts_badges(candidate) or "No Atlantic records", unsafe_allow_html=True)
        st.bar_chart(
            pd.DataFrame(
                {"Records": [candidate.records(c) for c in COUNTRIES]},
                index=[COUNTRY_LABELS[c] for c in COUNTRIES],
            ),
            color=FIRSTS_TOP_COLOR,
        )
        st.markdown(f"**Rationale:** {candidate.rationale}")


def read_output(path: Path) -> dict | None:
    """Read an optional generated JSON product without masking invalid files."""
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def first_horizon(path: Path) -> dict | None:
    document = read_output(path)
    if document is None:
        return None
    horizons = document.get("horizons", [])
    if not horizons:
        raise ValueError(f"No forecast horizons in {path}.")
    return horizons[0]


def read_forecast(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame.empty:
        raise ValueError(f"Forecast contains no rows: {path}")
    return frame


def forecast_panel(title: str, path: Path, plot: Path) -> None:
    st.subheader(title)
    forecast = read_forecast(path)
    if forecast is None:
        st.info("Forecast unavailable. Run the daily forecast.")
        return
    latest = forecast.iloc[0]
    st.metric(
        "Next-day probability",
        f"{latest['probability']:.1%}",
        str(latest["risk_level"]),
        delta_color="off",
    )
    st.caption(f"First forecast date: {latest['date']:%Y-%m-%d}")
    chart = forecast.set_index("date")[["probability"]].mul(100)
    chart.columns = ["Predicted probability (%)"]
    st.line_chart(chart, y="Predicted probability (%)", width="stretch")
    if plot.is_file():
        st.image(str(plot), width="stretch")
    with st.expander("Daily predictions"):
        display = forecast.copy()
        display["date"] = display["date"].dt.strftime("%Y-%m-%d")
        display["probability"] = display["probability"].map(lambda p: f"{p:.1%}")
        st.dataframe(display, width="stretch", hide_index=True)


def show_atmospheric_index(family: str) -> None:
    if family == "Eastern":
        score_column = "eastern_drift_index"
        component_column = "eastern_components"
        title = "Eastern Drift Index"
    elif family == "Atlantic":
        score_column = "atlantic_index"
        component_column = "atlantic_components"
        title = "Atlantic Index"
    else:
        raise ValueError(f"Unknown atmospheric index family: {family}.")

    missing_paths = [
        path
        for path in (
            WEATHER_FORECAST_FILE,
            EASTERN_EVENTS_FILE,
            ATLANTIC_EVENTS_FILE,
        )
        if not path.is_file()
    ]
    if missing_paths:
        st.info(
            "Atmospheric index inputs are unavailable: "
            + ", ".join(str(path) for path in missing_paths)
            + ". Run the daily forecast and build the occurrence summaries."
        )
        return

    weather, _ = load_weather_forecast(WEATHER_FORECAST_FILE)
    eastern_events = pd.read_csv(EASTERN_EVENTS_FILE, parse_dates=["date"])
    atlantic_events = pd.read_csv(ATLANTIC_EVENTS_FILE, parse_dates=["date"])
    forecasts = calculate_atmospheric_indices(
        weather, eastern_events, atlantic_events
    )

    st.caption(
        "Exploratory 0–100 heuristic from four Dutch coastal weather stations "
        "and the preceding 10 complete years of GB, IE, NL, BE and DK event "
        "summaries. Components are equally weighted. Regional pathways, "
        "blocking, Azores arrivals and hurricane remnants are proxies, not "
        "directly observed signals."
    )
    with st.expander("How these scores are calculated"):
        st.markdown(
            "- Wind direction alignment is the positive cosine toward the "
            "target bearing (90° easterly, 270° westerly); directional "
            "transport also scales by wind speed, capped at 15 m/s.\n"
            "- Persistence and continuation use trailing and forward three-day "
            "means. Connectivity measures the share of stations aligned with "
            "the target direction, scaled by wind strength.\n"
            "- Cyclone support averages a coastal low-pressure proxy (daily "
            "maximum pressure scaled from 1020 to 980 hPa), wind speed and "
            "four-station pressure gradient (scaled to 20 hPa).\n"
            "- Historical activity scores are log-scaled monthly counts from "
            "the 10 complete years before the forecast year, relative to the "
            "busiest month. They are historical seasonality, not live arrivals.\n"
            "- Sub-signals are equally weighted within each component. The "
            "Eastern index equally weights its three components; the Atlantic "
            "index equally weights its four. Contribution = component score × "
            "component weight."
        )
    selected_date = st.selectbox(
        "Forecast date",
        [forecast["date"] for forecast in forecasts],
        format_func=lambda date: pd.Timestamp(date).strftime("%a, %d %b %Y"),
        key=f"{family.lower()}_atmospheric_index_date",
    )
    forecast = next(
        item for item in forecasts if item["date"] == pd.Timestamp(selected_date)
    )
    score = float(forecast[score_column])
    st.metric(f"{title} · {selected_date:%d %b}", f"{score:.0f}/100")
    st.progress(score / 100.0, text=f"Composite score: {score:.1f} / 100")
    trend = pd.DataFrame(
        {
            "Eastern Drift Index": [item["eastern_drift_index"] for item in forecasts],
            "Atlantic Index": [item["atlantic_index"] for item in forecasts],
        },
        index=pd.DatetimeIndex([item["date"] for item in forecasts], name="Date"),
    )
    st.line_chart(trend[[title]], y=title, width="stretch")
    components = forecast[component_column]
    if not isinstance(components, tuple):
        raise TypeError(f"{title} components have an unexpected type.")
    component_columns = st.columns(len(components))
    for column, component in zip(component_columns, components):
        if not isinstance(component, ComponentScore):
            raise TypeError(f"{title} contains an invalid component.")
        with column.container(border=True):
            st.subheader(component.name)
            st.metric("Component score", f"{component.score:.0f}/100")
            st.progress(component.score / 100.0)
            st.metric(
                "Contribution to index",
                f"{component.contribution:.1f} points",
                f"{component.weight:.0%} weight",
            )
            st.caption(component.explanation)
            signal_rows = [
                {
                    "Driver": signal.name,
                    "Score": f"{signal.score:.0f}/100",
                    "Explanation": signal.explanation,
                }
                for signal in component.signals
                if isinstance(signal, SignalScore)
            ]
            if len(signal_rows) != len(component.signals):
                raise TypeError(f"{component.name} contains an invalid signal.")
            st.dataframe(
                pd.DataFrame(signal_rows),
                width="stretch",
                hide_index=True,
            )


def show_prediction_status(model: str, confidence: str) -> None:
    if model not in MODEL_STATUS:
        raise ValueError(f"Unknown prediction model category: {model}.")
    if confidence not in MODEL_CONFIDENCE:
        raise ValueError(f"Unknown model confidence level: {confidence}.")
    icon, description = MODEL_STATUS[model]
    st.markdown(
        f'<div role="status" style="border:1px solid #d0d7de;border-radius:8px;'
        f'padding:0.65rem 0.85rem;margin:-0.35rem 0 0.75rem 0;">'
        f'<span style="font-weight:700;">{icon} {model}</span>'
        f'<span style="margin-left:1rem;font-weight:600;">'
        f'Confidence: {confidence}</span><br/>'
        f'<span style="font-size:0.9rem;">{description}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def show_rare_hotspot_sites(path: Path, sites: tuple[str, ...]) -> None:
    st.markdown("**Requested site outlook**")
    if not path.is_file():
        st.info("Site-level forecasts are unavailable. Run the daily forecast.")
        return
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {"date", "location", "forecast_probability"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            f"Hotspot forecast is missing required columns: {sorted(missing)}."
        )
    if frame.empty or frame["date"].isna().any():
        raise ValueError(f"Hotspot forecast contains no valid dates: {path}.")
    available_dates = set(frame["date"].dt.date)
    first_date = frame["date"].min().date()
    horizon_dates = {
        horizon: first_date + timedelta(days=horizon - 1)
        for horizon in FORECAST_HORIZONS
    }
    missing_dates = [
        date for date in horizon_dates.values() if date not in available_dates
    ]
    if missing_dates:
        raise ValueError(
            f"Hotspot forecast is missing requested horizon dates: {missing_dates}."
        )
    rows = []
    for site in sites:
        row: dict[str, str] = {"Site": site}
        site_rows = frame.loc[frame["location"].eq(site)]
        for horizon, label in FORECAST_HORIZONS.items():
            date = horizon_dates[horizon]
            values = site_rows.loc[
                site_rows["date"].dt.date.eq(date), "forecast_probability"
            ]
            row[f"{label} · {date:%b %d}"] = (
                f"{values.max():.1%}" if not values.empty else "Unavailable"
            )
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption(
        "Unavailable means the current forecast has no exact matching site; "
        "available cell probabilities use heuristic site suitability."
    )


def forecast_ready() -> bool:
    if read_last_run() is None:
        st.info(
            "No Open-Meteo-backed forecast run has completed. Existing output "
            "files may be synthetic examples and are not shown as live forecasts. "
            "Use the sidebar to run the forecast."
        )
        return False
    return True


def dashboard_species_leader(
    metadata: dict, family: str, forecast_date: pd.Timestamp
) -> tuple[str, float, str | None] | None:
    if family == "Atlantic":
        layers = metadata.get("atlantic_vagrancy", {}).get("species_layers", [])
        configured = {
            str(item["slug"]) for item in SPECIES_LAYERS
            if not item.get("profile", {}).get("eastern", False)
        }
        paths = species_output_paths
    else:
        layers = metadata.get("eastern_hotspots", {}).get("species_layers", [])
        configured = {str(item["slug"]) for item in EASTERN_SPECIES_LAYERS}
        paths = eastern_species_output_paths
    candidates = []
    for layer in layers:
        slug = str(layer["slug"])
        if layer["status"] != "OK" or slug not in configured:
            continue
        path = paths(slug)["location"]
        frame = _leaderboard_data(path, ("date", "forecast_probability"))
        if frame is None:
            continue
        daily = frame.groupby("date")["forecast_probability"].max()
        if forecast_date not in daily.index or pd.isna(daily.loc[forecast_date]):
            continue
        value = float(daily.loc[forecast_date])
        previous = daily.get(forecast_date - pd.Timedelta(days=1))
        trend = (
            f"{(value - float(previous)) * 100:+.1f} pp vs previous forecast day"
            if previous is not None and pd.notna(previous) else None
        )
        candidates.append((str(layer["species"]), value, trend))
    return min(candidates, key=lambda item: (-item[1], item[0])) if candidates else None


def dashboard_previous_day(
    frame: pd.DataFrame | None, date: pd.Timestamp, column: str, scale: float = 1.0,
    unit: str = "points",
) -> str | None:
    if frame is None:
        return None
    current = frame.loc[frame["date"].eq(date), column]
    previous = frame.loc[frame["date"].eq(date - pd.Timedelta(days=1)), column]
    if current.empty or previous.empty or pd.isna(current.iloc[0]) or pd.isna(previous.iloc[0]):
        return None
    return f"{(float(current.iloc[0]) - float(previous.iloc[0])) * scale:+.1f} {unit} vs previous forecast day"


def dashboard_product_horizon(
    path: Path, metadata: dict, product: str
) -> dict | None:
    product_metadata = metadata.get(product, {})
    if product_metadata.get("status") == "skipped":
        return None
    document = read_output(path)
    if document is None:
        return None
    generated_at = product_metadata.get("generated_at")
    if generated_at and document.get("generated_at") != generated_at:
        return None
    horizons = document.get("horizons", [])
    if not horizons:
        raise ValueError(f"No forecast horizons in {path}.")
    horizon = horizons[0]
    start = metadata.get("forecast_start")
    if start and horizon["date"] != start:
        return None
    return horizon


def show_dashboard() -> None:
    st.title("Dutch BirdCast")
    st.caption("A forecast briefing for birders across the Netherlands and North Sea.")
    metadata = read_last_run()
    ready = metadata is not None
    eastern = read_forecast(EASTERN_FORECAST_FILE) if ready else None
    atlantic = read_forecast(ATLANTIC_FORECAST_FILE) if ready else None
    expected = pd.Timestamp(metadata["forecast_start"]) if metadata is not None and metadata.get("forecast_start") else None
    if expected is not None:
        if eastern is not None and not eastern["date"].eq(expected).any():
            eastern = None
        if atlantic is not None and not atlantic["date"].eq(expected).any():
            atlantic = None
    rating = dashboard_product_horizon(RATING_JSON_OUTPUT, metadata, "seawatch_day_rating") if metadata is not None else None
    goose = dashboard_product_horizon(GOOSE_JSON_OUTPUT, metadata, "goose_module") if metadata is not None else None
    support = first_horizon(DECISION_SUPPORT_FILE) if ready else None
    opportunity = first_horizon(BOI_JSON) if ready else None
    if metadata is not None and metadata.get("forecast_start"):
        if support and support.get("date") != metadata["forecast_start"]:
            support = None
        if opportunity and opportunity.get("date") != metadata["forecast_start"]:
            opportunity = None
    eastern_date = (expected if expected is not None else eastern["date"].min()) if eastern is not None else None
    atlantic_date = (expected if expected is not None else atlantic["date"].min()) if atlantic is not None else None
    eastern_leader = dashboard_species_leader(metadata, "Eastern", eastern_date) if metadata is not None and eastern_date is not None else None
    atlantic_leader = dashboard_species_leader(metadata, "Atlantic", atlantic_date) if metadata is not None and atlantic_date is not None else None

    st.subheader("Flagship indicators")
    cards = st.columns(4)
    with cards[0].container(border=True):
        st.metric(
            "🌊 North Sea Vagrancy Index",
            f"{eastern.loc[eastern['date'].eq(eastern_date), 'probability'].iloc[0]:.1%}" if eastern is not None else "Unavailable",
            dashboard_previous_day(eastern, eastern_date, "probability", 100, "pp") if eastern_date is not None else None,
            delta_color="off",
            help="The existing Eastern Vagrancy Index, based on pooled eastern-vagrant records.",
        )
        st.caption(
            f"Eastern Vagrancy Index · Forecast date: {eastern_date:%Y-%m-%d} · "
            f"Risk: {eastern.loc[eastern['date'].eq(eastern_date), 'risk_level'].iloc[0]}"
            if eastern is not None else "Forecast unavailable"
        )
        st.caption(f"Leading species layer: {eastern_leader[0]}" if eastern_leader else "Leading species layer: unavailable")
        if eastern_date is not None and dashboard_previous_day(eastern, eastern_date, "probability", 100, "pp") is None:
            st.caption("Previous forecast day: unavailable")
    with cards[1].container(border=True):
        st.metric(
            "🔥 Atlantic Vagrant Watch",
            f"{atlantic_leader[1]:.3%}" if atlantic_leader else "Unavailable",
            atlantic_leader[2] if atlantic_leader else None,
            delta_color="off",
        )
        st.caption(
            f"Highest species-layer cell probability · Forecast date: {atlantic_date:%Y-%m-%d}"
            if atlantic_leader and atlantic_date is not None
            else f"Species forecast unavailable · Index date: {atlantic_date:%Y-%m-%d}"
            if atlantic_date is not None else "Species forecast unavailable"
        )
        st.caption(f"Leading species: {atlantic_leader[0]}" if atlantic_leader else "Leading species: unavailable")
        if atlantic_leader and not atlantic_leader[2]:
            st.caption("Previous forecast day: unavailable")
    with cards[2].container(border=True):
        rating_date = pd.Timestamp(rating["date"]) if rating else None
        rating_frame = read_forecast(RATING_OUTPUT) if rating else None
        if rating_frame is not None and rating_date is not None:
            current_rating = rating_frame.loc[rating_frame["date"].eq(rating_date), "score"]
            if current_rating.empty or float(current_rating.iloc[0]) != float(rating["score"]):
                rating_frame = None
        rating_trend = dashboard_previous_day(rating_frame, rating_date, "score") if rating_date is not None else None
        component_points = rating.get("component_points", {}) if rating else {}
        species_points = {name: points for name, points in component_points.items() if name in SEABIRD_SPECIES_NAMES}
        seabird_leader = max(species_points, key=species_points.get) if species_points else None
        st.metric(
            "🌊 Seawatch Day Rating",
            f"{rating['score']}/100" if rating else "Unavailable",
            rating_trend,
            delta_color="off",
        )
        st.caption(f"Forecast date: {rating['date']}" if rating else "No forecast")
        st.caption(f"Rating: {rating['rating']} · Leading species contribution: {seabird_leader or 'unavailable'}" if rating else "Leading species contribution: unavailable")
        if rating and not rating_trend:
            st.caption("Previous forecast day: unavailable")
    with cards[3].container(border=True):
        goose_targets = goose.get("target_geese", []) if goose else []
        goose_leader = max(goose_targets, key=lambda item: item["target_score"])["species"] if goose_targets else None
        goose_trend = None
        if goose:
            goose_document = read_output(GOOSE_JSON_OUTPUT)
            goose_days = pd.DataFrame([
                {"date": pd.Timestamp(item["date"]), "score": item["goose_day_rating"]["score"]}
                for item in goose_document["horizons"]
            ])
            goose_trend = dashboard_previous_day(goose_days, pd.Timestamp(goose["date"]), "score")
        st.metric(
            "🪿 Goose Forecast",
            f"{goose['goose_day_rating']['score']}/100" if goose else "Unavailable",
            goose_trend,
            delta_color="off",
        )
        st.caption(
            ("Outside the winter season · " if goose and goose.get("off_season") else "")
            + (f"Forecast date: {goose['date']}" if goose else "No forecast")
        )
        st.caption(f"Rating: {goose['goose_day_rating']['rating']} · Leading rare-goose target: {goose_leader or 'unavailable'}" if goose else "Leading rare-goose target: unavailable")
        if goose and not goose_trend:
            st.caption("Previous forecast day: unavailable")

    st.subheader("Birding outlook")
    with st.container(border=True):
        parts = []
        if eastern is not None:
            row = eastern.loc[eastern["date"].eq(eastern_date)].iloc[0]
            parts.append(
                f"The Eastern Vagrancy Index for {row['date']:%d %b %Y} is "
                f"{row['probability']:.1%} ({row['risk_level']})."
            )
        if rating:
            parts.append(
                f"Seawatching is rated {rating['rating']} for {rating['date']}; "
                f"the leading coast is {rating['best_coast']['coast']}."
            )
        if goose:
            parts.append(
                f"The goose day rating is {goose['goose_day_rating']['rating']} "
                f"for {goose['date']}."
                + (" This is outside the winter training season." if goose.get("off_season") else "")
            )
        st.write(" ".join(parts) if parts else "Forecast data is unavailable; run the daily forecast.")
        st.caption("Scores describe modelled record events, not confirmed bird abundance.")

    st.subheader("Top opportunities")
    cols = st.columns(4)
    hotspots = opportunity.get("best_hotspots", []) if opportunity else []
    targets = opportunity.get("target_species", []) if opportunity else []
    for column, label, value, note in (
        (cols[0], "⭐ Best rarity hotspot", hotspots[0] if hotspots else "Unavailable",
         "Birding Opportunity Index · may be outside the Netherlands"),
        (cols[1], "🌊 Best seawatch location",
         support["best_dutch_locations"][0]["location"]
         if support and support.get("best_dutch_locations") else "Unavailable",
         "Best Dutch site · next forecast day"),
        (cols[2], "🎯 Most promising target", targets[0] if targets else "Unavailable",
         "Birding Opportunity Index · leading module"),
    ):
        with column.container(border=True):
            st.metric(label, value)
            st.caption(note)
    changes = []
    if ready:
        for label, path in (
            ("Eastern", EASTERN_FORECAST_FILE),
            ("Atlantic", ATLANTIC_FORECAST_FILE),
            ("Seabird", SEABIRD_FORECAST_FILE),
        ):
            frame = read_forecast(path)
            if frame is not None:
                first_date = expected if expected is not None else frame["date"].min()
                if not frame["date"].eq(first_date).any():
                    continue
                start = frame.loc[frame["date"].eq(first_date), "probability"]
                later = frame.loc[frame["date"].eq(first_date + pd.Timedelta(days=6)), "probability"]
                if not start.empty and not later.empty:
                    changes.append((label, float(later.iloc[0] - start.iloc[0])))
    with cols[3].container(border=True):
        best = max(changes, key=lambda item: item[1]) if changes else None
        st.metric(
            "📈 Largest improving index",
            best[0] if best and best[1] > 0 else "None" if best else "Unavailable",
            f"{best[1] * 100:+.1f} pp" if best and best[1] > 0 else None,
            delta_color="off",
        )
        st.caption("Change from first forecast day to +7 days, not a forecast revision")
    if opportunity:
        st.caption(f"Opportunity recommendations are for {opportunity['date']}.")
    if ready:
        with st.expander("Birding Opportunity Index details"):
            show_birding_opportunity_index()


def show_rare_birds() -> None:
    st.title("🌍 Rare Birds")
    section = st.radio(
        "Explore rare birds", ["Atmospheric Indices", "Forecasts", "Hotspots"],
        horizontal=True, key="rare_section",
    )
    if section == "Forecasts":
        view = st.segmented_control(
            "Forecasts",
            [
                "🌊 Atlantic Vagrant Watch",
                "🌏 Eastern Vagrant Watch",
                "⭐ Next Dutch Firsts",
            ],
            default="🌊 Atlantic Vagrant Watch",
            key="rare_forecast_view",
        )
        if view == "🌊 Atlantic Vagrant Watch":
            st.subheader("🌊 Atlantic Vagrant Watch")
            show_prediction_status("Forecast Model", "Medium")
            st.caption(
                "North American vagrants and their short-term rarity outlook. "
                "Corvo (Azores), Ireland and UK tracking is shown separately in "
                "Next Dutch Firsts; Corvo demo records are not live forecast inputs."
            )
            st.caption(
                "See Atlantic Index for the weather and historical-record "
                "component scores behind the transport outlook."
            )
            if forecast_ready():
                forecast_panel(
                    "Atlantic Vagrancy Forecast · 1–14 days",
                    ATLANTIC_FORECAST_FILE,
                    ATLANTIC_PLOT_FILE,
                )
                st.caption(ATLANTIC_VAGRANCY_DESCRIPTION)
                species = {
                    str(item["species"]): str(item["slug"])
                    for item in SPECIES_LAYERS
                    if not item.get("profile", {}).get("eastern", False)
                }
                show_species_leaderboard("Atlantic vagrants", species)
        elif view == "🌏 Eastern Vagrant Watch":
            st.subheader("🌏 Eastern Vagrant Watch")
            show_prediction_status("Forecast Model", "Medium")
            st.caption(
                "Siberian and East Asian vagrants, with the short-term Eastern "
                "Vagrancy forecast and species ranking. Easterly drift and "
                "Scandinavian blocking proxies are detailed in Eastern Drift Index."
            )
            st.info(
                "This forecast's occurrence training set covers Great Britain, "
                "Ireland, the Netherlands, Belgium and Denmark. Finland, Sweden, "
                "Norway and Germany source observations are not currently included."
            )
            if forecast_ready():
                forecast_panel(
                    "Eastern Vagrancy Forecast · 1–14 days",
                    EASTERN_FORECAST_FILE,
                    EASTERN_PLOT_FILE,
                )
                show_eastern_target_species()
        else:
            show_next_dutch_firsts()
        return

    if section == "Atmospheric Indices":
        view = st.segmented_control(
            "Atmospheric indices",
            ["🌊 Atlantic Index", "🌏 Eastern Drift Index", "🧭 Blocking Index"],
            default="🌊 Atlantic Index",
            key="rare_atmospheric_view",
        )
        if view == "🌊 Atlantic Index":
            st.subheader("🌊 Atlantic Index")
            show_prediction_status("Forecast Model", "Experimental")
            st.caption(
                "Atlantic vagrancy event probability; this is a weather-informed "
                "bird-record forecast, not a direct airflow measurement."
            )
            if forecast_ready():
                show_atmospheric_index("Atlantic")
                with st.expander("Learned Atlantic Vagrancy event forecast"):
                    forecast_panel(
                        "Atlantic Vagrancy Forecast · 1–14 days",
                        ATLANTIC_FORECAST_FILE,
                        ATLANTIC_PLOT_FILE,
                    )
        elif view == "🌏 Eastern Drift Index":
            st.subheader("🌏 Eastern Drift Index")
            show_prediction_status("Forecast Model", "Experimental")
            st.caption(
                "Eastern-vagrant event probability; it is not a direct easterly "
                "airflow or Siberian drift measurement."
            )
            if forecast_ready():
                show_atmospheric_index("Eastern")
                with st.expander("Learned Eastern Vagrancy event forecast"):
                    forecast_panel(
                        "Eastern Vagrancy Forecast · 1–14 days",
                        EASTERN_FORECAST_FILE,
                        EASTERN_PLOT_FILE,
                    )
        else:
            st.subheader("🧭 Blocking Index")
            show_prediction_status("Forecast Model", "Experimental")
            st.info(
                "The current weather feed covers four Dutch coastal stations, "
                "not the Scandinavian pressure field needed to calculate a "
                "standalone blocking index. The Eastern Drift Index displays "
                "its explicitly labelled local easterly-persistence proxy."
            )
            st.caption(
                "A Scandinavian blocking strength, persistence forecast and "
                "independent rarity-impact score cannot be derived from the "
                "available inputs."
            )
        return

    view = st.segmented_control(
        "Hotspots",
        ["🌊 Atlantic Hotspots", "🌏 Eastern Hotspots"],
        default="🌊 Atlantic Hotspots",
        key="rare_hotspot_view",
    )
    if view == "🌊 Atlantic Hotspots":
        st.subheader("🌊 Atlantic Hotspots")
        show_prediction_status("Hotspot Prediction Model", "Low")
        st.caption(
            "Priority Dutch Atlantic sites: Texel, Maasvlakte, IJmuiden, "
            "Schiermonnikoog and Eemshaven."
        )
        if forecast_ready():
            show_rare_hotspot_sites(
                ATLANTIC_LOCATION_FORECAST_FILE,
                ("Texel", "Maasvlakte", "IJmuiden", "Schiermonnikoog", "Eemshaven"),
            )
            with st.container(border=True):
                show_atlantic_location_forecasts()
    else:
        st.subheader("🌏 Eastern Hotspots")
        show_prediction_status("Hotspot Prediction Model", "Low")
        st.caption("Priority sites: Texel and Schiermonnikoog.")
        if forecast_ready():
            show_rare_hotspot_sites(
                EASTERN_LOCATION_FORECAST_FILE, ("Texel", "Schiermonnikoog")
            )
            with st.container(border=True):
                show_eastern_hotspots()


def show_seawatching() -> None:
    st.title("🌊 Seawatching")
    if not forecast_ready():
        return
    section = st.radio(
        "Explore seawatching",
        ["Day rating", "Species & sites", "Hotspot map", "Environmental drivers"],
        horizontal=True, key="seawatch_section",
    )
    if section == "Day rating":
        with st.container(border=True):
            show_seawatch_day_rating()
        with st.expander("Seawatch recommendation"):
            show_recommendation_banner()
        with st.expander("Seabird Index forecast and daily predictions"):
            forecast_panel("Seabird Index", SEABIRD_FORECAST_FILE, SEABIRD_PLOT_FILE)
        with st.expander("Rare seabird potential"):
            show_rarity_index()
    elif section == "Species & sites":
        st.caption(
            "Browse seabird species and select the general index or a species model. "
            "Species without independent forecasts are marked unavailable."
        )
        with st.container(border=True):
            show_seabird_decision_support()
    elif section == "Hotspot map":
        with st.container(border=True):
            if SEABIRD_LOCATION_FORECAST_FILE.is_file():
                show_atlantic_location_forecasts(
                    SEABIRD_LOCATION_FORECAST_FILE, product="Seabird",
                    map_file=SEABIRD_LOCATION_MAP_FILE, color_scale=0.35,
                )
            else:
                st.info("No seabird hotspot forecast is available yet. Run the forecast.")
    else:
        st.subheader("Environmental drivers")
        document = read_output(RATING_JSON_OUTPUT)
        support = read_output(DECISION_SUPPORT_FILE)
        if document is None or support is None:
            st.info("Environmental support data is unavailable. Run the forecast.")
            return
        weather_by_date = {h["date"]: h for h in support["horizons"]}
        for horizon in document["horizons"]:
            with st.expander(f"{horizon['label']} · {horizon['date']}", expanded=horizon == document["horizons"][0]):
                matching = weather_by_date.get(horizon["date"])
                if matching:
                    st.write(f"**Wind:** {matching['wind']['text']}")
                else:
                    st.info("Wind data is unavailable for this forecast date.")
                weather = horizon.get("weather", {})
                pressure = weather.get("minimum_pressure_hpa")
                st.write(
                    f"**Minimum coastal pressure:** {pressure:.1f} hPa"
                    if pressure is not None
                    else "**Minimum coastal pressure:** unavailable"
                )
                show_score_drivers(horizon)
                st.write("**Fetch and visibility:** no dedicated forecast is available.")
                st.caption("Driver contributions are model inputs, not evidence of causation.")


def show_migration() -> None:
    st.title("🪿 Migration")
    show_prediction_status("Forecast Model", "Experimental")
    if not forecast_ready():
        return
    section = st.radio(
        "Explore migration", ["Goose forecast", "Migration pulse & influx", "Waterfowl"],
        horizontal=True, key="migration_section",
    )
    if section == "Goose forecast":
        with st.container(border=True):
            show_goose_forecast()
    elif section == "Migration pulse & influx":
        st.subheader("Migration pulse & influx monitors")
        document = read_output(GOOSE_JSON_OUTPUT)
        if document is None:
            st.info("No goose movement or influx forecast is available yet.")
            return
        st.caption("Existing goose activity and European influx indicators; these are not a general migration radar.")
        rows = []
        for item in document["horizons"]:
            conditions = item.get("conditions", {})
            rows.append({
                "Date": item["date"],
                "Horizon": item["label"],
                "Goose activity": item["goose_activity"]["score"],
                "European rare goose influx": item["european_goose_influx"]["score"],
                "Cold outbreak": "Yes" if conditions.get("cold_outbreak") else "No" if conditions else "Unavailable",
                "Rapid temperature drop": "Yes" if conditions.get("rapid_temp_drop") else "No" if conditions else "Unavailable",
                "Season": "Outside winter training season" if item.get("off_season") else "Winter",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption("Detailed site rankings, weather and species contributions are in Goose forecast.")
    else:
        st.subheader("Waterfowl movements")
        st.write("🪿 Geese: the Goose Forecast provides activity, rare species and regional rankings.")
        st.info("🦆 Ducks and 🦢 swans: independent movement forecasts are not currently available.")


@st.cache_data(show_spinner=False)
def _read_leaderboard_columns(
    path: Path, modified_ns: int, size: int, columns: tuple[str, ...]
) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=list(columns), parse_dates=["date"])
    if frame.empty or frame["date"].isna().any():
        raise ValueError(f"Forecast contains no rows or invalid dates: {path}")
    return frame


def _leaderboard_data(path: Path, columns: tuple[str, ...]) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    stat = path.stat()
    return _read_leaderboard_columns(path, stat.st_mtime_ns, stat.st_size, columns)


def species_leaderboard(group: str, species: dict[str, str]) -> pd.DataFrame:
    rows = []
    for name, slug in species.items():
        seabird = group == "Seabirds"
        paths = (
            seabird_species_output_paths(slug)
            if seabird and slug in SEABIRD_SPECIES_NAMES
            else None
            if seabird
            else eastern_species_output_paths(slug)
            if group == "Eastern vagrants"
            else species_output_paths(slug)
        )
        location_column = "probability" if seabird else "forecast_probability"
        locations = _leaderboard_data(
            paths["location"], ("date", "location", location_column)
        ) if paths is not None else None
        forecast = (
            _leaderboard_data(paths["forecast"], ("date", "probability"))
            if seabird and paths is not None else locations
        )
        row = {
            "Species": name,
            "Forecast score": None,
            "Trend": "⚪ Unavailable",
            "Best date": None,
            "Best region": "Unavailable",
        }
        if forecast is not None:
            score_column = "probability" if seabird else "forecast_probability"
            daily = forecast.groupby("date")[score_column].max().sort_index()
            if daily.isna().any():
                raise ValueError(f"Forecast contains missing scores: {paths['forecast'] if seabird else paths['location']}")
            first_date = daily.index[0]
            row["Forecast score"] = float(daily.iloc[0]) * 100
            row["Best date"] = daily.idxmax().date()
            if len(daily) > 1:
                change = float(daily.iloc[1] - daily.iloc[0]) * 100
                if abs(change) < 0.05:
                    row["Trend"] = "🟡 Stable"
                elif change > 0:
                    row["Trend"] = f"🟢 Improving ({change:+.1f} pp)"
                else:
                    row["Trend"] = f"🔴 Declining ({change:+.1f} pp)"
            if locations is not None:
                current = locations.loc[locations["date"].eq(first_date)]
                if not current.empty and current[location_column].notna().any():
                    row["Best region"] = str(
                        current.loc[current[location_column].idxmax(), "location"]
                    )
        rows.append(row)
    result = pd.DataFrame(
        rows, columns=["Species", "Forecast score", "Trend", "Best date", "Best region"]
    )
    result = result.sort_values(
        ["Forecast score", "Species"], ascending=[False, True], na_position="last"
    ).reset_index(drop=True)
    result.insert(0, "Rank", pd.array(
        [i + 1 if pd.notna(score) else None for i, score in enumerate(result["Forecast score"])],
        dtype="Int64",
    ))
    return result


def show_species_leaderboard(group: str, species: dict[str, str]) -> None:
    leaderboard = species_leaderboard(group, species)
    st.subheader("Species leaderboard")
    if group == "Seabirds":
        st.caption(
            "Score: first forecast day's national species-model probability. "
            "Best region is the highest-scoring site on that day."
        )
    else:
        st.caption(
            "Score: first forecast day's highest species-layer cell probability; "
            "best region is that cell. These are heuristic location-layer scores."
        )
    st.caption(
        "Best date is the peak across the forecast period. Trend compares the next "
        "forecast day with the first, not an earlier forecast run: 🟢 improving, "
        "🟡 stable (change under 0.05 percentage points), 🔴 declining. "
        "Select a row to open its species forecast; click column headers to sort."
    )
    key = f"species_leaderboard_{group}"
    names = leaderboard["Species"].tolist()

    def select_species() -> None:
        selected = st.session_state[key]["selection"]["rows"]
        if selected:
            target = "seabird_product_selector" if group == "Seabirds" else f"explorer_species_{group}"
            st.session_state[target] = names[selected[0]]

    st.dataframe(
        leaderboard,
        hide_index=True,
        width="stretch",
        height=300,
        key=key,
        on_select=select_species,
        selection_mode="single-row",
        column_config={
            "Forecast score": st.column_config.NumberColumn("Forecast score", format="%.2f%%"),
            "Best date": st.column_config.DateColumn("Best date", format="YYYY-MM-DD"),
        },
    )


def dutch_species_locations(
    day: pd.DataFrame, probability_column: str, family: str
) -> pd.DataFrame:
    dutch = day.loc[day["country"].eq("NL")].copy()
    if dutch.empty:
        return dutch
    if dutch[probability_column].isna().any():
        raise ValueError("Dutch species forecast contains missing probabilities.")
    dutch = dutch.sort_values(
        [probability_column, "location"], ascending=[False, True], kind="stable"
    ).drop_duplicates("location").reset_index(drop=True)
    dutch["site"] = dutch["location"].str.split(" (", n=1, regex=False).str[0]
    dutch["rank_nl"] = range(1, len(dutch) + 1)
    risk_functions = {
        "Eastern vagrants": eastern_risk_level,
        "Atlantic vagrants": atlantic_risk_level,
        "Seabirds": seabird_risk_level,
    }
    dutch["rating_nl"] = dutch[probability_column].map(risk_functions[family])
    return dutch


def dutch_species_coasts(
    dutch: pd.DataFrame, probability_column: str
) -> pd.DataFrame:
    site_scores = dutch.groupby("site")[probability_column].max()
    rows = []
    for coast, sites in DUTCH_COAST_REGIONS.items():
        names = list(sites)
        if coast == "Wadden Islands":
            names.append("Vlieland and Terschelling")
        scores = site_scores.loc[site_scores.index.isin(names)]
        rows.append({
            "Coast": coast,
            "Score": float(scores.mean()) * 100 if not scores.empty else None,
            "Sites represented": len(scores),
        })
    result = pd.DataFrame(rows).sort_values(
        ["Score", "Coast"], ascending=[False, True], na_position="last"
    ).reset_index(drop=True)
    result.insert(0, "Rank", pd.array(
        [i + 1 if pd.notna(score) else None for i, score in enumerate(result["Score"])],
        dtype="Int64",
    ))
    return result


def show_dutch_species_recommendations(
    species: str,
    day: pd.DataFrame,
    probability_column: str,
    family: str,
    date: pd.Timestamp,
    *,
    show_recommendation: bool = True,
) -> None:
    with st.container(border=True):
        st.subheader("🇳🇱 Dutch Birding Recommendations")
        st.caption(
            f"Forecast for {date:%Y-%m-%d}. Rankings are relative to the available "
            "Dutch location cells, not confirmed bird presence."
        )
        dutch = dutch_species_locations(day, probability_column, family)
        if dutch.empty:
            st.info("No Dutch location forecast is available for this species and date.")
            return

        if show_recommendation:
            recommendations = dutch.drop_duplicates("site").head(2)["site"].tolist()
            names = " and ".join(recommendations)
            st.markdown(
                f"**Today's recommendation:** For {species}, the highest-scoring available "
                f"Dutch locations for {date:%Y-%m-%d} are {names}."
            )
        st.caption(
            "Coast scores average each represented named site's best cell. "
            "Coordinate-labelled cells remain in the site table and map but are not "
            "assigned to a coast. Missing coast scores mean no named sites were forecast."
        )
        left, right = st.columns(2)
        with left:
            st.markdown("**Dutch Coast Ranking**")
            st.dataframe(
                dutch_species_coasts(dutch, probability_column),
                column_config={"Score": st.column_config.NumberColumn("Mean probability", format="%.3f%%")},
                width="stretch", hide_index=True,
            )
            st.markdown("**Best Dutch Sites**")
            site_table = pd.DataFrame({
                "Rank": dutch["rank_nl"],
                "Location": dutch["location"],
                "Score": dutch[probability_column] * 100,
                "Rating": dutch["rating_nl"],
            })
            st.dataframe(
                site_table,
                column_config={"Score": st.column_config.NumberColumn("Probability", format="%.3f%%")},
                width="stretch", hide_index=True,
            )
        with right:
            st.markdown("**Dutch Forecast Map**")
            latitude, longitude = (
                ("latitude", "longitude") if family == "Seabirds"
                else ("center_latitude", "center_longitude")
            )
            if latitude not in dutch or longitude not in dutch:
                st.info("Map coordinates are unavailable for this forecast.")
            else:
                cells = day.loc[day["country"].eq("NL")].copy()
                mapped = cells.dropna(subset=[latitude, longitude]).copy()
                missing = len(cells) - len(mapped)
                if missing:
                    st.caption(f"{missing} cells without coordinates are omitted from the map.")
                if mapped.empty:
                    st.info("Map coordinates are unavailable for this forecast.")
                else:
                    maximum = float(mapped[probability_column].max())
                    relative = mapped[probability_column] / maximum if maximum > 0 else mapped[probability_column] * 0
                    mapped["color"] = [marker_color(float(value)) for value in relative]
                    mapped["radius"] = 4000 + 10000 * relative
                    mapped["score_text"] = mapped[probability_column].map(lambda value: f"{value:.3%}")
                    highlights = dutch.loc[dutch["rank_nl"].le(3)].dropna(subset=[latitude, longitude]).copy()
                    highlights["rank_label"] = highlights["rank_nl"].astype(str)
                    st.pydeck_chart(
                        pdk.Deck(
                            layers=[
                                pdk.Layer(
                                    "ScatterplotLayer", data=mapped,
                                    get_position=[longitude, latitude], get_fill_color="color",
                                    get_radius="radius", pickable=True,
                                ),
                                pdk.Layer(
                                    "TextLayer", data=highlights,
                                    get_position=[longitude, latitude], get_text="rank_label",
                                    get_size=16, get_color=[20, 20, 20, 255],
                                ),
                            ],
                            initial_view_state=pdk.ViewState(latitude=52.6, longitude=5.0, zoom=6),
                            tooltip={"html": "<b>{location}</b><br/>Probability: {score_text}"},
                        ),
                        width="stretch", height=480,
                    )
                    st.caption("Larger, warmer markers indicate higher relative scores; labels mark the top three mapped locations.")
        st.caption(
            "Scores are existing location-layer probabilities. Ratings use the forecast "
            "family's existing risk bands; location suitability is heuristic."
        )


CORE_DUTCH_SPECIES_SITES = ("Texel", "Schiermonnikoog", "Vlieland", "Maasvlakte", "IJmuiden")


def core_dutch_species_ranking(day: pd.DataFrame, family: str) -> pd.DataFrame:
    dutch = dutch_species_locations(day, "forecast_probability", family)
    if dutch.empty:
        scores = pd.Series(dtype=float)
    else:
        scores = dutch.groupby("site")["forecast_probability"].max()
    rating = eastern_risk_level if family == "Eastern vagrants" else atlantic_risk_level
    rows = []
    for site in CORE_DUTCH_SPECIES_SITES:
        score = float(scores.loc[site]) if site in scores.index else None
        rows.append({
            "Site": site,
            "Forecast score": score * 100 if score is not None else None,
            "Rating": rating(score) if score is not None else "Unavailable",
        })
    ranking = pd.DataFrame(rows).sort_values(
        ["Forecast score", "Site"], ascending=[False, True], na_position="last"
    ).reset_index(drop=True)
    ranking.insert(0, "Rank", pd.array(
        [i + 1 if pd.notna(score) else None for i, score in enumerate(ranking["Forecast score"])],
        dtype="Int64",
    ))
    return ranking


def show_core_dutch_species_ranking(
    species: str, day: pd.DataFrame, family: str, date: pd.Timestamp
) -> None:
    st.subheader("🇳🇱 Best Dutch Locations")
    ranking = core_dutch_species_ranking(day, family)
    st.dataframe(
        ranking, hide_index=True, width="stretch",
        column_config={
            "Forecast score": st.column_config.NumberColumn("Forecast score", format="%.3f%%"),
        },
    )
    available = ranking.loc[ranking["Forecast score"].notna()]
    if available.empty:
        st.info(f"No core Dutch location forecast is available for {species} on {date:%Y-%m-%d}.")
    else:
        names = " and ".join(available["Site"].head(2))
        st.markdown(
            f"**Dutch recommendation:** For {species}, the highest-scoring available "
            f"core Dutch {'locations are' if len(available) > 1 else 'location is'} "
            f"{names} for {date:%Y-%m-%d}."
        )
    st.caption(
        "Each score is the highest forecast cell labelled for that site. "
        "Vlieland and Terschelling combined cells are not a separate Vlieland forecast; "
        "missing sites are shown as unavailable. Scores are heuristic, not confirmed sightings."
    )


def show_family_dutch_recommendations(group: str) -> None:
    st.subheader("🇳🇱 Dutch Birding Recommendations")
    st.markdown("**Top 5 Dutch Locations**")
    path = (
        EASTERN_LOCATION_FORECAST_FILE
        if group == "Eastern vagrants" else ATLANTIC_LOCATION_FORECAST_FILE
    )
    frame = read_forecast(path)
    if frame is None:
        st.info("The family-level Dutch location forecast is unavailable. Run the daily forecast.")
        return
    metadata = read_last_run()
    date = (
        pd.Timestamp(metadata["forecast_start"])
        if metadata and metadata.get("forecast_start") else frame["date"].min()
    )
    day = frame.loc[frame["date"].eq(date)]
    if day.empty:
        st.info(f"No family-level location forecast is available for {date:%Y-%m-%d}.")
        return
    ranking = core_dutch_species_ranking(day, group)
    st.dataframe(
        ranking, hide_index=True, width="stretch",
        column_config={
            "Forecast score": st.column_config.NumberColumn("Forecast score", format="%.3f%%"),
        },
    )
    available = ranking.loc[ranking["Forecast score"].notna()]
    st.markdown("**Recommendation Summary**")
    if available.empty:
        st.info(f"No core Dutch location forecast is available for {date:%Y-%m-%d}.")
    else:
        names = " and ".join(available["Site"].head(2))
        st.write(
            f"For {group}, the highest-scoring available core Dutch "
            f"{'locations are' if len(available) > 1 else 'location is'} "
            f"{names} for {date:%Y-%m-%d}."
        )
    st.caption(
        "Family-level guild forecast, before species selection. Scores are the highest "
        "explicitly labelled cell per site and use the family's risk bands; they are "
        "heuristic and not confirmed sightings. Combined Vlieland and Terschelling "
        "cells are not Vlieland-specific; missing sites are unavailable."
    )


def show_species_explorer() -> None:
    st.title("🎯 Species Explorer")
    show_prediction_status("Descriptive Analytics", "Low")
    st.caption(
        "Historical summaries are descriptive and affected by observer effort. "
        "Species forecast layers below are separate model outputs."
    )
    if not forecast_ready():
        return
    eastern = {str(item["species"]): str(item["slug"]) for item in EASTERN_SPECIES_LAYERS}
    atlantic = {str(item["species"]): str(item["slug"]) for item in SPECIES_LAYERS}
    groups = {
        "Eastern vagrants": eastern,
        "Atlantic vagrants": atlantic,
    }
    group = st.radio("Forecast family", list(groups), horizontal=True, key="species_family")
    show_family_dutch_recommendations(group)
    show_species_leaderboard(group, groups[group])

    def clear_leaderboard_selection() -> None:
        st.session_state[f"species_leaderboard_{group}"] = {"selection": {"rows": []}}

    species = st.selectbox(
        "Search species", sorted(groups[group]), key=f"explorer_species_{group}",
        on_change=clear_leaderboard_selection,
    )
    path = (
        eastern_species_output_paths(eastern[species])["location"]
        if group == "Eastern vagrants"
        else species_output_paths(atlantic[species])["location"]
    )
    frame = read_forecast(path)
    if frame is None:
        st.info(f"No location forecast is available for {species}. Run the forecast.")
        return
    dates = sorted(frame["date"].dropna().unique())
    if not dates:
        raise ValueError(f"No valid forecast dates in {path}.")
    date = st.selectbox("Forecast date", dates, format_func=lambda d: pd.Timestamp(d).strftime("%Y-%m-%d"))
    selected = frame.loc[frame["date"].eq(date)].sort_values("forecast_probability", ascending=False)
    best = selected.iloc[0]
    daily = frame.groupby("date")["forecast_probability"].max().sort_index()
    previous_dates = daily.loc[daily.index < pd.Timestamp(date)]
    change = float(best["forecast_probability"] - previous_dates.iloc[-1]) if not previous_dates.empty else None
    with st.container(border=True):
        st.subheader(species)
        cards = st.columns(4)
        cards[0].metric("Best cell probability", f"{best['forecast_probability']:.1%}")
        cards[1].metric("Change from previous forecast day", f"{change * 100:+.1f} pp" if change is not None else "Unavailable")
        cards[2].metric("Best region", str(best["location"]))
        cards[3].metric("Best forecast date", daily.idxmax().strftime("%Y-%m-%d"))
        show_core_dutch_species_ranking(species, selected, group, pd.Timestamp(date))
        st.subheader("🌍 International Hotspots")
        international = selected.loc[selected["country"].notna() & selected["country"].ne("NL")]
        if international.empty:
            st.info("No international location forecast is available for this species and date.")
        else:
            display = international[["location", "country", "forecast_probability", "anomaly_score"]].copy()
            display.insert(0, "Rank", range(1, len(display) + 1))
            display["forecast_probability"] *= 100
            display["anomaly_score"] *= 100
            st.dataframe(
                display, width="stretch", hide_index=True,
                column_config={
                    "forecast_probability": st.column_config.NumberColumn("Forecast probability", format="%.3f%%"),
                    "anomaly_score": st.column_config.NumberColumn("Anomaly", format="%+.3f pp"),
                },
            )
        st.subheader("Time-series forecast")
        st.caption(
            "Best-cell probabilities are location-model outputs, not independent "
            "national species forecasts. The highest-scoring cell can change by date."
        )
        st.line_chart(daily.mul(100).rename("Best cell probability (%)"), width="stretch")
        with st.expander("Dutch map and additional site and coast rankings"):
            show_dutch_species_recommendations(
                species, selected, "forecast_probability", group, pd.Timestamp(date),
                show_recommendation=False,
            )
        with st.expander("Top 10 locations across all countries"):
            st.dataframe(
                selected.head(10)[["location", "country", "forecast_probability", "anomaly_score"]],
                width="stretch", hide_index=True,
            )
        st.write(
            "**Forecast explanation:** the guild forecast is combined with species "
            "seasonality and historical occupancy, coastal and regional suitability. "
            "Suitability weights are heuristic, not independently validated."
        )
        st.caption(
            "The species layer does not attribute its score to individual "
            "weather drivers. The Atlantic and Eastern atmospheric-index pages "
            "show separate, explicitly labelled weather and historical-record proxies."
        )
    if species == "Yellow-browed Warbler":
        with st.expander("Yellow-browed Warbler national forecast and 10 km outlook"):
            national = read_forecast(FORECAST_FILE)
            if national is None:
                st.info("No national Yellow-browed Warbler forecast is available.")
            else:
                first = national.iloc[0]
                st.metric(
                    str(first.get("risk_category", "Forecast")),
                    f"{first['probability']:.1%}",
                    help=f"National forecast for {first['date']:%Y-%m-%d}.",
                )
            show_location_forecasts()


def show_methods() -> None:
    st.title("🧪 Methods")
    with st.container(border=True):
        st.subheader("🧪 About the Models")
        st.write(
            "Forecasts estimate events in reported GBIF records, not abundance. "
            "Eastern and Atlantic guild models and seabird models use weather and "
            "seasonal features. Location layers combine forecasts with historical "
            "occurrence and heuristic suitability; they are not independently validated."
        )
        st.warning(
            "Open-Meteo grid forecasts are a source-mismatched proxy for the KNMI "
            "station observations used in training. Daily next-day probabilities "
            "are not separately calibrated; observer effort affects records."
        )
        st.write("Atlantic Vagrant Watch uses illustrative demo records, not verified live observations.")
    with st.container(border=True):
        st.subheader("📊 Model Performance")
        evaluation_files = {
            "Eastern Vagrancy": "eastern_vagrancy_evaluation.csv",
            "Atlantic Vagrancy": "atlantic_vagrancy_evaluation.csv",
            "Seabird": "seabird_evaluation.csv",
            "Seabird species": "seabird_species_evaluation.csv",
            "Goose": "goose_model_evaluation.csv",
        }
        name = st.selectbox("Evaluation", list(evaluation_files), key="methods_evaluation")
        path = ROOT / "outputs" / evaluation_files[name]
        if path.is_file():
            st.dataframe(pd.read_csv(path), width="stretch", hide_index=True)
        else:
            st.info(f"No {name} evaluation is available.")
    with st.container(border=True):
        st.subheader("🌦 Atmospheric Predictors")
        st.write(
            "The shared weather inputs include coastal wind direction and speed, "
            "gusts, temperature, precipitation and pressure, with derived and lagged "
            "features. The seawatch rating shows its available weather drivers."
        )
        st.subheader("🗂 Training Data")
        st.write(
            "Models use dated bird-record counts and KNMI coastal station observations; "
            "training windows, targets and evaluation vary by product. Goose models "
            "are trained on winter days. Historical reporting is not detection-corrected."
        )
        st.subheader("📚 Data Sources")
        st.write(
            "GBIF provides occurrence records, KNMI provides historical station "
            "weather and Open-Meteo provides forecast weather. eBird and "
            "Waarneming.nl are planned sources for the demo Atlantic watchlist; "
            "ERA5 is not an operational source for these displayed forecasts."
        )
        for name, status, purpose in PLANNED_SOURCES:
            st.markdown(f"- `{status}` **{name}**: {purpose}")
    if REPORT_FILE.is_file() and read_last_run() is not None:
        with st.expander("Daily Yellow-browed Warbler report"):
            st.markdown(REPORT_FILE.read_text(encoding="utf-8"))


def main() -> None:
    st.set_page_config(
        page_title="Dutch BirdCast",
        page_icon="🦆",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.sidebar.title("🦆 Dutch BirdCast")
    pages = {
        "🏠 Dashboard": show_dashboard,
        "🌍 Rare Birds": show_rare_birds,
        "🌊 Seawatching": show_seawatching,
        "🪿 Migration": show_migration,
        "🎯 Species Explorer": show_species_explorer,
        "🧪 Methods": show_methods,
    }
    selected = st.sidebar.radio("Navigation", list(pages))
    st.sidebar.divider()
    if st.sidebar.button("Download forecasts and run prediction", type="primary"):
        with st.spinner("Downloading weather and GBIF location data, then generating forecasts..."):
            run_daily_forecast()
        st.sidebar.success("Forecasts, charts and daily report generated.")
    metadata = read_last_run()
    if metadata:
        st.sidebar.caption(
            f"Last run: {metadata['generated_at']} · Source: {metadata['weather_source']}"
        )
        reference_forecast = read_forecast(EASTERN_FORECAST_FILE)
        if reference_forecast is not None:
            first_date = reference_forecast["date"].min().date()
            today = pd.Timestamp.now(tz="Europe/Amsterdam").date()
            if first_date < today:
                st.sidebar.warning(
                    f"The first forecast date is {first_date}; these outputs may be stale. "
                    "Run the daily forecast to refresh them."
                )
    else:
        st.sidebar.info("No operational forecast run recorded.")
    pages[selected]()



if __name__ == "__main__":
    main()
