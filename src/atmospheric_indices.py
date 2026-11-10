"""Transparent heuristic transport indices from coastal weather and history."""

from __future__ import annotations

from dataclasses import dataclass
from math import log1p

import numpy as np
import pandas as pd


STATIONS = (225, 235, 242, 310)
WIND_SPEED_SCALE_MS = 15.0
PRESSURE_GRADIENT_SCALE_HPA = 20.0
HISTORY_YEARS = 10
WEATHER_COLUMNS = {
    "date",
    *(f"{name}_{station}" for station in STATIONS for name in ("DDVEC", "FG", "PX")),
}


@dataclass(frozen=True)
class SignalScore:
    name: str
    score: float
    explanation: str


@dataclass(frozen=True)
class ComponentScore:
    name: str
    score: float
    weight: float
    contribution: float
    explanation: str
    signals: tuple[SignalScore, ...]


@dataclass(frozen=True)
class IndexForecast:
    date: pd.Timestamp
    score: float
    components: tuple[ComponentScore, ...]


def _bounded_score(value: float) -> float:
    if not np.isfinite(value):
        raise ValueError(f"Atmospheric score input must be finite: {value}.")
    return float(np.clip(value, 0.0, 100.0))


def _directional_alignment(direction: pd.Series, target_degrees: float) -> pd.Series:
    radians = np.deg2rad(direction)
    alignment = np.cos(radians - np.deg2rad(target_degrees)).clip(lower=0.0)
    return alignment.where(direction.ne(0), 0.0)


def _historical_monthly_scores(
    events: pd.DataFrame,
    forecast_year: int,
    value_column: str,
) -> dict[int, float]:
    required = {"date", value_column}
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(
            f"Occurrence history is missing required columns: {sorted(missing)}."
        )
    history = events.loc[:, ["date", value_column]].copy()
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    if history["date"].isna().any():
        raise ValueError("Occurrence history contains invalid dates.")
    history[value_column] = pd.to_numeric(history[value_column], errors="raise")
    if history[value_column].isna().any() or history[value_column].lt(0).any():
        raise ValueError("Occurrence history values must be non-negative.")
    history = history.loc[
        history["date"].dt.year.between(
            forecast_year - HISTORY_YEARS, forecast_year - 1
        )
    ]
    if history.empty:
        raise ValueError(
            f"No occurrence history for the {HISTORY_YEARS} complete years "
            f"before {forecast_year}."
        )
    monthly = history.assign(month=history["date"].dt.month).groupby("month")[
        value_column
    ].sum()
    monthly = monthly.reindex(range(1, 13), fill_value=0.0)
    maximum = float(monthly.max())
    if maximum == 0:
        return {month: 0.0 for month in range(1, 13)}
    log_maximum = log1p(maximum)
    return {
        int(month): _bounded_score(100.0 * log1p(float(value)) / log_maximum)
        for month, value in monthly.items()
    }


def _component(
    name: str,
    weight: float,
    signals: tuple[SignalScore, ...],
    explanation: str,
) -> ComponentScore:
    if not signals:
        raise ValueError(f"Component {name} must include at least one signal.")
    score = _bounded_score(float(np.mean([signal.score for signal in signals])))
    return ComponentScore(
        name=name,
        score=score,
        weight=weight,
        contribution=score * weight,
        explanation=explanation,
        signals=signals,
    )


def _validate_weather(weather: pd.DataFrame) -> pd.DataFrame:
    missing = WEATHER_COLUMNS.difference(weather.columns)
    if missing:
        raise ValueError(
            f"Weather forecast is missing required columns: {sorted(missing)}."
        )
    frame = weather.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame.empty or frame["date"].isna().any():
        raise ValueError("Weather forecast must contain valid dates.")
    if frame["date"].duplicated().any():
        raise ValueError("Weather forecast dates must be unique.")
    frame = frame.sort_values("date").reset_index(drop=True)
    for column in WEATHER_COLUMNS - {"date"}:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if frame[column].isna().any():
            raise ValueError(f"Weather forecast contains missing values: {column}.")
    for station in STATIONS:
        speed = frame[f"FG_{station}"]
        direction = frame[f"DDVEC_{station}"]
        pressure = frame[f"PX_{station}"]
        if speed.lt(0).any():
            raise ValueError("Forecast wind speed cannot be negative.")
        if direction.lt(0).any() or direction.gt(360).any():
            raise ValueError("Forecast wind direction must be between 0 and 360.")
        if pressure.le(0).any():
            raise ValueError("Forecast pressure must be positive.")
    return frame


