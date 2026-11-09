"""Tests for the Eastern Vagrancy Index dataset, predictor and hotspots."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import build_eastern_vagrancy_dataset as dataset
from src import forecast_eastern_locations as locations
from src import predict_eastern_vagrancy as predictor


def occurrences() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "countryCode": ["GB", "GB", "NL", "BE", "DK", "IE", "FR"],
            "decimalLatitude": [59.53, 53.58, 53.07, 51.33, 55.56, 51.44, 48.8],
            "decimalLongitude": [-1.63, 0.12, 4.78, 3.2, 8.1, -9.5, 2.3],
            "date": ["2019-10-10"] * 7,
        }
    )


def daily_counts() -> pd.DataFrame:
    return pd.DataFrame(
        {"date": ["2019-10-10", "2020-10-12", "2021-10-11"], "count": [20, 10, 30]}
    )


def national_forecast() -> pd.DataFrame:
    dates = pd.date_range("2022-10-11", periods=14)
    return pd.DataFrame(
        {"date": dates, "probability": [0.5 + 0.03 * i for i in range(14)]}
    )


class EasternDatasetTests(unittest.TestCase):
    def test_registry_covers_core_and_optional_species(self) -> None:
        names = {row["scientific_name"] for row in dataset.EASTERN_VAGRANCY_SPECIES}
        core = {row["scientific_name"] for row in dataset.EASTERN_VAGRANCY_SPECIES if row["core"]}
        self.assertEqual(len(core), 6)
        self.assertIn("Phylloscopus collybita tristis", core)
        self.assertIn("Motacilla citreola", names - core)
        self.assertEqual(set(dataset.TARGET_COUNTRIES), {"GB", "IE", "NL", "BE", "DK"})

    def test_unresolved_optional_species_is_skipped_but_core_fails(self) -> None:
        registry = [
            {"species": "Core", "scientific_name": "A a", "core": True},
        ]
        with patch.object(dataset, "resolve_taxon_key", side_effect=RuntimeError("x")):
            with self.assertRaises(RuntimeError):
                dataset.load_all_occurrences(registry)
            registry[0]["core"] = False
            result = dataset.load_all_occurrences(registry)
        self.assertTrue(result.empty)

    def test_outputs_pool_species_by_date(self) -> None:
        records = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-10-01", "2020-10-01", "2020-10-02"]),
                "species": ["Dusky Warbler", "Pallas's Warbler", "Dusky Warbler"],
                "countryCode": ["GB", "NL", "GB"],
            }
        )
        registry = [
            {"species": "Dusky Warbler"},
            {"species": "Pallas's Warbler"},
        ]
        summary, events, daily = dataset.build_outputs(records, registry)
        self.assertEqual(events["species_count"].tolist(), [2, 1])
        self.assertEqual(daily["count"].tolist(), [2, 1])
        self.assertEqual(summary.set_index("species").loc["Dusky Warbler", "records"], 2)


class EasternPredictorTests(unittest.TestCase):
    def test_risk_levels(self) -> None:
        self.assertEqual(
            [predictor.risk_level(p) for p in (0.05, 0.2, 0.4, 0.7)],
            ["LOW", "MODERATE", "HIGH", "VERY_HIGH"],
        )

    def test_rejects_other_artifacts(self) -> None:
        with self.assertRaises(ValueError):
            predictor.make_predictions(pd.DataFrame(), pd.DatetimeIndex([]), {"species": "x"})


class EasternLocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cells = locations.framework.add_suitability(
            locations.framework.build_grid(occurrences()),
            kind_weights=locations.EASTERN_KIND_WEIGHTS,
            west_facing_bonus=0.0,
            anchors=locations.EASTERN_ANCHORS,
            exposure_scale_km=locations.EASTERN_EXPOSURE_SCALE_KM,
            boosts=locations.EASTERN_BONUS_BOOSTS,
            sites=locations.EASTERN_SITES,
        )
        cls.result = locations.framework.calculate_atlantic_location_forecast(
            cls.cells,
            daily_counts(),
            national_forecast(),
            risk_function=predictor.risk_level,
        )

    def test_fair_isle_and_shetland_are_boosted_and_atlantic_groups_dropped(self) -> None:
        groups = {site.boost_group for site in locations.EASTERN_SITES}
        self.assertTrue({"Fair Isle", "Shetland", "Skagen"} <= groups)
        self.assertNotIn("Scilly Isles", groups)
        fair_isle = self.cells.loc[self.cells["nearest_site"].eq("Fair Isle")]
        self.assertGreater(fair_isle["bonus_boost"].max(), 1.4)

    def test_probability_bounds_and_ranking_order(self) -> None:
        self.assertTrue(self.result["forecast_probability"].between(0, 1).all())
        self.assertEqual(set(self.result["country"]) - set(locations.framework.TARGET_COUNTRIES), set())
        for _, day in self.result.groupby("date"):
            self.assertEqual(day["rank"].tolist(), list(range(1, len(day) + 1)))
            self.assertTrue(day["forecast_probability"].is_monotonic_decreasing)

    def test_top_ten_for_each_horizon(self) -> None:
        top = locations.top_hotspots(self.result)
        self.assertEqual(set(top), {1, 3, 7, 14})
        self.assertTrue(all(len(frame) <= 10 for frame in top.values()))

    def test_build_writes_files_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts = root / "counts.csv"
            daily_counts().to_csv(counts, index=False)
            with patch.object(locations, "load_all_occurrences", return_value=occurrences()):
                result = locations.build_eastern_location_forecast(
                    national_forecast(),
                    output_path=root / "detail.csv",
                    daily_counts_path=counts,
                    simple_output_path=root / "eastern_location_forecast.csv",
                    map_path=root / "eastern_location_forecast.png",
                )
            png = (root / "eastern_location_forecast.png").read_bytes()
            simple = pd.read_csv(root / "eastern_location_forecast.csv")
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(
            list(simple.columns),
            ["date", "location", "country", "latitude", "longitude",
             "probability", "anomaly_score", "rank"],
        )
        metadata = locations.hotspot_metadata(result)
        self.assertEqual(len(metadata["top10_locations"]), 10)
        self.assertIn("generated_at", metadata)


if __name__ == "__main__":
    unittest.main()
