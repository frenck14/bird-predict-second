"""Combine seabird probabilities and forecast weather into a daily 0-100 rating."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

if __package__:
    from .forecast_atlantic_locations import HORIZONS
    from .seabird_decision_support import (
        DUTCH_COASTS,
        _base_name,
        confidence_label,
        recommended_coast,
    )
    from .forecast_seabird_locations import _build_seabird_features
    from .forecast_seabird_species import species_output_paths
    from .seabird_guidance import coast_scores, dutch_site_scores, explain_rating
else:
    from forecast_atlantic_locations import HORIZONS
    from seabird_decision_support import (
        DUTCH_COASTS,
        _base_name,
        confidence_label,
        recommended_coast,
    )
    from forecast_seabird_locations import _build_seabird_features
    from forecast_seabird_species import species_output_paths
    from seabird_guidance import coast_scores, dutch_site_scores, explain_rating


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = ROOT / "outputs"
RATING_OUTPUT = OUTPUT_DIRECTORY / "seawatch_day_rating.csv"
HOTSPOTS_OUTPUT = OUTPUT_DIRECTORY / "seawatch_day_hotspots.csv"
RATING_JSON_OUTPUT = OUTPUT_DIRECTORY / "seawatch_day_rating.json"
GENERAL_FORECAST_FILE = OUTPUT_DIRECTORY / "seabird_forecast.csv"
GENERAL_LOCATION_FILE = OUTPUT_DIRECTORY / "seabird_location_forecast_detail.csv"
WEATHER_FORECAST_FILE = ROOT / "inputs/open_meteo_forecast_current.csv"
RATING_WEIGHTS = {
    "General Seabird Index": 0.40,
    "European Storm-petrel": 0.30,
    "Manx Shearwater": 0.20,
    "Sooty Shearwater": 0.10,
}
WEATHER_BONUSES = {
    "strong_westerly_wind": 10,
    "deep_atlantic_low": 10,
    "increasing_wind": 5,
    "peak_seawatching_season": 5,
}
WIND_THRESHOLD_KT = 20.0
WIND_THRESHOLD_MS = WIND_THRESHOLD_KT * 0.514444
DEEP_LOW_PRESSURE_HPA = 1000.0
RATING_BANDS = (
    (25, "Poor"),
    (50, "Fair"),
    (70, "Good"),
    (85, "Excellent"),
    (101, "Major Seawatch Day"),
)
HORIZON_BY_OFFSET = {days - 1: label for days, label in HORIZONS.items()}
SPECIES_FORECASTS = {
    "European Storm-petrel": OUTPUT_DIRECTORY / "storm_petrel_forecast.csv",
    "Manx Shearwater": OUTPUT_DIRECTORY / "manx_shearwater_forecast.csv",
    "Sooty Shearwater": OUTPUT_DIRECTORY / "sooty_shearwater_forecast.csv",
}
SPECIES_LOCATIONS = {
    species: species_output_paths(species)["detail"]
    for species in SPECIES_FORECASTS
}


class WeatherBonus(TypedDict):
    name: str
    points: int


def rating_category(score: int | float) -> str:
    if not math.isfinite(float(score)) or not 0 <= score <= 100:
        raise ValueError("Seawatch rating score must be finite and between 0 and 100.")
    for upper, label in RATING_BANDS:
        if score < upper:
            return label
    return "Major Seawatch Day"


def _validate_forecast(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    if not {"date", "probability"}.issubset(frame.columns):
        raise ValueError(f"{name} forecast must contain date and probability.")
    result = frame.loc[:, ["date", "probability"]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise").dt.normalize()
    result["probability"] = pd.to_numeric(result["probability"], errors="raise")
    if (
        result.empty
        or result["date"].isna().any()
        or result["date"].duplicated().any()
        or result["probability"].isna().any()
        or not result["probability"].between(0, 1).all()
    ):
        raise ValueError(
            f"{name} forecast must have unique dates and finite probabilities in [0, 1]."
        )
    return result


def _direction_degrees(row: pd.Series) -> float:
    return math.degrees(
        math.atan2(float(row["coast_wind_sin"]), float(row["coast_wind_cos"]))
    ) % 360


def _weather_conditions(
    weather: pd.DataFrame | None, target_date: pd.Timestamp
) -> tuple[dict[str, bool], dict[str, object]]:
    empty_flags = {
        "strong_westerly_wind": False,
        "deep_atlantic_low": False,
        "increasing_wind": False,
        "peak_seawatching_season": target_date.month in (10, 11),
    }
    empty_details: dict[str, object] = {
        "wind_speed_ms": None,
        "wind_speed_kt": None,
        "wind_direction_degrees": None,
        "wind_direction": "unknown",
        "minimum_pressure_hpa": None,
        "wind_change_ms": None,
    }
    if weather is None or weather.empty or "date" not in weather:
        return empty_flags, empty_details
    engineered = _build_seabird_features(weather)
    engineered = engineered.assign(
        date=pd.to_datetime(engineered["date"]).dt.normalize()
    ).sort_values("date")
    weather_date = target_date - pd.Timedelta(days=1)
    selected = engineered.loc[engineered["date"].eq(weather_date)]
    if selected.empty:
        return empty_flags, empty_details
    row = selected.iloc[0]
    speed = float(row["coast_wind_speed"])
    direction = _direction_degrees(row)
    pressure = float(row["coast_PX_min"]) / 10.0
    previous = engineered.loc[
        engineered["date"].eq(weather_date - pd.Timedelta(days=1))
    ]
    wind_change: float | None = None
    if not previous.empty:
        prior_speed = float(previous.iloc[0]["coast_wind_speed"])
        if math.isfinite(speed) and math.isfinite(prior_speed):
            wind_change = speed - prior_speed

    # KNMI DDVEC describes the direction the wind comes from. W through WNW
    # therefore spans 247.5 degrees inclusive to 292.5 degrees inclusive.
    west_wnw = 247.5 <= direction <= 292.5
    flags = {
        "strong_westerly_wind": (
            math.isfinite(speed) and speed >= WIND_THRESHOLD_MS and west_wnw
        ),
        "deep_atlantic_low": math.isfinite(pressure) and pressure <= DEEP_LOW_PRESSURE_HPA,
        "increasing_wind": wind_change is not None and wind_change > 0,
        "peak_seawatching_season": target_date.month in (10, 11),
    }
    direction_label = "unknown"
    if math.isfinite(direction):
        compass = (
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
        )
        direction_label = compass[int((direction + 11.25) // 22.5) % 16]
    details = {
        "wind_speed_ms": speed if math.isfinite(speed) else None,
        "wind_speed_kt": speed / 0.514444 if math.isfinite(speed) else None,
        "wind_direction_degrees": direction if math.isfinite(direction) else None,
        "wind_direction": direction_label,
        "minimum_pressure_hpa": pressure if math.isfinite(pressure) else None,
        "wind_change_ms": wind_change,
    }
    return flags, details


def _probability_maps(
    general_forecast: pd.DataFrame,
    species_forecasts: dict[str, pd.DataFrame],
    *,
    allow_partial_horizon: bool = False,
) -> dict[pd.Timestamp, dict[str, float]]:
    # Keep the public weight order stable; it is also the output component order.
    frames = {
        "General Seabird Index": _validate_forecast(
            general_forecast, "General Seabird Index"
        ),
        **{
            species: _validate_forecast(species_forecasts[species], species)
            for species in RATING_WEIGHTS
            if species != "General Seabird Index"
        },
    }
    base_dates = set(frames["General Seabird Index"]["date"])
    for name, frame in frames.items():
        if set(frame["date"]) != base_dates:
            raise ValueError(f"{name} dates do not match the general index dates.")
    ordered_dates = pd.DatetimeIndex(sorted(base_dates))
    expected_dates = pd.date_range(
        ordered_dates[0], periods=len(ordered_dates), freq="D"
    )
    valid_length = (
        1 <= len(ordered_dates) <= 14
        if allow_partial_horizon
        else len(ordered_dates) == 14
    )
    if not valid_length or not ordered_dates.equals(expected_dates):
        raise ValueError(
            "Rating forecasts require 14 consecutive dates."
            if not allow_partial_horizon
            else "Strict cutoff validation requires 1 to 14 consecutive forecast dates."
        )
    result: dict[pd.Timestamp, dict[str, float]] = {}
    for target in sorted(base_dates):
        result[pd.Timestamp(target)] = {
            name: float(frame.loc[frame["date"].eq(target), "probability"].iloc[0])
            for name, frame in frames.items()
        }
    return result


def calculate_rating(
    probabilities: dict[str, float],
    weather_flags: dict[str, bool] | None = None,
) -> dict[str, object]:
    """Apply the requested index weights, bonuses and category cutoffs."""
    if set(probabilities) != set(RATING_WEIGHTS):
        raise ValueError(
            f"Rating probabilities must include exactly {list(RATING_WEIGHTS)}."
        )
    if any(not math.isfinite(float(p)) or not 0 <= float(p) <= 1 for p in probabilities.values()):
        raise ValueError("All input probabilities must be finite and between 0 and 1.")
    contributions = {
        name: float(probabilities[name]) * weight * 100.0
        for name, weight in RATING_WEIGHTS.items()
    }
    flags = weather_flags or {}
    bonuses = {
        key: points if flags.get(key, False) else 0
        for key, points in WEATHER_BONUSES.items()
    }
    base_score = sum(contributions.values())
    applied_bonus = sum(bonuses.values())
    score = min(100, int(round(base_score + applied_bonus)))
    return {
        "score": score,
        "rating": rating_category(score),
        "base_score": base_score,
        "weather_bonus": applied_bonus,
        "component_points": contributions,
        "weather_bonuses": bonuses,
        "drivers": [
            {"name": name, "points": points}
            for name, points in contributions.items()
        ]
        + [
            {"name": name, "points": points}
            for name, points in bonuses.items()
            if points
        ],
    }


def _nearest_species_probabilities(
    general_day: pd.DataFrame,
    species_days: dict[str, pd.DataFrame],
) -> dict[str, np.ndarray]:
    """Map species grids onto general-index cells using nearest same-country cell."""
    result: dict[str, np.ndarray] = {}
    for species, frame in species_days.items():
        required = {
            "country",
            "grid_easting",
            "grid_northing",
            "forecast_probability",
        }
        if not required.issubset(frame.columns):
            raise ValueError(f"{species} location forecast is missing grid columns.")
        probabilities = np.zeros(len(general_day), dtype=float)
        for country in general_day["country"].unique():
            target_indices = np.flatnonzero(general_day["country"].eq(country).to_numpy())
            source = frame.loc[
                frame["country"].eq(country)
                & frame["forecast_probability"].notna()
            ]
            if source.empty:
                raise ValueError(
                    f"{species} has no location cells in country {country}."
                )
            tree = cKDTree(source[["grid_easting", "grid_northing"]].to_numpy())
            _, nearest = tree.query(
                general_day.iloc[target_indices][
                    ["grid_easting", "grid_northing"]
                ].to_numpy()
            )
            probabilities[target_indices] = source.iloc[nearest][
                "forecast_probability"
            ].to_numpy(dtype=float)
        result[species] = probabilities
    return result


def _top_dutch_sites(day: pd.DataFrame, limit: int = 3) -> list[dict[str, object]]:
    dutch = day.loc[day["country"].eq("NL")].sort_values(
        ["base_score", "location"], ascending=[False, True]
    )
    selected: list[dict[str, object]] = []
    names: set[str] = set()
    for row in dutch.itertuples(index=False):
        name = _base_name(str(row.location))
        if name in names:
            continue
        names.add(name)
        selected.append(
            {
                "location": str(row.location),
                "score": int(row.score),
                "rating": str(row.rating),
                "probability": float(row.forecast_probability),
            }
        )
        if len(selected) == limit:
            break
    return selected


def _horizon_payload(
    target_date: pd.Timestamp,
    label: str,
    frame: pd.DataFrame,
    rating: dict[str, object],
    confidence: str,
    best_coast: dict[str, object],
    top_dutch: list[dict[str, object]],
    wind_details: dict[str, object],
    input_probabilities: dict[str, float],
) -> dict[str, object]:
    return {
        "date": str(target_date.date()),
        "label": label,
        "score": rating["score"],
        "rating": rating["rating"],
        "confidence": confidence,
        "best_coast": best_coast,
        "top3_dutch_sites": top_dutch,
        "drivers": rating["drivers"],
        "component_points": rating["component_points"],
        "weather_bonuses": rating["weather_bonuses"],
        "input_probabilities": input_probabilities,
        "weather": wind_details,
        "top10_hotspots": [
            {
                "rank": int(row.rank),
                "location": str(row.location),
                "country": str(row.country),
                "score": int(row.score),
                "rating": str(row.rating),
                "latitude": float(row.latitude),
                "longitude": float(row.longitude),
            }
            for row in frame.head(10).itertuples(index=False)
        ],
    }


def build_rating_products(
    general_forecast: pd.DataFrame,
    species_forecasts: dict[str, pd.DataFrame],
    general_locations: pd.DataFrame,
    species_locations: dict[str, pd.DataFrame],
    weather: pd.DataFrame | None = None,
    generated_at: datetime | None = None,
    analysis_date: date | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Build all-date ratings, four horizon hotspot lists and dashboard JSON."""
    probabilities_by_date = _probability_maps(
        general_forecast,
        species_forecasts,
        allow_partial_horizon=analysis_date is not None,
    )
    if set(species_locations) != set(RATING_WEIGHTS) - {"General Seabird Index"}:
        raise ValueError("Species location forecasts must match the rating species.")
    locations = general_locations.copy()
    required_location_columns = {
        "date",
        "country",
        "location",
        "grid_easting",
        "grid_northing",
        "center_latitude",
        "center_longitude",
    }
    if not required_location_columns.issubset(locations.columns):
        raise ValueError("General location forecast is missing required grid columns.")
    locations["date"] = pd.to_datetime(locations["date"]).dt.normalize()
    for name in ["forecast_probability"]:
        if name not in locations:
            raise ValueError(f"General location forecast is missing {name}.")
    for species, frame in species_locations.items():
        frame = frame.copy()
        if "date" not in frame:
            raise ValueError(f"{species} location forecast must contain date.")
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        if set(frame["date"]) != set(probabilities_by_date):
            raise ValueError(f"{species} location dates do not match forecast dates.")
        species_locations[species] = frame

    engineered_weather = (
        _build_seabird_features(weather) if weather is not None else None
    )
    rating_frames: list[pd.DataFrame] = []
    hotspot_frames: list[pd.DataFrame] = []
    horizon_details: list[dict[str, object]] = []
    origin = min(probabilities_by_date)
    if analysis_date is not None and origin.date() != (
        analysis_date + timedelta(days=1)
    ):
        raise ValueError(
            "Seawatch rating must begin the day after analysis_date."
        )
    date_to_offset = {
        target: (target - origin).days for target in probabilities_by_date
    }
    for target, probabilities in probabilities_by_date.items():
        general_day = locations.loc[locations["date"].eq(target)].copy()
        if general_day.empty:
            raise ValueError(f"General location forecast is missing {target.date()}.")
        species_by_name: dict[str, pd.DataFrame] = {}
        for species, all_days in species_locations.items():
            day = all_days.loc[all_days["date"].eq(target)]
            if day.empty:
                raise ValueError(f"{species} location forecast is missing {target.date()}.")
            species_by_name[species] = day
        local_probabilities = _nearest_species_probabilities(
            general_day, species_by_name
        )
        flags, weather_details = _weather_conditions(engineered_weather, target)
        national_rating = calculate_rating(probabilities, flags)
        hotspot_rows = []
        for index, row in enumerate(general_day.itertuples(index=False)):
            local = {
                "General Seabird Index": float(row.forecast_probability),
                **{
                    species: float(values[index])
                    for species, values in local_probabilities.items()
                },
            }
            rating = calculate_rating(local, flags)
            hotspot_rows.append(
                {
                    "date": target,
                    "location": str(row.location),
                    "country": str(row.country),
                    "latitude": float(row.center_latitude),
                    "longitude": float(row.center_longitude),
                    "grid_easting": int(row.grid_easting),
                    "grid_northing": int(row.grid_northing),
                    "score": rating["score"],
                    "rating": rating["rating"],
                    "base_score": rating["base_score"],
                    "weather_bonus": rating["weather_bonus"],
                    "forecast_probability": float(rating["base_score"]) / 100.0,
                    "general_probability": local["General Seabird Index"],
                    "storm_petrel_probability": local["European Storm-petrel"],
                    "manx_shearwater_probability": local["Manx Shearwater"],
                    "sooty_shearwater_probability": local["Sooty Shearwater"],
                    "drivers": json.dumps(rating["drivers"]),
                }
            )
        hotspot_day = pd.DataFrame(hotspot_rows).sort_values(
            ["base_score", "location"], ascending=[False, True], kind="stable"
        )
        hotspot_day["rank"] = range(1, len(hotspot_day) + 1)
        rating_coast_frame = hotspot_day.drop(columns="forecast_probability").copy()
        rating_coast_frame["forecast_probability"] = hotspot_day["base_score"] / 100.0
        rating_coast = recommended_coast(
            rating_coast_frame
        )
        top_dutch = _top_dutch_sites(hotspot_day)
        offset = date_to_offset[target]
        label = HORIZONS.get(offset + 1, "")
        rating_frames.append(
            pd.DataFrame(
                [
                    {
                        "date": target,
                        "horizon": label,
                        "forecast_day": offset + 1,
                        "score": national_rating["score"],
                        "rating": national_rating["rating"],
                        "confidence": confidence_label(offset + 1),
                        "general_seabird_probability": probabilities[
                            "General Seabird Index"
                        ],
                        "storm_petrel_probability": probabilities[
                            "European Storm-petrel"
                        ],
                        "manx_shearwater_probability": probabilities[
                            "Manx Shearwater"
                        ],
                        "sooty_shearwater_probability": probabilities[
                            "Sooty Shearwater"
                        ],
                        "base_score": national_rating["base_score"],
                        "weather_bonus": national_rating["weather_bonus"],
                        "drivers": json.dumps(national_rating["drivers"]),
                        "best_coast": rating_coast["coast"],
                        "top3_dutch_sites": json.dumps(top_dutch),
                        "wind_direction": weather_details["wind_direction"],
                        "wind_speed_kt": weather_details["wind_speed_kt"],
                        "minimum_pressure_hpa": weather_details[
                            "minimum_pressure_hpa"
                        ],
                        "wind_change_ms": weather_details["wind_change_ms"],
                        "weather_bonuses": json.dumps(
                            national_rating["weather_bonuses"]
                        ),
                    }
                ]
            )
        )
        if offset + 1 in HORIZONS:
            top = hotspot_day.head(10).copy()
            top.insert(1, "horizon", HORIZONS[offset + 1])
            hotspot_frames.append(top)
            payload = (
                _horizon_payload(
                    target,
                    HORIZONS[offset + 1],
                    top,
                    national_rating,
                    confidence_label(offset + 1),
                    rating_coast,
                    top_dutch,
                    weather_details,
                    probabilities,
                )
            )
            payload["forecast_day"] = offset + 1
            payload["coast_ranking"] = coast_scores(dutch_site_scores(hotspot_day))
            payload.update(
                explain_rating(
                    probabilities,
                    RATING_WEIGHTS,
                    WEATHER_BONUSES,
                    national_rating["weather_bonuses"],
                    weather_details,
                )
            )
            horizon_details.append(payload)

    rating_frame = pd.concat(rating_frames, ignore_index=True)
    hotspots_frame = pd.concat(hotspot_frames, ignore_index=True)
    generated_at = generated_at or (
        datetime.combine(analysis_date, time.min, tzinfo=timezone.utc)
        if analysis_date is not None
        else datetime.now(timezone.utc)
    )
    document: dict[str, object] = {
        "product": "Seawatch Day Rating",
        "generated_at": generated_at.isoformat(),
        "formula": {
            "weights": RATING_WEIGHTS,
            "weather_bonuses": WEATHER_BONUSES,
            "wind_threshold_kt": WIND_THRESHOLD_KT,
            "wind_sector": "W through WNW (247.5°–292.5°)",
            "deep_low_pressure_hpa": DEEP_LOW_PRESSURE_HPA,
            "score_cap": 100,
            "rating_bands": [
                {"minimum": lower, "rating": label}
                for lower, label in zip((0, 25, 50, 70, 85), (row[1] for row in RATING_BANDS))
            ],
        },
        "horizons": horizon_details,
    }
    return rating_frame, hotspots_frame, document


