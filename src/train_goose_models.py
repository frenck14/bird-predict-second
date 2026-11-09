"""Train and evaluate the Winter Goose Module models.

Models (all next-day, winter days only, Oct-Mar):

* Goose Activity: probability that the pooled common-goose record count is
  above normal, i.e. at or above the P75 of that winter's daily counts.
* One model per rare goose: probability that the species' pooled
  NL/BE/DE/DK record count is at or above the P80 of that winter's counts
  (never below 1 record).

Labels are relative to each winter so GBIF observer growth does not become a
trend the model could learn. Evaluation is forward-chained by winter. The
out-of-fold leave-one-winter-out probabilities written to
``goose_historical_scores.csv`` give an honest historical distribution for the
percentile and P5-P95 scaling steps.
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

if __package__:
    from .build_dataset_v2 import add_coastal_features
    from .build_goose_dataset import (
        COMMON_GEESE, DAILY_OUTPUT, GOOSE_SPECIES, WINTER_MONTHS, countries_for,
    )
    from .forecast_species_comparison import make_estimator, weather_feature_columns
    from .goose_features import (
        GOOSE_FEATURE_COLUMNS, SEASONALITY_COLUMNS, add_goose_features, seasonality,
    )
else:
    from build_dataset_v2 import add_coastal_features
    from build_goose_dataset import (
        COMMON_GEESE, DAILY_OUTPUT, GOOSE_SPECIES, WINTER_MONTHS, countries_for,
    )
    from forecast_species_comparison import make_estimator, weather_feature_columns
    from goose_features import (
        GOOSE_FEATURE_COLUMNS, SEASONALITY_COLUMNS, add_goose_features, seasonality,
    )


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
WEATHER_FILE = ROOT / "data/processed/bird_predict_dataset_v2.csv"
EVALUATION_OUTPUT = OUTPUTS / "goose_model_evaluation.csv"
IMPORTANCE_OUTPUT = OUTPUTS / "goose_feature_importance.csv"
HISTORICAL_SCORES_OUTPUT = OUTPUTS / "goose_historical_scores.csv"
COMPARISON_OUTPUT = OUTPUTS / "goose_model_comparison.csv"

ACTIVITY_MODEL = "Goose Activity"
ACTIVITY_PERCENTILE = 75
RARE_PERCENTILE = 80
MIN_TRAIN_WINTERS = 4
MIN_POSITIVES_FOR_MODEL = 10
SUFFICIENT_EVENTS = 50
SUFFICIENT_HELD_OUT_EVENTS = 20
BETA_EVENTS = 30
BETA_HELD_OUT_EVENTS = 10
PRODUCTION_ROC_AUC = 0.65
BETA_ROC_AUC = 0.55
MODEL_SLUGS = {
    ACTIVITY_MODEL: "goose_activity",
    "Red-breasted Goose": "red_breasted_goose",
    "Lesser White-fronted Goose": "lesser_white_fronted_goose",
    "Snow Goose": "snow_goose",
    "Ross's Goose": "rosss_goose",
    "Black Brant": "black_brant",
}
MODEL_NAMES = list(MODEL_SLUGS)


def model_path(name: str, directory: Path = OUTPUTS) -> Path:
    return directory / f"{MODEL_SLUGS[name]}_model.joblib"


def winter_id(dates: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    """Winter season label: Oct-Dec of Y and Jan-Mar of Y+1 share Y."""
    dates = pd.DatetimeIndex(dates)
    return np.where(dates.month >= 7, dates.year, dates.year - 1)


def feature_frame(weather: pd.DataFrame) -> pd.DataFrame:
    """Shared coastal + goose features for a continuous daily weather frame."""
    return add_goose_features(add_coastal_features(weather))


def load_weather() -> pd.DataFrame:
    if not WEATHER_FILE.is_file():
        raise FileNotFoundError(
            f"Weather dataset missing: {WEATHER_FILE}. Run `python src/build_dataset_v2.py`."
        )
    weather = pd.read_csv(WEATHER_FILE, parse_dates=["date"]).sort_values("date")
    weather["date"] = weather["date"].dt.normalize()
    return weather.drop(
        columns=["month", "day_of_year", "day_of_year_sin", "day_of_year_cos"],
        errors="ignore",
    )


def load_counts(path: Path = DAILY_OUTPUT) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(
            f"Goose daily counts missing: {path}. Run `python src/build_goose_dataset.py`."
        )
    counts = pd.read_csv(path, parse_dates=["date"])
    if not {"date", "species", "count"}.issubset(counts.columns):
        raise ValueError("Goose daily counts must contain date, species and count.")
    return counts


def model_feature_columns(features: pd.DataFrame) -> list[str]:
    weather_columns = [
        column for column in weather_feature_columns(features)
        if column not in GOOSE_FEATURE_COLUMNS
    ]
    return list(SEASONALITY_COLUMNS) + weather_columns + list(GOOSE_FEATURE_COLUMNS)


def daily_target_counts(counts: pd.DataFrame, name: str) -> pd.Series:
    """Pooled common-goose count for the activity model, else the species' count."""
    species = COMMON_GEESE if name == ACTIVITY_MODEL else [name]
    subset = counts.loc[counts["species"].isin(species)]
    return subset.groupby("date")["count"].sum()


