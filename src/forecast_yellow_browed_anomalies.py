"""Forward-chain forecasts of exceptional Yellow-browed Warbler count days."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import shap

if __package__:
    from .forecast_species_comparison import (
        HORIZONS_DAYS,
        MIN_TRAIN_YEARS,
        SEASONALITY_FEATURES,
        calculate_metrics,
        load_species_data,
        make_estimator,
    )
else:
    from forecast_species_comparison import (
        HORIZONS_DAYS,
        MIN_TRAIN_YEARS,
        SEASONALITY_FEATURES,
        calculate_metrics,
        load_species_data,
        make_estimator,
    )


ROOT = Path(__file__).resolve().parents[1]
ANOMALY_OUTPUT = ROOT / "data/processed/yellow_browed_daily_anomalies.csv"
METRICS_OUTPUT = (
    ROOT / "data/processed/yellow_browed_anomaly_forecast_metrics.csv"
)
SHAP_OUTPUT = ROOT / "data/processed/yellow_browed_anomaly_shap_importance.csv"
REPORT_OUTPUT = ROOT / "reports/yellow_browed_anomaly_forecast.md"

ANOMALY_THRESHOLDS = (2, 4, 8)
DAY_OF_YEAR_WINDOW = 7
CLIMATOLOGY_PRIOR_STRENGTH = 30
MODEL_NAMES = ("Logistic Regression", "Random Forest", "XGBoost")


def calendar_day_numbers(dates: pd.Series) -> np.ndarray:
    """Map dates onto leap-year day numbers so calendar days align by month/day."""
    return pd.to_datetime(
        "2000-" + dates.dt.strftime("%m-%d"), errors="raise"
    ).dt.dayofyear.to_numpy()


def add_forward_expected_counts(data: pd.DataFrame) -> pd.DataFrame:
    """Estimate each date's climatology using earlier calendar years only."""
    result = data.copy().sort_values("date").reset_index(drop=True)
    result["calendar_day"] = calendar_day_numbers(result["date"])
    years = result["date"].dt.year.to_numpy()
    calendar_days = result["calendar_day"].to_numpy()
    counts = result["yellow_browed_records"].to_numpy(dtype=float)
    expected_counts = np.full(len(result), np.nan, dtype=float)

    for year in np.unique(years):
        year_positions = np.flatnonzero(years == year)
        history_positions = np.flatnonzero(years < year)
        if history_positions.size == 0:
            continue
        history_mean = float(counts[history_positions].mean())
        history_days = calendar_days[history_positions]
        history_counts = counts[history_positions]

        for position in year_positions:
            day_distance = np.abs(history_days - calendar_days[position])
            day_distance = np.minimum(day_distance, 366 - day_distance)
            neighborhood = day_distance <= DAY_OF_YEAR_WINDOW
            neighborhood_count = int(neighborhood.sum())
            expected_counts[position] = (
                history_counts[neighborhood].sum()
                + CLIMATOLOGY_PRIOR_STRENGTH * history_mean
            ) / (neighborhood_count + CLIMATOLOGY_PRIOR_STRENGTH)

    result["expected_count"] = expected_counts
    result["anomaly"] = (
        result["yellow_browed_records"] - result["expected_count"]
    )
    result["anomaly_ratio"] = (
        result["yellow_browed_records"] / result["expected_count"]
    )
    for threshold in ANOMALY_THRESHOLDS:
        result[f"anomaly_ge_{threshold}"] = (
            result["anomaly_ratio"] >= threshold
        ).astype("boolean")
        result.loc[
            result["expected_count"].isna(), f"anomaly_ge_{threshold}"
        ] = pd.NA
    return result


def create_supervised(
    data: pd.DataFrame,
    weather_columns: list[str],
    horizon_days: int,
    latest_origin: pd.Timestamp,
    threshold: int,
) -> pd.DataFrame:
    weather_features = data[weather_columns].shift(1)
    target_calendar = data[list(SEASONALITY_FEATURES)].shift(-horizon_days)
    supervised = pd.concat(
        [
            data["date"].rename("origin_date"),
            data["date"].shift(-horizon_days).rename("target_date"),
            data[f"anomaly_ge_{threshold}"]
            .shift(-horizon_days)
            .rename("target"),
            data["yellow_browed_records"]
            .shift(-horizon_days)
            .rename("observed_count"),
            data["expected_count"]
            .shift(-horizon_days)
            .rename("expected_count"),
            data["anomaly"]
            .shift(-horizon_days)
            .rename("anomaly"),
            data["anomaly_ratio"]
            .shift(-horizon_days)
            .rename("anomaly_ratio"),
            target_calendar,
            weather_features,
        ],
        axis=1,
    )
    return supervised.loc[
        supervised["target_date"].notna()
        & supervised["origin_date"].le(latest_origin)
        & supervised["target"].notna()
    ].reset_index(drop=True)