def build_from_outputs(
    weather: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Read persisted forecasts and location grids to make rating products."""
    if not GENERAL_FORECAST_FILE.is_file() or not GENERAL_LOCATION_FILE.is_file():
        raise FileNotFoundError("General Seabird forecast and location files are required.")
    general_forecast = pd.read_csv(GENERAL_FORECAST_FILE, parse_dates=["date"])
    general_locations = pd.read_csv(GENERAL_LOCATION_FILE, parse_dates=["date"])
    species_forecasts = {
        species: pd.read_csv(path, parse_dates=["date"])
        for species, path in SPECIES_FORECASTS.items()
    }
    species_locations = {
        species: pd.read_csv(path, parse_dates=["date"])
        for species, path in SPECIES_LOCATIONS.items()
    }
    return build_rating_products(
        general_forecast,
        species_forecasts,
        general_locations,
        species_locations,
        weather,
    )


def save_rating_products(
    rating: pd.DataFrame,
    hotspots: pd.DataFrame,
    document: dict[str, object],
    *,
    rating_path: Path = RATING_OUTPUT,
    hotspots_path: Path = HOTSPOTS_OUTPUT,
    json_path: Path = RATING_JSON_OUTPUT,
) -> None:
    for path in (rating_path, hotspots_path, json_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    rating.to_csv(rating_path, index=False, date_format="%Y-%m-%d")
    hotspots.to_csv(hotspots_path, index=False, date_format="%Y-%m-%d")
    json_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
