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
            "countryCode": ["GB", "NL", "FR"],
            "decimalLatitude": [49.92, 52.1, 48.8],
            "decimalLongitude": [-6.3, 5.1, 2.3],
            "date": ["2019-10-10", "2020-10-10", "2020-10-11"],
        }
    )


def daily_counts() -> pd.DataFrame:
    return pd.DataFrame(
        {"date": ["2019-10-10", "2020-10-12", "2021-10-11"], "count": [2, 1, 3]}
    )


class AtlanticLocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cells = locations.add_suitability(
            locations.build_grid(occurrences())
        )

    def test_grid_excludes_other_countries_and_adds_site_cells(self) -> None:
        self.assertEqual(
            set(self.cells["country"]).difference(["GB", "IE", "NL", "BE", "DK"]),
            set(),
        )
        self.assertGreater(len(self.cells), 3)
        self.assertEqual(self.cells["cell_id"].nunique(), len(self.cells))

    def test_bonus_sites_outrank_inland_cells(self) -> None:
        score = self.cells["coastal_suitability"] * self.cells["regional_suitability"]
        best = self.cells.loc[score.idxmax()]
        self.assertIn(best["nearest_site"], {"Scilly Isles", "Fair Isle"})
        self.assertGreater(best["bonus_boost"], 1.4)
        inland = self.cells.loc[self.cells["nearest_site"].eq("")]
        self.assertTrue(
            inland.empty or inland["coastal_suitability"].max() < 0.5
        )

    def test_forecast_is_product_bounded_and_ranked(self) -> None:
        national = pd.DataFrame(
            {"date": ["2022-10-11"], "probability": [0.2]}
        )
        result = locations.calculate_atlantic_location_forecast(
            self.cells, daily_counts(), national
        )
        expected = (
            0.2 * result["coastal_suitability"] * result["regional_suitability"]
        ).clip(0, 1)
        pd.testing.assert_series_equal(
            result["forecast_probability"], expected, check_names=False
        )
        self.assertTrue(result["forecast_probability"].between(0, 1).all())
        self.assertEqual(result["rank"].iloc[0], 1)
        self.assertTrue(result["forecast_probability"].is_monotonic_decreasing)
        self.assertTrue(
            result["risk_level"].isin(["LOW", "MODERATE", "HIGH", "VERY_HIGH"]).all()
        )

    def test_rejects_invalid_national_probability(self) -> None:
        with self.assertRaises(ValueError):
            locations.calculate_atlantic_location_forecast(
                self.cells,
                daily_counts(),
                pd.DataFrame({"date": ["2022-10-11"], "probability": [1.5]}),
            )

    def test_build_writes_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts = root / "counts.csv"
            daily_counts().to_csv(counts, index=False)
            output = root / "out.csv"
            with patch.object(
                locations, "load_all_occurrences", return_value=occurrences()
            ):
                result = locations.build_atlantic_location_forecast(
                    pd.DataFrame({"date": ["2022-10-11"], "probability": [0.1]}),
                    output_path=output,
                    daily_counts_path=counts,
                )
            written = pd.read_csv(output)
        self.assertEqual(len(written), len(result))
        self.assertIn("anomaly_score", written.columns)

    def test_cell_polygon_is_closed_wgs84_square(self) -> None:
        polygon = locations.cell_polygon(3160000, 3100000)
        self.assertEqual(polygon[0], polygon[-1])
        self.assertTrue(all(-8 < lon < -5 and 49 < lat < 51 for lon, lat in polygon))


if __name__ == "__main__":
    unittest.main()