def run_experiment() -> tuple[pd.DataFrame, pd.DataFrame]:
    data, weather_columns, latest_origin = load_species_data()
    data = add_forward_expected_counts(data)
    data_for_output = data.drop(columns="calendar_day")

    result_rows: list[dict[str, object]] = []
    for threshold in ANOMALY_THRESHOLDS:
        for horizon_days in HORIZONS_DAYS:
            supervised = create_supervised(
                data,
                weather_columns,
                horizon_days,
                latest_origin,
                threshold,
            )
            years = supervised["origin_date"].dt.year
            unique_years = np.sort(years.unique())
            if len(unique_years) <= MIN_TRAIN_YEARS:
                raise ValueError(
                    f"Insufficient test years for anomaly ratio >= {threshold}, "
                    f"horizon {horizon_days}."
                )
            test_years = unique_years[MIN_TRAIN_YEARS:]
            for test_year in test_years:
                test_year_start = pd.Timestamp(
                    year=int(test_year), month=1, day=1
                )
                train = supervised.loc[
                    supervised["target_date"] < test_year_start
                ]
                test = supervised.loc[years.eq(test_year)]
                if train.empty or test.empty:
                    raise RuntimeError(
                        f"Empty anomaly forecast fold in {test_year}."
                    )
                train_positive_count = int(train["target"].sum())
                train_negative_count = len(train) - train_positive_count
                if not train_positive_count or not train_negative_count:
                    raise ValueError(
                        f"Training fold before {test_year} lacks a class for "
                        f"anomaly ratio >= {threshold}, {horizon_days}-day horizon."
                    )

                feature_sets = {
                    "Seasonality only": list(SEASONALITY_FEATURES),
                    "Weather only": weather_columns,
                    "Seasonality + weather": (
                        list(SEASONALITY_FEATURES) + weather_columns
                    ),
                }
                y_test = test["target"].astype(int).to_numpy()
                for feature_group, feature_columns in feature_sets.items():
                    train_x = train[feature_columns]
                    test_x = test[feature_columns]
                    for model_name in MODEL_NAMES:
                        estimator = make_estimator(
                            model_name,
                            train_positive_count,
                            train_negative_count,
                        )
                        estimator.fit(train_x, train["target"].astype(int))
                        probabilities = estimator.predict_proba(test_x)[:, 1]
                        result_rows.append(
                            {
                                "threshold": threshold,
                                "horizon_days": horizon_days,
                                "feature_group": feature_group,
                                "model": model_name,
                                "test_year": int(test_year),
                                "train_days": len(train),
                                "train_positive_days": train_positive_count,
                                "test_days": len(test),
                                "test_positive_days": int(y_test.sum()),
                                "y_true": y_test,
                                "probabilities": probabilities,
                                "target_dates": test["target_date"].to_numpy(),
                            }
                        )

    fold_predictions = pd.DataFrame(result_rows)
    metric_rows = []
    group_keys = ["threshold", "horizon_days", "feature_group", "model"]
    for keys, group in fold_predictions.groupby(group_keys, sort=True):
        y_true = np.concatenate(group["y_true"].to_list())
        probabilities = np.concatenate(group["probabilities"].to_list())
        threshold, horizon_days, feature_group, model_name = keys
        metric_rows.append(
            {
                "threshold": int(threshold),
                "horizon_days": int(horizon_days),
                "feature_group": feature_group,
                "model": model_name,
                **calculate_metrics(y_true, probabilities),
                "test_prevalence": float(y_true.mean()),
                "test_positive_days": int(y_true.sum()),
                "test_days": len(y_true),
                "test_years": int(group["test_year"].nunique()),
            }
        )
    metrics = pd.DataFrame(metric_rows)
    pivot = metrics.pivot(
        index=["threshold", "horizon_days", "model"],
        columns="feature_group",
        values="pr_auc",
    )
    gains = pivot.reset_index()
    gains["weather_only_pr_auc_gain"] = (
        gains["Weather only"] - gains["Seasonality only"]
    )
    gains["combined_pr_auc_gain"] = (
        gains["Seasonality + weather"] - gains["Seasonality only"]
    )
    metrics = metrics.merge(
        gains[
            [
                "threshold",
                "horizon_days",
                "model",
                "weather_only_pr_auc_gain",
                "combined_pr_auc_gain",
            ]
        ],
        on=["threshold", "horizon_days", "model"],
        validate="many_to_one",
    )
    metrics["beats_seasonality_pr_auc"] = (
        metrics["feature_group"].eq("Seasonality + weather")
        & metrics["combined_pr_auc_gain"].gt(0)
    )
    return metrics, data_for_output


