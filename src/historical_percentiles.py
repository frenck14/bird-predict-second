"""Historical percentile context for the Seawatch Day Rating and Rarity Index."""

from __future__ import annotations

import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

if __package__:
    from .forecast_seabird_locations import _build_seabird_features
    from .forecast_seabird_species import SPECIES_MODEL_PATHS
    from .predict_seabird import DEFAULT_MODEL as GENERAL_MODEL
    from .predict_seabird import make_predictions as make_general_predictions
    from .predict_yellow_browed import make_predictions
    from .rarity_index import historical_rarity_raw
    from .seawatch_day_rating import (
        DEEP_LOW_PRESSURE_HPA,
        RATING_WEIGHTS,
        WEATHER_BONUSES,
        WIND_THRESHOLD_MS,
        _direction_degrees,
    )
else:
    from forecast_seabird_locations import _build_seabird_features
    from forecast_seabird_species import SPECIES_MODEL_PATHS
    from predict_seabird import DEFAULT_MODEL as GENERAL_MODEL
    from predict_seabird import make_predictions as make_general_predictions
    from predict_yellow_browed import make_predictions
    from rarity_index import historical_rarity_raw
    from seawatch_day_rating import (
        DEEP_LOW_PRESSURE_HPA,
        RATING_WEIGHTS,
        WEATHER_BONUSES,
        WIND_THRESHOLD_MS,
        _direction_degrees,
    )

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_PERCENTILES_OUTPUT = ROOT / "outputs/historical_percentiles.csv"
HISTORICAL_PERCENTILE_COLUMNS = [
    "date", "horizon_days",
    "seawatch_score", "seawatch_percentile", "seawatch_label",
    "rarity_score", "rarity_percentile", "rarity_label",
]
LABEL_BANDS = (
    (95, "Historic"),
    (90, "Exceptional"),
    (75, "Strong"),
    (50, "Above Average"),
    (0, "Common Conditions"),
)
CALENDAR_COLUMNS = ["month", "day_of_year", "day_of_year_sin", "day_of_year_cos"]


def percentile_label(percentile: float) -> str:
    for lower, label in LABEL_BANDS:
        if percentile >= lower:
            return label
    return LABEL_BANDS[-1][1]


def rank_text(percentile: float) -> str:
    return f"Higher than {percentile:.0f}% of historical forecast days"


def historical_percentile(score: float, history: pd.Series) -> float:
    """Percentage of historical days whose score is strictly lower."""
    values = pd.to_numeric(history, errors="raise").dropna().to_numpy()
    if values.size == 0:
        raise ValueError("Historical distribution is empty.")
    return float((values < score).mean() * 100.0)


def context(score: float, history: pd.Series) -> dict[str, object]:
    percentile = historical_percentile(score, history)
    return {
        "historical_percentile": round(percentile, 1),
        "historical_label": percentile_label(percentile),
        "historical_rank_text": rank_text(percentile),
    }


def _weather_flags(engineered: pd.DataFrame) -> pd.DataFrame:
    """Per target date weather bonuses, mirroring the live rating's flags."""
    frame = engineered.assign(date=pd.to_datetime(engineered["date"]).dt.normalize())
    frame = frame.sort_values("date").set_index("date")
    speed = frame["coast_wind_speed"].astype(float)
    direction = frame.apply(_direction_degrees, axis=1)
    pressure = frame["coast_PX_min"].astype(float) / 10.0
    change = speed.diff()
    flags = pd.DataFrame(
        {
            "strong_westerly_wind": (speed >= WIND_THRESHOLD_MS)
            & direction.between(247.5, 292.5),
            "deep_atlantic_low": pressure <= DEEP_LOW_PRESSURE_HPA,
            "increasing_wind": change > 0,
        }
    )
    flags.index = flags.index + pd.Timedelta(days=1)
    flags["peak_seawatching_season"] = flags.index.month.isin([10, 11])
    return flags.fillna(False)


