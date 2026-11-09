"""Forward-chaining weather forecasts for high bird-record-count days."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_FILE = ROOT / "data/processed/bird_predict_dataset_v2.csv"
HORIZONS_DAYS = (1, 3, 5, 7, 14)
FIRST_TEST_YEAR = 2015
CALENDAR_FEATURES = ("month", "day_of_year_sin", "day_of_year_cos")
EXCLUDED_COLUMNS = {"date", "n_records", "influx", *CALENDAR_FEATURES}


def load_data(data_file: Path) -> pd.DataFrame:
    """Load and validate the daily dataset used by the experiment."""
    if not data_file.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {data_file}. Build it with "
            "`python src/build_dataset_v2.py` first."
        )

    data = pd.read_csv(data_file, parse_dates=["date"]).sort_values("date")
    required = {"date", "n_records", *CALENDAR_FEATURES}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    if data["date"].isna().any() or data["date"].duplicated().any():
        raise ValueError("Dataset dates must be valid and unique.")

    data = data.reset_index(drop=True)
    expected_dates = pd.date_range(
        data["date"].min(), data["date"].max(), freq="D"
    )
    if not data["date"].equals(pd.Series(expected_dates, name="date")):
        raise ValueError("Dataset must contain one row for every calendar day.")

    data["influx"] = (data["n_records"] >= 10).astype(int)
    if data["influx"].nunique() < 2:
        raise ValueError("The dataset must contain both influx and non-influx days.")
    return data


def build_supervised_data(
    data: pd.DataFrame, horizon_days: int, weather_features: list[str]
) -> pd.DataFrame:
    """Align origin-date weather and known target-date calendar features."""
    features = pd.concat(
        [
            data[weather_features].shift(1),
            data[list(CALENDAR_FEATURES)].shift(-horizon_days),
        ],
        axis=1,
    )
    supervised = features.copy()
    supervised.insert(0, "origin_date", data["date"])
    supervised.insert(1, "target_date", data["date"].shift(-horizon_days))
    supervised["target"] = data["influx"].shift(-horizon_days)
    return supervised.dropna(subset=["target_date", "target"]).reset_index(drop=True)


def make_model(name: str, positives: int, negatives: int) -> Pipeline:
    if name == "Random Forest":
        estimator = RandomForestClassifier(
            n_estimators=300,
            min_samples_leaf=3,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )
    elif name == "XGBoost":
        estimator = XGBClassifier(
            n_estimators=150,
            max_depth=2,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            reg_lambda=2,
            scale_pos_weight=negatives / positives,
            eval_metric="logloss",
            n_jobs=1,
            random_state=42,
            verbosity=0,
        )
    else:
        raise ValueError(f"Unsupported model: {name}")

    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("model", estimator),
        ]
    )


def run_experiment(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    weather_features = [
        column for column in data.columns if column not in EXCLUDED_COLUMNS
    ]
    if not weather_features:
        raise ValueError("No weather features are available.")

    latest_origin = data["date"].max() - pd.Timedelta(days=max(HORIZONS_DAYS))
    last_test_year = int(latest_origin.year)
    models = ("Random Forest", "XGBoost")
    prediction_rows: list[dict[str, object]] = []

    for horizon_days in HORIZONS_DAYS:
        supervised = build_supervised_data(data, horizon_days, weather_features)
        eligible_origins = supervised["origin_date"].le(latest_origin)
        supervised = supervised.loc[eligible_origins]

        for test_year in range(FIRST_TEST_YEAR, last_test_year + 1):
            fold_start = pd.Timestamp(year=test_year, month=1, day=1)
            next_fold_start = pd.Timestamp(year=test_year + 1, month=1, day=1)
            train = supervised.loc[supervised["target_date"] < fold_start]
            test = supervised.loc[
                supervised["origin_date"].ge(fold_start)
                & supervised["origin_date"].lt(next_fold_start)
            ]
            if test.empty:
                continue

            positives = int(train["target"].sum())
            negatives = len(train) - positives
            if positives == 0 or negatives == 0:
                raise ValueError(
                    f"Training fold before {test_year} does not contain both classes."
                )

            # Select usable columns using training data only; do not learn
            # feature availability from the held-out period.
            feature_columns = [
                column
                for column in weather_features + list(CALENDAR_FEATURES)
                if train[column].notna().any()
            ]
            if not feature_columns:
                raise ValueError(f"No usable features before test year {test_year}.")

            train_x = train[feature_columns]
            train_y = train["target"].astype(int)
            test_x = test[feature_columns]
            test_y = test["target"].astype(int)

            for model_name in models:
                model = make_model(model_name, positives, negatives)
                model.fit(train_x, train_y)
                probabilities = model.predict_proba(test_x)[:, 1]

                prediction_rows.extend(
                    {
                        "horizon_days": horizon_days,
                        "model": model_name,
                        "origin_date": origin_date,
                        "target_date": target_date,
                        "target": int(target_value),
                        "probability": float(probability),
                    }
                    for origin_date, target_date, target_value, probability in zip(
                        test["origin_date"],
                        test["target_date"],
                        test_y,
                        probabilities,
                        strict=True,
                    )
                )

    predictions = pd.DataFrame(prediction_rows)
    if predictions.empty:
        raise ValueError("No forward-chaining predictions were produced.")

    summary_rows = []
    for (horizon_days, model_name), group in predictions.groupby(
        ["horizon_days", "model"], sort=True
    ):
        summary_rows.append(
            {
                "horizon_days": horizon_days,
                "model": model_name,
                "pr_auc": average_precision_score(
                    group["target"], group["probability"]
                ),
                "baseline_prevalence": group["target"].mean(),
                "positive_days": int(group["target"].sum()),
                "test_days": len(group),
                "test_years": group["origin_date"].dt.year.nunique(),
            }
        )
    summary = pd.DataFrame(summary_rows)
    return summary, predictions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="Path to the processed v2 daily dataset.",
    )
    args = parser.parse_args()

    data = load_data(args.data)
    summary, _ = run_experiment(data)
    summary["useful"] = summary["pr_auc"] > summary["baseline_prevalence"]
    best_by_horizon = summary.loc[
        summary.groupby("horizon_days")["pr_auc"].idxmax()
    ].sort_values("horizon_days")

    print(
        f"Data: {data['date'].min().date()} to {data['date'].max().date()} "
        f"({len(data):,} days; {int(data['influx'].sum())} influx days)."
    )
    print(
        f"Forward-chaining test origins: {FIRST_TEST_YEAR}-01-01 to "
        f"{(data['date'].max() - pd.Timedelta(days=max(HORIZONS_DAYS))).date()} "
        f"({int(summary['test_years'].max())} annual folds per model/horizon)."
    )
    print(
        "PR-AUC is average precision over pooled out-of-fold predictions. "
        "A horizon is useful when at least one model beats the pooled test "
        "prevalence baseline."
    )
    print(
        summary[
            [
                "horizon_days",
                "model",
                "pr_auc",
                "baseline_prevalence",
                "positive_days",
                "test_days",
                "test_years",
                "useful",
            ]
        ].to_string(
            index=False,
            formatters={
                "pr_auc": "{:.4f}".format,
                "baseline_prevalence": "{:.4f}".format,
            },
        )
    )

    useful_horizons = best_by_horizon.loc[
        best_by_horizon["pr_auc"] > best_by_horizon["baseline_prevalence"],
        "horizon_days",
    ]
    if useful_horizons.empty:
        print("Maximum useful forecasting lead time: none of the tested horizons.")
    else:
        print(
            "Maximum useful forecasting lead time: "
            f"{int(useful_horizons.max())} days."
        )


if __name__ == "__main__":
    main()
