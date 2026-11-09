"""Train and evaluate the Seabird Index (good seawatching day) model."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

if __package__:
    from .build_dataset_v2 import add_coastal_features
    from .forecast_species_comparison import make_estimator, weather_feature_columns
    from .seabird_features import add_seabird_features
    from .train_atlantic_vagrancy_model import (
        _build_supervised,
        _evaluate_forward_chaining,
        influx_cutoff,
    )
    from .train_eastern_vagrancy_model import _attach_counts, _read_counts
else:
    from build_dataset_v2 import add_coastal_features
    from forecast_species_comparison import make_estimator, weather_feature_columns
    from seabird_features import add_seabird_features
    from train_atlantic_vagrancy_model import (
        _build_supervised,
        _evaluate_forward_chaining,
        influx_cutoff,
    )
    from train_eastern_vagrancy_model import _attach_counts, _read_counts


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
WEATHER_FILE = ROOT / "data/processed/bird_predict_dataset_v2.csv"
DAILY_COUNTS_FILE = OUTPUTS / "seabird_daily_counts.csv"
SPECIES_SUMMARY_FILE = OUTPUTS / "seabird_species_summary.csv"
EVENTS_FILE = OUTPUTS / "seabird_events.csv"
MODEL_OUTPUT = OUTPUTS / "seabird_model.joblib"
EVALUATION_OUTPUT = OUTPUTS / "seabird_evaluation.csv"
IMPORTANCE_OUTPUT = OUTPUTS / "seabird_feature_importance.csv"
THRESHOLD_OUTPUT = OUTPUTS / "seabird_threshold.json"
COMPARISON_OUTPUT = OUTPUTS / "index_comparison.csv"
EASTERN_EVALUATION_FILE = OUTPUTS / "eastern_vagrancy_evaluation.csv"
ATLANTIC_EVALUATION_FILE = OUTPUTS / "atlantic_vagrancy_evaluation.csv"
INFLUX_PERCENTILE = 90
TRAINING_HORIZON_DAYS = 1
# Same confusion-matrix cut-off as the Eastern Influx Index (also P90 target).
CLASSIFICATION_THRESHOLD = 0.20
PRODUCT_NAME = "Seabird Index"
INTERPRETATION = "The Seabird Index represents the top 10% of seabird-event days."
COMPARISON_COLUMNS = [
    "model", "positive_days", "prevalence", "roc_auc", "pr_auc", "tp", "fp", "tn", "fn",
]
YELLOW_BROWED_PROXY = "Netherlands-only Yellow-browed Warbler proxy"


def build_features(weather: pd.DataFrame) -> pd.DataFrame:
    return add_seabird_features(add_coastal_features(weather))


def load_training_data() -> tuple[pd.DataFrame, list[str]]:
    for path, command in (
        (WEATHER_FILE, "python src/build_dataset_v2.py"),
        (DAILY_COUNTS_FILE, "python src/build_seabird_dataset.py"),
    ):
        if not path.is_file():
            raise FileNotFoundError(
                f"Required training data not found: {path}. "
                f"Build it with `{command}`."
            )
    weather = pd.read_csv(WEATHER_FILE, parse_dates=["date"]).sort_values("date")
    if weather["date"].isna().any() or weather["date"].duplicated().any():
        raise ValueError("Weather dataset must have unique, valid daily dates.")
    data = _attach_counts(
        build_features(weather),
        _read_counts(DAILY_COUNTS_FILE, "count", "Seabird daily counts"),
    )
    return data, weather_feature_columns(data)


def train_model() -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    data, weather_columns = load_training_data()
    supervised, feature_columns = _build_supervised(data, weather_columns, "count")
    cutoff = influx_cutoff(supervised["target"], INFLUX_PERCENTILE)
    labels = supervised["target"].ge(cutoff).astype(int)
    positive_count = int(labels.sum())
    negative_count = len(labels) - positive_count
    if not positive_count or not negative_count:
        raise ValueError("Seabird training data must contain both classes.")

    evaluation = _evaluate_forward_chaining(
        supervised,
        feature_columns,
        PRODUCT_NAME,
        CLASSIFICATION_THRESHOLD,
        influx_percentile=INFLUX_PERCENTILE,
    )
    evaluation["interpretation"] = INTERPRETATION

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
        raise ValueError(f"Invalid seabird species summary schema: {SPECIES_SUMMARY_FILE}")
    if not {"date", "count", "species_count"}.issubset(events.columns):
        raise ValueError(f"Invalid seabird event summary schema: {EVENTS_FILE}")
    artifact: dict[str, object] = {
        "model": estimator,
        "feature_columns": feature_columns,
        "species": PRODUCT_NAME,
        "product_name": PRODUCT_NAME,
        "model_name": "Random Forest",
        "target_definition": (
            f"daily seabird-guild count >= P{INFLUX_PERCENTILE} of training-day counts"
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
        **evaluation,
    }
    return artifact, importances, pd.DataFrame([evaluation])


def threshold_report(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "percentile": artifact["influx_percentile"],
        "threshold_count": artifact["influx_threshold_count"],
        "positive_days": artifact["training_positive_days"],
        "prevalence": artifact["full_period_prevalence"],
    }


def _comparison_row(model: str, row: pd.Series) -> dict[str, object]:
    return {
        "model": model,
        "positive_days": int(row["full_period_positive_days"]),
        "prevalence": float(row["full_period_prevalence"]),
        "roc_auc": float(row["roc_auc"]),
        "pr_auc": float(row["pr_auc"]),
        "tp": int(row["true_positive"]),
        "fp": int(row["false_positive"]),
        "tn": int(row["true_negative"]),
        "fn": int(row["false_negative"]),
    }


def index_comparison(
    seabird_evaluation: pd.DataFrame,
    eastern_path: Path = EASTERN_EVALUATION_FILE,
    atlantic_path: Path = ATLANTIC_EVALUATION_FILE,
) -> pd.DataFrame:
    """Compare the four flagship models using each model's evaluation CSV.

    Confusion matrices use each model's own cut-off (0.05 Atlantic, 0.20
    Eastern, Seabird and the Yellow-browed proxy), so tp/fp/tn/fn are not
    directly comparable across rows.
    """
    rows = []
    eastern = pd.read_csv(eastern_path).set_index("product")
    for label, product in (
        ("Yellow-browed Warbler", YELLOW_BROWED_PROXY),
        ("Eastern Influx Index", "Eastern Influx Index"),
    ):
        if product in eastern.index:
            rows.append(_comparison_row(label, eastern.loc[product]))
    atlantic = pd.read_csv(atlantic_path)
    if not atlantic.empty:
        rows.append(_comparison_row("Atlantic Vagrancy Index", atlantic.iloc[0]))
    rows.append(_comparison_row(PRODUCT_NAME, seabird_evaluation.iloc[0]))
    return pd.DataFrame(rows, columns=COMPARISON_COLUMNS)


def main() -> None:
    artifact, importances, evaluations = train_model()
    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_OUTPUT)
    importances.to_csv(IMPORTANCE_OUTPUT, index=False)
    evaluations.to_csv(EVALUATION_OUTPUT, index=False)
    THRESHOLD_OUTPUT.write_text(
        json.dumps(threshold_report(artifact), indent=2) + "\n", encoding="utf-8"
    )
    comparison = index_comparison(evaluations)
    comparison.to_csv(COMPARISON_OUTPUT, index=False)
    result = evaluations.iloc[0]
    print(f"Saved {artifact['model_name']} for {artifact['species']}: "
          f"{MODEL_OUTPUT.relative_to(ROOT)}")
    print("\nSpecies record totals and unique dates:")
    print(pd.DataFrame(artifact["target_species"]).to_string(index=False))
    print(
        f"\n{INTERPRETATION}\n"
        f"P{INFLUX_PERCENTILE} threshold count: {artifact['influx_threshold_count']:g}; "
        f"{artifact['training_positive_days']:,} positive days in "
        f"{artifact['training_rows']:,} rows "
        f"({artifact['full_period_prevalence']:.1%} prevalence)"
    )
    print(
        f"ROC AUC {result['roc_auc']:.3f}; PR AUC {result['pr_auc']:.3f}; "
        f"confusion (TN/FP/FN/TP) at {CLASSIFICATION_THRESHOLD:.2f}: "
        f"{int(result['true_negative'])}/{int(result['false_positive'])}/"
        f"{int(result['false_negative'])}/{int(result['true_positive'])}"
    )
    print(f"Data sufficient: {result['data_sufficient_for_meaningful_prediction']} "
          f"({result['sufficiency_rule']})")
    print("\nTop features:")
    print(importances.head(15).to_string(index=False))
    print("\nIndex comparison:")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
