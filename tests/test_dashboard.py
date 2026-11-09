from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

import app


class LocationDashboardTests(unittest.TestCase):
    def test_nearest_location_name_uses_nearest_reference_town(self) -> None:
        self.assertEqual(
            app.nearest_location_name(52.0907, 5.1214),
            "Near Utrecht (0 km)",
        )

    def test_location_map_tooltip_shows_location_and_forecast_metrics(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "cell_id": "100000-450000",
                    "grid_easting": 100000,
                    "grid_northing": 450000,
                    "center_latitude": 52.0907,
                    "center_longitude": 5.1214,
                    "forecast_probability": 0.8,
                    "expected_probability": 0.5,
                    "anomaly_score": 0.3,
                }
            ]
        )
        with (
            patch.object(app.pdk, "Layer"),
            patch.object(app.pdk, "Deck") as deck,
            patch.object(app.st, "pydeck_chart"),
        ):
            app.render_location_map(frame, "Test map", "forecast_probability")

        tooltip = deck.call_args.kwargs["tooltip"]["html"]
        self.assertIn("{location_name}", tooltip)
        self.assertIn("Forecast probability: {forecast_percent}", tooltip)
        self.assertIn("Baseline probability: {expected_percent}", tooltip)
        self.assertIn("Anomaly score: {anomaly_percentage_points}", tooltip)
        self.assertNotIn("{cell_id}", tooltip)

    def test_horizon_selection_updates_summary_rankings_and_maps(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "date": date,
                    "cell_id": "100000-450000",
                    "grid_easting": 100000,
                    "grid_northing": 450000,
                    "center_latitude": latitude,
                    "center_longitude": longitude,
                    "expected_probability": baseline,
                    "forecast_probability": forecast + day_offset / 1000,
                    "anomaly_score": anomaly,
                    "national_forecast_probability": 0.65 + day_offset / 100,
                }
                for day_offset, date in enumerate(
                    pd.date_range("2026-10-17", periods=14, freq="D")
                )
                for latitude, longitude, baseline, forecast, anomaly in (
                    (52.0907, 5.1214, 0.5, 0.8, 0.3),
                    (51.9244, 4.4777, 0.5, 0.4, -0.1),
                    (52.9563, 4.7608, 0.3, 0.2, -0.1),
                )
            ]
        )

        column_groups: list[list[MagicMock]] = []

        def columns(count: int) -> list[MagicMock]:
            result = [MagicMock() for _ in range(count)]
            column_groups.append(result)
            return result

        events: list[str] = []
        map_frames: list[pd.DataFrame] = []

        def record_markdown(value: str) -> None:
            events.append(value)

        def record_map(
            data: pd.DataFrame, *_: object, **__: object
        ) -> None:
            map_frames.append(data)

        with tempfile.TemporaryDirectory() as directory:
            forecast_path = Path(directory) / "location.csv"
            frame.to_csv(forecast_path, index=False)
            with (
                patch.object(app, "LOCATION_FORECAST_FILE", forecast_path),
                patch.object(app.st, "columns", side_effect=columns),
                patch.object(app.st, "radio", return_value=7) as radio,
                patch.object(app.st, "markdown", side_effect=record_markdown),
                patch.object(app.st, "dataframe") as dataframe,
                patch.object(app, "render_location_map", side_effect=record_map),
            ):
                app.show_location_forecasts()

        self.assertEqual(radio.call_args.args[0], "Forecast horizon")
        self.assertEqual(radio.call_args.kwargs["options"], [1, 3, 7, 14])
        format_option = radio.call_args.kwargs["format_func"]
        self.assertEqual(
            [format_option(horizon) for horizon in [1, 3, 7, 14]],
            [
                "Tomorrow · Oct 17, 2026",
                "+3 days · Oct 19, 2026",
                "+7 days · Oct 23, 2026",
                "+14 days · Oct 30, 2026",
            ],
        )
        headings = [
            "**Top 10 hotspots**",
            "**Top 10 positive anomalies**",
            "**Top 10 coldspots**",
        ]
        for heading in headings:
            self.assertIn(heading, events)
        self.assertEqual(len(map_frames), 2)
        for map_frame in map_frames:
            self.assertTrue(
                map_frame["date"].eq(pd.Timestamp("2026-10-23")).all()
            )

        self.assertEqual(dataframe.call_count, 3)
        hotspot_table = dataframe.call_args_list[0].args[0]
        anomaly_table = dataframe.call_args_list[1].args[0]
        coldspot_table = dataframe.call_args_list[2].args[0]
        self.assertEqual(
            hotspot_table.columns.tolist(),
            ["Rank", "Location", "Forecast probability", "Anomaly score"],
        )
        self.assertEqual(
            anomaly_table.columns.tolist(),
            ["Rank", "Location", "Forecast probability", "Anomaly score"],
        )
        self.assertEqual(
            coldspot_table.columns.tolist(),
            ["Rank", "Location", "Forecast probability"],
        )
        self.assertEqual(hotspot_table["Rank"].tolist(), [1, 2, 3])
        self.assertEqual(
            hotspot_table.iloc[0]["Location"], "Near Utrecht (0 km)"
        )
        self.assertEqual(
            anomaly_table.iloc[0]["Forecast probability"], "80.6%"
        )
        self.assertEqual(
            coldspot_table.iloc[0]["Forecast probability"], "20.6%"
        )
        self.assertEqual(
            column_groups[0][0].metric.call_args.args[1], "71.0%"
        )


if __name__ == "__main__":
    unittest.main()
