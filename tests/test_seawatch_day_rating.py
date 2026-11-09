from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src import seawatch_day_rating as rating


class RatingFormulaTests(unittest.TestCase):
    def test_category_boundaries(self):
        self.assertEqual(rating.rating_category(0), "Poor")
        self.assertEqual(rating.rating_category(24), "Poor")
        self.assertEqual(rating.rating_category(25), "Fair")
        self.assertEqual(rating.rating_category(50), "Good")
        self.assertEqual(rating.rating_category(70), "Excellent")
        self.assertEqual(rating.rating_category(85), "Major Seawatch Day")

    def test_weighted_score_weather_bonuses_and_cap(self):
        probabilities = {
            "General Seabird Index": 0.5,
            "European Storm-petrel": 0.4,
            "Manx Shearwater": 0.3,
            "Sooty Shearwater": 0.2,
        }
        score = rating.calculate_rating(probabilities)
        self.assertEqual(score["base_score"], 40)
        self.assertEqual(score["score"], 40)
        all_bonuses = {
            key: True for key in rating.WEATHER_BONUSES
        }
        boosted = rating.calculate_rating(
            {key: 1.0 for key in rating.RATING_WEIGHTS}, all_bonuses
        )
        self.assertEqual(boosted["score"], 100)
        self.assertEqual(boosted["rating"], "Major Seawatch Day")
        self.assertEqual(boosted["weather_bonus"], 30)

    def test_reject_invalid_probabilities(self):
        probabilities = {key: 0.5 for key in rating.RATING_WEIGHTS}
        probabilities["Manx Shearwater"] = 1.1
        with self.assertRaises(ValueError):
            rating.calculate_rating(probabilities)

    def test_weather_bonus_conditions(self):
        dates = pd.to_datetime(["2026-10-16", "2026-10-17"])
        direction = math_radians = np.deg2rad(270.0)
        engineered = pd.DataFrame(
            {
                "date": dates,
                "coast_wind_speed": [9.0, 11.0],
                "coast_wind_sin": [np.sin(math_radians)] * 2,
                "coast_wind_cos": [np.cos(math_radians)] * 2,
                "coast_PX_min": [10020.0, 9990.0],
            }
        )
        with patch.object(
            rating, "_build_seabird_features", return_value=engineered
        ):
            flags, details = rating._weather_conditions(
                pd.DataFrame({"date": dates}),
                pd.Timestamp("2026-10-18"),
            )
        self.assertEqual(
            flags,
            {
                "strong_westerly_wind": True,
                "deep_atlantic_low": True,
                "increasing_wind": True,
                "peak_seawatching_season": True,
            },
        )
        self.assertAlmostEqual(details["wind_speed_kt"], 21.4, places=1)
        self.assertAlmostEqual(details["wind_change_ms"], 2.0)

    def test_rating_and_hotspot_outputs(self):
        dates = pd.date_range("2026-10-18", periods=14, freq="D")
        general = pd.DataFrame({"date": dates, "probability": [0.3] * 14})
        species_forecasts = {
            species: pd.DataFrame({"date": dates, "probability": [0.2] * 14})
            for species in rating.SPECIES_FORECASTS
        }
        location_rows = []
        for day in dates:
            for index, (location, country, easting, northing) in enumerate(
                [("Texel", "NL", 1000, 2000), ("Fair Isle", "GB", 3000, 4000)]
            ):
                location_rows.append(
                    {
                        "date": day,
                        "country": country,
                        "location": location,
                        "grid_easting": easting,
                        "grid_northing": northing,
                        "center_latitude": 53.0 + index,
                        "center_longitude": 4.0 - index,
                        "forecast_probability": 0.4 - index * 0.1,
                    }
                )
        general_locations = pd.DataFrame(location_rows)
        species_locations = {}
        for species in rating.SPECIES_FORECASTS:
            rows = []
            for day in dates:
                for index, (country, easting, northing, probability) in enumerate(
                    [("NL", 1000, 2000, 0.25), ("GB", 3000, 4000, 0.15)]
                ):
                    rows.append(
                        {
                            "date": day,
                            "country": country,
                            "grid_easting": easting,
                            "grid_northing": northing,
                            "forecast_probability": probability + index * 0.01,
                        }
                    )
            species_locations[species] = pd.DataFrame(rows)
        with patch.object(
            rating,
            "_weather_conditions",
            return_value=(
                {key: False for key in rating.WEATHER_BONUSES},
                {
                    "wind_direction": "unknown",
                    "wind_speed_kt": None,
                    "minimum_pressure_hpa": None,
                    "wind_change_ms": None,
                },
            ),
        ):
            daily, hotspots, document = rating.build_rating_products(
                general,
                species_forecasts,
                general_locations,
                species_locations,
                generated_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
            )
        self.assertEqual(len(daily), 14)
        self.assertEqual(
            daily.loc[daily["horizon"].ne(""), "horizon"].tolist(),
            ["Tomorrow", "+3 days", "+7 days", "+14 days"],
        )
        self.assertEqual(set(hotspots["horizon"]), set(rating.HORIZONS.values()))
        self.assertTrue(hotspots.groupby("horizon").size().eq(2).all())
        self.assertTrue(daily["score"].between(0, 100).all())
        self.assertEqual(document["product"], "Seawatch Day Rating")
        self.assertEqual(len(document["horizons"]), 4)
        self.assertEqual(document["horizons"][0]["top3_dutch_sites"][0]["location"], "Texel")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {
                "rating_path": root / "seawatch_day_rating.csv",
                "hotspots_path": root / "seawatch_day_hotspots.csv",
                "json_path": root / "seawatch_day_rating.json",
            }
            rating.save_rating_products(
                daily, hotspots, document, **paths
            )
            self.assertTrue(paths["rating_path"].is_file())
            self.assertTrue(paths["hotspots_path"].is_file())
            saved = json.loads(paths["json_path"].read_text())
            self.assertEqual(saved["horizons"][0]["score"], daily.iloc[0]["score"])


if __name__ == "__main__":
    unittest.main()
