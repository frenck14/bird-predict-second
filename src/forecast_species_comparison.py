"""Compare forward-chained forecasts for Bird-Predict target species."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

if __package__:
    from .build_dataset_v2 import add_coastal_features
else:
    from build_dataset_v2 import add_coastal_features


ROOT = Path(__file__).resolve().parents[1]
WEATHER_FILE = ROOT / "data/processed/bird_predict_dataset_v2.csv"
YELLOW_BROWED_DAILY_FILE = (
    ROOT / "data/processed/yellow_browed_warbler_daily_counts.csv"
)
PIPIT_FACET_FILE = ROOT / "data/raw/red_throated_pipit_event_date_facets.csv"
MANX_FACET_FILE = ROOT / "data/raw/manx_shearwater_event_date_facets.csv"
BLUETAIL_FACET_FILE = ROOT / "data/raw/blauwstaart_event_date_facets.csv"
METRICS_OUTPUT = ROOT / "data/processed/species_forecast_metrics.csv"
REPORT_OUTPUT = ROOT / "reports/species_forecast_comparison.md"

TARGET_THRESHOLDS = (10, 25, 50)
HORIZONS_DAYS = (1, 3, 5, 7, 14)
MIN_TRAIN_YEARS = 5
MONTH_PRIOR_STRENGTH = 30
CLASSIFICATION_THRESHOLD = 0.5

MODEL_NAMES = (
    "Seasonal baseline",
    "Logistic Regression",
    "Random Forest",
    "XGBoost",
)
SEASONALITY_FEATURES = (
    "month",
    "day_of_year",
    "day_of_year_sin",
    "day_of_year_cos",
)


SPECIES_TARGETS = (
    ("Pallid Swift", "pallid_swift_records"),
    ("Yellow-browed Warbler", "yellow_browed_records"),
    ("Manx Shearwater", "manx_shearwater_records"),
    ("Red-throated Pipit", "red_throated_pipit_records"),
)


def load_gbif_facet_counts(filepath: Path, column_name: str) -> pd.DataFrame:
    """Convert complete-date GBIF facet buckets to daily record totals."""
    if not filepath.is_file():
        raise FileNotFoundError(
            f"GBIF date facets not found: {filepath}. Generate the species "
            "facets with the corresponding feasibility assessment script."
        )

    daily_counts: dict[date, int] = {}
    with filepath.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if not {"name", "count"}.issubset(reader.fieldnames or []):
            raise ValueError(
                f"GBIF date facets must have name and count columns: {filepath}"
            )
        for row in reader:
            value = row["name"][:10]
            try:
                event_day = date.fromisoformat(value)
            except ValueError:
                continue
            daily_counts[event_day] = (
                daily_counts.get(event_day, 0) + int(row["count"])
            )

    return pd.DataFrame(
        {
            "date": pd.to_datetime(list(daily_counts)),
            column_name: list(daily_counts.values()),
        }
    )


def load_species_data(
    *, include_bluetail: bool = False
) -> tuple[pd.DataFrame, list[str], pd.Timestamp]:
    """Join all target labels to the shared coastal-weather calendar."""
    if not WEATHER_FILE.is_file():
        raise FileNotFoundError(
            f"Weather dataset not found: {WEATHER_FILE}. "
            "Build it with `python src/build_dataset_v2.py`."
        )
    if not YELLOW_BROWED_DAILY_FILE.is_file():
        raise FileNotFoundError(
            f"Yellow-browed Warbler daily counts not found: "
            f"{YELLOW_BROWED_DAILY_FILE}. Build them with "
            "`python src/build_yellow_browed_warbler_dataset.py`."
        )

    weather = pd.read_csv(WEATHER_FILE, parse_dates=["date"]).sort_values("date")
    if weather["date"].isna().any() or weather["date"].duplicated().any():
        raise ValueError("Weather dataset must have unique, valid daily dates.")
    weather = add_coastal_features(weather)
    yellow_browed = pd.read_csv(
        YELLOW_BROWED_DAILY_FILE, parse_dates=["date"]
    )
    required_weather = {"date", "n_records", *SEASONALITY_FEATURES}
    missing = required_weather.difference(weather.columns)
    if missing:
        raise ValueError(f"Weather dataset missing columns: {sorted(missing)}")
    if weather["date"].isna().any() or weather["date"].duplicated().any():
        raise ValueError("Weather dataset must have unique, valid daily dates.")
    if yellow_browed["date"].isna().any() or yellow_browed["date"].duplicated().any():
        raise ValueError(
            "Yellow-browed Warbler daily counts must have unique, valid dates."
        )
    if yellow_browed["record_count"].isna().any():
        raise ValueError("Yellow-browed Warbler counts must not be missing.")

    data = weather.merge(
        yellow_browed[["date", "record_count"]].rename(
            columns={"record_count": "yellow_browed_records"}
        ),
        on="date",
        how="left",
        validate="one_to_one",
    )
    data["yellow_browed_records"] = (
        data["yellow_browed_records"].fillna(0).astype(int)
    )
    data["pallid_swift_records"] = data["n_records"].astype(int)
    facet_sources = [
        (PIPIT_FACET_FILE, "red_throated_pipit_records"),
        (MANX_FACET_FILE, "manx_shearwater_records"),
    ]
    if include_bluetail:
        facet_sources.append(
            (BLUETAIL_FACET_FILE, "bluetail_records")
        )
    for filepath, column_name in facet_sources:
        facet_counts = load_gbif_facet_counts(filepath, column_name)
        if facet_counts["date"].duplicated().any():
            raise ValueError(
                f"GBIF daily counts contain duplicate dates: {filepath}"
            )
        data = data.merge(
            facet_counts,
            on="date",
            how="left",
            validate="one_to_one",
        )
        data[column_name] = data[column_name].fillna(0).astype(int)

    weather_columns = weather_feature_columns(data)

    # Both taxon models share only dates with the same observed weather.
    # Restrict forecast origins to preserve identical evaluation windows across
    # horizons and species.
    latest_origin = data["date"].max() - pd.Timedelta(days=max(HORIZONS_DAYS))
    return data.reset_index(drop=True), weather_columns, latest_origin


def weather_feature_columns(data: pd.DataFrame) -> list[str]:
    """Return the shared model's station, coastal, rolling, and lag features."""
    station_ids = ("235", "242", "225", "310")
    station_weather = [
        f"{variable}_{station_id}"
        for station_id in station_ids
        for variable in ("FG", "FHX", "TG", "TN", "TX", "RH", "PX")
        if f"{variable}_{station_id}" in data.columns
    ]
    station_wind = [
        f"{variable}_{station_id}"
        for station_id in station_ids
        for variable in ("wind_sin", "wind_cos")
        if f"{variable}_{station_id}" in data.columns
    ]
    coastal_weather = [
        column for column in data.columns if column.startswith("coast_")
    ]
    temporal_weather = [
        column
        for column in data.columns
        if "_lag_" in column
        or "_change_" in column
        or "_rolling_" in column
    ]
    observed_weather = (
        station_weather + station_wind + coastal_weather + temporal_weather
    )
    available_stations = {
        column.rsplit("_", 1)[-1] for column in station_weather
    }
    if set(station_ids).difference(available_stations):
        raise ValueError(
            "Weather dataset does not contain all four configured stations."
        )
    weather_columns = list(dict.fromkeys(observed_weather))
    if not weather_columns:
        raise ValueError("No weather features available.")
    return weather_columns


