"""Train and evaluate the Atlantic Vagrancy Index arrival-day model."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    roc_auc_score,
)

if __package__:
    from .build_dataset_v2 import add_coastal_features
    from .forecast_species_comparison import (
        MIN_TRAIN_YEARS,
        SEASONALITY_FEATURES,
        build_horizon_data,
        make_estimator,
        weather_feature_columns,
    )
else:
    from build_dataset_v2 import add_coastal_features
    from forecast_species_comparison import (
        MIN_TRAIN_YEARS,
        SEASONALITY_FEATURES,
        build_horizon_data,
        make_estimator,
        weather_feature_columns,
    )


ROOT = Path(__file__).resolve().parents[1]
WEATHER_FILE = ROOT / "data/processed/bird_predict_dataset_v2.csv"
DAILY_COUNTS_FILE = ROOT / "outputs/atlantic_vagrancy_daily_counts.csv"
SPECIES_SUMMARY_FILE = ROOT / "outputs/atlantic_vagrancy_species_summary.csv"
EVENTS_FILE = ROOT / "outputs/atlantic_vagrancy_events.csv"
LEGACY_DAILY_COUNTS_FILE = ROOT / "outputs/american_passerine_daily_counts.csv"
MODEL_OUTPUT = ROOT / "outputs/atlantic_vagrancy_model.joblib"
EVALUATION_OUTPUT = ROOT / "outputs/atlantic_vagrancy_evaluation.csv"
IMPORTANCE_OUTPUT = ROOT / "outputs/atlantic_vagrancy_feature_importance.csv"
TRAINING_HORIZON_DAYS = 1
CLASSIFICATION_THRESHOLD = 0.05
MIN_FULL_PERIOD_EVENTS_FOR_SUFFICIENCY = 50
MIN_HELD_OUT_EVENTS_FOR_SUFFICIENCY = 20


def load_training_data() -> tuple[pd.DataFrame, list[str]]:
    for path, builder_command in (
        (WEATHER_FILE, "python src/build_dataset_v2.py"),
        (
            DAILY_COUNTS_FILE,
            "python src/build_atlantic_vagrancy_dataset.py",
        ),
    ):
        if not path.is_file():
            raise FileNotFoundError(
                f"Required training data not found: {path}. "
                f"Build it with `{builder_command}`."
            )
    weather = pd.read_csv(WEATHER_FILE, parse_dates=["date"]).sort_values("date")
    if weather["date"].isna().any() or weather["date"].duplicated().any():
        raise ValueError("Weather dataset must have unique, valid daily dates.")
    weather = add_coastal_features(weather)
    counts = pd.read_csv(DAILY_COUNTS_FILE, parse_dates=["date"])
    if not {"date", "count"}.issubset(counts.columns):
        raise ValueError(
            "Atlantic Vagrancy daily counts must contain date and count."
        )
    if counts["date"].isna().any() or counts["date"].duplicated().any():
        raise ValueError(
            "Atlantic Vagrancy daily counts must have unique, valid dates."
        )
    counts["count"] = pd.to_numeric(counts["count"], errors="raise")
    if counts["count"].isna().any() or counts["count"].lt(0).any():
        raise ValueError("Atlantic Vagrancy counts must be non-negative.")
    if not np.equal(counts["count"], np.floor(counts["count"])).all():
        raise ValueError("Atlantic Vagrancy counts must be whole numbers.")

    data = weather.merge(
        counts[["date", "count"]],
        on="date",
        how="left",
        validate="one_to_one",
    )
    data["count"] = data["count"].fillna(0).astype(int)
    data["event"] = data["count"].gt(0).astype(int)
    return data, weather_feature_columns(data)


def _build_supervised(
    data: pd.DataFrame,
    weather_columns: list[str],
    target_column: str,
) -> tuple[pd.DataFrame, list[str]]:
    latest_origin = data["date"].max() - pd.Timedelta(
        days=TRAINING_HORIZON_DAYS
    )
    supervised = build_horizon_data(
        data,
        weather_columns,
        target_column,
        TRAINING_HORIZON_DAYS,
        latest_origin,
    )
    supervised["target"] = supervised["target"].astype(int)
    return supervised, list(SEASONALITY_FEATURES) + weather_columns


def influx_cutoff(counts: pd.Series, percentile: float) -> float:
    """Percentile of daily counts, at least 1 so zero-count days are never events."""
    return max(float(np.percentile(counts, percentile)), 1.0)


def _evaluate_forward_chaining(
    supervised: pd.DataFrame,
    feature_columns: list[str],
    product: str,
    threshold: float = CLASSIFICATION_THRESHOLD,
    influx_percentile: float | None = None,
) -> dict[str, object]:
    """Forward-chained evaluation.

    With influx_percentile, supervised["target"] holds daily counts and each
    fold labels days >= that percentile of its own training counts.
    """
    years = supervised["origin_date"].dt.year
    unique_years = np.sort(years.unique())
    if len(unique_years) <= MIN_TRAIN_YEARS:
        raise ValueError(
            f"Need more than {MIN_TRAIN_YEARS} years for forward-chaining "
            f"evaluation; found {len(unique_years)}."
        )

    actual: list[np.ndarray] = []
    probabilities: list[np.ndarray] = []
    for test_year in unique_years[MIN_TRAIN_YEARS:]:
        train = supervised.loc[
            supervised["target_date"]
            < pd.Timestamp(year=int(test_year), month=1, day=1)
        ]
        test = supervised.loc[years.eq(test_year)]
        if train.empty or test.empty:
            raise RuntimeError(
                f"Empty forward-chaining fold for {product}, test year "
                f"{test_year}."
            )
        train_target = train["target"]
        test_target = test["target"]
        if influx_percentile is not None:
            cut = influx_cutoff(train["target"], influx_percentile)
            train_target = train["target"].ge(cut).astype(int)
            test_target = test["target"].ge(cut).astype(int)
        positive_count = int(train_target.sum())
        negative_count = len(train) - positive_count
        if positive_count == 0:
            fold_probabilities = np.zeros(len(test), dtype=float)
        else:
            estimator = make_estimator(
                "Random Forest",
                positive_count,
                negative_count,
                random_forest_class_weight=None,
            )
            estimator.fit(train[feature_columns], train_target)
            fold_probabilities = estimator.predict_proba(
                test[feature_columns]
            )[:, 1]
        actual.append(test_target.to_numpy(dtype=int))
        probabilities.append(fold_probabilities)

    y_true = np.concatenate(actual)
    y_probability = np.concatenate(probabilities)
    y_predicted = y_probability >= threshold
    true_negative, false_positive, false_negative, true_positive = (
        confusion_matrix(y_true, y_predicted, labels=[0, 1]).ravel()
    )
    held_out_positive_days = int(y_true.sum())
    full_target = supervised["target"]
    if influx_percentile is not None:
        full_target = full_target.ge(
            influx_cutoff(full_target, influx_percentile)
        ).astype(int)
    full_period_positive_days = int(full_target.sum())
    sufficient = (
        full_period_positive_days >= MIN_FULL_PERIOD_EVENTS_FOR_SUFFICIENCY
        and held_out_positive_days >= MIN_HELD_OUT_EVENTS_FOR_SUFFICIENCY
    )
    report: dict[str, object] = {
        "product": product,
        "roc_auc": (
            float(roc_auc_score(y_true, y_probability))
            if np.unique(y_true).size == 2
            else float("nan")
        ),
        "pr_auc": (
            float(average_precision_score(y_true, y_probability))
            if held_out_positive_days
            else float("nan")
        ),
        "confusion_threshold": threshold,
        "true_negative": int(true_negative),
        "false_positive": int(false_positive),
        "false_negative": int(false_negative),
        "true_positive": int(true_positive),
        "evaluation_rows": len(y_true),
        "evaluation_positive_days": held_out_positive_days,
        "evaluation_prevalence": float(y_true.mean()),
        "full_period_positive_days": full_period_positive_days,
        "full_period_prevalence": float(full_target.mean()),
        "data_sufficient_for_meaningful_prediction": sufficient,
        "sufficiency_rule": (
            f"at least {MIN_FULL_PERIOD_EVENTS_FOR_SUFFICIENCY} full-period "
            f"and {MIN_HELD_OUT_EVENTS_FOR_SUFFICIENCY} held-out event days"
        ),
        "evaluation_start_date": str(
            supervised.loc[
                supervised["origin_date"].dt.year.ge(
                    int(unique_years[MIN_TRAIN_YEARS])
                ),
                "target_date",
            ].min().date()
        ),
        "evaluation_end_date": str(
            supervised.loc[
                supervised["origin_date"].dt.year.ge(
                    int(unique_years[MIN_TRAIN_YEARS])
                ),
                "target_date",
            ].max().date()
        ),
    }
    return report


def _load_legacy_counts(data: pd.DataFrame) -> pd.DataFrame:
    if not LEGACY_DAILY_COUNTS_FILE.is_file():
        raise FileNotFoundError(
            "Cannot compare against the Netherlands-only prototype: "
            f"{LEGACY_DAILY_COUNTS_FILE} is missing."
        )
    legacy = pd.read_csv(LEGACY_DAILY_COUNTS_FILE, parse_dates=["date"])
    if not {"date", "count"}.issubset(legacy.columns):
        raise ValueError(
            "Netherlands-only prototype counts must contain date and count."
        )
    if legacy["date"].isna().any() or legacy["date"].duplicated().any():
        raise ValueError(
            "Netherlands-only prototype counts must have unique valid dates."
        )
    legacy_data = data.drop(columns=["count", "event"]).merge(
        legacy[["date", "count"]],
        on="date",
        how="left",
        validate="one_to_one",
    )
    legacy_data["count"] = legacy_data["count"].fillna(0).astype(int)
    legacy_data["event"] = legacy_data["count"].gt(0).astype(int)
    return legacy_data


def train_model() -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    data, weather_columns = load_training_data()
    supervised, feature_columns = _build_supervised(
        data, weather_columns, "event"
    )
    positive_count = int(supervised["target"].sum())
    negative_count = len(supervised) - positive_count
    if not positive_count or not negative_count:
        raise ValueError(
            "Atlantic Vagrancy training data must contain both event and "
            "non-event days."
        )

    evaluation = _evaluate_forward_chaining(
        supervised, feature_columns, "Atlantic Vagrancy Index"
    )
    legacy_data = _load_legacy_counts(data)
    legacy_supervised, _ = _build_supervised(
        legacy_data, weather_columns, "event"
    )
    legacy_evaluation = _evaluate_forward_chaining(
        legacy_supervised,
        feature_columns,
        "Netherlands-only American Passerine prototype",
    )
    evaluations = pd.DataFrame([evaluation, legacy_evaluation])

    estimator = make_estimator(
        "Random Forest",
        positive_count,
        negative_count,
        random_forest_class_weight=None,
    )
    estimator.fit(supervised[feature_columns], supervised["target"])
    importances = pd.DataFrame(
        {
            "feature": feature_columns,
            "importance": estimator.named_steps["model"].feature_importances_,
        }
    ).sort_values("importance", ascending=False, kind="stable")

    species_summary = pd.read_csv(SPECIES_SUMMARY_FILE)
    events = pd.read_csv(EVENTS_FILE, parse_dates=["date"])
    if not {"species", "records", "unique_dates", "countries"}.issubset(
        species_summary.columns
    ):
        raise ValueError(
            f"Invalid Atlantic species summary schema: {SPECIES_SUMMARY_FILE}"
        )
    if not {"date", "count", "species_count"}.issubset(events.columns):
        raise ValueError(f"Invalid Atlantic event summary schema: {EVENTS_FILE}")
    if events["date"].isna().any() or events["date"].duplicated().any():
        raise ValueError(f"Atlantic event dates must be unique and valid: {EVENTS_FILE}")
    out_of_weather_records = int(
        species_summary["records"].sum()
        - data["count"].sum()
    )
    artifact: dict[str, object] = {
        "model": estimator,
        "feature_columns": feature_columns,
        "species": "Atlantic Vagrancy Index",
        "model_name": "Random Forest",
        "target_definition": "one or more target-guild occurrences on target date",
        "target_species": species_summary.to_dict(orient="records"),
        "target_countries": ["GB", "IE", "NL", "BE", "DK"],
        "excluded_species": ["Junco hyemalis"],
        "training_horizon_days": TRAINING_HORIZON_DAYS,
        "training_rows": len(supervised),
        "training_positive_days": positive_count,
        "training_start_date": str(supervised["target_date"].min().date()),
        "training_end_date": str(supervised["target_date"].max().date()),
        "trained_through_weather_date": str(data["date"].max().date()),
        "records_outside_weather_calendar": out_of_weather_records,
        "all_time_observation_records": int(species_summary["records"].sum()),
        "all_time_positive_days": len(events),
        **evaluation,
    }
    return artifact, importances, evaluations


def main() -> None:
    artifact, importances, evaluations = train_model()
    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_OUTPUT)
    importances.to_csv(IMPORTANCE_OUTPUT, index=False)
    evaluations.to_csv(EVALUATION_OUTPUT, index=False)
    print(
        f"Saved {artifact['model_name']} for {artifact['species']}: "
        f"{MODEL_OUTPUT.relative_to(ROOT)}"
    )
    print("\nSpecies record totals and unique dates:")
    print(pd.DataFrame(artifact["target_species"]).to_string(index=False))
    print(
        f"\nAtlantic guild: {artifact['training_positive_days']:,} positive "
        f"days in {artifact['training_rows']:,} weather dates "
        f"({artifact['full_period_prevalence']:.2%} prevalence)."
    )
    print(
        f"All-date GBIF total: {artifact['all_time_observation_records']:,} "
        f"records on {artifact['all_time_positive_days']:,} unique positive "
        "dates."
    )
    print("\nForward-chained evaluation (common weather dates):")
    print(
        evaluations[
            [
                "product",
                "roc_auc",
                "pr_auc",
                "evaluation_positive_days",
                "evaluation_prevalence",
                "true_positive",
                "false_positive",
                "false_negative",
                "true_negative",
                "data_sufficient_for_meaningful_prediction",
            ]
        ].to_string(index=False)
    )
    print(f"\nFeature importance: {IMPORTANCE_OUTPUT.relative_to(ROOT)}")
    print(importances.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
