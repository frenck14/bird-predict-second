"""Generate a Seabird Index forecast from regional weather inputs."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import joblib
import pandas as pd

if __package__:
    from .build_dataset_v2 import add_coastal_features
    from .predict_yellow_browed import (
        load_weather_forecast,
        make_predictions as make_shared_predictions,
        save_plot as save_shared_plot,
    )
    from .seabird_features import add_seabird_features
else:
    from build_dataset_v2 import add_coastal_features
    from predict_yellow_browed import (
        load_weather_forecast,
        make_predictions as make_shared_predictions,
        save_plot as save_shared_plot,
    )
    from seabird_features import add_seabird_features


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "outputs/seabird_model.joblib"
DEFAULT_OUTPUT = ROOT / "outputs/seabird_forecast.csv"
DEFAULT_PLOT = ROOT / "outputs/seabird_forecast.png"
# Seabird-event days are rare, so use the same broad cut points as the Eastern
# Influx Index.
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


def _feature_builder(weather: pd.DataFrame) -> pd.DataFrame:
    return add_seabird_features(add_coastal_features(weather))


def analysis_predictor_dates(
    weather: pd.DataFrame,
    predictor_dates: pd.DatetimeIndex,
    analysis_date: date | None,
) -> pd.DatetimeIndex:
    if analysis_date is None:
        return predictor_dates
    requested = pd.date_range(
        pd.Timestamp(analysis_date), periods=len(predictor_dates), freq="D"
    )
    available = pd.DatetimeIndex(pd.to_datetime(weather["date"]).dt.normalize())
    missing = requested.difference(available)
    if len(missing):
        raise ValueError(
            "Historical weather is missing analysis-window dates: "
            f"{missing.strftime('%Y-%m-%d').tolist()}"
        )
    return requested


def make_predictions(
    weather: pd.DataFrame,
    predictor_dates: pd.DatetimeIndex,
    artifact: dict[str, object],
    analysis_date: date | None = None,
) -> pd.DataFrame:
    if artifact.get("species") != "Seabird Index":
        raise ValueError("Saved model artifact is not for the Seabird Index.")
    predictor_dates = analysis_predictor_dates(
        weather, predictor_dates, analysis_date
    )
    shared_predictions = make_shared_predictions(
        weather,
        predictor_dates,
        artifact,
        feature_builder=_feature_builder,
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
    low, moderate, high = (threshold * 100 for threshold in RISK_THRESHOLDS)
    save_shared_plot(
        predictions,
        path,
        title="Seabird Index — 14-day daily risk forecast",
        bands=(
            (0, low, "#d9f0d3", "LOW"),
            (low, moderate, "#ffffbf", "MODERATE"),
            (moderate, high, "#fdae61", "HIGH"),
            (high, 100, "#d73027", "VERY_HIGH"),
        ),
    )


def save_forecast(
    predictions: pd.DataFrame,
    output_path: Path = DEFAULT_OUTPUT,
    plot_path: Path = DEFAULT_PLOT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output_path, index=False, date_format="%Y-%m-%d")
    save_plot(predictions, plot_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--weather-forecast",
        type=Path,
        required=True,
        help="Daily KNMI-scaled Open-Meteo input CSV.",
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--plot", type=Path, default=DEFAULT_PLOT)
    args = parser.parse_args()
    if not args.model.is_file():
        raise FileNotFoundError(f"Seabird model not found: {args.model}")
    weather, predictor_dates = load_weather_forecast(args.weather_forecast)
    artifact = joblib.load(args.model)
    predictions = make_predictions(weather, predictor_dates, artifact)
    save_forecast(predictions, args.output, args.plot)


if __name__ == "__main__":
    main()
