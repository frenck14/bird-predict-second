from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.seabird_validation import (
    DataLeakageError,
    StrictValidationUnavailable,
    _fit_cutoff_model,
    _predict_from_cutoff,
    calculate_validation_metrics,
    check_data_leakage,
    evaluate_forecast,
    filter_to_cutoff_date,
)
from src import seabird_validation as validation


class SeabirdValidationTests(unittest.TestCase):
    def test_filter_to_cutoff_date_keeps_cutoff_and_drops_future_rows(self) -> None:
        records = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2020-06-29", "2020-06-30", "2020-07-01"]
                ),
                "value": [1, 2, 3],
            }
        )

        filtered = filter_to_cutoff_date(records, date(2020, 6, 30))

        self.assertEqual(filtered["value"].tolist(), [1, 2])
        self.assertEqual(len(records), 3)

    def test_leakage_check_reports_the_source(self) -> None:
        with self.assertRaisesRegex(DataLeakageError, "hotspot history records"):
            check_data_leakage(
                {
                    "hotspot history records": pd.DataFrame(
                        {"date": pd.to_datetime(["2020-07-01"])}
                    )
                },
                {},
                date(2020, 6, 30),
            )

    def test_leakage_check_rejects_future_weather_and_occurrences(self) -> None:
        for source in ("weather records", "occurrence records"):
            with self.subTest(source=source):
                with self.assertRaisesRegex(DataLeakageError, source):
                    check_data_leakage(
                        {
                            source: pd.DataFrame(
                                {"date": pd.to_datetime(["2020-07-01"])}
                            )
                        },
                        {},
                        date(2020, 6, 30),
                    )

    def test_leakage_check_rejects_artifact_trained_after_cutoff(self) -> None:
        with self.assertRaisesRegex(DataLeakageError, "training_end_date"):
            check_data_leakage(
                {},
                {
                    "General Seabird Index": {
                        "training_end_date": "2020-07-01"
                    }
                },
                date(2020, 6, 30),
            )

    def test_validation_metrics_use_training_cutoff_for_event_labels(self) -> None:
        forecast = pd.DataFrame(
            {
                "product": ["General Seabird Index", "Northern Fulmar"],
                "probability": [0.8, 0.1],
            }
        )
        observations = pd.DataFrame(
            {
                "product": ["General Seabird Index", "Northern Fulmar"],
                "count": [10, 0],
            }
        )

        metrics = calculate_validation_metrics(
            forecast,
            observations,
            {
                "General Seabird Index": 5,
                "Northern Fulmar": 1,
            },
        )

        self.assertEqual(metrics["actual_event"].tolist(), [1, 0])
        self.assertEqual(metrics["predicted_event"].tolist(), [1, 0])
        self.assertAlmostEqual(metrics.iloc[0]["brier_score"], 0.04)
        self.assertAlmostEqual(metrics.iloc[1]["brier_score"], 0.01)

    def test_fit_model_uses_only_weather_before_each_training_target(self) -> None:
        class CaptureModel:
            def fit(self, features: pd.DataFrame, labels: pd.Series) -> None:
                self.features = features.copy()
                self.labels = labels.copy()

        model = CaptureModel()
        weather = pd.DataFrame(
            {
                "date": pd.date_range("2020-01-01", periods=10, freq="D"),
                "weather": range(10),
            }
        )
        occurrences = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2020-01-02", "2020-01-04", "2020-01-06", "2020-01-08"]
                ),
                "species": ["Northern Fulmar"] * 4,
            }
        )
        with (
            patch.object(validation, "_build_seabird_features", side_effect=lambda frame: frame),
            patch.object(validation, "weather_feature_columns", return_value=["weather"]),
            patch.object(validation, "make_estimator", return_value=model),
            patch.object(validation, "influx_cutoff", return_value=1.0),
        ):
            artifact = _fit_cutoff_model(
                weather, occurrences, date(2020, 1, 10), "Northern Fulmar", 3
            )

        self.assertEqual(artifact["training_end_date"], "2020-01-10")
        self.assertLessEqual(
            pd.Timestamp(artifact["trained_through_weather_date"]),
            pd.Timestamp("2020-01-10"),
        )
        self.assertLessEqual(model.features["weather"].max(), 6)
        self.assertTrue(model.labels.isin([0, 1]).all())

    def test_prediction_rejects_weather_after_analysis_date(self) -> None:
        weather = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-06-30", "2020-07-01"]),
                "weather": [1.0, 2.0],
            }
        )
        with self.assertRaisesRegex(DataLeakageError, "weather inputs"):
            _predict_from_cutoff(
                weather,
                date(2020, 6, 30),
                date(2020, 7, 1),
                {},
            )

    def test_prediction_uses_only_the_cutoff_weather_snapshot(self) -> None:
        class CaptureModel:
            def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
                self.features = features.copy()
                return np.array([[0.7, 0.3]])

        model = CaptureModel()
        weather = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-06-29", "2020-06-30"]),
                "weather": [4.0, 5.0],
            }
        )
        artifact = {
            "model": model,
            "feature_columns": ["month", "weather"],
            "weather_feature_columns": ["weather"],
        }
        with patch.object(
            validation,
            "_build_seabird_features",
            side_effect=lambda frame: frame,
        ):
            probability = _predict_from_cutoff(
                weather, date(2020, 6, 30), date(2020, 7, 14), artifact
            )

        self.assertAlmostEqual(probability, 0.3)
        self.assertEqual(model.features["weather"].tolist(), [5.0])
        self.assertEqual(model.features["month"].tolist(), [7])

    def test_missing_holdout_observations_are_reported_unavailable(self) -> None:
        with patch.object(
            validation,
            "load_cached_occurrences",
            return_value=pd.DataFrame(
                {
                    "date": pd.to_datetime(["2020-07-01"]),
                    "species": ["Northern Fulmar"],
                }
            ),
        ):
            from src.seabird_validation import load_validation_observations

            with self.assertRaisesRegex(
                StrictValidationUnavailable,
                "Strict validation unavailable for this date",
            ):
                load_validation_observations(
                    [date(2020, 7, 1), date(2020, 7, 2)]
                )

    def test_evaluation_accepts_only_the_next_day_holdout(self) -> None:
        result = {
            "analysis_date": date(2020, 6, 30),
            "target_date": date(2020, 7, 1),
            "forecasts": {
                "Northern Fulmar": pd.DataFrame(
                    {"date": [pd.Timestamp("2020-07-01")], "probability": [0.1]}
                )
            },
            "artifacts": {
                "Northern Fulmar": {"influx_threshold_count": 1.0}
            },
        }
        observations = pd.DataFrame(
            {
                "product": ["Northern Fulmar"],
                "count": [0],
                "date": [pd.Timestamp("2020-07-01")],
            }
        )

        metrics = evaluate_forecast(
            result,
            observations,
            data_cutoff_date=date(2020, 6, 30),
        )
        self.assertEqual(metrics.iloc[0]["actual_event"], 0)

        observations.loc[0, "date"] = pd.Timestamp("2020-07-02")
        with self.assertRaisesRegex(ValueError, "limited to the day after the cutoff"):
            evaluate_forecast(
                result,
                observations,
                data_cutoff_date=date(2020, 6, 30),
            )

    def test_evaluation_accepts_a_three_day_holdout(self) -> None:
        analysis_date = date(2020, 6, 30)
        dates = pd.date_range("2020-07-01", periods=3, freq="D")
        result = {
            "analysis_date": analysis_date,
            "target_date": date(2020, 7, 1),
            "target_dates": list(dates.date),
            "holdout_days": 3,
            "forecasts": {
                "Northern Fulmar": pd.DataFrame(
                    {
                        "date": dates,
                        "probability": [0.1, 0.4, 0.9],
                        "event_threshold_count": [1.0, 2.0, 3.0],
                    }
                )
            },
            "artifacts": {},
        }
        observations = pd.DataFrame(
            {
                "product": ["Northern Fulmar"] * 3,
                "count": [0, 2, 4],
                "date": dates,
            }
        )

        metrics = evaluate_forecast(
            result, observations, data_cutoff_date=analysis_date
        )

        self.assertEqual(metrics["date"].tolist(), list(dates))
        self.assertEqual(metrics["actual_event"].tolist(), [0, 1, 1])
        self.assertEqual(metrics["event_threshold_count"].tolist(), [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