def _prepare_weather_signals(
    weather: pd.DataFrame,
) -> pd.DataFrame:
    frame = _validate_weather(weather)
    signals = pd.DataFrame({"date": frame["date"]})
    for label, direction in (("east", 90.0), ("west", 270.0)):
        alignment_columns = []
        speed_columns = []
        flux_columns = []
        for station in STATIONS:
            alignment_column = f"{label}_alignment_{station}"
            speed_column = f"speed_score_{station}"
            flux_column = f"{label}_flux_{station}"
            alignment = _directional_alignment(
                frame[f"DDVEC_{station}"], direction
            )
            speed = (frame[f"FG_{station}"] / 10.0).clip(
                lower=0.0, upper=WIND_SPEED_SCALE_MS
            ) / WIND_SPEED_SCALE_MS
            signals[alignment_column] = alignment * 100.0
            signals[speed_column] = speed * 100.0
            signals[flux_column] = alignment * speed * 100.0
            alignment_columns.append(alignment_column)
            speed_columns.append(speed_column)
            flux_columns.append(flux_column)
        signals[f"{label}_direction"] = signals[alignment_columns].mean(axis=1)
        signals[f"{label}_speed"] = signals[speed_columns].mean(axis=1)
        signals[f"{label}_flow"] = signals[flux_columns].mean(axis=1)
        supported_stations = (
            signals[alignment_columns].ge(50.0).sum(axis=1) / len(STATIONS)
        )
        signals[f"{label}_connectivity"] = (
            supported_stations * signals[f"{label}_speed"]
        )
        signals[f"{label}_persistence"] = (
            signals[f"{label}_flow"].rolling(3, min_periods=1).mean()
        )
        signals[f"{label}_continuation"] = (
            signals[f"{label}_flow"]
            .iloc[::-1]
            .rolling(3, min_periods=1)
            .mean()
            .iloc[::-1]
            .to_numpy()
        )

    pressure_columns = [f"PX_{station}" for station in STATIONS]
    pressure_hpa = frame[pressure_columns] / 10.0
    signals["pressure_hpa"] = pressure_hpa.mean(axis=1)
    signals["pressure_min_hpa"] = pressure_hpa.min(axis=1)
    signals["pressure_gradient_hpa"] = pressure_hpa.max(axis=1) - pressure_hpa.min(axis=1)
    signals["low_pressure_proxy"] = (
        (1020.0 - signals["pressure_min_hpa"]).clip(0.0, 40.0) / 40.0 * 100.0
    )
    signals["wind_speed"] = frame[
        [f"FG_{station}" for station in STATIONS]
    ].mean(axis=1) / 10.0
    signals["wind_speed_score"] = (
        signals["wind_speed"].clip(0.0, WIND_SPEED_SCALE_MS)
        / WIND_SPEED_SCALE_MS
        * 100.0
    )
    signals["pressure_gradient_score"] = (
        signals["pressure_gradient_hpa"].clip(
            0.0, PRESSURE_GRADIENT_SCALE_HPA
        )
        / PRESSURE_GRADIENT_SCALE_HPA
        * 100.0
    )
    signals["cyclone_proxy"] = signals[
        ["low_pressure_proxy", "wind_speed_score", "pressure_gradient_score"]
    ].mean(axis=1)
    return signals


