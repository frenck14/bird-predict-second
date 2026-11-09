"""Train independent P90 event models for selected seawatch species."""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

if __package__:
    from . import build_seabird_dataset as dataset
    from .build_dataset_v2 import add_coastal_features
    from .forecast_species_comparison import make_estimator, weather_feature_columns
    from .seabird_features import add_seabird_features
    from .train_atlantic_vagrancy_model import (
        _build_supervised,
        _evaluate_forward_chaining,
        influx_cutoff,
    )
else:
    import build_seabird_dataset as dataset
    from build_dataset_v2 import add_coastal_features
    from forecast_species_comparison import make_estimator, weather_feature_columns
    from seabird_features import add_seabird_features
    from train_atlantic_vagrancy_model import (
        _build_supervised,
        _evaluate_forward_chaining,
        influx_cutoff,
    )


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
WEATHER_FILE = ROOT / "data/processed/bird_predict_dataset_v2.csv"
SPECIES_COUNTS_FILE = OUTPUTS / "seabird_species_daily_counts.csv"
MODEL_DIRECTORY = OUTPUTS
EVALUATION_OUTPUT = OUTPUTS / "seabird_species_evaluation.csv"
IMPORTANCE_OUTPUT = OUTPUTS / "seabird_species_feature_importance.csv"
PERCENTILE = 90
CLASSIFICATION_THRESHOLD = 0.20
TRAINING_HORIZON_DAYS = 1
SPECIES_NAMES = (
    "European Storm-petrel",
    "Northern Fulmar",
    "Sooty Shearwater",
    "Manx Shearwater",
    "Great Shearwater",
)
SLUGS = {
    "European Storm-petrel": "storm_petrel",
    "Northern Fulmar": "fulmar",
    "Sooty Shearwater": "sooty_shearwater",
    "Manx Shearwater": "manx_shearwater",
    "Great Shearwater": "great_shearwater",
}


def model_path(species: str, directory: Path = MODEL_DIRECTORY) -> Path:
    return directory / f"{SLUGS[species]}_model.joblib"


def _read_species_counts(species: str) -> pd.DataFrame:
    if not SPECIES_COUNTS_FILE.is_file():
        raise FileNotFoundError(
            f"Species daily counts not found: {SPECIES_COUNTS_FILE}. "
            "Run `python src/build_seabird_dataset.py` first."
        )
    counts = pd.read_csv(SPECIES_COUNTS_FILE, parse_dates=["date"])
    if not {"date", "species", "count"}.issubset(counts.columns):
        raise ValueError(
            "Seabird species daily counts must contain date, species and count."
        )
    counts = counts.loc[counts["species"].eq(species), ["date", "count"]].copy()
    if counts.empty:
        raise ValueError(f"No GBIF daily counts are available for {species}.")
    counts["date"] = pd.to_datetime(counts["date"]).dt.normalize()
    counts["count"] = pd.to_numeric(counts["count"], errors="raise")
    if (
        counts["date"].isna().any()
        or counts["date"].duplicated().any()
        or counts["count"].isna().any()
        or counts["count"].lt(0).any()
        or not np.equal(counts["count"], np.floor(counts["count"])).all()
    ):
        raise ValueError(f"Invalid date or count in {species} daily counts.")
    return counts


def load_species_training_data(
    species: str,
) -> tuple[pd.DataFrame, list[str]]:
    for path, command in (
        (WEATHER_FILE, "python src/build_dataset_v2.py"),
        (
            SPECIES_COUNTS_FILE,
            "python src/build_seabird_dataset.py",
        ),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"Required input missing: {path}. Run `{command}`.")
    weather = pd.read_csv(WEATHER_FILE, parse_dates=["date"]).sort_values("date")
    if weather["date"].isna().any() or weather["date"].duplicated().any():
        raise ValueError("Weather dataset must have unique, valid daily dates.")
    weather["date"] = weather["date"].dt.normalize()
    weather = add_seabird_features(add_coastal_features(weather))
    data = weather.merge(
        _read_species_counts(species), on="date", how="left", validate="one_to_one"
    )
    data["count"] = data["count"].fillna(0).astype(int)
    return data, weather_feature_columns(data)


def train_species_model(
    species: str,
) -> tuple[dict[str, object], dict[str, object], pd.DataFrame]:
    data, weather_columns = load_species_training_data(species)
    supervised, feature_columns = _build_supervised(data, weather_columns, "count")
    cutoff = influx_cutoff(supervised["target"], PERCENTILE)
    labels = supervised["target"].ge(cutoff).astype(int)
    positives = int(labels.sum())
    negatives = len(labels) - positives
    if not positives or not negatives:
        raise ValueError(
            f"{species} P{PERCENTILE} target has only one class "
            f"(threshold={cutoff:g}, positive_days={positives}, rows={len(labels)})."
        )

    evaluation = _evaluate_forward_chaining(
        supervised,
        feature_columns,
        f"{species} Seabird Model",
        CLASSIFICATION_THRESHOLD,
        influx_percentile=PERCENTILE,
    )
    estimator = make_estimator(
        "Random Forest", positives, negatives, random_forest_class_weight=None
    )
    estimator.fit(supervised[feature_columns], labels)
    importance = pd.DataFrame(
        {
            "species": species,
            "feature": feature_columns,
            "importance": estimator.named_steps["model"].feature_importances_,
        }
    ).sort_values("importance", ascending=False, kind="stable")
    artifact: dict[str, object] = {
        "model": estimator,
        "feature_columns": feature_columns,
        "species": species,
        "product_name": species,
        "model_name": "Random Forest",
        "target_definition": f"daily {species} count >= training P{PERCENTILE}",
        "influx_percentile": PERCENTILE,
        "influx_threshold_count": cutoff,
        "training_horizon_days": TRAINING_HORIZON_DAYS,
        "training_rows": len(supervised),
        "training_positive_days": positives,
        "training_start_date": str(supervised["target_date"].min().date()),
        "training_end_date": str(supervised["target_date"].max().date()),
        "trained_through_weather_date": str(data["date"].max().date()),
        **evaluation,
    }
    evaluation = {**evaluation, "threshold_count": cutoff}
    LOGGER.info(
        "%s: P%d count >= %g; %d/%d positive training days; sufficiency=%s",
        species,
        PERCENTILE,
        cutoff,
        positives,
        len(supervised),
        evaluation["data_sufficient_for_meaningful_prediction"],
    )
    return artifact, evaluation, importance


def train_all_species(
    output_directory: Path = MODEL_DIRECTORY,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_directory.mkdir(parents=True, exist_ok=True)
    evaluations: list[dict[str, object]] = []
    importances: list[pd.DataFrame] = []
    for number, species in enumerate(SPECIES_NAMES, start=1):
        LOGGER.info("Training seabird species model %d/%d: %s", number, len(SPECIES_NAMES), species)
        artifact, evaluation, importance = train_species_model(species)
        joblib.dump(artifact, model_path(species, output_directory))
        evaluations.append(evaluation)
        importances.append(importance)
    evaluation_frame = pd.DataFrame(evaluations)
    importance_frame = pd.concat(importances, ignore_index=True)
    evaluation_frame.to_csv(EVALUATION_OUTPUT, index=False)
    importance_frame.to_csv(IMPORTANCE_OUTPUT, index=False)
    return evaluation_frame, importance_frame


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    evaluations, _ = train_all_species()
    print(evaluations.to_string(index=False))


if __name__ == "__main__":
    main()
