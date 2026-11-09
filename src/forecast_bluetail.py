"""Run and explain the forward-chained Bluetail forecasting experiment."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import shap

if __package__:
    from .forecast_species_comparison import (
        METRICS_OUTPUT,
        MIN_TRAIN_YEARS,
        SEASONALITY_FEATURES,
        build_horizon_data,
        load_species_data,
        make_estimator,
        run_experiment,
    )
else:
    from forecast_species_comparison import (
        METRICS_OUTPUT,
        MIN_TRAIN_YEARS,
        SEASONALITY_FEATURES,
        build_horizon_data,
        load_species_data,
        make_estimator,
        run_experiment,
    )


ROOT = Path(__file__).resolve().parents[1]
SPECIES = "Bluetail"
SPECIES_TARGETS = ((SPECIES, "bluetail_records"),)
METRICS_FILE = ROOT / "data/processed/bluetail_forecast_metrics.csv"
MODEL_IMPORTANCE_FILE = (
    ROOT / "data/processed/bluetail_feature_importance.csv"
)
SHAP_IMPORTANCE_FILE = ROOT / "data/processed/bluetail_shap_importance.csv"
REPORT_FILE = ROOT / "reports/bluetail_forecast_experiment.md"
COMPARISON_SPECIES = (
    "Yellow-browed Warbler",
    "Pallid Swift",
    "Red-throated Pipit",
    "Manx Shearwater",
    SPECIES,
)
METRIC_COLUMNS = (
    "species",
    "threshold",
    "horizon_days",
    "model",
    "roc_auc",
    "pr_auc",
    "precision",
    "recall",
    "f1",
    "seasonal_baseline_pr_auc",
    "test_prevalence",
    "test_positive_days",
    "test_days",
    "test_years",
    "beats_seasonal_pr_auc",
    "beats_prevalence_baseline",
)


def load_comparison_metrics(bluetail_metrics: pd.DataFrame) -> pd.DataFrame:
    if not METRICS_OUTPUT.is_file():
        raise FileNotFoundError(
            f"Existing comparison metrics not found: {METRICS_OUTPUT}. "
            "Run `python src/forecast_species_comparison.py` first."
        )
    historical = pd.read_csv(METRICS_OUTPUT)
    missing = set(METRIC_COLUMNS).difference(historical.columns)
    if missing:
        raise ValueError(
            f"Existing comparison metrics are missing columns: "
            f"{sorted(missing)}"
        )
    historical = historical.loc[
        historical["species"].isin(COMPARISON_SPECIES[:-1]), METRIC_COLUMNS
    ]
    combined = pd.concat(
        [historical, bluetail_metrics.loc[:, METRIC_COLUMNS]],
        ignore_index=True,
    )
    return combined


def select_best_model(metrics: pd.DataFrame) -> pd.Series:
    candidates = metrics.loc[
        metrics["species"].eq(SPECIES)
        & metrics["model"].ne("Seasonal baseline")
    ]
    if candidates.empty or candidates["pr_auc"].isna().all():
        raise ValueError("No valid Bluetail weather-model results.")
    return candidates.loc[candidates["pr_auc"].idxmax()]


def classify_feature(feature: str) -> str:
    if feature in SEASONALITY_FEATURES:
        return "Seasonality"
    if "wind_sin" in feature or "wind_cos" in feature:
        return "Wind direction"
    if "pressure_change_" in feature:
        return "Pressure change"
    if "pressure" in feature or "PX_" in feature:
        return "Pressure"
    if (
        feature.startswith(("TG_", "TN_", "TX_", "temperature_", "temp_"))
        or feature.startswith(("coast_TG_", "coast_TX_"))
    ):
        return "Temperature"
    return "Other"


def positive_class_shap_values(
    estimator: object,
    test_features: pd.DataFrame,
    feature_columns: list[str],
) -> np.ndarray:
    imputer = estimator.named_steps["imputer"]
    model = estimator.named_steps["model"]
    transformed = imputer.transform(test_features)
    if "scale" in estimator.named_steps:
        transformed = estimator.named_steps["scale"].transform(transformed)

    if model.__class__.__name__ == "LogisticRegression":
        explanation = shap.LinearExplainer(
            model, transformed, feature_perturbation="interventional"
        )(transformed)
    else:
        explanation = shap.TreeExplainer(model)(transformed)
    values = np.asarray(explanation.values)
    if values.ndim == 3:
        if values.shape[-1] < 2:
            values = values[:, :, 0]
        else:
            values = values[:, :, 1]
    if values.shape != (len(test_features), len(feature_columns)):
        raise ValueError(
            f"Unexpected SHAP shape {values.shape}; expected "
            f"{(len(test_features), len(feature_columns))}."
        )
    return values


def calculate_importance(
    best: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame, int, int, int]:
    data, weather_columns, latest_origin = load_species_data(
        include_bluetail=True
    )
    threshold = int(best["threshold"])
    horizon_days = int(best["horizon_days"])
    model_name = str(best["model"])
    data["bluetail_target"] = (
        data["bluetail_records"] >= threshold
    ).astype(int)
    supervised = build_horizon_data(
        data,
        weather_columns,
        "bluetail_target",
        horizon_days,
        latest_origin,
    )
    supervised["target"] = supervised["target"].astype(int)
    years = supervised["origin_date"].dt.year
    unique_years = np.sort(years.unique())
    if len(unique_years) <= MIN_TRAIN_YEARS:
        raise ValueError("Insufficient test years for forward-held-out SHAP.")

    feature_columns = list(SEASONALITY_FEATURES) + weather_columns
    fold_shap_values: list[np.ndarray] = []
    model_importances: list[np.ndarray] = []
    test_count = 0
    positive_test_count = 0
    for test_year in unique_years[MIN_TRAIN_YEARS:]:
        train = supervised.loc[
            supervised["target_date"]
            < pd.Timestamp(year=int(test_year), month=1, day=1)
        ]
        test = supervised.loc[years.eq(test_year)]
        positive_count = int(train["target"].sum())
        negative_count = len(train) - positive_count
        if train.empty or test.empty or not positive_count or not negative_count:
            raise ValueError(
                f"Invalid training/test fold before or during {test_year}."
            )

        estimator = make_estimator(
            model_name, positive_count, negative_count
        )
        estimator.fit(train[feature_columns], train["target"])
        values = positive_class_shap_values(
            estimator, test[feature_columns], feature_columns
        )
        fold_shap_values.append(np.abs(values))

        model = estimator.named_steps["model"]
        if model_name == "Logistic Regression":
            importance = np.abs(model.coef_[0])
        else:
            importance = model.feature_importances_
        if importance.shape != (len(feature_columns),):
            raise ValueError(
                f"Unexpected feature-importance shape {importance.shape}."
            )
        model_importances.append(np.asarray(importance, dtype=float))
        test_count += len(test)
        positive_test_count += int(test["target"].sum())

    all_shap_values = np.concatenate(fold_shap_values, axis=0)
    mean_model_importance = np.mean(model_importances, axis=0)
    shap_importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "mean_abs_shap": all_shap_values.mean(axis=0),
        }
    )
    shap_importance["category"] = shap_importance["feature"].map(
        classify_feature
    )
    shap_importance = shap_importance.sort_values(
        "mean_abs_shap", ascending=False
    ).reset_index(drop=True)
    shap_importance.insert(0, "rank", np.arange(1, len(shap_importance) + 1))

    feature_importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "mean_model_importance": mean_model_importance,
        }
    )
    feature_importance["category"] = feature_importance["feature"].map(
        classify_feature
    )
    feature_importance = feature_importance.sort_values(
        "mean_model_importance", ascending=False
    ).reset_index(drop=True)
    feature_importance.insert(
        0, "rank", np.arange(1, len(feature_importance) + 1)
    )
    test_year_count = len(unique_years) - MIN_TRAIN_YEARS
    return (
        feature_importance,
        shap_importance,
        test_count,
        positive_test_count,
        test_year_count,
    )


def comparison_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    weather_metrics = metrics.loc[
        metrics["species"].isin(COMPARISON_SPECIES)
        & metrics["model"].ne("Seasonal baseline")
    ]
    best_models = weather_metrics.loc[
        weather_metrics.groupby(
            ["species", "threshold", "horizon_days"]
        )["pr_auc"].idxmax()
    ].copy()
    best_models["pr_auc_lift"] = (
        best_models["pr_auc"] - best_models["seasonal_baseline_pr_auc"]
    )
    return best_models


def build_report(
    metrics: pd.DataFrame,
    best: pd.Series,
    feature_importance: pd.DataFrame,
    shap_importance: pd.DataFrame,
    test_count: int,
    positive_test_count: int,
    test_year_count: int,
) -> str:
    bluetail_metrics = metrics.loc[metrics["species"].eq(SPECIES)].sort_values(
        ["threshold", "horizon_days", "model"]
    )
    comparison = comparison_summary(metrics)
    summary = comparison.groupby("species").agg(
        mean_best_pr_auc=("pr_auc", "mean"),
        mean_seasonal_pr_auc=("seasonal_baseline_pr_auc", "mean"),
        mean_pr_auc_lift=("pr_auc_lift", "mean"),
        scenarios_beating_seasonality=(
            "pr_auc_lift",
            lambda values: int((values > 0).sum()),
        ),
    )
    ranked_species = summary.sort_values(
        ["mean_pr_auc_lift", "scenarios_beating_seasonality"],
        ascending=[False, False],
    )
    best_per_threshold = comparison.loc[
        comparison.groupby(["species", "threshold"])["pr_auc"].idxmax()
    ].set_index(["species", "threshold"])
    category_summary = (
        shap_importance.groupby("category", as_index=False)["mean_abs_shap"]
        .sum()
        .sort_values("mean_abs_shap", ascending=False)
    )
    category_summary["share"] = (
        category_summary["mean_abs_shap"]
        / category_summary["mean_abs_shap"].sum()
    )
    seasonality_share = float(
        category_summary.loc[
            category_summary["category"].eq("Seasonality"), "share"
        ].sum()
    )
    top_features = ", ".join(
        f"`{row.feature}`"
        for row in shap_importance.head(5).itertuples(index=False)
    )
    leader = str(ranked_species.index[0])

    lines = [
        "# Bluetail Forecasting Experiment",
        "",
        "## Objective and method",
        "",
        "This experiment forecasts whether Dutch GBIF daily records for "
        "*Tarsiger cyanurus* reach ≥10, ≥25, or ≥50 at 1, 3, 5, 7, or 14 "
        "days ahead. Occurrence labels come from the archived GBIF "
        "Netherlands event-date facets; dates with no facet are zero on the "
        "shared KNMI weather calendar. The weather features are the same "
        "four-station coastal dataset and derived features used for "
        "Yellow-browed Warbler and Red-throated Pipit.",
        "",
        "Validation is annual expanding-window forward chaining, with the "
        "first five years for initial training. Each test-year model trains "
        "only on examples whose target date precedes that year. Weather "
        "features use observations available through the day before the "
        "forecast origin; target-date calendar features are known in "
        "advance. Median imputation and model fitting occur within each "
        "fold. If a fold has no positive training examples, weather-model "
        "predictions are zero and the fold remains in evaluation.",
        "",
        "The seasonal baseline uses month-specific training event rates "
        "smoothed with 30 prior-equivalent observations. Logistic Regression "
        "is class-weighted, Random Forest uses balanced subsampling, and "
        "XGBoost uses the training fold's negative-to-positive ratio. "
        "ROC-AUC and average-precision PR-AUC pool held-out predictions; "
        "precision, recall, and F1 use a fixed 0.5 cutoff.",
        "",
        "## Bluetail performance",
        "",
        "| Target | Horizon | Model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Seasonal PR-AUC | Positive test days |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in bluetail_metrics.itertuples(index=False):
        lines.append(
            f"| ≥{row.threshold} | {row.horizon_days} d | {row.model} | "
            f"{row.roc_auc:.4f} | {row.pr_auc:.4f} | "
            f"{row.precision:.4f} | {row.recall:.4f} | {row.f1:.4f} | "
            f"{row.seasonal_baseline_pr_auc:.4f} | "
            f"{row.test_positive_days} |"
        )

    lines.extend(
        [
            "",
            "## Direct comparison with Bird-Predict species",
            "",
            "For each species and threshold, this table shows the "
            "highest-PR-AUC weather model across the five horizons. The "
            "matched seasonal baseline is shown for the selected horizon. "
            "Selection across this grid is descriptive, not an independent "
            "validation.",
            "",
            "| Species | Target | Best model | Horizon | ROC-AUC | PR-AUC | Seasonal PR-AUC | Precision | Recall | F1 | Positive test days |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for threshold in (10, 25, 50):
        for species in COMPARISON_SPECIES:
            row = best_per_threshold.loc[(species, threshold)]
            lines.append(
                f"| {species} | ≥{threshold} | {row['model']} | "
                f"{int(row['horizon_days'])} d | {row['roc_auc']:.4f} | "
                f"{row['pr_auc']:.4f} | "
                f"{row['seasonal_baseline_pr_auc']:.4f} | "
                f"{row['precision']:.4f} | {row['recall']:.4f} | "
                f"{row['f1']:.4f} | {int(row['test_positive_days'])} |"
            )

    lines.extend(
        [
            "",
            "## Forecastability ranking",
            "",
            "Ranked by the mean best-weather-model PR-AUC lift over the "
            "matched seasonal baseline across all 15 threshold/horizon "
            "scenarios. Model selection is performed consistently for every "
            "species. PR-AUC depends on prevalence, and the ranking is "
            "descriptive, not a significance test.",
            "",
            "| Rank | Species | Mean best weather PR-AUC | Mean seasonal PR-AUC | Mean PR-AUC lift | Scenarios beating seasonality |",
            "|---:|---|---:|---:|---:|---:|",
        ]
    )
    for rank, (species, row) in enumerate(ranked_species.iterrows(), start=1):
        lines.append(
            f"| {rank} | {species} | {row['mean_best_pr_auc']:.4f} | "
            f"{row['mean_seasonal_pr_auc']:.4f} | "
            f"{row['mean_pr_auc_lift']:+.4f} | "
            f"{int(row['scenarios_beating_seasonality'])}/15 |"
        )

    lines.extend(
        [
            "",
            "## Feature importance",
            "",
            f"Feature importance is averaged across each held-out annual fold "
            f"for the selected {best['model']} model, target ≥"
            f"{int(best['threshold'])}, horizon {int(best['horizon_days'])} "
            f"days. The selected experiment result has PR-AUC "
            f"{best['pr_auc']:.4f} and ROC-AUC {best['roc_auc']:.4f}. "
            "Random Forest/XGBoost built-in impurity or gain importances "
            "are averaged fold-wise; Logistic Regression uses absolute "
            "standardized coefficients.",
            "",
            "| Rank | Feature | Mean model importance | Category |",
            "|---:|---|---:|---|",
        ]
    )
    for row in feature_importance.head(20).itertuples(index=False):
        lines.append(
            f"| {row.rank} | `{row.feature}` | "
            f"{row.mean_model_importance:.6f} | {row.category} |"
        )
    lines.extend(
        [
            "",
            "## SHAP importance",
            "",
            "SHAP values were computed on held-out forecast dates for each "
            f"annual fold and pooled across {test_count:,} dates, "
            f"{test_year_count} test years, and {positive_test_count} "
            "positive target days. Values are mean absolute SHAP on the "
            "model output scale; they describe predictive contribution "
            "magnitude, not causation.",
            "",
            "| Rank | Feature | Mean absolute SHAP | Category |",
            "|---:|---|---:|---|",
        ]
    )
    for row in shap_importance.head(20).itertuples(index=False):
        lines.append(
            f"| {row.rank} | `{row.feature}` | "
            f"{row.mean_abs_shap:.6f} | {row.category} |"
        )
    lines.extend(
        [
            "",
            "### SHAP by feature family",
            "",
            "| Feature family | Total mean absolute SHAP | Share |",
            "|---|---:|---:|",
        ]
    )
    for row in category_summary.itertuples(index=False):
        lines.append(
            f"| {row.category} | {row.mean_abs_shap:.6f} | "
            f"{row.share:.1%} |"
        )

    lines.extend(
        [
            "",
            "## Biological interpretation",
            "",
            f"Seasonality contributes {seasonality_share:.1%} of total "
            "absolute SHAP importance. The most influential predictors are "
            f"{top_features}. A day-of-year contribution is consistent with "
            "Bluetail migration and seasonal passage through the Netherlands. "
            "Temperature, wind, and pressure associations may reflect "
            "migration conditions, stopover, detectability, or observer "
            "effort; this observational experiment cannot distinguish these "
            "mechanisms or infer causal weather effects.",
            "",
            "SHAP magnitude does not show whether a particular weather "
            "condition increases or decreases predicted records. GBIF "
            "observations reflect reporting effort and are not abundance "
            "estimates; event-date clusters may represent shared migration "
            "or reporting episodes rather than independent bird-level "
            "observations.",
            "",
            "## Recommendation",
            "",
        ]
    )
    if leader == SPECIES:
        conclusion = (
            "Bluetail ranks first by mean best-weather-model PR-AUC lift "
            "across the predefined 15-scenario grid. "
        )
    else:
        conclusion = (
            f"No. {leader} currently ranks first by mean best-weather-model "
            "PR-AUC lift across the predefined 15-scenario grid. "
        )
    lines.extend(
        [
            conclusion
            + "This comparative score is evidence of relative held-out "
            "ranking performance, but not a formal significance test or "
            "proof of operational utility. The strongest ≥10 Bluetail "
            "scenario is "
            + (
                f"{best_per_threshold.loc[(SPECIES, 10), 'model']} at "
                f"{int(best_per_threshold.loc[(SPECIES, 10), 'horizon_days'])} "
                f"days (PR-AUC "
                f"{best_per_threshold.loc[(SPECIES, 10), 'pr_auc']:.4f}); "
                f"there are only "
                f"{int(best_per_threshold.loc[(SPECIES, 10), 'test_positive_days'])} "
                "positive held-out days. "
            )
            + "The ≥25 and ≥50 thresholds have progressively less support, "
            "so their metrics should be treated as unstable when positive "
            "days are sparse.",
            "",
            "**Recommendation:** retain Bluetail as an exploratory candidate "
            "and prioritize interpretation around the ≥10 target. Do not "
            "promote it as the strongest weather-driven Bird-Predict species "
            "unless its pooled lift and rare-event precision/recall remain "
            "competitive on a later, independent evaluation period.",
            "",
            "## Limitations",
            "",
            "- All species share the 2010-10-01 to 2026-08-10 KNMI calendar; "
            "historical occurrences outside it are not used.",
            "- The 0.5 classification threshold is fixed and may yield zero "
            "precision, recall, or F1 for rare targets.",
            "- The best model/horizon summaries use the same held-out grid "
            "for selection and comparison, so they may overstate general "
            "performance.",
            "- GBIF reporting effort varies and is not controlled; counts "
            "are not measures of abundance.",
            "- Absolute SHAP values and feature importance describe fitted "
            "model behavior and are not causal explanations.",
            "",
            "Metrics: `data/processed/bluetail_forecast_metrics.csv`. "
            "Model importance: `data/processed/bluetail_feature_importance.csv`. "
            "SHAP importance: `data/processed/bluetail_shap_importance.csv`. "
            "Existing comparison results: "
            "`data/processed/species_forecast_metrics.csv`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    metrics = run_experiment(species_targets=SPECIES_TARGETS)
    metrics.to_csv(METRICS_FILE, index=False, float_format="%.8f")
    comparison_metrics = load_comparison_metrics(metrics)
    best = select_best_model(comparison_metrics)
    (
        model_importance,
        shap_importance,
        test_count,
        positive_test_count,
        test_year_count,
    ) = calculate_importance(best)
    model_importance.to_csv(
        MODEL_IMPORTANCE_FILE, index=False, float_format="%.10f"
    )
    shap_importance.to_csv(
        SHAP_IMPORTANCE_FILE, index=False, float_format="%.10f"
    )
    report = build_report(
        comparison_metrics,
        best,
        model_importance,
        shap_importance,
        test_count,
        positive_test_count,
        test_year_count,
    )
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"Metrics: {METRICS_FILE.relative_to(ROOT)}")
    print(f"Feature importance: {MODEL_IMPORTANCE_FILE.relative_to(ROOT)}")
    print(f"SHAP importance: {SHAP_IMPORTANCE_FILE.relative_to(ROOT)}")
    print(f"Report: {REPORT_FILE.relative_to(ROOT)}")
    print(
        f"Best Bluetail result: {best['model']}, threshold >= "
        f"{int(best['threshold'])}, horizon {int(best['horizon_days'])}d, "
        f"PR-AUC {best['pr_auc']:.4f}"
    )


if __name__ == "__main__":
    main()