def _build_components(
    row: pd.Series,
    eastern_monthly_events: dict[int, float],
    eastern_monthly_species: dict[int, float],
    atlantic_monthly_events: dict[int, float],
) -> tuple[tuple[ComponentScore, ...], tuple[ComponentScore, ...]]:
    month = int(pd.Timestamp(row["date"]).month)

    eastern_airflow = _component(
        "Easterly Airflow",
        1.0 / 3.0,
        (
            SignalScore("Wind direction", float(row["east_direction"]), "Alignment with winds from the east across four coastal stations."),
            SignalScore("Wind speed", float(row["east_speed"]), "Mean forecast wind speed, scaled to 15 m/s."),
            SignalScore("Persistence", float(row["east_persistence"]), "Trailing up-to-three-day easterly transport proxy."),
            SignalScore("Transport connectivity", float(row["east_connectivity"]), "Cross-station directional agreement multiplied by wind strength."),
        ),
        "Local coastal easterly transport proxy; it does not measure Siberian winds.",
    )
    eastern_drift = _component(
        "Siberian Drift Potential",
        1.0 / 3.0,
        (
            SignalScore("Scandinavian blocking proxy", float(row["east_persistence"]), "Persistent local easterlies are used as a circulation proxy; no Scandinavian pressure field is available."),
            SignalScore("Siberian drift pathway", float(row["east_flow"]), "Easterly direction and wind speed at the Dutch coastal stations."),
            SignalScore("Seasonal timing", eastern_monthly_events[month], "Log-scaled historical Eastern vagrant event counts for this month."),
            SignalScore("Atmospheric transport corridor", float(row["east_connectivity"]), "Agreement in easterly flow across the four coastal stations."),
        ),
        "Heuristic drift potential from local flow and historical seasonality, not a Siberian trajectory model.",
    )
    eastern_influx = _component(
        "Continental Influx Risk",
        1.0 / 3.0,
        (
            SignalScore("Migrant pressure proxy", eastern_monthly_events[month], "Historical Eastern vagrant event activity for this month; not a current arrival count."),
            SignalScore("Scandinavian arrival reports proxy", eastern_monthly_species[month], "Historical species counts in GB, IE, NL, BE and DK; Scandinavian reports are not in the source data."),
            SignalScore("Migration density indicators", eastern_monthly_species[month], "Log-scaled historical monthly species counts from the covered countries."),
            SignalScore("Forecast continuation", float(row["east_continuation"]), "Forward up-to-three-day easterly transport in the weather forecast."),
        ),
        "Historical regional activity and short-range transport proxy; not live Scandinavian migration density.",
    )

    westerly_transport = _component(
        "Westerly Transport",
        0.25,
        (
            SignalScore("Wind direction", float(row["west_direction"]), "Alignment with winds from the west across four coastal stations."),
            SignalScore("Wind speed", float(row["west_speed"]), "Mean forecast wind speed, scaled to 15 m/s."),
            SignalScore("Persistence", float(row["west_persistence"]), "Trailing up-to-three-day westerly transport proxy."),
            SignalScore("Transport connectivity", float(row["west_connectivity"]), "Cross-station directional agreement multiplied by wind strength."),
        ),
        "Local coastal westerly transport proxy; no wider Atlantic wind field is available.",
    )
    cyclone_support = _component(
        "Cyclone Support",
        0.25,
        (
            SignalScore("Low-pressure proxy", float(row["low_pressure_proxy"]), "Lowest of the four stations' daily maximum pressures, scaled from 1020 to 980 hPa."),
            SignalScore("Wind support", float(row["wind_speed_score"]), "Mean coastal wind speed, scaled to 15 m/s."),
            SignalScore("Pressure gradient", float(row["pressure_gradient_score"]), "Difference between station daily maximum pressures, scaled to 20 hPa."),
        ),
        "Coastal pressure and wind proxies; not a cyclone track or intensity analysis.",
    )
    hurricane_remnant = _component(
        "Hurricane Remnant Influence",
        0.25,
        (
            SignalScore("Atlantic seasonal activity proxy", atlantic_monthly_events[month], "Historical Atlantic-vagrant event activity for this month."),
            SignalScore("Cyclone environment proxy", float(row["cyclone_proxy"]), "Coastal pressure, wind and pressure-gradient proxy; no tropical cyclone tracks are available."),
            SignalScore("Westerly pathway", float(row["west_flow"]), "Current westerly direction and wind-speed support."),
        ),
        "Broad seasonal/cyclone proxy only; the inputs cannot identify hurricane remnants.",
    )
    azores_arrival = _component(
        "Azores Arrival Signal",
        0.25,
        (
            SignalScore("Historical Atlantic arrival seasonality", atlantic_monthly_events[month], "Historical Atlantic-guild event counts in GB, IE, NL, BE and DK for this month; no Azores records are included."),
            SignalScore("Westerly transport connection", float(row["west_connectivity"]), "Cross-station westerly agreement and wind strength."),
            SignalScore("Forecast persistence", float(row["west_continuation"]), "Forward up-to-three-day westerly transport in the weather forecast."),
        ),
        "Seasonality and local westerly proxy; not a live Azores arrival report feed.",
    )
    return (
        (eastern_airflow, eastern_drift, eastern_influx),
        (westerly_transport, cyclone_support, hurricane_remnant, azores_arrival),
    )


def calculate_atmospheric_indices(
    weather: pd.DataFrame,
    eastern_events: pd.DataFrame,
    atlantic_events: pd.DataFrame,
) -> list[dict[str, object]]:
    """Calculate equal-component-weight heuristic indices for each forecast day."""
    signals = _prepare_weather_signals(weather)
    forecast_year = int(signals["date"].min().year)
    eastern_monthly_events = _historical_monthly_scores(
        eastern_events, forecast_year, "count"
    )
    eastern_monthly_species = _historical_monthly_scores(
        eastern_events, forecast_year, "species_count"
    )
    atlantic_monthly_events = _historical_monthly_scores(
        atlantic_events, forecast_year, "count"
    )
    results: list[dict[str, object]] = []
    for row in signals.to_dict(orient="records"):
        day = pd.Series(row)
        eastern_components, atlantic_components = _build_components(
            day,
            eastern_monthly_events,
            eastern_monthly_species,
            atlantic_monthly_events,
        )
        eastern_score = _bounded_score(
            sum(component.contribution for component in eastern_components)
        )
        atlantic_score = _bounded_score(
            sum(component.contribution for component in atlantic_components)
        )
        results.append(
            {
                "date": pd.Timestamp(row["date"]),
                "eastern_drift_index": eastern_score,
                "eastern_components": eastern_components,
                "atlantic_index": atlantic_score,
                "atlantic_components": atlantic_components,
            }
        )
    return results