def make_estimator(
    name: str,
    positive_count: int,
    negative_count: int,
    *,
    random_forest_class_weight: str | None = "balanced_subsample",
) -> Pipeline:
    if positive_count == 0 or negative_count == 0:
        raise ValueError("Each training fold must contain both target classes.")

    if name == "Logistic Regression":
        estimator = LogisticRegression(
            class_weight="balanced", max_iter=3000, C=0.5
        )
        steps = [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("model", estimator),
        ]
    elif name == "Random Forest":
        estimator = RandomForestClassifier(
            n_estimators=300,
            min_samples_leaf=3,
            class_weight=random_forest_class_weight,
            random_state=42,
            n_jobs=-1,
        )
        steps = [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("model", estimator),
        ]
    elif name == "XGBoost":
        estimator = XGBClassifier(
            n_estimators=150,
            max_depth=2,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            reg_lambda=2,
            scale_pos_weight=negative_count / positive_count,
            eval_metric="logloss",
            n_jobs=1,
            random_state=42,
            verbosity=0,
        )
        steps = [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("model", estimator),
        ]
    else:
        raise ValueError(f"Unknown model: {name}")

    return Pipeline(steps)


def calculate_metrics(
    y_true: np.ndarray, probabilities: np.ndarray
) -> dict[str, float]:
    predicted = probabilities >= CLASSIFICATION_THRESHOLD
    has_positive = bool(np.any(y_true == 1))
    has_both_classes = np.unique(y_true).size == 2
    return {
        "roc_auc": (
            float(roc_auc_score(y_true, probabilities))
            if has_both_classes
            else float("nan")
        ),
        "pr_auc": (
            float(average_precision_score(y_true, probabilities))
            if has_positive
            else float("nan")
        ),
        "precision": float(
            precision_score(y_true, predicted, zero_division=0)
        ),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
    }