def winter_relative_labels(
    target_dates: pd.DatetimeIndex, series: pd.Series, percentile: float
) -> tuple[np.ndarray, dict[int, float]]:
    """Label days at or above the winter's own percentile (minimum 1 record)."""
    counts = series.reindex(target_dates).fillna(0).to_numpy(dtype=float)
    seasons = winter_id(target_dates)
    labels = np.zeros(len(counts), dtype=int)
    cutoffs: dict[int, float] = {}
    for season in np.unique(seasons):
        mask = seasons == season
        cutoff = max(float(np.percentile(counts[mask], percentile)), 1.0)
        cutoffs[int(season)] = cutoff
        labels[mask] = (counts[mask] >= cutoff).astype(int)
    return labels, cutoffs


def build_supervised(
    features: pd.DataFrame, feature_columns: list[str], counts: pd.Series, percentile: float
) -> pd.DataFrame:
    """Weather at date d predicts the label of d+1; winter target days only."""
    indexed = features.set_index("date").sort_index()
    target_dates = indexed.index + pd.Timedelta(days=1)
    keep = target_dates.month.isin(WINTER_MONTHS) & (target_dates <= indexed.index.max())
    origin_dates = indexed.index[keep]
    targets = target_dates[keep]
    labels, _ = winter_relative_labels(targets, counts, percentile)
    calendar = seasonality(targets).set_index(origin_dates)
    weather_columns = [c for c in feature_columns if c not in SEASONALITY_COLUMNS]
    frame = pd.concat([calendar, indexed.loc[origin_dates, weather_columns]], axis=1)
    frame["origin_date"] = origin_dates
    frame["target_date"] = targets
    frame["winter"] = winter_id(targets)
    frame["label"] = labels
    return frame.reset_index(drop=True)


def monthly_baseline(frame: pd.DataFrame) -> dict[int, float]:
    """Smoothed monthly event rate, used when a species has too few events."""
    overall = (frame["label"].sum() + 0.5) / (len(frame) + 1.0)
    rates = {}
    for month, group in frame.groupby("month"):
        rates[int(month)] = float((group["label"].sum() + overall * 5) / (len(group) + 5))
    return rates


def predict_with_artifact(artifact: dict[str, object], inputs: pd.DataFrame) -> np.ndarray:
    """Probabilities from a trained model, or the monthly baseline if untrained."""
    if artifact["model"] is None:
        rates = artifact["monthly_baseline"]
        fallback = float(np.mean(list(rates.values()))) if rates else 0.0
        return np.array([rates.get(int(m), fallback) for m in inputs["month"]], dtype=float)
    return artifact["model"].predict_proba(inputs[artifact["feature_columns"]])[:, 1]


