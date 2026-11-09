from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.download_open_meteo_forecast import (
    DownloadedForecast,
    HOURLY_VARIABLES,
    normalize_hourly_forecast,
)
from src import forecast_seabird_locations as seabird_locations_module
from src.predict_yellow_browed import (
    build_daily_report,
    load_weather_forecast,
    make_predictions,
    save_plot,
)
from src import run_daily_forecast


class OpenMeteoNormalizationTests(unittest.TestCase):
    def test_maps_hourly_values_to_daily_knmi_scaled_fields(self) -> None:
        times = pd.date_range(
            "2026-10-01 00:00", periods=24, freq="h"
        ).strftime("%Y-%m-%dT%H:%M").tolist()
        values = {
            "time": times,
            "temperature_2m": [10.0] * 24,
            "precipitation": [0.1] * 24,
            "pressure_msl": [1012.0] * 24,
            "wind_speed_10m": [2.0] * 24,
            "wind_direction_10m": [90] * 24,
        }
        self.assertEqual(set(values), {"time", *HOURLY_VARIABLES})
        result = normalize_hourly_forecast({"hourly": values}, 235)

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["date"], pd.Timestamp("2026-10-01"))
        self.assertEqual(row["station_id"], 235)
        self.assertAlmostEqual(row["DDVEC"], 90)
        self.assertAlmostEqual(row["FG"], 20)
        self.assertAlmostEqual(row["FHX"], 20)
        self.assertAlmostEqual(row["TG"], 100)
        self.assertAlmostEqual(row["TN"], 100)
        self.assertAlmostEqual(row["TX"], 100)
        self.assertAlmostEqual(row["RH"], 24)
        self.assertAlmostEqual(row["PX"], 10120)
        self.assertEqual(
            list(result.columns),
            [
                "date",
                "station_id",
                "DDVEC",
                "FG",
                "FHX",
                "TG",
                "TN",
                "TX",
                "RH",
                "PX",
            ],
        )

    def test_rejects_misaligned_hourly_series(self) -> None:
        payload = {
            "hourly": {
                "time": ["2026-10-01T00:00"],
                **{variable: [1, 2] for variable in HOURLY_VARIABLES},
            }
        }
        with self.assertRaisesRegex(ValueError, "equally sized lists"):
            normalize_hourly_forecast(payload, 235)


