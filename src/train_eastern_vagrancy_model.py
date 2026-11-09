"""Train and evaluate the Eastern Vagrancy Index arrival-day model."""

from __future__ import annotations

from pathlib import Path

import json

import joblib
import numpy as np
import pandas as pd

if __package__:
    from .build_dataset_v2 import add_coastal_features
    from .forecast_species_comparison import make_estimator, weather_feature_columns
    from .train_atlantic_vagrancy_model import (
        _build_supervised,
        _evaluate_forward_chaining,
        influx_cutoff,
    )
else:
    from build_dataset_v2 import add_coastal_features
    from forecast_species_comparison import make_estimator, weather_feature_columns
    from train_atlantic_vagrancy_model import (
        _build_supervised,
        _evaluate_forward_chaining,
        influx_cutoff,
    )


ROOT = Path(__file__).resolve().parents[1]
WEATHER_FILE = ROOT / "data/processed/bird_predict_dataset_v2.csv"
DAILY_COUNTS_FILE = ROOT / "outputs/eastern_vagrancy_daily_counts.csv"
SPECIES_SUMMARY_FILE = ROOT / "outputs/eastern_vagrancy_species_summary.csv"
EVENTS_FILE = ROOT / "outputs/eastern_vagrancy_events.csv"
PROXY_DAILY_COUNTS_FILE = (
    ROOT / "data/processed/yellow_browed_warbler_daily_counts.csv"
)
MODEL_OUTPUT = ROOT / "outputs/eastern_vagrancy_model.joblib"
EVALUATION_OUTPUT = ROOT / "outputs/eastern_vagrancy_evaluation.csv"
IMPORTANCE_OUTPUT = ROOT / "outputs/eastern_vagrancy_feature_importance.csv"
THRESHOLD_OUTPUT = ROOT / "outputs/eastern_influx_threshold.json"
COMPARISON_OUTPUT = ROOT / "outputs/eastern_target_comparison.csv"
INFLUX_PERCENTILE = 90
INTERPRETATION = "The Eastern Influx Index represents the top 10% of eastern-vagrant days."
TRAINING_HORIZON_DAYS = 1
# Confusion-matrix cut-off, shared by both target definitions so they compare.
CLASSIFICATION_THRESHOLD = 0.20
PROXY_PRODUCT = "Netherlands-only Yellow-browed Warbler proxy"


def _read_counts(path: Path, column: str, label: str) -> pd.DataFrame:
    counts = pd.read_csv(path, parse_dates=["date"])
    if not {"date", column}.issubset(counts.columns):
        raise ValueError(f"{label} must contain date and {column}.")
    if counts["date"].isna().any() or counts["date"].duplicated().any():
        raise ValueError(f"{label} must have unique, valid dates.")
    counts[column] = pd.to_numeric(counts[column], errors="raise")
    if counts[column].isna().any() or counts[column].lt(0).any():
        raise ValueError(f"{label} must be non-negative.")
    return counts[["date", column]].rename(columns={column: "count"})