def build_horizon_data(
    data: pd.DataFrame,
    weather_columns: list[str],
    target_column: str,
    horizon_days: int,
    latest_origin: pd.Timestamp,
) -> pd.DataFrame:
    weather_features = data[weather_columns].shift(1)
    known_target_calendar = data[list(SEASONALITY_FEATURES)].shift(-horizon_days)
    supervised = pd.concat(
        [
            data[["date"]].rename(columns={"date": "origin_date"}),
            data["date"].shift(-horizon_days).rename("target_date"),
            data[target_column].shift(-horizon_days).rename("target"),
            known_target_calendar,
            weather_features,
        ],
        axis=1,
    )
    supervised = supervised.loc[
        supervised["target_date"].notna()
        & supervised["origin_date"].le(latest_origin)
    ].reset_index(drop=True)
    return supervised


def run_experiment(
    species_targets: tuple[tuple[str, str], ...] | None = None,
) -> pd.DataFrame:
    target_species = species_targets or SPECIES_TARGETS
    data, weather_columns, latest_origin = load_species_data(
        include_bluetail=any(
            name == "Bluetail" for name, _ in target_species
        )
    )
    result_rows: list[dict[str, object]] = []

    for species, count_column in target_species:
        for threshold in TARGET_THRESHOLDS:
            target_column = f"influx_ge_{threshold}"
            data[target_column] = (data[count_column] >= threshold).astype(int)

            for horizon_days in HORIZONS_DAYS:
                supervised = build_horizon_data(
                    data,
                    weather_columns,
                    target_column,
                    horizon_days,
                    latest_origin,
                )
                supervised["target"] = supervised["target"].astype(int)

                years = supervised["origin_date"].dt.year
                unique_years = np.sort(years.unique())
                if len(unique_years) <= MIN_TRAIN_YEARS:
                    raise ValueError(
                        f"Insufficient test years for {species}, threshold "
                        f">={threshold}, horizon {horizon_days}."
                    )
                test_years = unique_years[MIN_TRAIN_YEARS:]
                for test_year in test_years:
                    train = supervised.loc[
                        supervised["target_date"]
                        < pd.Timestamp(year=int(test_year), month=1, day=1)
                    ]
                    test = supervised.loc[years.eq(test_year)]
                    train_positive_count = int(train["target"].sum())
                    train_negative_count = len(train) - train_positive_count
                    if train.empty or test.empty:
                        raise RuntimeError(
                            f"Empty forward-chaining fold for {species}, "
                            f"threshold >={threshold}, horizon {horizon_days}, "
                            f"test year {test_year}."
                        )

                    overall_rate = float(train["target"].mean())
                    monthly_rates = train.groupby(
                        train["target_date"].dt.month
                    )["target"].agg(["sum", "count"])
                    smoothed_monthly_rates = (
                        monthly_rates["sum"]
                        + MONTH_PRIOR_STRENGTH * overall_rate
                    ) / (monthly_rates["count"] + MONTH_PRIOR_STRENGTH)
                    seasonal_probabilities = (
                        test["target_date"]
                        .dt.month.map(smoothed_monthly_rates)
                        .fillna(overall_rate)
                        .to_numpy(dtype=float)
                    )

                    y_test = test["target"].to_numpy(dtype=int)
                    fold_predictions: dict[str, np.ndarray] = {
                        "Seasonal baseline": seasonal_probabilities
                    }
                    feature_columns = list(SEASONALITY_FEATURES) + weather_columns
                    train_x = train[feature_columns]
                    test_x = test[feature_columns]
                    for model_name in MODEL_NAMES[1:]:
                        if train_positive_count == 0:
                            # Keep early folds in the held-out series when a
                            # rare target has not yet occurred in training.
                            fold_predictions[model_name] = np.zeros(
                                len(test), dtype=float
                            )
                            continue
                        estimator = make_estimator(
                            model_name,
                            train_positive_count,
                            train_negative_count,
                        )
                        estimator.fit(train_x, train["target"].astype(int))
                        fold_predictions[model_name] = estimator.predict_proba(
                            test_x
                        )[:, 1]

                    for model_name, probabilities in fold_predictions.items():
                        result_rows.append(
                            {
                                "species": species,
                                "threshold": threshold,
                                "horizon_days": horizon_days,
                                "model": model_name,
                                "test_year": int(test_year),
                                "train_days": len(train),
                                "train_positive_days": train_positive_count,
                                "test_days": len(test),
                                "test_positive_days": int(y_test.sum()),
                                "target_prevalence": float(y_test.mean()),
                                "y_true": y_test,
                                "probabilities": probabilities,
                            }
                        )

    return aggregate_predictions(result_rows)


