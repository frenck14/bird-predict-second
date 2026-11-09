from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src import build_atlantic_vagrancy_dataset as dataset_builder
from src.build_dataset_v2 import STATION_FILES, add_coastal_features
from src.forecast_species_comparison import weather_feature_columns
from src.predict_atlantic_vagrancy import make_predictions, risk_level


class AtlanticVagrancyDatasetTests(unittest.TestCase):
    def test_registry_has_core_and_optional_species_but_not_junco(self) -> None:
        registry_names = {
            species["scientific_name"]
            for species in dataset_builder.ATLANTIC_VAGRANCY_SPECIES
        }
        self.assertEqual(len(registry_names), 9)
        self.assertTrue(
            all(
                species["core"]
                for species in dataset_builder.ATLANTIC_VAGRANCY_SPECIES[:5]
            )
        )
        self.assertNotIn("Junco hyemalis", registry_names)

    def test_filters_country_wild_coordinates_dates_and_captive_records(self) -> None:
        records = pd.DataFrame(
            [
                {
                    "key": 1,
                    "scientificName": "Vireo olivaceus",
                    "taxonKey": 10,
                    "eventDate": "2020-09-12T12:00:00",
                    "decimalLatitude": 52.1,
                    "decimalLongitude": 5.1,
                    "basisOfRecord": "HUMAN_OBSERVATION",
                    "countryCode": "NL",
                },
                {
                    "key": 2,
                    "scientificName": "Vireo olivaceus",
                    "taxonKey": 10,
                    "eventDate": "2020-09-12",
                    "decimalLatitude": 52.1,
                    "decimalLongitude": 5.1,
                    "basisOfRecord": "PRESERVED_SPECIMEN",
                    "countryCode": "NL",
                },
                {
                    "key": 3,
                    "scientificName": "Vireo olivaceus",
                    "taxonKey": 10,
                    "eventDate": "2020-09",
                    "decimalLatitude": 52.1,
                    "decimalLongitude": 5.1,
                    "basisOfRecord": "HUMAN_OBSERVATION",
                    "countryCode": "NL",
                },
                {
                    "key": 4,
                    "scientificName": "Vireo olivaceus",
                    "taxonKey": 10,
                    "eventDate": "2020-09-12",
                    "decimalLatitude": 91,
                    "decimalLongitude": 5.1,
                    "basisOfRecord": "HUMAN_OBSERVATION",
                    "countryCode": "NL",
                },
                {
                    "key": 5,
                    "scientificName": "Vireo olivaceus",
                    "taxonKey": 10,
                    "eventDate": "2020-09-12",
                    "decimalLatitude": 52.1,
                    "decimalLongitude": 5.1,
                    "basisOfRecord": "HUMAN_OBSERVATION",
                    "countryCode": "BE",
                },
                {
                    "key": 6,
                    "scientificName": "Vireo olivaceus",
                    "taxonKey": 10,
                    "eventDate": "2020-09-12",
                    "decimalLatitude": 52.1,
                    "decimalLongitude": 5.1,
                    "basisOfRecord": "HUMAN_OBSERVATION",
                    "countryCode": "NL",
                    "degreeOfEstablishment": "CAPTIVE",
                },
            ]
        )

        filtered = dataset_builder.filter_occurrences(records, 10, "NL")

        self.assertEqual(filtered["key"].tolist(), [1])
        self.assertEqual(filtered.loc[0, "date"], pd.Timestamp("2020-09-12"))

    def test_download_pages_and_reuses_raw_species_country_cache(self) -> None:
        results = [
            {
                "key": key,
                "scientificName": "Vireo olivaceus",
                "taxonKey": 10,
                "eventDate": "2020-09-12",
                "decimalLatitude": 52.1,
                "decimalLongitude": 5.1,
                "basisOfRecord": "HUMAN_OBSERVATION",
                "countryCode": "NL",
            }
            for key in (1, 2, 3)
        ]
        responses = [
            {"count": 3, "results": results[:2]},
            {"count": 3, "results": results[2:]},
        ]
        with tempfile.TemporaryDirectory(
            dir=dataset_builder.ROOT
        ) as directory:
            with (
                patch.object(dataset_builder, "PAGE_SIZE", 2),
                patch.object(
                    dataset_builder, "RAW_DIRECTORY", Path(directory)
                ),
                patch.object(
                    dataset_builder, "_fetch_json", side_effect=responses
                ) as fetch_json,
            ):
                downloaded = dataset_builder.download_species_country(
                    "Red-eyed Vireo", "Vireo olivaceus", "NL", 10
                )
                cached = dataset_builder.download_species_country(
                    "Red-eyed Vireo", "Vireo olivaceus", "NL", 10
                )

        self.assertEqual(len(downloaded), 3)
        self.assertEqual(len(cached), 3)
        self.assertEqual(fetch_json.call_count, 2)

    def test_build_outputs_reports_species_and_distinct_species_by_day(self) -> None:
        registry = [
            {"species": "Vireo"},
            {"species": "Warbler"},
            {"species": "Ovenbird"},
        ]
        records = pd.DataFrame(
            {
                "key": [1, 2, 3],
                "species": ["Vireo", "Vireo", "Warbler"],
                "countryCode": ["GB", "IE", "NL"],
                "date": pd.to_datetime(
                    ["2020-09-12", "2020-09-12", "2020-09-13"]
                ),
            }
        )

        summary, events, daily = dataset_builder.build_outputs(
            records, registry
        )

        self.assertEqual(
            summary.columns.tolist(),
            ["species", "records", "unique_dates", "countries"],
        )
        self.assertEqual(summary["records"].tolist(), [2, 1, 0])
        self.assertEqual(summary.loc[0, "countries"], "GB;IE")
        self.assertEqual(
            events.columns.tolist(), ["date", "count", "species_count"]
        )
        self.assertEqual(events["count"].tolist(), [2, 1])
        self.assertEqual(events["species_count"].tolist(), [1, 1])
        self.assertEqual(daily.columns.tolist(), ["date", "count"])


