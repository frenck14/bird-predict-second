"""Audit backtest species-presence metrics over several probability thresholds."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from .forecast_seabird_species import SPECIES_NAMES
from .seabird_backtest import FORECAST_DAYS, build_seabird_backtest
from .seabird_observation_validation import (
    calculate_metrics,
    holdout_observations,
    load_observation_records,
    match_species,
)

THRESHOLDS = (0.05, 0.10, 0.15, 0.20)
OUTPUT_FILE = Path("outputs/seabird_validation/threshold_analysis.csv")


def analyze_thresholds(
    forecast: pd.DataFrame,
    records: pd.DataFrame,
    analysis_date: date,
) -> pd.DataFrame:
    """Evaluate the same 14-day hindcast and observations at each threshold."""
    dates = pd.date_range(
        pd.Timestamp(analysis_date) + pd.Timedelta(days=1), periods=FORECAST_DAYS
    )
    if not {"date", "species", "probability"}.issubset(forecast.columns):
        raise ValueError("Forecast must include date, species and probability.")
    forecast = forecast.copy()
    forecast["date"] = pd.to_datetime(forecast["date"], errors="raise").dt.normalize()
    forecast["probability"] = pd.to_numeric(forecast["probability"], errors="raise")
    expected = pd.MultiIndex.from_product(
        [dates, SPECIES_NAMES], names=["date", "species"]
    )
    actual = pd.MultiIndex.from_frame(forecast[["date", "species"]])
    if (
        actual.has_duplicates
        or len(actual) != len(expected)
        or not actual.isin(expected).all()
        or not forecast["probability"].between(0, 1).all()
    ):
        raise ValueError("Forecast must contain valid probabilities for every species and holdout date.")

    observations = holdout_observations(records, dates)
    if observations.empty:
        raise ValueError("No observations are available in the holdout window.")

    rows = []
    for threshold in THRESHOLDS:
        matches = match_species(forecast, observations, probability_threshold=threshold)
        metrics = calculate_metrics(
            matches, forecast, observations, probability_threshold=threshold
        )
        rows.append(
            {
                "analysis_date": analysis_date.isoformat(),
                "window_start": dates[0].date().isoformat(),
                "window_end": dates[-1].date().isoformat(),
                "threshold": threshold,
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "true_positives": metrics["true_positives"],
                "false_positives": metrics["false_positives"],
                "false_negatives": metrics["false_negatives"],
                "predicted_species": "; ".join(matches.loc[matches["predicted"], "species"]),
                "observed_species": "; ".join(matches.loc[matches["observed"], "species"]),
            }
        )
    result = pd.DataFrame(rows)
    result["max_f1"] = result["f1"].eq(result["f1"].max())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_date", type=date.fromisoformat, help="Cutoff date (YYYY-MM-DD)")
    args = parser.parse_args()
    records = load_observation_records()
    result = build_seabird_backtest(args.analysis_date)
    forecast = result["species"]
    if not isinstance(forecast, pd.DataFrame):
        raise TypeError("Historical forecast result has an invalid species payload.")
    analysis = analyze_thresholds(forecast, records, args.analysis_date)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    analysis.to_csv(OUTPUT_FILE, index=False)
    print(analysis.to_string(index=False))
    print(f"\nWrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