def aggregate_predictions(
    fold_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Pool all forward-held-out predictions before computing each metric."""
    aggregated_rows = []
    group_keys = ("species", "threshold", "horizon_days", "model")
    for keys, group in pd.DataFrame(fold_rows).groupby(
        list(group_keys), sort=True
    ):
        y_true = np.concatenate(group["y_true"].to_list())
        probabilities = np.concatenate(group["probabilities"].to_list())
        metrics = calculate_metrics(y_true, probabilities)
        species, threshold, horizon_days, model = keys
        aggregated_rows.append(
            {
                "species": species,
                "threshold": int(threshold),
                "horizon_days": int(horizon_days),
                "model": model,
                **metrics,
                "seasonal_baseline_pr_auc": np.nan,
                "test_prevalence": float(y_true.mean()),
                "test_positive_days": int(y_true.sum()),
                "test_days": len(y_true),
                "test_years": int(group["test_year"].nunique()),
            }
        )

    metrics = pd.DataFrame(aggregated_rows)
    seasonal_scores = (
        metrics.loc[metrics["model"].eq("Seasonal baseline")]
        .set_index(["species", "threshold", "horizon_days"])["pr_auc"]
    )
    keys = zip(
        metrics["species"],
        metrics["threshold"],
        metrics["horizon_days"],
        strict=True,
    )
    metrics["seasonal_baseline_pr_auc"] = [
        seasonal_scores.loc[(species, threshold, horizon)]
        for species, threshold, horizon in keys
    ]
    metrics["beats_seasonal_pr_auc"] = (
        metrics["model"].ne("Seasonal baseline")
        & metrics["pr_auc"].gt(metrics["seasonal_baseline_pr_auc"])
    )
    metrics["beats_prevalence_baseline"] = metrics["pr_auc"].gt(
        metrics["test_prevalence"]
    )
    return metrics.sort_values(
        ["species", "threshold", "horizon_days", "model"]
    ).reset_index(drop=True)


def write_report(metrics: pd.DataFrame) -> None:
    lines = [
        "# Bird-Predict Species Forecast Comparison",
        "",
        "## Method",
        "",
        "All four species use the shared four-station coastal weather dataset and "
        "the exact same daily forecast origins, train/test folds, features, "
        "models, and decision threshold. Each target is whether the species "
        "has at least the specified number of GBIF records on the target date.",
        "",
        "Expanding annual folds use the first five calendar years as the "
        "initial training window. Each test-origin year is predicted from "
        "training examples whose target dates precede that year. The common "
        "forecast-origin window ends 14 days before the final shared weather "
        "date, so every horizon uses the same held-out dates. Predictors "
        "match the Pallid Swift full-feature scenario: station weather "
        "(excluding raw wind direction), circular wind components, coastal "
        "summaries, and weather lag/change features. They are shifted to "
        "observations available through the day before the forecast origin; "
        "target-date calendar features are known in advance. Imputation and "
        "model fitting occur inside each fold.",
        "",
        "The seasonal baseline is the month-specific training event rate, "
        f"smoothed with {MONTH_PRIOR_STRENGTH} prior-equivalent observations. "
        "Logistic Regression is class-weighted; Random Forest uses balanced "
        "subsampling; XGBoost uses the fold's negative-to-positive ratio. "
        f"Precision, recall, and F1 use a fixed probability threshold of "
        f"{CLASSIFICATION_THRESHOLD}. ROC-AUC and PR-AUC are pooled across "
        "forward-held-out predictions (PR-AUC is average precision).",
        "",
        "A horizon is called **useful beyond seasonality** if at least one "
        "weather model has higher pooled PR-AUC than the seasonal baseline. "
        "This is a descriptive comparison, not a significance test.",
        "",
        "GBIF date-facet targets (Red-throated Pipit and Manx Shearwater) "
        "aggregate buckets with complete calendar dates and use zero counts "
        "for unobserved dates. If an early training fold contains no positive "
        "examples for a target threshold, weather models predict zero for "
        "that fold; the fold remains in pooled evaluation rather than being "
        "silently removed.",
        "",
        "## Results",
        "",
    ]
    for threshold in TARGET_THRESHOLDS:
        lines.extend(
            [
                f"### Target: at least {threshold} GBIF records",
                "",
                "| Species | Horizon | Model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Baseline PR-AUC | Test prevalence | Positive test days |",
                "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        subset = metrics.loc[metrics["threshold"].eq(threshold)]
        for row in subset.itertuples(index=False):
            number = lambda value: "NA" if pd.isna(value) else f"{value:.4f}"
            lines.append(
                f"| {row.species} | {row.horizon_days} d | {row.model} | "
                f"{number(row.roc_auc)} | {number(row.pr_auc)} | "
                f"{number(row.precision)} | {number(row.recall)} | "
                f"{number(row.f1)} | {number(row.seasonal_baseline_pr_auc)} | "
                f"{number(row.test_prevalence)} | {row.test_positive_days} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Maximum useful forecasting horizon",
            "",
            "| Species | Target threshold | Maximum horizon beating seasonal PR-AUC |",
            "|---|---:|---:|",
        ]
    )
    for species, _ in SPECIES_TARGETS:
        for threshold in TARGET_THRESHOLDS:
            subset = metrics.loc[
                metrics["species"].eq(species)
                & metrics["threshold"].eq(threshold)
                & metrics["beats_seasonal_pr_auc"]
            ]
            if subset.empty:
                maximum = "None"
            else:
                maximum = f"{int(subset['horizon_days'].max())} days"
            lines.append(f"| {species} | >= {threshold} | {maximum} |")

    weather_metrics = metrics.loc[metrics["model"].ne("Seasonal baseline")]
    scenario_keys = ["species", "threshold", "horizon_days"]
    best_weather = weather_metrics.loc[
        weather_metrics.groupby(scenario_keys)["pr_auc"].idxmax()
    ]
    best_weather = best_weather.assign(
        pr_auc_lift=(
            best_weather["pr_auc"]
            - best_weather["seasonal_baseline_pr_auc"]
        ),
        beats_seasonal=(
            best_weather["pr_auc"]
            > best_weather["seasonal_baseline_pr_auc"]
        ),
    )
    forecastability = best_weather.groupby("species").agg(
        mean_best_pr_auc=("pr_auc", "mean"),
        mean_seasonal_pr_auc=("seasonal_baseline_pr_auc", "mean"),
        mean_pr_auc_lift=("pr_auc_lift", "mean"),
        mean_test_prevalence=("test_prevalence", "mean"),
        mean_f1=("f1", "mean"),
        scenarios_beating_seasonality=("beats_seasonal", "sum"),
    )
    lines.extend(
        [
            "",
            "## Which species is more forecastable?",
            "",
            "Across the 15 threshold/horizon combinations, the table below "
            "averages the highest-PR-AUC weather model in each combination. "
            "Model selection here is descriptive and is not a separate "
            "validation procedure.",
            "",
            "| Species | Mean best weather PR-AUC | Mean seasonal PR-AUC | Mean PR-AUC lift | Mean test prevalence | Mean F1 | Scenarios beating seasonality |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for species, _ in SPECIES_TARGETS:
        row = forecastability.loc[species]
        lines.append(
            f"| {species} | {row['mean_best_pr_auc']:.4f} | "
            f"{row['mean_seasonal_pr_auc']:.4f} | "
            f"{row['mean_pr_auc_lift']:.4f} | "
            f"{row['mean_test_prevalence']:.4f} | "
            f"{row['mean_f1']:.4f} | "
            f"{int(row['scenarios_beating_seasonality'])}/"
            f"{len(best_weather.loc[best_weather['species'].eq(species)])} |"
        )
    ranking = forecastability.sort_values(
        ["mean_pr_auc_lift", "scenarios_beating_seasonality"],
        ascending=[False, False],
    )
    leading_species = ranking.index[0]
    leading = forecastability.loc[leading_species]
    pipit = forecastability.loc["Red-throated Pipit"]
    lines.extend(
        [
            "",
            f"**Conclusion:** {leading_species} ranks first by mean best-model "
            "PR-AUC lift over the seasonal baseline in this comparison "
            f"({leading['mean_pr_auc_lift']:.4f}; "
            f"{int(leading['scenarios_beating_seasonality'])}/15 scenarios "
            "beating seasonality). Red-throated Pipit has mean lift "
            f"{pipit['mean_pr_auc_lift']:.4f} and beats seasonality in "
            f"{int(pipit['scenarios_beating_seasonality'])}/15 scenarios. "
            "Therefore the results do not establish Red-throated Pipit as the "
            "most meteorologically forecastable species unless it ranks first "
            "by this measure. This model-grid summary is descriptive, not a "
            "significance test or independent validation; PR-AUC also depends "
            "on event prevalence, and GBIF counts reflect reporting effort "
            "rather than abundance.",
        ]
    )
    lines.extend(
        [
            "",
            "The full metric grid, including per-horizon model results, is "
            "saved in `data/processed/species_forecast_metrics.csv`.",
            "",
            "Caveats: GBIF reporting effort is not controlled, records are "
            "not abundance estimates, high-count days cluster in episodes, "
            "and the latest year is incomplete. A PR-AUC improvement over "
            "seasonality alone does not establish prospective operational "
            "utility.",
            "",
        ]
    )

    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    metrics = run_experiment()
    METRICS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(METRICS_OUTPUT, index=False, float_format="%.8f")
    write_report(metrics)
    print(f"Metrics saved to {METRICS_OUTPUT.relative_to(ROOT)}")
    print(f"Report saved to {REPORT_OUTPUT.relative_to(ROOT)}")
    print("Pooled forward-chaining PR-AUC and maximum useful horizons:")
    print(
        metrics[
            [
                "species",
                "threshold",
                "horizon_days",
                "model",
                "pr_auc",
                "seasonal_baseline_pr_auc",
                "test_prevalence",
                "beats_seasonal_pr_auc",
            ]
        ].to_string(
            index=False,
            formatters={
                "pr_auc": "{:.4f}".format,
                "seasonal_baseline_pr_auc": "{:.4f}".format,
                "test_prevalence": "{:.4f}".format,
            },
        )
    )
    print("\nMaximum horizon beating seasonal PR-AUC:")
    summary = (
        metrics.loc[metrics["beats_seasonal_pr_auc"]]
        .groupby(["species", "threshold"])["horizon_days"]
        .max()
    )
    for species, _ in SPECIES_TARGETS:
        for threshold in TARGET_THRESHOLDS:
            horizon = summary.get((species, threshold))
            value = "none" if horizon is None else f"{int(horizon)} days"
            print(f"{species}, >={threshold}: {value}")


if __name__ == "__main__":
    main()