def historical_seawatch_scores(historical_weather: pd.DataFrame) -> pd.Series:
    """Unrounded historical Seawatch Day Rating (0-100) for each model date."""
    weather = historical_weather.copy()
    weather["date"] = pd.to_datetime(weather["date"]).dt.normalize()
    weather = weather.sort_values("date").reset_index(drop=True)
    weather = weather.drop(columns=CALENDAR_COLUMNS, errors="ignore")
    dates = pd.DatetimeIndex(weather["date"])
    predictor_dates = dates[:-1]
    probabilities = {
        "General Seabird Index": make_general_predictions(
            weather, predictor_dates, joblib.load(GENERAL_MODEL)
        ).set_index("date")["probability"]
    }
    for species in RATING_WEIGHTS:
        if species == "General Seabird Index":
            continue
        probabilities[species] = make_predictions(
            weather,
            predictor_dates,
            joblib.load(SPECIES_MODEL_PATHS[species]),
            feature_builder=_build_seabird_features,
        ).set_index("date")["probability"]
    base = sum(
        probabilities[name] * weight * 100.0
        for name, weight in RATING_WEIGHTS.items()
    )
    flags = _weather_flags(_build_seabird_features(weather)).reindex(base.index)
    bonus = sum(
        flags[name].fillna(False).astype(bool) * points
        for name, points in WEATHER_BONUSES.items()
    )
    return (base + bonus).clip(upper=100.0).rename("seawatch_score")


def historical_distributions(
    historical_weather: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    """Return (seawatch scores, rarity raw scores) over all historical days."""
    return (
        historical_seawatch_scores(historical_weather),
        historical_rarity_raw(historical_weather),
    )


def apply_percentile_context(
    rating_document: dict[str, object],
    rarity_document: dict[str, object],
    seawatch_history: pd.Series,
    rarity_history: pd.Series,
) -> pd.DataFrame:
    """Annotate both documents in place and return the combined CSV frame.

    Seawatch uses the unrounded score (base + bonuses, capped); Rarity uses the
    unclipped raw score, so neither displayed rounding nor clipping adds ties.
    """
    rarity_by_date = {h["date"]: h for h in rarity_document["horizons"]}
    rows = []
    for horizon in rating_document["horizons"]:
        rarity = rarity_by_date[horizon["date"]]
        seawatch_exact = min(
            100.0,
            sum(horizon["component_points"].values())
            + sum(horizon["weather_bonuses"].values()),
        )
        seawatch_context = context(seawatch_exact, seawatch_history)
        rarity_context = context(float(rarity["rarity_raw"]), rarity_history)
        horizon.update(seawatch_context)
        rarity.update(rarity_context)
        rows.append(
            {
                "date": horizon["date"],
                "horizon_days": int(horizon["forecast_day"]),
                "seawatch_score": horizon["score"],
                "seawatch_percentile": seawatch_context["historical_percentile"],
                "seawatch_label": seawatch_context["historical_label"],
                "rarity_score": rarity["rarity_index"],
                "rarity_percentile": rarity_context["historical_percentile"],
                "rarity_label": rarity_context["historical_label"],
            }
        )
    summary = {
        "method": "share of all historical model-output days with a lower score",
        "seawatch_sample_size": int(seawatch_history.notna().sum()),
        "rarity_sample_size": int(rarity_history.notna().sum()),
        "labels": {"<50": "Common Conditions", "50-75": "Above Average",
                   "75-90": "Strong", "90-95": "Exceptional", "95+": "Historic"},
    }
    rating_document["historical_context"] = summary
    rarity_document["historical_context"] = summary
    return pd.DataFrame(rows, columns=HISTORICAL_PERCENTILE_COLUMNS)


def save_historical_percentiles(
    frame: pd.DataFrame, path: Path = HISTORICAL_PERCENTILES_OUTPUT
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