def _attach_counts(weather: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    data = weather.merge(counts, on="date", how="left", validate="one_to_one")
    data["count"] = data["count"].fillna(0).astype(int)
    data["event"] = data["count"].gt(0).astype(int)
    return data


def load_training_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    for path, command in (
        (WEATHER_FILE, "python src/build_dataset_v2.py"),
        (DAILY_COUNTS_FILE, "python src/build_eastern_vagrancy_dataset.py"),
    ):
        if not path.is_file():
            raise FileNotFoundError(
                f"Required training data not found: {path}. "
                f"Build it with `{command}`."
            )
    weather = pd.read_csv(WEATHER_FILE, parse_dates=["date"]).sort_values("date")
    if weather["date"].isna().any() or weather["date"].duplicated().any():
        raise ValueError("Weather dataset must have unique, valid daily dates.")
    weather = add_coastal_features(weather)
    data = _attach_counts(
        weather,
        _read_counts(DAILY_COUNTS_FILE, "count", "Eastern Vagrancy daily counts"),
    )
    return data, weather, weather_feature_columns(data)


def train_model() -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    data, weather, weather_columns = load_training_data()
    # Target column holds the daily count; labels are derived per fold.
    supervised, feature_columns = _build_supervised(data, weather_columns, "count")
    cutoff = influx_cutoff(supervised["target"], INFLUX_PERCENTILE)
    labels = supervised["target"].ge(cutoff).astype(int)
    positive_count = int(labels.sum())
    negative_count = len(labels) - positive_count
    if not positive_count or not negative_count:
        raise ValueError("Eastern Influx training data must contain both classes.")

    influx = _evaluate_forward_chaining(
        supervised,
        feature_columns,
        "Eastern Influx Index",
        CLASSIFICATION_THRESHOLD,
        influx_percentile=INFLUX_PERCENTILE,
    )
    any_supervised = supervised.assign(target=supervised["target"].gt(0).astype(int))
    any_occurrence = _evaluate_forward_chaining(
        any_supervised,
        feature_columns,
        "Eastern Vagrancy Index (count > 0)",
        CLASSIFICATION_THRESHOLD,
    )
    evaluations = [influx, any_occurrence]
    if PROXY_DAILY_COUNTS_FILE.is_file():
        proxy_data = _attach_counts(
            weather,
            _read_counts(
                PROXY_DAILY_COUNTS_FILE, "record_count", "Yellow-browed daily counts"
            ),
        )
        proxy_supervised, _ = _build_supervised(proxy_data, weather_columns, "event")
        evaluations.append(
            _evaluate_forward_chaining(
                proxy_supervised, feature_columns, PROXY_PRODUCT,
                CLASSIFICATION_THRESHOLD,
            )
        )
    for row in evaluations:
        row["interpretation"] = INTERPRETATION

    estimator = make_estimator(
        "Random Forest", positive_count, negative_count, random_forest_class_weight=None
    )
    estimator.fit(supervised[feature_columns], labels)
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
        raise ValueError(f"Invalid Eastern species summary schema: {SPECIES_SUMMARY_FILE}")
    if not {"date", "count", "species_count"}.issubset(events.columns):
        raise ValueError(f"Invalid Eastern event summary schema: {EVENTS_FILE}")
    artifact: dict[str, object] = {
        "model": estimator,
        "feature_columns": feature_columns,
        "species": "Eastern Vagrancy Index",
        "product_name": "Eastern Influx Index",
        "model_name": "Random Forest",
        "target_definition": (
            f"daily eastern-guild count >= P{INFLUX_PERCENTILE} of training-day counts"
        ),
        "influx_percentile": INFLUX_PERCENTILE,
        "influx_threshold_count": cutoff,
        "interpretation": INTERPRETATION,
        "target_species": species_summary.to_dict(orient="records"),
        "target_countries": ["GB", "IE", "NL", "BE", "DK"],
        "training_horizon_days": TRAINING_HORIZON_DAYS,
        "training_rows": len(supervised),
        "training_positive_days": positive_count,
        "training_start_date": str(supervised["target_date"].min().date()),
        "training_end_date": str(supervised["target_date"].max().date()),
        "trained_through_weather_date": str(data["date"].max().date()),
        "records_outside_weather_calendar": int(
            species_summary["records"].sum() - data["count"].sum()
        ),
        "all_time_observation_records": int(species_summary["records"].sum()),
        "all_time_positive_days": len(events),
        **influx,
    }
    return artifact, importances, pd.DataFrame(evaluations)


def threshold_report(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "percentile": artifact["influx_percentile"],
        "threshold_count": artifact["influx_threshold_count"],
        "positive_days": artifact["training_positive_days"],
        "prevalence": artifact["full_period_prevalence"],
    }


def target_comparison(evaluations: pd.DataFrame) -> pd.DataFrame:
    labels = {
        "Eastern Vagrancy Index (count > 0)": "count_gt_0",
        "Eastern Influx Index": "count_ge_p90",
    }
    rows = evaluations.loc[evaluations["product"].isin(labels)].copy()
    rows["target_definition"] = rows["product"].map(labels)
    rows = rows.rename(
        columns={
            "full_period_positive_days": "positive_days",
            "full_period_prevalence": "prevalence",
            "true_positive": "tp",
            "false_positive": "fp",
            "true_negative": "tn",
            "false_negative": "fn",
        }
    )
    rows = rows.set_index("target_definition").loc[["count_gt_0", "count_ge_p90"]]
    return rows.reset_index()[
        ["target_definition", "positive_days", "prevalence", "roc_auc", "pr_auc",
         "tp", "fp", "tn", "fn"]
    ]


def main() -> None:
    artifact, importances, evaluations = train_model()
    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_OUTPUT)
    importances.to_csv(IMPORTANCE_OUTPUT, index=False)
    evaluations.to_csv(EVALUATION_OUTPUT, index=False)
    THRESHOLD_OUTPUT.write_text(
        json.dumps(threshold_report(artifact), indent=2) + "\n", encoding="utf-8"
    )
    target_comparison(evaluations).to_csv(COMPARISON_OUTPUT, index=False)
    print(f"Saved {artifact['model_name']} for {artifact['species']}: "
          f"{MODEL_OUTPUT.relative_to(ROOT)}")
    print("\nSpecies record totals and unique dates:")
    print(pd.DataFrame(artifact["target_species"]).to_string(index=False))
    print(
        f"\n{INTERPRETATION}\n"
        f"P{INFLUX_PERCENTILE} threshold count: {artifact['influx_threshold_count']:g}; "
        f"{artifact['training_positive_days']:,} positive days in "
        f"{artifact['training_rows']:,} weather dates "
        f"({artifact['full_period_prevalence']:.2%} prevalence). "
        f"Sufficient: {artifact['data_sufficient_for_meaningful_prediction']}"
    )
    print("\nForward-chained evaluation (common weather dates):")
    print(
        evaluations[
            [
                "product", "roc_auc", "pr_auc", "evaluation_positive_days",
                "evaluation_prevalence", "true_positive", "false_positive",
                "false_negative", "true_negative",
                "data_sufficient_for_meaningful_prediction",
            ]
        ].to_string(index=False)
    )
    print(f"\nFeature importance: {IMPORTANCE_OUTPUT.relative_to(ROOT)}")
    print(importances.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
