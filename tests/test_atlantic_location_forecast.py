from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import forecast_atlantic_locations as locations


def occurrences() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "countryCode": ["GB", "NL", "BE", "DK", "IE", "FR"],
            "decimalLatitude": [49.92, 51.53, 51.33, 57.74, 51.44, 48.8],
            "decimalLongitude": [-6.3, 3.45, 3.2, 10.6, -9.5, 2.3],
            "date": ["2019-10-10"] * 6,
        }
    )


def daily_counts() -> pd.DataFrame:
    return pd.DataFrame(
        {"date": ["2019-10-10", "2020-10-12", "2021-10-11"], "count": [2, 1, 3]}
    )


def national_forecast() -> pd.DataFrame:
    dates = pd.date_range("2022-10-11", periods=14)
    return pd.DataFrame(
        {"date": dates, "probability": [0.02 + 0.01 * i for i in range(14)]}
    )


class AtlanticLocationForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cells = locations.add_suitability(
            locations.build_grid(occurrences())
        )
        cls.result = locations.calculate_atlantic_location_forecast(
            cls.cells, daily_counts(), national_forecast()
        )

    def test_requested_bonus_regions_boost_their_cells(self) -> None:
        regions = {
            "Scilly Isles",
            "Fair Isle",
            "Shetland",
            "Outer Hebrides",
            "Norfolk coast",
            "East Yorkshire coast",
            "Zeeland coast",
            "Belgian coast",
            "Skagen",
        }
        self.assertTrue(regions <= set(locations.BONUS_BOOSTS))
        sites = {site.boost_group for site in locations.SITES}
        self.assertTrue(regions <= sites)
        for region in ("Zeeland coast", "Belgian coast", "Skagen"):
            site = next(s for s in locations.SITES if s.boost_group == region)
            boosted = self.cells.loc[self.cells["nearest_site"].eq(site.name)]
            self.assertFalse(boosted.empty, region)
            self.assertGreater(boosted["bonus_boost"].max(), 1.1)

    def test_only_target_countries_are_forecast(self) -> None:
        self.assertEqual(
            set(self.result["country"]) - {"GB", "IE", "NL", "BE", "DK"}, set()
        )

    def test_probability_bounds_and_ranking_order(self) -> None:
        self.assertTrue(self.result["forecast_probability"].between(0, 1).all())
        for _, day in self.result.groupby("date"):
            ordered = day.sort_values("rank")
            self.assertEqual(list(ordered["rank"]), list(range(1, len(day) + 1)))
            self.assertTrue(ordered["forecast_probability"].is_monotonic_decreasing)

    def test_locations_are_unique_per_date(self) -> None:
        for _, day in self.result.groupby("date"):
            self.assertTrue(day["location"].is_unique)

    def test_simple_schema(self) -> None:
        simple = locations.simple_location_forecast(self.result)
        self.assertEqual(
            list(simple.columns),
            [
                "date",
                "location",
                "country",
                "latitude",
                "longitude",
                "probability",
                "anomaly_score",
                "rank",
            ],
        )

    def test_top_ten_for_each_horizon(self) -> None:
        top = locations.top_hotspots(self.result)
        self.assertEqual(set(top), {1, 3, 7, 14})
        days = locations.horizon_dates(self.result["date"])
        for horizon, frame in top.items():
            self.assertLessEqual(len(frame), 10)
            self.assertTrue(frame["date"].eq(days[horizon]).all())
            self.assertTrue(frame["forecast_probability"].is_monotonic_decreasing)

    def test_missing_horizon_date_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            locations.horizon_dates(self.result.loc[self.result["date"].lt("2022-10-20"), "date"])

    def test_map_is_generated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = locations.save_location_map(
                self.result, Path(directory) / "map.png"
            )
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_build_writes_all_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts = root / "counts.csv"
            daily_counts().to_csv(counts, index=False)
            with patch.object(
                locations, "load_all_occurrences", return_value=occurrences()
            ):
                locations.build_atlantic_location_forecast(
                    national_forecast(),
                    output_path=root / "detail.csv",
                    daily_counts_path=counts,
                    simple_output_path=root / "atlantic_location_forecast.csv",
                    map_path=root / "atlantic_location_forecast.png",
                )
            self.assertTrue((root / "detail.csv").is_file())
            self.assertTrue((root / "atlantic_location_forecast.png").is_file())
            simple = pd.read_csv(root / "atlantic_location_forecast.csv")
        self.assertEqual(len(simple), len(self.result))
        self.assertTrue(simple["probability"].between(0, 1).all())

    def test_hotspot_metadata(self) -> None:
        metadata = locations.hotspot_metadata(self.result)
        self.assertEqual(
            set(metadata),
            {
                "strongest_location",
                "strongest_probability",
                "top10_locations",
                "generated_at",
            },
        )
        top = metadata["top10_locations"]
        self.assertEqual(top[0]["location"], metadata["strongest_location"])
        self.assertEqual(top[0]["probability"], metadata["strongest_probability"])
        self.assertLessEqual(len(top), 10)


if __name__ == "__main__":
    unittest.main()
