"""Report forward-held-out SHAP importance for Red-throated Pipit."""

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
    )
else:
    from forecast_species_comparison import (
        METRICS_OUTPUT,
        MIN_TRAIN_YEARS,
        SEASONALITY_FEATURES,
        build_horizon_data,
        load_species_data,
        make_estimator,
    )


ROOT = Path(__file__).resolve().parents[1]
IMPORTANCE_OUTPUT = (
    ROOT / "data/processed/red_throated_pipit_shap_importance.csv"
)
REPORT_OUTPUT = ROOT / "reports/red_throated_pipit_forecast_experiment.md"
SPECIES = "Red-throated Pipit"
COMPARISON_SPECIES = (
    SPECIES,
    "Yellow-browed Warbler",
    "Pallid Swift",
    "Manx Shearwater",
)


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


def load_metrics() -> pd.DataFrame:
    if not METRICS_OUTPUT.is_file():
        raise FileNotFoundError(
            f"Forecast metrics not found: {METRICS_OUTPUT}. "
            "Run `python src/forecast_species_comparison.py` first."
        )
    metrics = pd.read_csv(METRICS_OUTPUT)
    required = {
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
        "test_positive_days",
        "test_days",
        "test_years",
    }
    missing = required.difference(metrics.columns)
    if missing:
        raise ValueError(
            f"Forecast metrics missing columns: {sorted(missing)}"
        )
    return metrics


def select_best_model(metrics: pd.DataFrame) -> pd.Series:
    candidates = metrics.loc[
        metrics["species"].eq(SPECIES)
        & metrics["model"].ne("Seasonal baseline")
    ]
    if candidates.empty or candidates["pr_auc"].isna().all():
        raise ValueError("No valid Red-throated Pipit weather-model results.")
    return candidates.loc[candidates["pr_auc"].idxmax()]


def calculate_oof_importance(
    threshold: int, horizon_days: int
) -> tuple[pd.DataFrame, int, int, int]:
    data, weather_columns, latest_origin = load_species_data()
    data["pipit_target"] = (
        data["red_throated_pipit_records"] >= threshold
    ).astype(int)
    supervised = build_horizon_data(
        data,
        weather_columns,
        "pipit_target",
        horizon_days,
        latest_origin,
    )
    supervised["target"] = supervised["target"].astype(int)
    years = supervised["origin_date"].dt.year
    unique_years = np.sort(years.unique())
    if len(unique_years) <= MIN_TRAIN_YEARS:
        raise ValueError("Insufficient test years for forward-held-out SHAP.")

    feature_columns = list(SEASONALITY_FEATURES) + weather_columns
    fold_values = []
    test_count = 0
    test_positive_count = 0
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
                f"Invalid SHAP training/test fold before or during {test_year}."
            )

        estimator = make_estimator(
            "XGBoost", positive_count, negative_count
        )
        estimator.fit(train[feature_columns], train["target"])
        test_matrix = estimator.named_steps["imputer"].transform(
            test[feature_columns]
        )
        explanation = shap.TreeExplainer(
            estimator.named_steps["model"]
        )(test_matrix)
        values = np.asarray(explanation.values)
        if values.ndim == 3:
            if values.shape[-1] != 1:
                raise ValueError(
                    "Expected binary XGBoost SHAP values with one output."
                )
            values = values[:, :, 0]
        if values.shape != (len(test), len(feature_columns)):
            raise ValueError(
                f"Unexpected SHAP shape {values.shape}; expected "
                f"{(len(test), len(feature_columns))}."
            )

        fold_values.append(np.abs(values))
        test_count += len(test)
        test_positive_count += int(test["target"].sum())

    all_values = np.concatenate(fold_values, axis=0)
    importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "mean_abs_shap": all_values.mean(axis=0),
        }
    )
    importance["category"] = importance["feature"].map(classify_feature)
    importance = importance.sort_values(
        "mean_abs_shap", ascending=False
    ).reset_index(drop=True)
    importance.insert(0, "rank", np.arange(1, len(importance) + 1))
    test_year_count = len(unique_years) - MIN_TRAIN_YEARS
    return importance, test_count, test_positive_count, test_year_count


