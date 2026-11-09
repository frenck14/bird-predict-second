from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import forecast_seabird_species as species_forecast
from src.build_seabird_dataset import build_species_daily_counts
from src.forecast_atlantic_locations import HORIZONS
from src.train_seabird_species_models import SPECIES_NAMES, SLUGS


class SeabirdSpeciesDatasetTests(unittest.TestCase):
    def test_species_daily_counts_pool_countries_by_species_and_date(self):
        records = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2020-10-01T00:00",
                        "2020-10-01T12:00",
                        "2020-10-02T00:00",
                    ],
                    format="ISO8601",
                ),
                "species": ["Northern Fulmar", "Northern Fulmar", "Manx Shearwater"],
            }
        )
        counts = build_species_daily_counts(records)
        self.assertEqual(
            counts.to_dict(orient="records"),
            [
                {"date": pd.Timestamp("2020-10-02"), "species": "Manx Shearwater", "count": 1},
                {"date": pd.Timestamp("2020-10-01"), "species": "Northern Fulmar", "count": 2},
            ],
        )

    def test_species_registry_has_independent_products(self):
        self.assertEqual(len(SPECIES_NAMES), 5)
        self.assertEqual(len(set(SLUGS.values())), 5)
        for species in SPECIES_NAMES:
            paths = species_forecast.species_output_paths(species)
            self.assertTrue(paths["forecast"].name.endswith("_forecast.csv"))
            self.assertTrue(paths["location"].name.endswith("_location_forecast.csv"))


class SeabirdSpeciesLocationTests(unittest.TestCase):
    def test_species_location_forecast_writes_horizon_top_tens_and_map(self):
        species = "European Storm-petrel"
        records = pd.DataFrame(
            {
                "species": [species] * 8,
                "countryCode": ["NL", "NL", "GB", "GB", "NL", "GB", "IE", "DK"],
                "decimalLatitude": [53.06, 52.96, 59.53, 60.24, 51.63, 58.20, 53.61, 55.55],
                "decimalLongitude": [4.76, 4.76, -1.63, -1.21, 3.69, -6.70, -10.22, 8.08],
                "date": pd.to_datetime(
                    [
                        "2010-10-01", "2011-10-03", "2012-10-05", "2013-10-07",
                        "2014-10-09", "2015-10-11", "2016-10-13", "2017-10-15",
                    ]
                ),
            }
        )
        forecast = pd.DataFrame(
            {
                "date": pd.date_range("2026-10-18", periods=14, freq="D"),
                "probability": [0.2 + day / 100 for day in range(14)],
                "risk_level": ["MODERATE"] * 14,
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            counts_path = output_dir / "species_counts.csv"
            count_dates = pd.date_range("2010-01-01", "2025-12-31", freq="D")
            pd.DataFrame(
                {
                    "date": count_dates,
                    "species": species,
                    "count": [int(day.dayofyear in (274, 276, 278)) for day in count_dates],
                }
            ).to_csv(counts_path, index=False)
            with patch.object(
                species_forecast.framework,
                "_seasonal_expected_probability",
                return_value=0.2,
            ):
                detailed, hotspots = species_forecast.build_species_location_forecast(
                    species,
                    records,
                    forecast,
                    daily_counts_path=counts_path,
                    output_directory=output_dir,
                )
            paths = species_forecast.species_output_paths(species, output_dir)
            for key in ("location", "detail", "hotspots", "map"):
                self.assertTrue(paths[key].is_file(), key)
            compact = pd.read_csv(paths["location"])
            self.assertEqual(
                compact.columns.tolist(),
                [
                    "date", "location", "country", "latitude", "longitude",
                    "probability", "anomaly_score", "rank",
                ],
            )
            self.assertTrue(detailed["forecast_probability"].between(0, 1).all())
            self.assertEqual(set(hotspots["horizon_days"]), set(HORIZONS))
            self.assertTrue(hotspots.groupby("horizon_days").size().eq(10).all())
            self.assertTrue(
                hotspots.groupby("date")["forecast_probability"]
                .apply(lambda values: values.is_monotonic_decreasing)
                .all()
            )


if __name__ == "__main__":
    unittest.main()