def _fit(frame: pd.DataFrame, feature_columns: list[str]) -> dict[str, object]:
    positives = int(frame["label"].sum())
    negatives = len(frame) - positives
    artifact: dict[str, object] = {
        "model": None, "feature_columns": feature_columns,
        "monthly_baseline": monthly_baseline(frame),
    }
    if positives >= MIN_POSITIVES_FOR_MODEL and negatives >= MIN_POSITIVES_FOR_MODEL:
        estimator = make_estimator("Random Forest", positives, negatives, random_forest_class_weight=None)
        estimator.fit(frame[feature_columns], frame["label"])
        artifact["model"] = estimator
    return artifact


def out_of_fold_probabilities(
    frame: pd.DataFrame, feature_columns: list[str], *, forward: bool
) -> pd.Series:
    """Forward-chained (train on earlier winters) or leave-one-winter-out."""
    winters = np.sort(frame["winter"].unique())
    result = pd.Series(np.nan, index=frame.index)
    for index, winter in enumerate(winters):
        if forward and index < MIN_TRAIN_WINTERS:
            continue
        train = frame.loc[frame["winter"] < winter] if forward else frame.loc[frame["winter"] != winter]
        test = frame.loc[frame["winter"] == winter]
        result.loc[test.index] = predict_with_artifact(_fit(train, feature_columns), test)
    return result


def evaluation_status(sufficient: bool, positives: int, held_out: int, roc_auc: float) -> str:
    if sufficient and roc_auc >= PRODUCTION_ROC_AUC:
        return "Production"
    if positives >= BETA_EVENTS and held_out >= BETA_HELD_OUT_EVENTS and roc_auc >= BETA_ROC_AUC:
        return "Beta"
    return "Experimental"


def evaluate(frame: pd.DataFrame, probabilities: pd.Series, name: str) -> dict[str, object]:
    scored = frame.loc[probabilities.notna()]
    y_true = scored["label"].to_numpy()
    y_probability = probabilities.loc[scored.index].to_numpy()
    positives = int(frame["label"].sum())
    held_out = int(y_true.sum())
    both = np.unique(y_true).size == 2
    roc_auc = float(roc_auc_score(y_true, y_probability)) if both else float("nan")
    pr_auc = float(average_precision_score(y_true, y_probability)) if held_out else float("nan")
    sufficient = positives >= SUFFICIENT_EVENTS and held_out >= SUFFICIENT_HELD_OUT_EVENTS
    return {
        "model": name,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "training_records": len(frame),
        "positive_events": positives,
        "evaluation_records": len(scored),
        "evaluation_positive_events": held_out,
        "evaluation_prevalence": float(y_true.mean()) if len(y_true) else float("nan"),
        "data_sufficiency": sufficient,
        "sufficiency_rule": (
            f"at least {SUFFICIENT_EVENTS} event days and "
            f"{SUFFICIENT_HELD_OUT_EVENTS} held-out event days"
        ),
        "status": evaluation_status(sufficient, positives, held_out, roc_auc)
        if not np.isnan(roc_auc) else "Experimental",
    }


def build_comparison_report(
    current: pd.DataFrame, previous_metrics: pd.DataFrame
) -> pd.DataFrame:
    """Compare current fold metrics with the preserved pre-expansion baseline."""
    comparison = current[["model", "roc_auc", "pr_auc"]].rename(
        columns={"roc_auc": "roc_auc_after", "pr_auc": "pr_auc_after"}
    ).merge(previous_metrics.reset_index(), on="model", how="left", validate="one_to_one")
    comparison["roc_auc_change"] = comparison["roc_auc_after"] - comparison["roc_auc_before"]
    comparison["pr_auc_change"] = comparison["pr_auc_after"] - comparison["pr_auc_before"]
    return comparison[
        [
            "model", "roc_auc_before", "roc_auc_after", "pr_auc_before",
            "pr_auc_after", "roc_auc_change", "pr_auc_change",
        ]
    ]