def explain_best_model(
    metrics: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    combined = metrics.loc[
        metrics["feature_group"].eq("Seasonality + weather")
        & metrics["pr_auc"].notna()
    ]
    if combined.empty:
        raise ValueError("No valid combined-feature model metrics for SHAP.")
    best = combined.loc[combined["pr_auc"].idxmax()]
    threshold = int(best["threshold"])
    horizon_days = int(best["horizon_days"])
    model_name = str(best["model"])

    data, weather_columns, latest_origin = load_species_data()
    data = add_forward_expected_counts(data)
    supervised = create_supervised(
        data,
        weather_columns,
        horizon_days,
        latest_origin,
        threshold,
    )
    years = supervised["origin_date"].dt.year
    feature_columns = list(SEASONALITY_FEATURES) + weather_columns
    absolute_values = []

    for test_year in np.sort(years.unique())[MIN_TRAIN_YEARS:]:
        train = supervised.loc[
            supervised["target_date"]
            < pd.Timestamp(year=int(test_year), month=1, day=1)
        ]
        test = supervised.loc[years.eq(test_year)]
        positive_count = int(train["target"].sum())
        negative_count = len(train) - positive_count
        estimator = make_estimator(
            model_name, positive_count, negative_count
        )
        estimator.fit(train[feature_columns], train["target"].astype(int))
        imputer = estimator.named_steps["imputer"]
        model = estimator.named_steps["model"]
        train_matrix = imputer.transform(train[feature_columns])
        test_matrix = imputer.transform(test[feature_columns])

        if model_name == "Logistic Regression":
            scaler = estimator.named_steps["scale"]
            explainer = shap.LinearExplainer(
                model, scaler.transform(train_matrix[: min(len(train), 200)])
            )
            values = explainer(scaler.transform(test_matrix)).values
        else:
            explainer = shap.TreeExplainer(model)
            values = explainer(test_matrix).values
            if values.ndim == 3:
                if values.shape[-1] == 2:
                    values = values[:, :, 1]
                elif values.shape[-1] == 1:
                    values = values[:, :, 0]
                else:
                    raise ValueError("SHAP expected a single binary model output.")
        if values.shape != (len(test), len(feature_columns)):
            raise ValueError(
                f"Unexpected SHAP output shape {values.shape} for {model_name}."
            )
        absolute_values.append(np.abs(values))

    values = np.concatenate(absolute_values, axis=0)
    importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "mean_abs_shap": values.mean(axis=0),
        }
    ).sort_values("mean_abs_shap", ascending=False, ignore_index=True)
    importance.insert(0, "rank", np.arange(1, len(importance) + 1))
    importance["feature_group"] = np.where(
        importance["feature"].isin(SEASONALITY_FEATURES),
        "Seasonality",
        "Weather",
    )
    return importance, best