def best_weather_results(metrics: pd.DataFrame) -> pd.DataFrame:
    weather = metrics.loc[
        metrics["species"].isin(COMPARISON_SPECIES)
        & metrics["model"].ne("Seasonal baseline")
    ]
    best = weather.loc[
        weather.groupby(
            ["species", "threshold", "horizon_days"]
        )["pr_auc"].idxmax()
    ].copy()
    best["pr_auc_lift"] = best["pr_auc"] - best["seasonal_baseline_pr_auc"]
    return best


def build_report(
    metrics: pd.DataFrame,
    best: pd.Series,
    importance: pd.DataFrame,
    test_count: int,
    test_positive_count: int,
    test_year_count: int,
) -> str:
    pipit_metrics = metrics.loc[metrics["species"].eq(SPECIES)].sort_values(
        ["threshold", "horizon_days", "model"]
    )
    comparison = best_weather_results(metrics)
    best_by_threshold = comparison.loc[
        comparison.groupby(["species", "threshold"])["pr_auc"].idxmax()
    ]
    best_comparison = best_by_threshold.set_index(["species", "threshold"])
    forecastability = comparison.groupby("species").agg(
        mean_best_pr_auc=("pr_auc", "mean"),
        mean_seasonal_pr_auc=("seasonal_baseline_pr_auc", "mean"),
        mean_pr_auc_lift=("pr_auc_lift", "mean"),
        scenarios_beating_seasonality=(
            "pr_auc_lift",
            lambda values: int((values > 0).sum()),
        ),
    )
    ranking = forecastability.sort_values(
        ["mean_pr_auc_lift", "scenarios_beating_seasonality"],
        ascending=[False, False],
    )
    top_categories = importance.head(20)
    category_summary = (
        importance.groupby("category", as_index=False)["mean_abs_shap"]
        .sum()
        .sort_values("mean_abs_shap", ascending=False)
    )
    category_summary["share"] = (
        category_summary["mean_abs_shap"]
        / category_summary["mean_abs_shap"].sum()
    )
    group_shares = category_summary.set_index("category")["share"]
    seasonality_share = float(group_shares.get("Seasonality", 0.0))
    non_seasonal_share = 1.0 - seasonality_share

    lines = [
        "# Red-throated Pipit Forecasting Experiment",
        "",
        "## Objective and data",
        "",
        "This experiment forecasts whether Dutch GBIF daily record counts "
        "reach ≥10, ≥25, or ≥50 records, 1, 3, 5, 7, or 14 days ahead. "
        "Pipit labels come from the archived GBIF Netherlands event-date "
        "facets; dates without a facet are assigned zero on the shared KNMI "
        "weather calendar. Four coastal KNMI stations and the existing "
        "weather-feature pipeline are used. Records are observation/reporting "
        "counts, not abundance estimates.",
        "",
        "## Method",
        "",
        "The method matches the shared Yellow-browed Warbler, Pallid Swift, "
        "and Manx Shearwater comparison in "
        "`reports/species_forecast_comparison.md`: expanding annual "
        "forward-chaining, first five calendar years for initial training, "
        "and 12 held-out test years. All species use identical forecast "
        "origins, target-date calendar features, and observed weather "
        "features available through the day before the forecast origin. "
        "Median imputation and model fitting are performed within each fold.",
        "",
        "Models are the month-specific smoothed seasonal baseline, "
        "class-weighted Logistic Regression, balanced Random Forest, and "
        "class-weighted XGBoost. ROC-AUC and average-precision PR-AUC are "
        "computed from pooled out-of-fold predictions. Precision, recall, "
        "and F1 use a fixed 0.5 probability threshold. If early training "
        "folds have no positive examples, the weather models predict zero "
        "and the fold stays in evaluation.",
        "",
        "## Pipit performance",
        "",
        "All Pipit thresholds, horizons, and models are shown below. "
        "Positive test days are pooled across the same 4,226 held-out dates "
        "and 12 test years for every Pipit scenario.",
        "",
        "| Target | Horizon | Model | ROC-AUC | PR-AUC | Precision | Recall | F1 | Seasonal PR-AUC | Positive test days |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in pipit_metrics.itertuples(index=False):
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
            "## Direct species comparison",
            "",
            "For each species and target threshold, the row reports that "
            "species' highest-PR-AUC weather model across the five tested "
            "horizons. Horizon/model selection uses the same comparison grid "
            "for every species and is descriptive, not a new independent "
            "validation. Seasonal PR-AUC is from the matched threshold and "
            "horizon.",
            "",
            "| Species | Target | Selected model | Horizon | ROC-AUC | PR-AUC | Seasonal PR-AUC | PR lift | Precision | Recall | F1 | Positive test days |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for threshold in (10, 25, 50):
        for species in COMPARISON_SPECIES:
            row = best_comparison.loc[(species, threshold)]
            lines.append(
                f"| {species} | ≥{threshold} | {row['model']} | "
                f"{int(row['horizon_days'])} d | {row['roc_auc']:.4f} | "
                f"{row['pr_auc']:.4f} | "
                f"{row['seasonal_baseline_pr_auc']:.4f} | "
                f"{row['pr_auc_lift']:+.4f} | "
                f"{row['precision']:.4f} | {row['recall']:.4f} | "
                f"{row['f1']:.4f} | {int(row['test_positive_days'])} |"
            )

    lines.extend(
        [
            "",
            "## Cross-species forecastability summary",
            "",
            "For each of 15 threshold/horizon combinations, take the best "
            "weather-model PR-AUC and subtract the matched seasonal "
            "baseline PR-AUC; the table summarizes those descriptive lifts.",
            "",
            "| Species | Mean best weather PR-AUC | Mean seasonal PR-AUC | Mean PR-AUC lift | Scenarios beating seasonality |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for species, row in forecastability.iterrows():
        lines.append(
            f"| {species} | {row['mean_best_pr_auc']:.4f} | "
            f"{row['mean_seasonal_pr_auc']:.4f} | "
            f"{row['mean_pr_auc_lift']:+.4f} | "
            f"{int(row['scenarios_beating_seasonality'])}/15 |"
        )

    top_feature_names = ", ".join(
        f"`{row.feature}`" for row in importance.head(5).itertuples()
    )
    lines.extend(
        [
            "",
            "## Feature importance and SHAP",
            "",
            f"The selected Pipit model is **{best['model']}** for ≥"
            f"{int(best['threshold'])} records at {int(best['horizon_days'])} "
            f"days (highest Pipit weather-model PR-AUC, {best['pr_auc']:.4f}; "
            f"ROC-AUC {best['roc_auc']:.4f}). SHAP TreeExplainer values were "
            "computed separately on every annual held-out fold and pooled "
            "over "
            f"{test_count:,} dates in {test_year_count} test years "
            f"({test_positive_count} positive target days). Importance is "
            "mean absolute SHAP on the model's raw output scale; it measures "
            "predictive contribution magnitude, not causal effects.",
            "",
            "### Top 20 features",
            "",
            "| Rank | Feature | Mean absolute SHAP | Category |",
            "|---:|---|---:|---|",
        ]
    )
    for row in top_categories.itertuples(index=False):
        lines.append(
            f"| {row.rank} | `{row.feature}` | "
            f"{row.mean_abs_shap:.6f} | {row.category} |"
        )
    lines.extend(
        [
            "",
            "### SHAP importance by feature family",
            "",
            "| Feature family | Total mean absolute SHAP | Share |",
            "|---|---:|---:|",
        ]
    )
    for row in category_summary.itertuples(index=False):
        lines.append(
            f"| {row.category} | {row.mean_abs_shap:.6f} | {row.share:.1%} |"
        )

    lines.extend(
        [
            "",
            "## Biological interpretation",
            "",
            f"Seasonality accounts for {seasonality_share:.1%} of pooled "
            "absolute SHAP importance, so the model's signal is "
            + (
                "predominantly phenological rather than meteorological. "
                if seasonality_share >= 0.5
                else "not dominated by the calendar alone. "
            )
            + f"The highest-ranked predictors are {top_feature_names}. "
            "Red-throated Pipits pass through the Netherlands during "
            "migration; a day-of-year signal is biologically plausible as "
            "migration timing. Weather signals may reflect conditions "
            "associated with migration, stopover, detectability, or observer "
            "activity. Their importance does not establish a causal response "
            "to wind, pressure, or temperature.",
            "",
            f"Seasonal share is {seasonality_share:.1%}; the remaining "
            f"{non_seasonal_share:.1%} is distributed across weather and other "
            "predictor families. Absolute SHAP values do not reveal whether "
            "a weather condition raises or lowers predicted risk. GBIF "
            "counts are affected by uneven reporting effort and should not "
            "be interpreted as bird abundance.",
            "",
            "The complete pooled held-out feature ranking is saved in "
            "`data/processed/red_throated_pipit_shap_importance.csv`.",
            "",
            "## Recommendation",
            "",
        ]
    )
    leader = str(ranking.index[0])
    pipit_lift = float(
        forecastability.loc[SPECIES, "mean_pr_auc_lift"]
    )
    leader_lift = float(forecastability.loc[leader, "mean_pr_auc_lift"])
    if leader == SPECIES:
        conclusion = (
            "By mean best-weather-model PR-AUC lift across the full grid, "
            "Red-throated Pipit ranks first in this descriptive comparison. "
        )
    else:
        conclusion = (
            f"Red-throated Pipit is not the strongest species by the "
            f"predefined grid summary: {leader} ranks first "
            f"(mean PR-AUC lift {leader_lift:+.4f} vs Pipit's "
            f"{pipit_lift:+.4f}). "
        )
    pipit_10 = best_comparison.loc[(SPECIES, 10)]
    lines.extend(
        [
            conclusion
            + f"For the ≥10 target, Pipit's strongest model is "
            f"{pipit_10['model']} at {int(pipit_10['horizon_days'])} days "
            f"(PR-AUC {pipit_10['pr_auc']:.4f}, seasonal PR-AUC "
            f"{pipit_10['seasonal_baseline_pr_auc']:.4f}, F1 "
            f"{pipit_10['f1']:.4f}); it has only "
            f"{int(pipit_10['test_positive_days'])} positive test days. "
            "At ≥25 and ≥50 records, the best Pipit weather models have "
            "zero precision/recall/F1 at the fixed 0.5 threshold, and the "
            "≥50 target has only eight positive held-out days.",
            "",
            "**Recommendation:** retain Red-throated Pipit as an exploratory "
            "weather-driven candidate for the ≥10-record target, but do not "
            "promote it as the strongest Bird-Predict species or as an "
            "operational forecast. Yellow-browed Warbler and Pallid Swift "
            "show stronger and more consistent held-out performance in this "
            "comparison. The rare ≥25/≥50 Pipit targets need more independent "
            "positive events before their scores or feature explanations are "
            "stable enough for operational use.",
            "",
            "## Limitations",
            "",
            "- The 0.5 classification cutoff is fixed; it produces zero "
            "precision, recall, and F1 for some rare-event models despite "
            "ranking skill above baseline.",
            "- Selecting the best model, horizon, and threshold on this same "
            "held-out grid is descriptive and can overstate performance; "
            "there is no independent final test period.",
            "- High-count dates can cluster in migration/reporting episodes, "
            "so positive days are not necessarily independent events.",
            "- GBIF facets and the KNMI date coverage can change; "
            "`country=NL` is a GBIF country-code filter, not a coordinate "
            "boundary.",
            "- SHAP summarizes fitted model behavior, not causal effects; "
            "changing observer effort may be confounded with weather and "
            "season.",
            "",
            "The complete shared performance grid is in "
            "`data/processed/species_forecast_metrics.csv`; the all-species "
            "method and full model results are in "
            "`reports/species_forecast_comparison.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    metrics = load_metrics()
    best = select_best_model(metrics)
    importance, test_count, positive_count, test_year_count = (
        calculate_oof_importance(
            int(best["threshold"]), int(best["horizon_days"])
        )
    )
    IMPORTANCE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    importance.to_csv(IMPORTANCE_OUTPUT, index=False, float_format="%.10f")
    report = build_report(
        metrics,
        best,
        importance,
        test_count,
        positive_count,
        test_year_count,
    )
    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text(report, encoding="utf-8")
    print(
        f"Selected: {best['model']}, threshold >= {int(best['threshold'])}, "
        f"horizon {int(best['horizon_days'])} days, "
        f"PR-AUC {best['pr_auc']:.4f}"
    )
    print(f"Importance CSV: {IMPORTANCE_OUTPUT.relative_to(ROOT)}")
    print(f"Report: {REPORT_OUTPUT.relative_to(ROOT)}")
    print(importance.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
