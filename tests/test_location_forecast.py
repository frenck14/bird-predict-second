from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pandas as pd

from src import forecast_location


class LocationForecastTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target_date = pd.Timestamp("2023-10-10")
        event_dates = [
            f"{year}-10-10"
            for year in (2019, 2020, 2021, 2022)
        ]
        observations = [
            {
                "eventDate": event_date,
                "decimalLatitude": 52.1,
                "decimalLongitude": 5.1,
                "coordinateUncertaintyInMeters": 100,
            }
            for event_date in event_dates
        ]
        observations.extend(
            {
                "eventDate": f"{year}-06-01",
                "decimalLatitude": 52.5,
                "decimalLongitude": 4.8,
                "coordinateUncertaintyInMeters": 100,
            }
            for year in (2019, 2020, 2021, 2022)
        )
        self.observations = pd.DataFrame(observations)
        dates = pd.date_range("2019-01-01", "2022-12-31", freq="D")
        self.national_history = pd.DataFrame(
            {"date": dates, "record_count": 0}
        )
        self.national_forecast = pd.DataFrame(
            {"date": [self.target_date], "probability": [0.8]}
        )

    def test_calculates_historical_probability_and_anomaly_by_cell(self) -> None:
        result = forecast_location.calculate_location_forecast(
            self.observations,
            self.national_history,
            self.national_forecast,
            target_threshold=10,
        )

        observed_cells = self.observations.loc[
            :, ["decimalLatitude", "decimalLongitude"]
        ].drop_duplicates()
        self.assertEqual(len(result), len(observed_cells))
        hotspot = result.loc[
            result["expected_probability"].idxmax()
        ]
        coldspot = result.loc[
            result["expected_probability"].idxmin()
        ]
        self.assertAlmostEqual(hotspot["expected_probability"], 0.9)
        self.assertAlmostEqual(coldspot["expected_probability"], 0.1)
        self.assertGreater(hotspot["forecast_probability"], 0.8)
        self.assertGreater(hotspot["anomaly_score"], 0)
        self.assertAlmostEqual(
            hotspot["anomaly_score"],
            hotspot["forecast_probability"] - hotspot["expected_probability"],
        )

    def test_uses_exact_10_km_epsg_28992_cell_boundaries(self) -> None:
        observations = forecast_location._prepare_occurrences(
            self.observations
        )
        row = observations.iloc[0]
        polygon = forecast_location.cell_polygon(
            int(row["grid_easting"]), int(row["grid_northing"])
        )
        eastings, northings = forecast_location.WGS84_TO_RD.transform(
            [point[0] for point in polygon],
            [point[1] for point in polygon],
        )
        self.assertAlmostEqual(max(eastings) - min(eastings), 10_000, places=3)
        self.assertAlmostEqual(max(northings) - min(northings), 10_000, places=3)
        self.assertEqual(polygon[0], polygon[-1])

    def test_download_paginates_and_writes_minimal_occurrence_cache(self) -> None:
        def fake_request(url: str) -> dict[str, object]:
            query = parse_qs(urlparse(url).query)
            if query["limit"] == ["0"]:
                return {"count": 302, "results": []}
            offset = int(query["offset"][0])
            page_size = min(300, 302 - offset)
            return {
                "count": 302,
                "results": [
                    {
                        "eventDate": "2020-10-10",
                        "decimalLatitude": 52.1,
                        "decimalLongitude": 5.1,
                        "coordinateUncertaintyInMeters": 100,
                    }
                    for _ in range(page_size)
                ],
            }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "locations.csv"
            progress = StringIO()
            with patch.object(
                forecast_location, "_request_json", side_effect=fake_request
            ) as request, redirect_stdout(progress), self.assertLogs(
                forecast_location.__name__, level="INFO"
            ) as logs:
                result = forecast_location.download_location_occurrences(
                    output
                )

            self.assertEqual(len(result), 302)
            self.assertTrue(output.is_file())
            self.assertEqual(request.call_count, 3)
            self.assertEqual(len(pd.read_csv(output)), 302)
            self.assertIn("Downloading page 1 of 2", progress.getvalue())
            self.assertIn("Downloading page 2 of 2", progress.getvalue())
            self.assertIn("GBIF total record count: 302", progress.getvalue())
            self.assertIn("page size: 300", progress.getvalue())
            self.assertIn("total pages: 2", progress.getvalue())
            self.assertIn("Downloaded 302 of 302 records", progress.getvalue())
            self.assertIn(f"cache={output}", progress.getvalue())
            self.assertIn("cache size=", progress.getvalue())
            self.assertIn("total runtime=", progress.getvalue())
            self.assertIn("average time per page=", progress.getvalue())
            self.assertTrue(
                any(
                    "page=1" in message and "elapsed=" in message
                    for message in logs.output
                )
            )

    def test_download_preserves_completed_pages_when_interrupted(self) -> None:
        def fake_request(url: str) -> dict[str, object]:
            query = parse_qs(urlparse(url).query)
            if query["limit"] == ["0"]:
                return {"count": 302, "results": []}
            if query["offset"] == ["300"]:
                raise RuntimeError("simulated interrupted download")
            return {
                "count": 302,
                "results": [
                    {
                        "eventDate": "2020-10-10",
                        "decimalLatitude": 52.1,
                        "decimalLongitude": 5.1,
                        "coordinateUncertaintyInMeters": 100,
                    }
                    for _ in range(300)
                ],
            }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "locations.csv"
            progress = StringIO()
            with patch.object(
                forecast_location, "_request_json", side_effect=fake_request
            ) as request, self.assertLogs(
                forecast_location.__name__, level="INFO"
            ) as logs, redirect_stdout(progress):
                with self.assertRaisesRegex(
                    RuntimeError, "simulated interrupted download"
                ):
                    forecast_location.download_location_occurrences(output)

            self.assertEqual(request.call_count, 6)
            self.assertEqual(len(pd.read_csv(output)), 300)
            self.assertIn("Request for page 2 failed", progress.getvalue())
            self.assertIn("attempt 4 of 4", progress.getvalue())
            self.assertIn("saved records=300", progress.getvalue())
            self.assertTrue(
                any(
                    "downloaded=300" in message
                    for message in logs.output
                )
            )

    def test_download_resumes_after_cached_pages(self) -> None:
        def fake_request(url: str) -> dict[str, object]:
            query = parse_qs(urlparse(url).query)
            if query["limit"] == ["0"]:
                return {"count": 302, "results": []}
            offset = int(query["offset"][0])
            return {
                "count": 302,
                "results": [
                    {
                        "eventDate": "2020-10-10",
                        "decimalLatitude": 52.1,
                        "decimalLongitude": 5.1,
                        "coordinateUncertaintyInMeters": 100,
                    }
                    for _ in range(302 - offset)
                ],
            }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "locations.csv"
            cached_records = pd.DataFrame(
                [
                    {
                        "eventDate": "2020-10-10",
                        "decimalLatitude": 52.1,
                        "decimalLongitude": 5.1,
                        "coordinateUncertaintyInMeters": 100,
                    }
                    for _ in range(301)
                ]
            )
            cached_records.to_csv(output, index=False)
            progress = StringIO()
            with patch.object(
                forecast_location, "_request_json", side_effect=fake_request
            ) as request, redirect_stdout(progress):
                result = forecast_location.download_location_occurrences(
                    output
                )

            requested_offsets = [
                parse_qs(urlparse(call.args[0]).query).get("offset")
                for call in request.call_args_list[1:]
            ]
            self.assertEqual(requested_offsets, [["300"]])
            self.assertEqual(len(result), 302)
            self.assertEqual(len(pd.read_csv(output)), 302)
            self.assertIn("Cached records: 300", progress.getvalue())
            self.assertIn("Completed pages: 1", progress.getvalue())
            self.assertIn("Remaining pages: 1", progress.getvalue())

    def test_download_retries_failed_page_request(self) -> None:
        attempts = 0

        def fake_request(url: str) -> dict[str, object]:
            nonlocal attempts
            query = parse_qs(urlparse(url).query)
            if query["limit"] == ["0"]:
                return {"count": 1, "results": []}
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary failure")
            return {
                "count": 1,
                "results": [
                    {
                        "eventDate": "2020-10-10",
                        "decimalLatitude": 52.1,
                        "decimalLongitude": 5.1,
                        "coordinateUncertaintyInMeters": 100,
                    }
                ],
            }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "locations.csv"
            progress = StringIO()
            with patch.object(
                forecast_location, "_request_json", side_effect=fake_request
            ), redirect_stdout(progress):
                result = forecast_location.download_location_occurrences(output)

        self.assertEqual(len(result), 1)
        self.assertEqual(attempts, 2)
        self.assertIn("Request for page 1 failed (attempt 1 of 4)", progress.getvalue())

    def test_request_logs_url_and_uses_page_timeout(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b'{"count": 0}'
        url = "https://api.gbif.org/v1/occurrence/search?limit=0"

        with patch.object(
            forecast_location, "urlopen", return_value=response
        ) as urlopen, self.assertLogs(
            forecast_location.__name__, level="INFO"
        ) as logs:
            result = forecast_location._request_json(url)

        self.assertEqual(result, {"count": 0})
        self.assertEqual(
            urlopen.call_args.kwargs["timeout"],
            forecast_location.PAGE_TIMEOUT_SECONDS,
        )
        self.assertTrue(any(url in message for message in logs.output))

    def test_build_writes_forecast_from_cached_occurrences_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            occurrences_path = root / "locations.csv"
            history_path = root / "national-history.csv"
            output_path = root / "location-forecast.csv"
            self.observations.to_csv(occurrences_path, index=False)
            self.national_history.to_csv(history_path, index=False)

            result = forecast_location.build_location_forecast(
                self.national_forecast,
                {"target_threshold": 10},
                occurrence_path=occurrences_path,
                national_history_path=history_path,
                output_path=output_path,
            )

            self.assertTrue(output_path.is_file())
            self.assertEqual(len(pd.read_csv(output_path)), len(result))
            self.assertEqual(result["date"].nunique(), 1)
            self.assertEqual(result["cell_id"].nunique(), 2)

    def test_rejects_occurrences_outside_european_netherlands(self) -> None:
        outside = self.observations.copy()
        outside.loc[0, "decimalLatitude"] = 48.0
        with self.assertRaisesRegex(ValueError, "no dated, usable coordinates"):
            forecast_location._prepare_occurrences(
                outside.iloc[[0]].reset_index(drop=True)
            )


if __name__ == "__main__":
    unittest.main()
