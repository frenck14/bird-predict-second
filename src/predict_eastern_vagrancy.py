"""Generate an Eastern Vagrancy Index forecast from regional weather inputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

if __package__:
    from .predict_yellow_browed import (
        make_predictions as make_shared_predictions,
        save_plot as save_shared_plot,
    )
else:
    from predict_yellow_browed import (
        make_predictions as make_shared_predictions,
        save_plot as save_shared_plot,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "outputs/eastern_vagrancy_model.joblib"
DEFAULT_OUTPUT = ROOT / "outputs/eastern_vagrancy_forecast.csv"
DEFAULT_PLOT = ROOT / "outputs/eastern_vagrancy_forecast.png"
# Influx days are ~10% of dates, so the bands sit above the Atlantic ones.
# Upper probability bounds of LOW, MODERATE and HIGH; anything above is VERY_HIGH.
RISK_THRESHOLDS = (0.10, 0.25, 0.50)


def risk_level(probability: float) -> str:
    low, moderate, high = RISK_THRESHOLDS
    if probability < low:
        return "LOW"
    if probability < moderate:
        return "MODERATE"
    if probability < high:
        return "HIGH"
    return "VERY_HIGH"


def make_predictions(
    weather: pd.DataFrame,
    predictor_dates: pd.DatetimeIndex,
    artifact: dict[str, object],
) -> pd.DataFrame:
    if artifact.get("species") != "Eastern Vagrancy Index":
        raise ValueError("Saved model artifact is not for the Eastern Vagrancy Index.")
    shared_predictions = make_shared_predictions(weather, predictor_dates, artifact)
    return pd.DataFrame(
        {
            "date": shared_predictions["date"],
            "probability": shared_predictions["probability"],
            "risk_level": shared_predictions["probability"].map(
                lambda probability: risk_level(float(probability))
            ),
        }
    )


def save_plot(predictions: pd.DataFrame, path: Path) -> None:
    low, moderate, high = (threshold * 100 for threshold in RISK_THRESHOLDS)
    save_shared_plot(
        predictions,
        path,
        title="Eastern Vagrancy Index (influx days) — 14-day daily risk forecast",
        bands=(
            (0, low, "#d9f0d3", "LOW"),
            (low, moderate, "#ffffbf", "MODERATE"),
            (moderate, high, "#fdae61", "HIGH"),
            (high, 100, "#d73027", "VERY_HIGH"),
        ),
    )


def save_forecast(predictions: pd.DataFrame) -> None:
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(DEFAULT_OUTPUT, index=False, date_format="%Y-%m-%d")
    save_plot(predictions, DEFAULT_PLOT)
