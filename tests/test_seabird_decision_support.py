import unittest
from datetime import date

import pandas as pd

from src import seabird_decision_support as ds


class DecisionSupportTests(unittest.TestCase):
    def test_event_status_bands(self):
        self.assertEqual(ds.event_status(0.05), "Normal")
        self.assertEqual(ds.event_status(0.10), "Good")
        self.assertEqual(ds.event_status(0.30), "Excellent")
        self.assertEqual(ds.event_status(0.50), "Major Seawatch Day")

    def test_score_and_confidence(self):
        self.assertEqual(ds.index_score(0.25), 50)
        self.assertEqual(ds.index_score(0.9), 100)
        self.assertEqual(
            [ds.confidence_label(h) for h in (1, 3, 7, 14)],
            ["High", "High", "Medium", "Low"],
        )

    def test_compass_label(self):
        self.assertEqual(ds.compass_label(247), "WSW")
        self.assertEqual(ds.compass_label(359), "N")

    def test_trend_uses_earlier_issue_for_same_day(self):
        history = pd.DataFrame(
            {
                "issued_on": ["2026-10-16", "2026-10-17"],
                "date": ["2026-10-18", "2026-10-18"],
                "probability": [0.10, 0.40],
            }
        )
        trend = ds.trend_vs_yesterday(
            pd.Timestamp("2026-10-18"), 0.30, history, date(2026, 10, 17)
        )
        self.assertEqual(trend["direction"], "up")
        self.assertAlmostEqual(trend["change"], 0.20)
        none = ds.trend_vs_yesterday(
            pd.Timestamp("2026-10-18"), 0.3, None, date(2026, 10, 17)
        )
        self.assertEqual(none["direction"], "n/a")

    def test_recommended_coast_and_history_roundtrip(self):
        day = pd.DataFrame(
            {
                "location": ["Texel", "Texel (NW)", "Petten", "Westkapelle", "Fair Isle"],
                "country": ["NL", "NL", "NL", "NL", "GB"],
                "forecast_probability": [0.2, 0.1, 0.05, 0.04, 0.9],
            }
        )
        self.assertEqual(ds.recommended_coast(day)["coast"], "Wadden islands")
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.csv"
            forecast = pd.DataFrame(
                {"date": pd.to_datetime(["2026-10-18"]), "probability": [0.2]}
            )
            ds.update_history(forecast, path, date(2026, 10, 17))
            history = ds.update_history(forecast, path, date(2026, 10, 17))
            self.assertEqual(len(history), 1)
            self.assertEqual(len(ds.load_history(path)), 1)


if __name__ == "__main__":
    unittest.main()