def write_report(
    metrics: pd.DataFrame,
    anomalies: pd.DataFrame,
    importance: pd.DataFrame,
    best: pd.Series,
) -> None:
    lines = [
        "# Yellow-browed Warbler Anomaly Forecasting",
        "",
        "## Anomaly definition",
        "",
        f"Expected count is a smoothed, prior-calendar-year day-of-year "
        f"climatology: observed counts from dates within ±{DAY_OF_YEAR_WINDOW} "
        f"calendar days are pooled, with "
        f"{CLIMATOLOGY_PRIOR_STRENGTH} prior-equivalent observations at the "
        "prior-year overall daily mean. The current calendar year is excluded "
        "from its own expectation. Anomaly is observed count minus expected "
        "count; anomaly ratio is observed count divided by expected count. "
        "Thus ratio 2 means twice expected, not 200% above expected. Dates "
        "without prior-year history have undefined expected counts and are "
        "excluded.",
        "",
        f"The output anomaly table covers {anomalies['date'].min().date()} to "
        f"{anomalies['date'].max().date()} and "
        f"{anomalies['expected_count'].notna().sum():,} dates with a valid "
        "forward-only expected count.",
        "",
        "| Anomaly label | Positive dates | Prevalence |",
        "|---|---:|---:|",
    ]
    for threshold in ANOMALY_THRESHOLDS:
        label = anomalies[f"anomaly_ge_{threshold}"]
        lines.append(
            f"| anomaly ratio >= {threshold} | {int(label.sum())} | "
            f"{label.mean():.2%} |"
        )

    lines.extend(
        [
            "",
            "## Evaluation design",
            "",
            "Evaluation follows the existing species comparison: expanding "
            "calendar-year forward chaining, the first five usable calendar "
            "years as initial history, 1/3/5/7/14-day horizons, and the same "
            "Logistic Regression, Random Forest, and XGBoost configurations. "
            "Labels use the forward-only expected-count series; target-date "
            "calendar features are known in advance, and weather features "
            "are shifted to weather available through the day before the "
            "forecast origin. Metrics pool held-out annual predictions. "
            "Precision, recall, and F1 use a 0.5 probability threshold; "
            "PR-AUC is average precision.",
            "",
            "## Pooled results",
            "",
        ]
    )
    for threshold in ANOMALY_THRESHOLDS:
        lines.extend(
            [
                f"### Anomaly ratio >= {threshold}",
                "",
                "| Horizon | Feature set | Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | Test prevalence | Test positives |",
                "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        subset = metrics.loc[metrics["threshold"].eq(threshold)].sort_values(
            ["horizon_days", "feature_group", "model"]
        )
        for row in subset.itertuples(index=False):
            formatter = lambda value: "NA" if pd.isna(value) else f"{value:.4f}"
            lines.append(
                f"| {row.horizon_days} d | {row.feature_group} | {row.model} | "
                f"{formatter(row.pr_auc)} | {formatter(row.roc_auc)} | "
                f"{formatter(row.precision)} | {formatter(row.recall)} | "
                f"{formatter(row.f1)} | {formatter(row.test_prevalence)} | "
                f"{row.test_positive_days} |"
            )
        lines.append("")

    delta = (
        metrics.loc[metrics["feature_group"].eq("Seasonality + weather")]
        .groupby("threshold")
        .agg(
            mean_pr_auc_gain=("combined_pr_auc_gain", "mean"),
            median_pr_auc_gain=("combined_pr_auc_gain", "median"),
            positive_comparisons=("combined_pr_auc_gain", lambda x: int((x > 0).sum())),
            comparisons=("combined_pr_auc_gain", "size"),
        )
    )
    weather_only_delta = (
        metrics.loc[metrics["feature_group"].eq("Weather only")]
        .groupby("threshold")["weather_only_pr_auc_gain"]
        .mean()
    )
    all_combined_deltas = metrics.loc[
        metrics["feature_group"].eq("Seasonality + weather"),
        "combined_pr_auc_gain",
    ]
    lines.extend(
        [
            "## Extra predictive value of weather beyond seasonality",
            "",
            "The key incremental comparison is (seasonality + weather) PR-AUC "
            "minus seasonality-only PR-AUC for the same threshold, horizon, "
            "and model. Weather-only versus seasonality-only deltas are also "
            "included in the metrics CSV.",
            "",
            "| Anomaly ratio | Mean weather-only minus seasonality PR-AUC | Mean combined-minus-seasonality PR-AUC | Median combined delta | Positive combined comparisons |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for threshold, row in delta.iterrows():
        lines.append(
            f"| >= {threshold} | {weather_only_delta.loc[threshold]:+.4f} | "
            f"{row['mean_pr_auc_gain']:+.4f} | "
            f"{row['median_pr_auc_gain']:.4f} | "
            f"{int(row['positive_comparisons'])}/{int(row['comparisons'])} |"
        )
    lines.extend(
        [
            "",
            f"Across all 45 paired model/horizon/threshold comparisons, "
            f"mean combined-minus-seasonality PR-AUC was "
            f"{all_combined_deltas.mean():+.4f}; weather helped in "
            f"{int((all_combined_deltas > 0).sum())}/45 comparisons.",
        ]
    )

    lines.extend(
        [
            "",
            "## SHAP explanation of the best combined model",
            "",
            f"Highest pooled PR-AUC combined model: anomaly ratio >= "
            f"{int(best['threshold'])}, {int(best['horizon_days'])}-day "
            f"horizon, {best['model']} (PR-AUC {best['pr_auc']:.4f}; "
            f"ROC-AUC {best['roc_auc']:.4f}). SHAP mean absolute values are "
            "pooled over forward-held-out folds. They show predictive "
            "contribution magnitude, not causal effects or contribution "
            "direction.",
            "",
            "| Rank | Feature | Mean absolute SHAP |",
            "|---:|---|---:|",
        ]
    )
    for row in importance.head(20).itertuples(index=False):
        lines.append(
            f"| {row.rank} | `{row.feature}` | {row.mean_abs_shap:.6f} |"
        )
    shap_groups = (
        importance.groupby("feature_group")["mean_abs_shap"]
        .sum()
        .div(importance["mean_abs_shap"].sum())
    )
    lines.extend(
        [
            "",
            "SHAP group contribution shares (sum of mean absolute values): "
            f"seasonality {shap_groups.get('Seasonality', 0.0):.1%}; "
            f"weather {shap_groups.get('Weather', 0.0):.1%}.",
        ]
    )

    best_gain = metrics.loc[
        metrics["feature_group"].eq("Seasonality + weather")
        & metrics["threshold"].eq(int(best["threshold"]))
        & metrics["horizon_days"].eq(int(best["horizon_days"]))
        & metrics["model"].eq(str(best["model"]))
    ]["combined_pr_auc_gain"].iloc[0]
    if best_gain > 0:
        conclusion = (
            "Weather adds measurable predictive information for the best "
            f"combined configuration (PR-AUC gain {best_gain:+.4f} over its "
            "seasonality-only counterpart)."
        )
    else:
        conclusion = (
            "Weather does not improve the best combined configuration over "
            "its seasonality-only counterpart on pooled PR-AUC "
            f"(delta {best_gain:+.4f})."
        )
    lines.extend(
        [
            "",
            "## Are exceptional influxes weather driven?",
            "",
            conclusion
            + f" Overall, combined models beat their seasonality-only "
            f"counterparts in {int((all_combined_deltas > 0).sum())}/45 "
            f"paired comparisons, with mean PR-AUC change "
            f"{all_combined_deltas.mean():+.4f}. This is not evidence that "
            "exceptional influxes are reliably weather driven; seasonality "
            "remains the stronger baseline, and adding weather usually does "
            "not improve ranking skill. Individual SHAP weather contributions "
            "can be sizeable while adding little incremental skill because "
            "they may be redundant with seasonal information. This "
            "observational experiment does not establish that weather causes "
            "anomalies: migration timing, reporting effort, detectability, "
            "and shared seasonal conditions may all contribute.",
            "",
            "## Artifacts",
            "",
            "- Daily forward-only expectation, anomaly, ratio, and labels: "
            "`data/processed/yellow_browed_daily_anomalies.csv`",
            "- Full fold-pooled metrics and paired PR-AUC deltas: "
            "`data/processed/yellow_browed_anomaly_forecast_metrics.csv`",
            "- Full feature ranking: "
            "`data/processed/yellow_browed_anomaly_shap_importance.csv`",
            "",
        ]
    )
    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    metrics, anomalies = run_experiment()
    importance, best = explain_best_model(metrics)
    ANOMALY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    anomalies.to_csv(ANOMALY_OUTPUT, index=False, float_format="%.8f")
    METRICS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(METRICS_OUTPUT, index=False, float_format="%.8f")
    SHAP_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    importance.to_csv(SHAP_OUTPUT, index=False, float_format="%.10f")
    write_report(metrics, anomalies, importance, best)
    print(
        f"Best combined model: anomaly ratio >= {int(best['threshold'])}, "
        f"{int(best['horizon_days'])}-day horizon, {best['model']}; "
        f"PR-AUC {best['pr_auc']:.4f}, ROC-AUC {best['roc_auc']:.4f}."
    )
    print(f"Report: {REPORT_OUTPUT.relative_to(ROOT)}")
    print("Weather PR-AUC gains over seasonality by anomaly threshold:")
    print(
        metrics.loc[
            metrics["feature_group"].eq("Seasonality + weather")
        ].groupby("threshold")["combined_pr_auc_gain"].mean().to_string()
    )
    print("Top SHAP features:")
    print(importance.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