class ProductionInferenceTests(unittest.TestCase):
    def test_existing_example_runs_through_production_inference(self) -> None:
        root = Path(__file__).resolve().parents[1]
        weather_path = root / "inputs/example_forecast.csv"
        model_path = root / "outputs/yellow_browed_model.joblib"
        if not weather_path.is_file() or not model_path.is_file():
            self.skipTest("Existing forecast example or model artifact unavailable")

        import joblib

        weather, predictor_dates = load_weather_forecast(weather_path)
        artifact = joblib.load(model_path)
        predictions = make_predictions(weather, predictor_dates, artifact)
        self.assertEqual(len(predictions), 14)
        self.assertTrue(predictions["probability"].between(0, 1).all())
        self.assertEqual(predictions["date"].diff().dropna().dt.days.unique().tolist(), [1])

        with tempfile.TemporaryDirectory() as directory:
            plot = Path(directory) / "forecast.png"
            save_plot(predictions, plot)
            self.assertGreater(plot.stat().st_size, 0)
            report = build_daily_report(
                predictions,
                artifact,
                plot,
                weather_source="Open-Meteo test forecast",
            )
            self.assertIn("Open-Meteo test forecast", report)
            self.assertIn("source-mismatched input", report)
            self.assertIn("daily dates one day after", report)

    def test_daily_job_writes_forecast_chart_report_and_metadata(self) -> None:
        root = Path(__file__).resolve().parents[1]
        example = root / "inputs/example_forecast.csv"
        if not example.is_file() or not run_daily_forecast.DEFAULT_MODEL.is_file():
            self.skipTest("Existing forecast example or model artifact unavailable")

        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            import joblib

            yellow_artifact = joblib.load(run_daily_forecast.DEFAULT_MODEL)
            atlantic_artifact = {
                **yellow_artifact,
                "species": "Atlantic Vagrancy Index",
            }
            atlantic_model = output_root / "atlantic_model.joblib"
            joblib.dump(atlantic_artifact, atlantic_model)
            eastern_model = output_root / "eastern_model.joblib"
            joblib.dump(
                {**yellow_artifact, "species": "Eastern Vagrancy Index"},
                eastern_model,
            )
            seabird_model = output_root / "seabird_model.joblib"
            joblib.dump(
                {**yellow_artifact, "species": "Seabird Index"},
                seabird_model,
            )
            seabird_counts = output_root / "seabird_counts.csv"
            pd.DataFrame(
                {
                    "date": pd.date_range("2020-09-01", periods=60, freq="D"),
                    "count": [0] * 57 + [1, 2, 3],
                }
            ).to_csv(seabird_counts, index=False)
            seabird_occurrences = pd.DataFrame(
                {
                    "countryCode": ["NL", "GB"],
                    "decimalLatitude": [53.06, 59.53],
                    "decimalLongitude": [4.76, -1.63],
                    "date": pd.to_datetime(["2020-10-01", "2021-10-01"]),
                    "species": ["European Storm-petrel", "Northern Fulmar"],
                }
            )
            from src.train_seabird_species_models import SPECIES_NAMES

            species_paths = {}
            species_models = {}
            for species in SPECIES_NAMES:
                slug = run_daily_forecast.seabird_species_output_paths(species)["forecast"].stem.removesuffix("_forecast")
                paths = {
                    "forecast": output_root / f"{slug}_forecast.csv",
                    "location": output_root / f"{slug}_location_forecast.csv",
                    "detail": output_root / f"{slug}_location_forecast_detail.csv",
                    "hotspots": output_root / f"{slug}_hotspots.csv",
                    "map": output_root / f"{slug}_location_forecast.png",
                    "model": output_root / f"{slug}_model.joblib",
                }
                species_paths[species] = paths
                paths["model"].touch()
                species_models[species] = paths["model"]

            def isolated_species_products(weather, predictor_dates, occurrences):
                dates = predictor_dates + pd.Timedelta(days=1)
                products = {}
                for species, paths in species_paths.items():
                    frame = pd.DataFrame(
                        {
                            "date": dates,
                            "probability": [0.2] * len(dates),
                            "risk_level": ["MODERATE"] * len(dates),
                        }
                    )
                    frame.to_csv(paths["forecast"], index=False, date_format="%Y-%m-%d")
                    pd.DataFrame(
                        {
                            "date": dates,
                            "location": ["Texel"] * len(dates),
                            "country": ["NL"] * len(dates),
                            "latitude": [53.06] * len(dates),
                            "longitude": [4.76] * len(dates),
                            "probability": [0.1] * len(dates),
                            "anomaly_score": [0.01] * len(dates),
                            "rank": [1] * len(dates),
                        }
                    ).to_csv(paths["location"], index=False, date_format="%Y-%m-%d")
                    detail_rows = []
                    for day in dates:
                        for location, country, easting, northing, lat, lon in (
                            ("Texel", "NL", 1000, 2000, 53.06, 4.76),
                            ("Fair Isle", "GB", 3000, 4000, 59.53, -1.63),
                            ("Skagen", "DK", 5000, 6000, 57.72, 10.58),
                        ):
                            detail_rows.append(
                                {
                                    "date": day,
                                    "cell_id": location,
                                    "country": country,
                                    "location": location,
                                    "grid_easting": easting,
                                    "grid_northing": northing,
                                    "center_latitude": lat,
                                    "center_longitude": lon,
                                    "forecast_probability": 0.1,
                                }
                            )
                    pd.DataFrame(detail_rows).to_csv(
                        paths["detail"], index=False, date_format="%Y-%m-%d"
                    )
                    products[species] = frame
                return products
            real_eastern_locations = (
                run_daily_forecast.build_eastern_location_forecast
            )

            def isolated_eastern_locations(predictions, **_: object):
                return real_eastern_locations(
                    predictions,
                    output_path=output_root / "eastern_detail.csv",
                    simple_output_path=output_root / "eastern_location.csv",
                    map_path=output_root / "eastern_location.png",
                )

            real_atlantic_locations = (
                run_daily_forecast.build_atlantic_location_forecast
            )

            def isolated_atlantic_locations(predictions, **_: object):
                return real_atlantic_locations(
                    predictions,
                    output_path=output_root / "atlantic_detail.csv",
                    simple_output_path=output_root / "atlantic_location.csv",
                    map_path=output_root / "atlantic_location.png",
                )

            real_seabird_locations = (
                run_daily_forecast.build_seabird_location_forecast
            )

            def isolated_seabird_locations(predictions, **_: object):
                with patch.object(
                    seabird_locations_module,
                    "load_all_occurrences",
                    return_value=seabird_occurrences,
                ):
                    return real_seabird_locations(
                        predictions,
                        output_path=output_root / "seabird_detail.csv",
                        simple_output_path=output_root / "seabird_location.csv",
                        map_path=output_root / "seabird_location.png",
                        daily_counts_path=seabird_counts,
                    )

            downloaded = DownloadedForecast(
                path=example,
                source_description="Open-Meteo API test forecast",
            )
            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "download_open_meteo_forecast",
                        return_value=downloaded,
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "build_location_forecast",
                        return_value=pd.DataFrame({"cell_id": ["test"]}),
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "build_atlantic_location_forecast",
                        side_effect=isolated_atlantic_locations,
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "build_eastern_location_forecast",
                        side_effect=isolated_eastern_locations,
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "build_seabird_location_forecast",
                        side_effect=isolated_seabird_locations,
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast, "DEFAULT_EASTERN_MODEL", eastern_model
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_EASTERN_OUTPUT",
                        output_root / "eastern_forecast.csv",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_EASTERN_PLOT",
                        output_root / "eastern_forecast.png",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_SEABIRD_MODEL",
                        seabird_model,
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_SEABIRD_OUTPUT",
                        output_root / "seabird_forecast.csv",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_SEABIRD_PLOT",
                        output_root / "seabird_forecast.png",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "SEABIRD_LOCATION_FORECAST_FILE",
                        output_root / "seabird_detail.csv",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "SEABIRD_LOCATION_CSV",
                        output_root / "seabird_location.csv",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "SEABIRD_LOCATION_MAP",
                        output_root / "seabird_location.png",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "build_species_layers",
                        return_value=pd.DataFrame({"species": ["test"]}),
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_OUTPUT",
                        output_root / "forecast.csv",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_ATLANTIC_MODEL",
                        atlantic_model,
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_ATLANTIC_OUTPUT",
                        output_root / "atlantic_forecast.csv",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_ATLANTIC_PLOT",
                        output_root / "atlantic_forecast.png",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_PLOT",
                        output_root / "forecast.png",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "DEFAULT_REPORT",
                        output_root / "report.md",
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "RUN_METADATA",
                        output_root / "run.json",
                    )
                )
                for name, file in (
                    ("SEABIRD_DECISION_FILE", "seabird_decision.json"),
                    ("SEABIRD_HISTORY_FILE", "seabird_history.csv"),
                ):
                    stack.enter_context(
                        patch.object(run_daily_forecast, name, output_root / file)
                    )
                for name, file in (
                    ("SEAWATCH_RATING_OUTPUT", "seawatch_day_rating.csv"),
                    ("SEAWATCH_HOTSPOTS_OUTPUT", "seawatch_day_hotspots.csv"),
                    ("SEAWATCH_RATING_JSON_OUTPUT", "seawatch_day_rating.json"),
                ):
                    stack.enter_context(
                        patch.object(run_daily_forecast, name, output_root / file)
                    )
                for name, file in (
                    ("TARGET_SPECIES_OUTPUT", "target_species.csv"),
                    ("HISTORICAL_PERCENTILES_OUTPUT", "historical_percentiles.csv"),
                    ("RARITY_INDEX_OUTPUT", "rarity_index.csv"),
                    ("RARITY_INDEX_JSON_OUTPUT", "rarity_index.json"),
                ):
                    stack.enter_context(
                        patch.object(run_daily_forecast, name, output_root / file)
                    )
                history_index = pd.date_range("2020-01-01", periods=100)
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "historical_distributions",
                        return_value=(
                            pd.Series(range(100), index=history_index, dtype=float),
                            pd.Series(
                                [i / 50 for i in range(100)], index=history_index
                            ),
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "SEABIRD_WEATHER_FILE",
                        output_root / "history.csv",
                    )
                )
                pd.DataFrame({"date": ["2020-01-01"]}).to_csv(
                    output_root / "history.csv", index=False
                )
                rarity_forecast = pd.DataFrame(
                    {
                        "date": pd.date_range("2026-10-14", periods=14, freq="D"),
                        "rarity_index": [42.0] * 14,
                        "leading_rarity_species": ["Great Shearwater"] * 14,
                    }
                )
                rarity_document = {
                    "generated_at": "2026-10-17T00:00:00+00:00",
                    "horizons": [
                        {
                            "date": str(day.date()),
                            "rarity_index": 42.0,
                            "rarity_raw": 1.0,
                            "leading_rarity_species": "Great Shearwater",
                            "label": label,
                            "forecast_day": offset,
                            "species_probabilities": {
                                "Northern Fulmar": 0.1,
                                "Manx Shearwater": 0.1,
                                "European Storm-petrel": 0.1,
                                "Sooty Shearwater": 0.1,
                                "Great Shearwater": 0.1,
                            },
                        }
                        for day, label, offset in (
                            (pd.Timestamp("2026-10-14"), "Tomorrow", 1),
                            (pd.Timestamp("2026-10-16"), "+3 days", 3),
                            (pd.Timestamp("2026-10-20"), "+7 days", 7),
                            (pd.Timestamp("2026-10-27"), "+14 days", 14),
                        )
                    ],
                }
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "build_rarity_index",
                        return_value=(rarity_forecast, rarity_document),
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "save_rarity_outputs",
                        side_effect=lambda daily, document: (
                            daily.to_csv(
                                output_root / "rarity_index.csv", index=False
                            ),
                            (output_root / "rarity_index.json").write_text(
                                json.dumps(document)
                            ),
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "SEABIRD_SPECIES_MODEL_PATHS",
                        species_models,
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "seabird_species_output_paths",
                        side_effect=lambda species: species_paths[species],
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "generate_seabird_species_products",
                        side_effect=isolated_species_products,
                    )
                )
                stack.enter_context(
                    patch.object(
                        run_daily_forecast,
                        "load_seabird_occurrences",
                        return_value=seabird_occurrences,
                    )
                )
                metadata = run_daily_forecast.run_daily_forecast()

            self.assertTrue((output_root / "forecast.csv").is_file())
            self.assertTrue(
                (output_root / "atlantic_forecast.csv").is_file()
            )
            self.assertTrue((output_root / "forecast.png").is_file())
            self.assertTrue(
                (output_root / "atlantic_forecast.png").is_file()
            )
            self.assertTrue((output_root / "report.md").is_file())
            self.assertTrue((output_root / "run.json").is_file())
            decision = json.loads((output_root / "seabird_decision.json").read_text())
            self.assertEqual(
                [h["horizon_days"] for h in decision["horizons"]], [1, 3, 7, 14]
            )
            self.assertTrue((output_root / "seabird_history.csv").is_file())
            self.assertTrue((output_root / "atlantic_location.csv").is_file())
            self.assertTrue((output_root / "atlantic_location.png").is_file())
            hotspots = json.loads((output_root / "run.json").read_text())[
                "atlantic_hotspots"
            ]
            self.assertEqual(len(hotspots["top10_locations"]), 10)
            self.assertIn("generated_at", hotspots)
            self.assertTrue((output_root / "eastern_forecast.csv").is_file())
            self.assertTrue((output_root / "eastern_forecast.png").is_file())
            self.assertTrue((output_root / "eastern_location.csv").is_file())
            self.assertTrue((output_root / "eastern_location.png").is_file())
            self.assertTrue((output_root / "seabird_forecast.csv").is_file())
            self.assertTrue((output_root / "seabird_forecast.png").is_file())
            self.assertTrue((output_root / "seabird_location.csv").is_file())
            self.assertTrue((output_root / "seabird_location.png").is_file())
            self.assertTrue((output_root / "seawatch_day_rating.csv").is_file())
            self.assertTrue((output_root / "seawatch_day_hotspots.csv").is_file())
            self.assertTrue((output_root / "seawatch_day_rating.json").is_file())
            self.assertTrue((output_root / "rarity_index.csv").is_file())
            self.assertTrue((output_root / "target_species.csv").is_file())
            self.assertTrue((output_root / "historical_percentiles.csv").is_file())
            self.assertTrue((output_root / "rarity_index.json").is_file())
            eastern_hotspots = json.loads((output_root / "run.json").read_text())[
                "eastern_hotspots"
            ]
            self.assertEqual(len(eastern_hotspots["top10_locations"]), 10)
            seabird_hotspots = json.loads((output_root / "run.json").read_text())[
                "seabird_hotspots"
            ]
            self.assertEqual(len(seabird_hotspots["top10_locations"]), 10)
            self.assertIn("best_dutch_site", seabird_hotspots)
            self.assertIn("Open-Meteo", metadata["weather_source"])
            self.assertEqual(
                metadata["atlantic_vagrancy"]["forecast_csv"],
                str(output_root / "atlantic_forecast.csv"),
            )
            self.assertIn("seawatch_day_rating", metadata)
            self.assertIn("rarity_index", metadata)
            self.assertEqual(set(metadata["seabird_species"]), set(SPECIES_NAMES))
            for paths in species_paths.values():
                self.assertTrue(paths["forecast"].is_file())
                self.assertTrue(paths["location"].is_file())


if __name__ == "__main__":
    unittest.main()