class AtlanticVagrancyForecastTests(unittest.TestCase):
    def test_risk_levels_cover_probability_scale(self) -> None:
        self.assertEqual(
            [risk_level(value) for value in (0.0, 0.05, 0.10, 0.20, 1.0)],
            ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "VERY_HIGH"],
        )

    def test_synoptic_features_and_forecast_schema(self) -> None:
        dates = pd.date_range("2026-10-01", periods=8, freq="D")
        weather = pd.DataFrame({"date": dates})
        for station_id in STATION_FILES:
            for variable in (
                "DDVEC",
                "FG",
                "FHX",
                "TG",
                "TN",
                "TX",
                "RH",
                "PX",
            ):
                weather[f"{variable}_{station_id}"] = range(len(dates))
        engineered = add_coastal_features(weather)
        features = weather_feature_columns(engineered)
        self.assertIn("coast_pressure_gradient", features)
        self.assertIn("coast_atlantic_storm_pressure", features)
        self.assertIn("coast_west_wind_component", features)
        self.assertIn("wind_speed_rolling_anomaly_3d", features)
        self.assertIn("precipitation_lag_24h", features)

        predictions = make_predictions(
            weather,
            pd.DatetimeIndex(dates[-2:]),
            {
                "species": "Atlantic Vagrancy Index",
                "model": _FixedProbabilityModel(),
                "feature_columns": ["month"],
            },
        )

        self.assertEqual(
            predictions.columns.tolist(), ["date", "probability", "risk_level"]
        )
        self.assertEqual(predictions["risk_level"].tolist(), ["LOW", "HIGH"])


class _FixedProbabilityModel:
    def predict_proba(self, _features: pd.DataFrame) -> np.ndarray:
        return np.array([[0.97, 0.03], [0.85, 0.15]])


if __name__ == "__main__":
    unittest.main()
