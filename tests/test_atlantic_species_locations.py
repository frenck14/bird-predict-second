from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

from src import forecast_atlantic_species_locations as layers


def records() -> pd.DataFrame:
    dates = pd.to_datetime(
        [f"{year}-10-{day:02d}" for year in range(2015, 2024) for day in (8, 12)]
        + ["2021-04-02"]
    )
    count = len(dates)
    return pd.DataFrame(
        {
            "date": dates,
            "decimalLatitude": [49.92] * (count - 2) + [52.1, 52.1],
            "decimalLongitude": [-6.3] * (count - 2) + [5.1, 5.1],
            "countryCode": ["GB"] * (count - 2) + ["NL", "NL"],
        }
    )


def national_forecast() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-10-10", "2024-01-15"],
            "probability": [0.3, 0.3],
        }
    )


def daily_counts() -> pd.DataFrame:
    return pd.DataFrame(
        {"date": ["2019-10-10", "2020-10-12", "2021-10-11"], "count": [2, 1, 3]}
    )


class SpeciesLayerTests(unittest.TestCase):
    def test_registry_contains_requested_species_with_unique_slugs(self) -> None:
        names = {layer["species"] for layer in layers.SPECIES_LAYERS}
        self.assertEqual(len(layers.SPECIES_LAYERS), 10)
        self.assertTrue(
            {"Yellow-browed Warbler", "Bobolink", "Dark-eyed Junco"} <= names
        )
        slugs = [layer["slug"] for layer in layers.SPECIES_LAYERS]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_junco_is_not_in_the_guild_registry(self) -> None:
        from src.build_atlantic_vagrancy_dataset import ATLANTIC_VAGRANCY_SPECIES

        guild = {s["scientific_name"] for s in ATLANTIC_VAGRANCY_SPECIES}
        self.assertNotIn("Junco hyemalis", guild)

    def test_seasonal_curve_peaks_in_season_and_respects_floor(self) -> None:
        curve = layers.seasonal_curve(records()["date"])
        self.assertAlmostEqual(curve.max(), 1.0)
        october = layers._calendar_day_number(pd.Timestamp("2024-10-10")) - 1
        january = layers._calendar_day_number(pd.Timestamp("2024-01-15")) - 1
        self.assertGreater(curve[october], 0.9)
        self.assertEqual(curve[january], layers.SEASONAL_FLOOR)

    def test_species_suitability_is_relative_to_best_cell(self) -> None:
        cells = layers.species_cells(records(), {})
        self.assertAlmostEqual(cells["species_suitability"].max(), 1.0)
        self.assertGreater(cells["occupied_years"].max(), 5)
        self.assertEqual(
            cells.loc[cells["occupied_years"].eq(0), "species_suitability"]
            .lt(cells["species_suitability"].max())
            .all(),
            True,
        )

    def test_forecast_multiplies_all_four_terms_and_ranks(self) -> None:
        forecast, hotspots, anomalies = layers.calculate_species_layer(
            records(), {}, daily_counts(), national_forecast()
        )
        expected = (
            forecast["atlantic_national_probability"]
            * forecast["species_suitability"]
            * forecast["coastal_suitability"]
            * forecast["regional_suitability"]
        ).clip(0, 1)
        pd.testing.assert_series_equal(
            forecast["forecast_probability"], expected, check_names=False
        )
        october = forecast.loc[forecast["date"].eq("2024-10-10")]
        january = forecast.loc[forecast["date"].eq("2024-01-15")]
        self.assertGreater(
            october["forecast_probability"].max(),
            january["forecast_probability"].max(),
        )
        for date, day in hotspots.groupby("date"):
            for kind in ("HOTSPOT", "COLDSPOT"):
                group = day.loc[day["ranking_type"].eq(kind)]
                self.assertLessEqual(len(group), layers.TOP_N)
                self.assertEqual(list(group["rank"]), list(range(1, len(group) + 1)))
            hot = day.loc[day["ranking_type"].eq("HOTSPOT"), "forecast_probability"]
            cold = day.loc[day["ranking_type"].eq("COLDSPOT"), "forecast_probability"]
            self.assertTrue(hot.is_monotonic_decreasing)
            self.assertTrue(cold.is_monotonic_increasing)
        self.assertTrue(anomalies["anomaly_score"].gt(0).all())

    def test_eastern_profile_prefers_eastern_landfall(self) -> None:
        grid = layers.build_grid(
            pd.DataFrame(
                {
                    "countryCode": ["GB", "NL"],
                    "decimalLatitude": [49.92, 53.58],
                    "decimalLongitude": [-6.3, 0.12],
                    "date": ["2020-10-01", "2020-10-02"],
                }
            )
        )
        atlantic = layers.add_suitability(grid)
        eastern = layers.add_suitability(
            grid,
            anchors=layers.EASTERN_ANCHORS,
            west_facing_bonus=0.0,
            exposure_scale_km=400.0,
        )
        scilly = atlantic["nearest_site"].eq("Scilly Isles")
        spurn = atlantic["nearest_site"].eq("Spurn")
        self.assertGreater(
            eastern.loc[spurn, "regional_suitability"].iloc[0],
            eastern.loc[scilly, "regional_suitability"].iloc[0],
        )
        self.assertGreater(
            atlantic.loc[scilly, "regional_suitability"].iloc[0],
            atlantic.loc[spurn, "regional_suitability"].iloc[0],
        )

    def test_build_writes_three_csvs_and_summary(self) -> None:
        registry = [
            {"species": "Test Bird", "scientific_name": "Testus birdus", "slug": "test_bird"},
            {"species": "Empty Bird", "scientific_name": "Nullus avis", "slug": "empty_bird"},
        ]

        def fake(species: dict[str, object]) -> pd.DataFrame:
            if species["slug"] == "test_bird":
                return records()
            return pd.DataFrame()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts = root / "counts.csv"
            daily_counts().to_csv(counts, index=False)
            with patch.object(layers, "load_species_occurrences", side_effect=fake):
                summary = layers.build_species_layers(
                    national_forecast(),
                    registry,
                    output_directory=root,
                    daily_counts_path=counts,
                    summary_path=root / "summary.csv",
                )
            paths = layers.species_output_paths("test_bird", root)
            for path in paths.values():
                self.assertTrue(path.is_file(), path)
            self.assertFalse(layers.species_output_paths("empty_bird", root)["location"].exists())
            hotspot_columns = pd.read_csv(paths["hotspots"]).columns
            self.assertIn("ranking_type", hotspot_columns)
        statuses = dict(zip(summary["slug"], summary["status"]))
        self.assertEqual(statuses, {"test_bird": "OK", "empty_bird": "NO_DATA"})

    def test_large_queries_are_downloaded_in_year_partitions(self) -> None:
        from src import build_atlantic_vagrancy_dataset as dataset

        def fake_fetch(url: str) -> dict[str, object]:
            query = parse_qs(urlparse(url).query)
            if "facet" in query:
                return {
                    "count": 5,
                    "facets": [
                        {"counts": [
                            {"name": "2020", "count": 3},
                            {"name": "2021", "count": 2},
                        ]}
                    ],
                }
            year = query.get("year", [None])[0]
            count = {"2020": 3, "2021": 2}.get(year, 5)
            offset = int(query["offset"][0])
            limit = int(query["limit"][0])
            results = [
                {
                    "key": int(year or 0) * 10 + index,
                    "taxonKey": 7,
                    "countryCode": "GB",
                    "basisOfRecord": "HUMAN_OBSERVATION",
                    "eventDate": f"{year or 2020}-10-01",
                    "decimalLatitude": 52.0,
                    "decimalLongitude": 1.0,
                }
                for index in range(offset, min(offset + limit, count))
            ]
            return {"count": count, "results": results}

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(dataset, "RAW_DIRECTORY", Path(directory)),
                patch.object(dataset, "_fetch_json", side_effect=fake_fetch),
                patch.object(dataset, "YEAR_PARTITION_THRESHOLD", 1),
                patch.object(dataset, "PAGE_SIZE", 2),
            ):
                frame = dataset.download_species_country("Bird", "Testus birdus", "GB", 7)
        self.assertEqual(len(frame), 5)


if __name__ == "__main__":
    unittest.main()
