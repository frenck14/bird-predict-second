"""Train and save the experiment's best Yellow-browed Warbler model."""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

if __package__:
    from .forecast_species_comparison import (
        HORIZONS_DAYS,
        METRICS_OUTPUT,
        SEASONALITY_FEATURES,
        build_horizon_data,
        load_species_data,
        make_estimator,
    )
else:
    from forecast_species_comparison import (
        HORIZONS_DAYS,
        METRICS_OUTPUT,
        SEASONALITY_FEATURES,
        build_horizon_data,
        load_species_data,
        make_estimator,
    )


ROOT = Path(__file__).resolve().parents[1]
MODEL_OUTPUT = ROOT / "outputs/yellow_browed_model.joblib"


def train_model() -> dict[str, object]:
    if not METRICS_OUTPUT.is_file():
        raise FileNotFoundError(
            f"Forecast metrics not found: {METRICS_OUTPUT}. "
            "Run `python src/forecast_species_comparison.py` first."
        )
    metrics = pd.read_csv(METRICS_OUTPUT)
    candidates = metrics.loc[
        metrics["species"].eq("Yellow-browed Warbler")
        & metrics["model"].ne("Seasonal baseline")
    ]
    if candidates.empty or candidates["pr_auc"].isna().all():
        raise ValueError("No valid Yellow-browed Warbler model results found.")
    best = candidates.loc[candidates["pr_auc"].idxmax()]

    data, weather_columns, latest_origin = load_species_data()
    threshold = int(best["threshold"])
    horizon_days = int(best["horizon_days"])
    model_name = str(best["model"])
    if horizon_days not in HORIZONS_DAYS:
        raise ValueError(f"Unsupported forecast horizon: {horizon_days}")

    data["yellow_browed_target"] = (
        data["yellow_browed_records"] >= threshold
    ).astype(int)
    supervised = build_horizon_data(
        data,
        weather_columns,
        "yellow_browed_target",
        horizon_days,
        latest_origin,
    )
    supervised["target"] = supervised["target"].astype(int)
    positive_count = int(supervised["target"].sum())
    negative_count = len(supervised) - positive_count
    if not positive_count or not negative_count:
        raise ValueError("Full training data must contain both target classes.")

    feature_columns = list(SEASONALITY_FEATURES) + weather_columns
    estimator = make_estimator(
        model_name, positive_count, negative_count
    )
    estimator.fit(supervised[feature_columns], supervised["target"])
    return {
        "model": estimator,
        "feature_columns": feature_columns,
        "species": "Yellow-browed Warbler",
        "target_threshold": threshold,
        "training_horizon_days": horizon_days,
        "model_name": model_name,
        "experiment_pr_auc": float(best["pr_auc"]),
        "experiment_roc_auc": float(best["roc_auc"]),
        "experiment_f1": float(best["f1"]),
        "training_rows": len(supervised),
        "training_positive_rows": positive_count,
        "training_start_date": str(supervised["target_date"].min().date()),
        "training_end_date": str(supervised["target_date"].max().date()),
        "trained_through_weather_date": str(data["date"].max().date()),
    }


def main() -> None:
    artifact = train_model()
    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_OUTPUT)
    print(f"Saved {artifact['model_name']} model: {MODEL_OUTPUT.relative_to(ROOT)}")
    print(
        f"Target >= {artifact['target_threshold']} records, "
        f"{artifact['training_horizon_days']}-day horizon; "
        f"experiment PR-AUC {artifact['experiment_pr_auc']:.4f}, "
        f"ROC-AUC {artifact['experiment_roc_auc']:.4f}."
    )
    print(
        f"Training dates: {artifact['training_start_date']} to "
        f"{artifact['training_end_date']} "
        f"({artifact['training_rows']} rows, "
        f"{artifact['training_positive_rows']} positive)."
    )


if __name__ == "__main__":
    main()
