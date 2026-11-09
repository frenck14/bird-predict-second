from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.build_dataset_v2 import STATION_FILES
from src.build_seabird_dataset import threshold_summary
from src.forecast_seabird_locations import (
    best_dutch_site,
    build_seabird_location_forecast,
)
from src.predict_seabird import risk_level
from src import forecast_seabird_locations as seabird_locations
from src.seabird_features import add_seabird_features


def _toy_weather() -> pd.DataFrame:
    dates = pd.date_range("2026-10-01", periods=4, freq="D")
    frame = pd.DataFrame({"date": dates})
    for station_id in STATION_FILES:
        frame[f"FG_{station_id}"] = [12.0, 16.0, 18.0, 14.0]
        frame[f"FHX_{station_id}"] = [130.0, 150.0, 170.0, 160.0]
        frame[f"DDVEC_{station_id}"] = [280.0, 290.0, 300.0, 310.0]
        frame[f"TG_{station_id}"] = [100.0, 110.0, 120.0, 130.0]
        frame[f"TX_{station_id}"] = [110.0, 120.0, 130.0, 140.0]
        frame[f"PX_{station_id}"] = [10150.0, 10120.0, 10080.0, 10050.0]
        frame[f"RH_{station_id}"] = [2.0, 3.0, 4.0, 5.0]
        frame[f"TN_{station_id}"] = [90.0, 95.0, 100.0, 105.0]
    return frame


class SeabirdFeatureTests(unittest.TestCase):
    def test_add_seabird_features_adds_expected_columns(self) -> None:
        engineered = add_seabird_features(_toy_weather())
        for column in (
            "coast_wind_speed",
            "coast_gust_speed",
            "coast_westerly_wind_component",
            "coast_southwest_wind_component",
            "coast_northwest_wind_component",
            "coast_pressure_tendency_24h",
            "coast_atlantic_storm_index",
            "coast_wave_proxy",
            "coast_sustained_onshore_flow",
        ):
            self.assertIn(column, engineered.columns)
        self.assertTrue(engineered["coast_wave_proxy"].notna().any())
        self.assertEqual(risk_level(0.0), "LOW")
        self.assertEqual(risk_level(0.95), "VERY_HIGH")

    def test_threshold_summary_uses_p90_cutoff(self) -> None:
        daily = pd.DataFrame({"date": pd.date_range("2026-10-01", periods=5), "count": [0, 1, 2, 10, 20]})
        summary = threshold_summary(daily)
        self.assertEqual(summary["percentile"], 90)
        self.assertGreaterEqual(summary["threshold_count"], 1)
        self.assertAlmostEqual(summary["prevalence"], 0.2)


class SeabirdLocationTests(unittest.TestCase):
    def test_build_seabird_location_forecast_writes_outputs(self) -> None:
        occurrences = pd.DataFrame(
            {
                "countryCode": ["NL", "GB"],
                "decimalLatitude": [53.06, 59.53],
                "decimalLongitude": [4.76, -1.63],
                "date": pd.to_datetime(["2020-10-01", "2021-10-01"]),
            }
        )
        national_forecast = pd.DataFrame(
            {
                "date": pd.date_range("2026-10-02", periods=14, freq="D"),
                "probability": [0.2 + (i / 100) for i in range(14)],
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            counts = directory / "counts.csv"
            pd.DataFrame(
                {
                    "date": pd.date_range("2020-09-01", periods=60, freq="D"),
                    "count": [0] * 57 + [1, 2, 3],
                }
            ).to_csv(counts, index=False)

            with (
                patch.object(
                    seabird_locations,
                    "load_all_occurrences",
                    return_value=occurrences,
                ),
                patch.object(
                    seabird_locations.framework,
                    "_seasonal_expected_probability",
                    return_value=0.5,
                ),
            ):
                result = build_seabird_location_forecast(
                    national_forecast,
                    output_path=directory / "detail.csv",
                    daily_counts_path=counts,
                    simple_output_path=directory / "simple.csv",
                    map_path=directory / "map.png",
                )
                self.assertFalse(result.empty)
                self.assertTrue((directory / "detail.csv").is_file())
                self.assertTrue((directory / "simple.csv").is_file())
                self.assertTrue((directory / "map.png").is_file())
                self.assertTrue(result["forecast_probability"].between(0, 1).all())
                first_day = result.loc[result["date"].eq(pd.Timestamp("2026-10-02"))]
                self.assertEqual(first_day["rank"].iloc[0], 1)
                self.assertGreaterEqual(
                    first_day.iloc[0]["forecast_probability"],
                    first_day.iloc[-1]["forecast_probability"],
                )
                self.assertEqual(
                    pd.read_csv(directory / "simple.csv").columns.tolist(),
                    [
                        "date", "location", "country", "latitude", "longitude",
                        "probability", "anomaly_score", "rank",
                    ],
                )
                self.assertEqual(best_dutch_site(result)["country"], "NL")


if __name__ == "__main__":
    unittest.main()
