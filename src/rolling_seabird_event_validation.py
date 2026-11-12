"""Annual expanding-window, one-day-ahead seabird event validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .forecast_seabird_locations import _build_seabird_features
from .forecast_seabird_species import SPECIES_NAMES
from .forecast_species_comparison import MIN_TRAIN_YEARS
from .predict_yellow_browed import add_target_calendar
from .seabird_backtest import load_cached_occurrences, load_historical_weather
from .seabird_observation_validation import OBSERVATIONS_FILE
from .seabird_validation import _fit_cutoff_model, check_data_leakage
from .train_seabird_species_models import CLASSIFICATION_THRESHOLD

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "outputs/seabird_validation/rolling_event_validation.csv"
SUMMARY_PATH = ROOT / "outputs/seabird_validation/event_validation_summary.md"
PREDICTIONS_PATH = ROOT / "outputs/seabird_validation/rolling_event_predictions.csv"


def load_observations(path: Path = ROOT / OBSERVATIONS_FILE) -> pd.DataFrame:
    records = pd.read_csv(path, parse_dates=["date"])
    required = {"date", "species", "count"}
    if not required.issubset(records.columns):
        raise ValueError(f"{path} must contain {sorted(required)}.")
    records["date"] = pd.to_datetime(records["date"], errors="raise").dt.normalize()
    records["count"] = pd.to_numeric(records["count"], errors="raise")
    if (
        records.empty
        or records["date"].isna().any()
        or records["species"].isna().any()
        or records["count"].isna().any()
        or not np.isfinite(records["count"]).all()
        or (records["count"] < 0).any()
        or (records["count"] % 1 != 0).any()
    ):
        raise ValueError("Observation records must have valid dates, species and nonnegative integer counts.")
    return records


def summarize_rows(rows: pd.DataFrame, species: str, year: str) -> dict[str, object]:
    actual = rows["actual_event"].astype(bool)
    predicted = rows["probability"].ge(CLASSIFICATION_THRESHOLD)
    tp = int((actual & predicted).sum())
    fp = int((~actual & predicted).sum())
    fn = int((actual & ~predicted).sum())
    tn = int((~actual & ~predicted).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    brier = float(((rows["probability"] - actual.astype(int)) ** 2).mean())
    baseline = float(((rows["baseline_probability"] - actual.astype(int)) ** 2).mean())
    return {
        "species": species,
        "year": year,
        "start_date": rows["date"].min().date().isoformat(),
        "end_date": rows["date"].max().date().isoformat(),
        "evaluated_days": len(rows),
        "event_days": int(actual.sum()),
        "event_prevalence": float(actual.mean()),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "brier_score": brier,
        "baseline_brier_score": baseline,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "event_threshold_min": float(rows["event_threshold_count"].min()),
        "event_threshold_max": float(rows["event_threshold_count"].max()),
        "probability_threshold": CLASSIFICATION_THRESHOLD,
    }


def evaluate_rolling(
    weather: pd.DataFrame,
    occurrences: pd.DataFrame,
    observations: pd.DataFrame,
    predictions: list[pd.DataFrame] | None = None,
) -> pd.DataFrame:
    weather = weather.sort_values("date").reset_index(drop=True)
    dates = pd.DatetimeIndex(pd.to_datetime(weather["date"], errors="raise")).normalize()
    if dates.empty or dates.has_duplicates or dates.hasnans:
        raise ValueError("Weather must have unique valid dates.")
    if not dates.equals(pd.date_range(dates.min(), dates.max())):
        raise ValueError("Weather must cover consecutive days for one-day lead training.")
    weather = weather.assign(date=dates)
    occurrence_dates = pd.to_datetime(occurrences["date"], errors="raise").dt.normalize()
    if occurrence_dates.isna().any():
        raise ValueError("Occurrence dates must be valid.")
    occurrences = occurrences.assign(date=occurrence_dates)
    observed_counts = observations.groupby(["date", "species"])["count"].sum()
    last_target = min(dates.max() + pd.Timedelta(days=1), observations["date"].max())
    years = sorted(dates.year.unique())
    if len(years) < MIN_TRAIN_YEARS:
        raise ValueError("Insufficient calendar years for rolling validation.")
    first_year = years[MIN_TRAIN_YEARS - 1] + 1
    if first_year > last_target.year:
        raise ValueError("No evaluation dates after the training-history period.")

    # The feature builder uses current and trailing weather only. Its prefix
    # invariance is covered by a test because this frame includes later dates.
    engineered = _build_seabird_features(weather)
    if not pd.DatetimeIndex(engineered["date"]).equals(dates):
        raise ValueError("Engineered weather dates do not match input dates.")
    summaries = []
    species_rows: dict[str, list[pd.DataFrame]] = {name: [] for name in SPECIES_NAMES}
    for year in range(first_year, last_target.year + 1):
        train_cutoff = pd.Timestamp(year=year, month=1, day=1) - pd.Timedelta(days=1)
        train_weather = weather.loc[weather["date"].le(train_cutoff)].copy()
        train_features = engineered.loc[engineered["date"].le(train_cutoff)].copy()
        train_occurrences = occurrences.loc[occurrences["date"].le(train_cutoff)].copy()
        target_dates = pd.date_range(
            train_cutoff + pd.Timedelta(days=1),
            min(pd.Timestamp(year=year, month=12, day=31), last_target),
        )
        origins = target_dates - pd.Timedelta(days=1)
        origin_features = engineered.set_index("date").loc[origins].reset_index(drop=True)
        calendar = add_target_calendar(target_dates).reset_index(drop=True)
        for species in SPECIES_NAMES:
            print(f"Evaluating {year}: {species}", flush=True)
            artifact = _fit_cutoff_model(
                train_weather, train_occurrences, train_cutoff.date(), species, 1,
                engineered_weather=train_features,
            )
            check_data_leakage({}, {species: artifact}, train_cutoff.date())
            feature_columns = artifact["feature_columns"]
            weather_columns = artifact["weather_feature_columns"]
            if not isinstance(feature_columns, list) or not isinstance(weather_columns, list):
                raise TypeError("Cutoff model artifact has an invalid feature schema.")
            model_inputs = pd.concat(
                [calendar, origin_features.loc[:, weather_columns]], axis=1
            )
            probabilities = artifact["model"].predict_proba(model_inputs[feature_columns])[:, 1]
            if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
                raise ValueError(f"Invalid forecast probabilities for {species} in {year}.")
            index = pd.MultiIndex.from_arrays(
                [target_dates, [species] * len(target_dates)], names=["date", "species"]
            )
            counts = observed_counts.reindex(index, fill_value=0).to_numpy()
            threshold = float(artifact["influx_threshold_count"])
            rows = pd.DataFrame(
                {
                    "date": target_dates,
                    "probability": probabilities,
                    "actual_event": counts >= threshold,
                    "event_threshold_count": threshold,
                    "baseline_probability": (
                        int(artifact["training_positive_days"]) / int(artifact["training_rows"])
                    ),
                }
            )
            if predictions is not None:
                predictions.append(rows.assign(species=species))
            summaries.append(summarize_rows(rows, species, str(year)))
            species_rows[species].append(rows)
    for species, frames in species_rows.items():
        summaries.append(summarize_rows(pd.concat(frames, ignore_index=True), species, "all"))
    return pd.DataFrame(summaries)


def write_summary(summary: pd.DataFrame, path: Path = SUMMARY_PATH) -> None:
    overall = summary.loc[summary["year"].eq("all")]
    lines = [
        "# Rolling seabird influx-event validation",
        "",
        "## Method",
        "",
        "Annual expanding-window models are trained through December 31 before each",
        "evaluation year, using the existing strict-cutoff one-day-lead model and",
        "training-only P90 occurrence-count threshold (minimum one record). Each",
        "day's prediction uses the preceding day's historical observed weather;",
        "model parameters and the event threshold remain frozen for that year.",
        "This is a hindcast with observed-weather proxy inputs, not archived",
        "operational forecast replay. The probability decision cutoff is 0.20.",
        "",
        "The existing five-calendar-year convention counts partial calendar years,",
        "so it does not necessarily require five full years of training data.",
        f"Evaluated dates are {overall['start_date'].min()} through {overall['end_date'].max()}.",
        "The last evaluation year is partial. The last evaluated date is bounded",
        "by the earlier of one day after the last available weather date and the",
        "last date in the observation file; a last record date does not prove",
        "complete reporting through that date.",
        "",
        "The observations are GBIF occurrence-record counts, summed across",
        "countries. No qualifying record is treated as zero, not proven absence.",
        "Archive completeness and reporting effort may vary over time and by",
        "species. Training uses the historical occurrence cache and evaluation",
        "uses the derived observations file; this is temporal holdout, not an",
        "independent data source. Thresholds, and hence event definitions, can",
        "change between annual folds.",
        "",
        "## Overall results",
        "",
        "| Species | Days | Event days | Prevalence | Precision | Recall | F1 | Brier | Training-prevalence baseline Brier |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in overall.itertuples(index=False):
        lines.append(
            f"| {row.species} | {row.evaluated_days} | {row.event_days} | "
            f"{row.event_prevalence:.3f} | {row.precision:.3f} | {row.recall:.3f} | "
            f"{row.f1:.3f} | {row.brier_score:.5f} | {row.baseline_brier_score:.5f} |"
        )
    better = overall.loc[overall["brier_score"] < overall["baseline_brier_score"], "species"].tolist()
    not_better = overall.loc[overall["brier_score"] >= overall["baseline_brier_score"], "species"].tolist()
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Lower Brier than the annual training-prevalence baseline: {', '.join(better) or 'none'}.",
            f"- Not lower than that baseline: {', '.join(not_better) or 'none'}.",
            f"- F1 ranges from {overall['f1'].min():.3f} to {overall['f1'].max():.3f}",
            "  at the common 0.20 probability cutoff. The differing scores suggest",
            "  performance varies by species rather than being uniformly poor.",
            "- This comparison alone cannot isolate model weakness from probability",
            "  calibration or the decision threshold. In particular, rare-event",
            "  precision and F1 depend heavily on event prevalence.",
            "",
            "Overall precision, recall and F1 use pooled daily confusion counts,",
            "not an average of yearly scores. Brier is the mean squared error of",
            "daily event probabilities. The baseline uses each year's training",
            "event prevalence as a constant probability on that year's holdout",
            "days. A lower Brier score is better. Undefined precision or recall",
            "is reported as zero, matching the existing validation convention.",
            "",
            "The CSV includes yearly folds and pooled `all` rows, confusion counts,",
            "date coverage and training event-count threshold ranges. Comparing",
            "F1 between species without considering prevalence can mislead;",
            "rare events and incomplete records make sparse-species estimates",
            "especially uncertain. These results measure the 0.20 operating point,",
            "not performance at every possible probability threshold.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    observations = load_observations()
    weather = load_historical_weather()
    occurrences = load_cached_occurrences()
    predictions: list[pd.DataFrame] = []
    summary = evaluate_rolling(weather, occurrences, observations, predictions)
    pd.concat(predictions, ignore_index=True).to_csv(
        PREDICTIONS_PATH, index=False, date_format="%Y-%m-%d"
    )
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(CSV_PATH, index=False)
    write_summary(summary)
    print(summary.loc[summary["year"].eq("all")].to_string(index=False))
    print(f"Wrote {CSV_PATH} and {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