def train_all(
    output_directory: Path = OUTPUTS,
    names: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    names = names or MODEL_NAMES
    output_directory.mkdir(parents=True, exist_ok=True)
    if COMPARISON_OUTPUT.is_file():
        previous = pd.read_csv(COMPARISON_OUTPUT)
        previous_metrics = previous.set_index("model")[
            ["roc_auc_before", "pr_auc_before"]
        ]
    elif EVALUATION_OUTPUT.is_file():
        previous = pd.read_csv(EVALUATION_OUTPUT)
        previous_metrics = previous.set_index("model")[["roc_auc", "pr_auc"]].rename(
            columns={"roc_auc": "roc_auc_before", "pr_auc": "pr_auc_before"}
        )
    else:
        previous_metrics = pd.DataFrame(
            columns=["roc_auc_before", "pr_auc_before"], dtype=float
        )
    features = feature_frame(load_weather())
    counts = load_counts()
    feature_columns = model_feature_columns(features)
    evaluations, importances = [], []
    history: dict[str, pd.Series] = {}
    for number, name in enumerate(names, start=1):
        LOGGER.info("Training goose model %d/%d: %s", number, len(names), name)
        percentile = ACTIVITY_PERCENTILE if name == ACTIVITY_MODEL else RARE_PERCENTILE
        frame = build_supervised(features, feature_columns, daily_target_counts(counts, name), percentile)
        evaluation = evaluate(frame, out_of_fold_probabilities(frame, feature_columns, forward=True), name)
        history[name] = out_of_fold_probabilities(frame, feature_columns, forward=False).set_axis(
            frame["target_date"]
        )
        artifact = _fit(frame, feature_columns)
        artifact.update(
            {
                "product_name": name,
                "model_name": "Random Forest" if artifact["model"] is not None else "Monthly baseline",
                "event_percentile": percentile,
                "training_records": len(frame),
                "training_positive_events": int(frame["label"].sum()),
                "training_start_date": str(frame["target_date"].min().date()),
                "training_end_date": str(frame["target_date"].max().date()),
                "status": evaluation["status"],
                "countries": (
                    list(countries_for(next(
                        entry for entry in GOOSE_SPECIES
                        if entry["species"] == name
                    )))
                    if name != ACTIVITY_MODEL else ["NL"]
                ),
                **{k: evaluation[k] for k in ("roc_auc", "pr_auc", "data_sufficiency")},
            }
        )
        evaluation["model_type"] = artifact["model_name"]
        joblib.dump(artifact, model_path(name, output_directory))
        if artifact["model"] is not None:
            importance = pd.DataFrame(
                {"model": name, "feature": feature_columns,
                 "importance": artifact["model"].named_steps["model"].feature_importances_}
            ).sort_values("importance", ascending=False, kind="stable")
            importance["rank"] = np.arange(1, len(importance) + 1)
            importances.append(importance)
        evaluations.append(evaluation)
        LOGGER.info("%s: %s", name, evaluation)
    evaluation_frame = pd.DataFrame(evaluations)
    importance_frame = (
        pd.concat(importances, ignore_index=True) if importances
        else pd.DataFrame(columns=["model", "feature", "importance", "rank"])
    )
    scores = pd.DataFrame(history)
    scores.index.name = "date"
    comparison = build_comparison_report(evaluation_frame, previous_metrics)
    evaluation_frame.to_csv(EVALUATION_OUTPUT, index=False)
    importance_frame.to_csv(IMPORTANCE_OUTPUT, index=False)
    scores.reset_index().to_csv(HISTORICAL_SCORES_OUTPUT, index=False, date_format="%Y-%m-%d")
    comparison.to_csv(COMPARISON_OUTPUT, index=False)
    return evaluation_frame, importance_frame, scores


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    evaluations, _, _ = train_all()
    print(evaluations.drop(columns=["sufficiency_rule"]).to_string(index=False))


if __name__ == "__main__":
    main()
