"""Generate a 14-day Yellow-browed Warbler risk forecast from station weather."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__:
    from .build_dataset_v2 import (
        STATION_FILES,
        WEATHER_VARIABLES,
        add_coastal_features,
    )
else:
    from build_dataset_v2 import (
        STATION_FILES,
        WEATHER_VARIABLES,
        add_coastal_features,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "outputs/yellow_browed_model.joblib"
DEFAULT_OUTPUT = ROOT / "outputs/yellow_browed_forecast.csv"
DEFAULT_PLOT = ROOT / "outputs/yellow_browed_forecast.png"
DEFAULT_REPORT = ROOT / "outputs/yellow_browed_report.md"
FORECAST_DAYS = 14
REQUIRED_INPUT_COLUMNS = {
    "date",
    "station_id",
    *WEATHER_VARIABLES,
}
INVALID_MINUS_ONE_VARIABLES = {"DDVEC", "FG", "FHX", "PX"}
RISK_CATEGORIES = ("Very Low", "Low", "Moderate", "High", "Very High")


def load_weather_forecast(path: Path) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    if not path.is_file():
        raise FileNotFoundError(f"Weather forecast file not found: {path}")

    raw = pd.read_csv(path)
    missing_columns = REQUIRED_INPUT_COLUMNS.difference(raw.columns)
    if missing_columns:
        raise ValueError(
            f"Weather forecast is missing columns: {sorted(missing_columns)}"
        )

    raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.normalize()
    if raw["date"].isna().any():
        raise ValueError("Weather forecast contains invalid dates.")
    raw["station_id"] = pd.to_numeric(
        raw["station_id"], errors="raise"
    ).astype(int)
    station_ids = set(STATION_FILES)
    available_stations = set(raw["station_id"].unique())
    missing_stations = station_ids.difference(available_stations)
    if missing_stations:
        raise ValueError(
            f"Weather forecast is missing stations: {sorted(missing_stations)}"
        )
    raw = raw.loc[raw["station_id"].isin(station_ids)].copy()
    if raw.duplicated(["date", "station_id"]).any():
        raise ValueError("Weather forecast has duplicate date/station rows.")

    for variable in WEATHER_VARIABLES:
        raw[variable] = pd.to_numeric(raw[variable], errors="coerce")
        raw[variable] = raw[variable].mask(raw[variable] == -9999)
        if variable in INVALID_MINUS_ONE_VARIABLES:
            raw[variable] = raw[variable].mask(raw[variable] == -1)
        elif variable == "RH":
            raw.loc[raw[variable].eq(-1), variable] = 0

    dates = pd.DatetimeIndex(sorted(raw["date"].unique()))
    if len(dates) < FORECAST_DAYS:
        raise ValueError(
            f"Weather forecast must contain at least {FORECAST_DAYS} "
            f"distinct daily dates; found {len(dates)}."
        )
    predictor_dates = dates[-FORECAST_DAYS:]
    expected_dates = pd.date_range(
        predictor_dates[0], predictor_dates[-1], freq="D"
    )
    if not predictor_dates.equals(expected_dates):
        raise ValueError("The final 14 weather forecast dates must be consecutive.")

    rows_per_date = (
        raw.loc[raw["date"].isin(predictor_dates)]
        .groupby("date")["station_id"]
        .nunique()
    )
    if not rows_per_date.eq(len(station_ids)).all():
        incomplete_dates = rows_per_date.index[
            rows_per_date.ne(len(station_ids))
        ].strftime("%Y-%m-%d").tolist()
        raise ValueError(
            "Each of the final 14 forecast dates must include all four "
            f"stations; incomplete dates: {incomplete_dates}"
        )

    weather = pd.DataFrame({"date": dates})
    for station_id in sorted(station_ids):
        station = (
            raw.loc[raw["station_id"].eq(station_id)]
            .drop(columns="station_id")
            .rename(
                columns={
                    variable: f"{variable}_{station_id}"
                    for variable in WEATHER_VARIABLES
                }
            )
        )
        weather = weather.merge(
            station, on="date", how="left", validate="one_to_one"
        )

    return weather.sort_values("date").reset_index(drop=True), predictor_dates


def add_target_calendar(dates: pd.DatetimeIndex) -> pd.DataFrame:
    day_of_year = dates.dayofyear
    annual_phase = 2 * np.pi * day_of_year / 365.2425
    return pd.DataFrame(
        {
            "month": dates.month,
            "day_of_year": day_of_year,
            "day_of_year_sin": np.sin(annual_phase),
            "day_of_year_cos": np.cos(annual_phase),
        }
    )


def risk_category(probability: float) -> str:
    percent = probability * 100
    if percent < 20:
        return "Very Low"
    if percent < 40:
        return "Low"
    if percent < 60:
        return "Moderate"
    if percent < 80:
        return "High"
    return "Very High"


def make_predictions(
    weather: pd.DataFrame,
    predictor_dates: pd.DatetimeIndex,
    artifact: dict[str, object],
    feature_builder: Callable[[pd.DataFrame], pd.DataFrame] = add_coastal_features,
) -> pd.DataFrame:
    model = artifact["model"]
    feature_columns = artifact["feature_columns"]
    if not isinstance(feature_columns, list) or not feature_columns:
        raise ValueError("Saved model artifact has no feature-column schema.")

    engineered = feature_builder(weather)
    target_dates = predictor_dates + pd.Timedelta(days=1)
    indexed = engineered.set_index("date")
    missing_dates = predictor_dates.difference(indexed.index)
    if len(missing_dates):
        raise ValueError(
            f"Engineered weather is missing predictor dates: "
            f"{missing_dates.strftime('%Y-%m-%d').tolist()}"
        )

    calendar = add_target_calendar(target_dates)
    weather_features = indexed.loc[predictor_dates]
    inputs = pd.concat(
        [
            calendar.reset_index(drop=True),
            weather_features.reset_index(drop=True),
        ],
        axis=1,
    )
    missing_features = set(feature_columns).difference(inputs.columns)
    if missing_features:
        raise ValueError(
            f"Input weather cannot construct saved model features: "
            f"{sorted(missing_features)}"
        )
    probabilities = model.predict_proba(inputs[feature_columns])[:, 1]
    if not np.isfinite(probabilities).all():
        raise ValueError("Model produced non-finite forecast probabilities.")

    return pd.DataFrame(
        {
            "date": target_dates,
            "probability": probabilities,
            "risk_category": [
                risk_category(float(probability))
                for probability in probabilities
            ],
        }
    )


def save_plot(
    predictions: pd.DataFrame,
    path: Path,
    title: str = "Yellow-browed Warbler — 14-day daily risk forecast",
    bands: tuple[tuple[float, float, str, str], ...] | None = None,
) -> None:
    probabilities = predictions["probability"] * 100
    dates = predictions["date"]
    fig, axis = plt.subplots(figsize=(11, 5))
    risk_bands = bands or (
        (0, 20, "#d9f0d3", "Very Low"),
        (20, 40, "#ffffbf", "Low"),
        (40, 60, "#fee08b", "Moderate"),
        (60, 80, "#fdae61", "High"),
        (80, 100, "#d73027", "Very High"),
    )
    for lower, upper, color, _ in risk_bands:
        axis.axhspan(lower, upper, color=color, alpha=0.28, zorder=0)
    axis.plot(dates, probabilities, marker="o", color="#264653", linewidth=2)
    axis.set(
        title=title,
        xlabel="Target date",
        ylabel="Predicted probability (%)",
        ylim=(0, 100),
    )
    axis.grid(axis="y", alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def build_daily_report(
    predictions: pd.DataFrame,
    artifact: dict[str, object],
    plot_path: Path,
    synthetic_example: bool = False,
    weather_source: str | None = None,
) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mean_probability = predictions["probability"].mean()
    max_row = predictions.loc[predictions["probability"].idxmax()]
    lines = [
        "# Bird-Predict Daily Report: Yellow-browed Warbler",
        "",
        f"Generated: {generated}",
        "",
        *(
            [
                "**Input note:** This is an illustrative synthetic weather "
                "scenario, not an official weather forecast."
            ]
            if synthetic_example
            else []
        ),
        *([""] if synthetic_example else []),
        f"Forecast dates: {predictions['date'].min().date()} to "
        f"{predictions['date'].max().date()}",
        "",
        "## Summary",
        "",
        f"- Mean predicted daily risk: {mean_probability:.1%}",
        f"- Highest predicted risk: {max_row['probability']:.1%} on "
        f"{max_row['date'].date()} ({max_row['risk_category']})",
        f"- Model: {artifact['model_name']}; target is at least "
        f"{artifact['target_threshold']} records.",
        f"- Experiment reference: {artifact['training_horizon_days']}-day "
        f"lead PR-AUC {artifact['experiment_pr_auc']:.4f}, ROC-AUC "
        f"{artifact['experiment_roc_auc']:.4f}.",
        *([f"- Weather input: {weather_source}."] if weather_source else []),
        "",
        "## Daily forecast",
        "",
        "| Date | Probability | Risk category |",
        "|---|---:|---|",
    ]
    for row in predictions.itertuples(index=False):
        lines.append(
            f"| {row.date.date()} | {row.probability:.1%} | "
            f"{row.risk_category} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation and limitations",
            "",
            "Weather-source caveat: the production model was trained using KNMI "
            "station observations. This run uses Open-Meteo forecast-model grid "
            "points near the four KNMI coastal stations, with hourly values "
            "aggregated to local daily values and converted to the KNMI scaling. "
            "The sources, spatial representation, and aggregation are not "
            "identical, so this is a source-mismatched input and its probabilities "
            "have not been validated or recalibrated for Open-Meteo. KNMI `RH` "
            "means daily precipitation (0.1 mm), not relative humidity; the "
            "adapter maps Open-Meteo precipitation to `RH` and does not use "
            "relative humidity as that field.",
            "",
            "This model was selected and evaluated as a fixed 14-day-ahead "
            "classifier. Applying it to daily dates one day after each "
            "weather-valid date is a lead-time shift from that experiment; "
            "probabilities for nearer dates are not separately calibrated "
            "or validated. Yellow-browed Warbler targets represent GBIF "
            "record counts, not abundance, and may reflect observer effort "
            "and detectability. Treat categories as model scores, not "
            "certainty.",
            "",
            f"Risk plot: `{plot_path.name}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--weather-forecast",
        type=Path,
        required=True,
        help="CSV with date, station_id, and KNMI variables for each day/station.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL,
        help="Path to the saved Yellow-browed Warbler model artifact.",
    )
    parser.add_argument(
        "--synthetic-example",
        action="store_true",
        help="Mark the report input as an illustrative, non-official scenario.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path for the prediction CSV.",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        default=DEFAULT_PLOT,
        help="Path for the forecast plot.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Path for the daily report.",
    )
    args = parser.parse_args()

    if not args.model.is_file():
        raise FileNotFoundError(
            f"Saved model not found: {args.model}. "
            "Run `python src/train_yellow_browed_model.py` first."
        )
    artifact = joblib.load(args.model)
    if artifact.get("species") != "Yellow-browed Warbler":
        raise ValueError("Saved model artifact is not for Yellow-browed Warbler.")

    weather, predictor_dates = load_weather_forecast(args.weather_forecast)
    predictions = make_predictions(weather, predictor_dates, artifact)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output_csv, index=False, date_format="%Y-%m-%d")
    save_plot(predictions, args.plot)
    report = build_daily_report(
        predictions,
        artifact,
        args.plot,
        synthetic_example=args.synthetic_example,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(f"Forecast CSV saved to {args.output_csv}")
    print(f"Risk plot saved to {args.plot}")
    print(f"Daily report saved to {args.report}")
    print(predictions.to_string(index=False, formatters={"probability": "{:.1%}".format}))


if __name__ == "__main__":
    main()
