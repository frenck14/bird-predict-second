"""Generate an Atlantic Vagrancy Index forecast from regional weather inputs."""

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
DEFAULT_MODEL = ROOT / "outputs/atlantic_vagrancy_model.joblib"
DEFAULT_OUTPUT = ROOT / "outputs/atlantic_vagrancy_forecast.csv"
DEFAULT_PLOT = ROOT / "outputs/atlantic_vagrancy_forecast.png"


def risk_level(probability: float) -> str:
    if probability < 0.05:
        return "LOW"
    if probability < 0.10:
        return "MODERATE"
    if probability < 0.20:
        return "HIGH"
    return "VERY_HIGH"


def make_predictions(
    weather: pd.DataFrame,
    predictor_dates: pd.DatetimeIndex,
    artifact: dict[str, object],
) -> pd.DataFrame:
    if artifact.get("species") != "Atlantic Vagrancy Index":
        raise ValueError("Saved model artifact is not for the Atlantic Vagrancy Index.")
    shared_predictions = make_shared_predictions(
        weather, predictor_dates, artifact
    )
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
    save_shared_plot(
        predictions,
        path,
        title="Atlantic Vagrancy Index — 14-day daily risk forecast",
        bands=(
            (0, 5, "#d9f0d3", "LOW"),
            (5, 10, "#ffffbf", "MODERATE"),
            (10, 20, "#fdae61", "HIGH"),
            (20, 100, "#d73027", "VERY_HIGH"),
        ),
    )


def save_forecast(predictions: pd.DataFrame) -> None:
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(DEFAULT_OUTPUT, index=False, date_format="%Y-%m-%d")
    save_plot(predictions, DEFAULT_PLOT)
