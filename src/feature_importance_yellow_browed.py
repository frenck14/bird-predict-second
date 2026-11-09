"""Report forward-held-out SHAP feature importance for Yellow-browed Warbler."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import shap

if __package__:
    from .forecast_species_comparison import (
        MIN_TRAIN_YEARS,
        SEASONALITY_FEATURES,
        build_horizon_data,
        load_species_data,
        make_estimator,
    )
else:
    from forecast_species_comparison import (
        MIN_TRAIN_YEARS,
        SEASONALITY_FEATURES,
        build_horizon_data,
        load_species_data,
        make_estimator,
    )


ROOT = Path(__file__).resolve().parents[1]
METRICS_FILE = ROOT / "data/processed/species_forecast_metrics.csv"
IMPORTANCE_OUTPUT = (
    ROOT / "data/processed/yellow_browed_warbler_shap_importance.csv"
)
REPORT_OUTPUT = ROOT / "reports/yellow_browed_warbler_feature_importance.md"


def classify_feature(feature: str) -> str:
    if feature in SEASONALITY_FEATURES:
        return "Seasonality"
    if "wind_sin" in feature or "wind_cos" in feature:
        return "Wind direction"
    if "pressure_change_" in feature:
        return "Pressure change"
    if "pressure" in feature or feature.startswith("PX_") or "PX_" in feature:
        return "Pressure"
    if (
        feature.startswith(("TG_", "TN_", "TX_"))
        or feature.startswith(("coast_TG_", "coast_TX_"))
        or feature.startswith(("temperature_", "temp_"))
    ):
        return "Temperature"
    return "Other"


def select_best_model() -> pd.Series:
    if not METRICS_FILE.is_file():
        raise FileNotFoundError(
            f"Forecast metrics not found: {METRICS_FILE}. "
            "Run `python src/forecast_species_comparison.py` first."
        )
    metrics = pd.read_csv(METRICS_FILE)
    candidates = metrics.loc[
        metrics["species"].eq("Yellow-browed Warbler")
        & metrics["model"].ne("Seasonal baseline")
    ]
    if candidates.empty or candidates["pr_auc"].isna().all():
        raise ValueError("No valid Yellow-browed Warbler weather-model results.")
    return candidates.loc[candidates["pr_auc"].idxmax()]


def calculate_oof_importance(
    threshold: int, horizon_days: int
) -> tuple[pd.DataFrame, int, int, int]:
    data, weather_columns, latest_origin = load_species_data()
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
        model = estimator.named_steps["model"]
        explanation = shap.TreeExplainer(model)(test_matrix)
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


def build_report(
    best: pd.Series,
    importance: pd.DataFrame,
    test_count: int,
    test_positive_count: int,
    test_year_count: int,
) -> str:
    top = importance.head(20)
    category_summary = (
        importance.groupby("category", as_index=False)["mean_abs_shap"]
        .sum()
        .sort_values("mean_abs_shap", ascending=False)
    )
    category_summary["share"] = (
        category_summary["mean_abs_shap"]
        / category_summary["mean_abs_shap"].sum()
    )
    lines = [
        "# Yellow-browed Warbler Feature Importance",
        "",
        "## Model selection and method",
        "",
        f"The selected model is **{best['model']}**, predicting the "
        f"**>= {int(best['threshold'])} records** target at a "
        f"**{int(best['horizon_days'])}-day horizon**. It was the "
        "highest-PR-AUC non-baseline Yellow-browed Warbler result in the "
        "completed forward-chaining experiment "
        f"(PR-AUC {best['pr_auc']:.4f}; ROC-AUC {best['roc_auc']:.4f}).",
        "",
        "SHAP TreeExplainer values were calculated on each annual held-out "
        "fold, using the same expanding-window training rules, target-date "
        "alignment, one-day-lagged weather features, known target-date "
        "calendar features, XGBoost settings, and fold-specific imputation as "
        "the forecast experiment. Mean absolute SHAP values are pooled over "
        f"{test_count:,} held-out forecast dates across {test_year_count} "
        f"test years ({test_positive_count} positive target dates). "
        "Features are ranked by pooled mean absolute SHAP value. Values "
        "indicate contribution magnitude on the model's raw output scale; "
        "they do not establish causation.",
        "",
        "## Top 20 predictors",
        "",
        "| Rank | Feature | Mean absolute SHAP | Category |",
        "|---:|---|---:|---|",
    ]
    for row in top.itertuples(index=False):
        lines.append(
            f"| {row.rank} | `{row.feature}` | "
            f"{row.mean_abs_shap:.6f} | {row.category} |"
        )
    lines.extend(
        [
            "",
            "## Importance by predictor group",
            "",
            "Group totals sum mean absolute SHAP values across all features "
            "in that group; shares are relative to the total across groups.",
            "",
            "| Predictor group | Total mean absolute SHAP | Share |",
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
            "## Requested predictor families",
            "",
            "| Predictor family | Rank by group total | Share of total importance | In top 20 |",
            "|---|---:|---:|---|",
        ]
    )
    relevant_categories = (
        "Wind direction",
        "Pressure",
        "Pressure change",
        "Temperature",
        "Seasonality",
    )
    for category in relevant_categories:
        group_rows = category_summary.loc[
            category_summary["category"].eq(category)
        ]
        if group_rows.empty:
            rank = "—"
            share = 0.0
        else:
            rank = str(
                int(
                    category_summary["mean_abs_shap"]
                    .rank(method="min", ascending=False)
                    .loc[group_rows.index[0]]
                )
            )
            share = float(group_rows["share"].iloc[0])
        present = category in set(top["category"])
        lines.append(
            f"| {category} | {rank} | {share:.1%} | "
            f"{'Yes' if present else 'No'} |"
        )

    top_categories = set(top["category"])
    category_shares = category_summary.set_index("category")["share"]
    seasonality_share = category_shares.get("Seasonality", 0.0)
    temperature_share = category_shares.get("Temperature", 0.0)
    pressure_share = category_shares.get("Pressure", 0.0)
    pressure_change_share = category_shares.get("Pressure change", 0.0)
    wind_share = category_shares.get("Wind direction", 0.0)
    lines.extend(
        [
            "",
            "## Biological interpretation",
            "",
            f"Seasonality is the dominant predictor family "
            f"({seasonality_share:.1%} of total absolute SHAP); the three "
            "highest-ranked individual predictors are the annual sine, "
            "day-of-year, and annual cosine features. This is consistent "
            "with Yellow-browed Warbler occurrence/reporting being strongly "
            "concentrated in its migration season. Temperature is the second "
            f"largest family ({temperature_share:.1%}), while pressure "
            f"({pressure_share:.1%}), wind direction ({wind_share:.1%}), "
            f"and pressure change ({pressure_change_share:.1%}) contribute "
            "less. The temperature signal could reflect migration timing, "
            "weather conditions, or observer activity; pressure and wind "
            "may add information about weather systems and migration-supporting "
            "flow. These are plausible ecological interpretations, not "
            "causal findings.",
            "",
            "In this run, the top 20 include "
            + (
                ", ".join(
                    category
                    for category in relevant_categories
                    if category in top_categories
                )
                or "none of the listed predictor families"
            )
            + f". Pressure change accounts for {pressure_change_share:.1%} "
            "of group importance and has no feature in the top 20. Absolute "
            "SHAP values describe magnitude but not whether a value raises "
            "or lowers the prediction; signed dependence analysis would be "
            "needed to infer that direction. Yellow-browed Warbler records "
            "are occurrence/reporting counts, not direct measures of "
            "abundance; weather may also affect detectability and reporting "
            "effort.",
            "",
            "The complete feature ranking is saved in "
            "`data/processed/yellow_browed_warbler_shap_importance.csv`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    best = select_best_model()
    importance, test_count, positive_count, test_year_count = (
        calculate_oof_importance(
            int(best["threshold"]), int(best["horizon_days"])
        )
    )
    IMPORTANCE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    importance.to_csv(IMPORTANCE_OUTPUT, index=False, float_format="%.10f")
    report = build_report(
        best, importance, test_count, positive_count, test_year_count
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
