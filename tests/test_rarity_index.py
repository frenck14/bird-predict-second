from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src import rarity_index as rarity


class RarityIndexTests(unittest.TestCase):
    def forecasts(self, dates: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
        probabilities = {
            "Northern Fulmar": 0.10,
            "Manx Shearwater": 0.20,
            "European Storm-petrel": 0.30,
            "Sooty Shearwater": 0.40,
            "Great Shearwater": 0.50,
        }
        return {
            species: pd.DataFrame(
                {"date": dates, "probability": [probability] * len(dates)}
            )
            for species, probability in probabilities.items()
        }

    def test_rarity_weights_and_raw_score(self):
        dates = pd.date_range("2026-10-18", periods=14, freq="D")
        combined = rarity.combine_rarity_raw(self.forecasts(dates))
        expected = 0.10 * 0.5 + 0.20 + 0.30 * 2.0 + 0.40 * 3.0 + 0.50 * 6.0
        self.assertAlmostEqual(combined.iloc[0]["rarity_raw"], expected)
        self.assertEqual(rarity.RARITY_WEIGHTS["Great Shearwater"], 6.0)
        self.assertEqual(len(rarity.RARITY_WEIGHTS), 5)

    def test_historical_percentile_scaling_is_clipped(self):
        history = pd.Series(range(100), dtype=float)
        requested = pd.Series([0, 4.95, 49.5, 94.05, 99], dtype=float)
        scores, info = rarity.scale_rarity_scores(requested, history)
        self.assertEqual(scores.iloc[0], 0)
        self.assertAlmostEqual(scores.iloc[1], 0)
        self.assertAlmostEqual(scores.iloc[2], 50)
        self.assertAlmostEqual(scores.iloc[3], 100)
        self.assertEqual(scores.iloc[4], 100)
        self.assertEqual(info["lower_percentile"], 5)
        self.assertEqual(info["upper_percentile"], 95)
        self.assertAlmostEqual(info["historical_raw_p5"], 4.95)
        self.assertAlmostEqual(info["historical_raw_p95"], 94.05)

    def test_degenerate_historical_range_is_an_error(self):
        with self.assertRaises(ValueError):
            rarity.scale_rarity_scores(pd.Series([1.0]), pd.Series([2.0] * 20))

    def test_forecast_date_mismatch_is_an_error(self):
        dates = pd.date_range("2026-10-18", periods=14, freq="D")
        forecasts = self.forecasts(dates)
        forecasts["Great Shearwater"] = forecasts["Great Shearwater"].iloc[:-1]
        with self.assertRaisesRegex(ValueError, "same dates"):
            rarity.combine_rarity_raw(forecasts)

    def test_document_horizons_and_saved_output(self):
        dates = pd.date_range("2026-10-18", periods=14, freq="D")
        history = pd.Series(
            [i / 10 for i in range(100)],
            index=pd.date_range("2010-01-02", periods=100, freq="D"),
        )
        daily, scale = rarity.rarity_index_frame(self.forecasts(dates), history)
        document = rarity.build_rarity_document(
            daily,
            scale,
            datetime(2026, 10, 17, tzinfo=timezone.utc),
        )
        self.assertEqual(
            [horizon["label"] for horizon in document["horizons"]],
            ["Tomorrow", "+3 days", "+7 days", "+14 days"],
        )
        self.assertTrue(daily["rarity_index"].between(0, 100).all())
        self.assertEqual(
            document["horizons"][0]["leading_rarity_species"], "Great Shearwater"
        )
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "rarity_index.csv"
            json_path = Path(tmp) / "rarity_index.json"
            rarity.save_rarity_outputs(
                daily,
                document,
                csv_path=csv_path,
                json_path=json_path,
            )
            self.assertTrue(csv_path.is_file())
            self.assertEqual(
                json.loads(json_path.read_text())["rarity_weights"],
                rarity.RARITY_WEIGHTS,
            )


if __name__ == "__main__":
    unittest.main()
