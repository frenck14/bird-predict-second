from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from src.forecast_seabird_species import SPECIES_NAMES
from src.seabird_threshold_analysis import analyze_thresholds, main


def forecast_fixture() -> pd.DataFrame:
    dates = pd.date_range("2024-10-16", periods=14)
    probabilities = [0.04999, 0.05, 0.10, 0.15, 0.20]
    return pd.DataFrame(
        [
            {"date": day, "species": species, "probability": probability}
            for day in dates
            for species, probability in zip(SPECIES_NAMES, probabilities)
        ]
    )


def test_thresholds_use_full_precision_and_include_boundaries() -> None:
    records = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-10-16", "2024-10-29", "2024-10-30"]),
            "species": [SPECIES_NAMES[0], SPECIES_NAMES[1], SPECIES_NAMES[4]],
        }
    )
    result = analyze_thresholds(forecast_fixture(), records, date(2024, 10, 15))

    assert result["threshold"].tolist() == [0.05, 0.10, 0.15, 0.20]
    assert result["true_positives"].tolist() == [1, 0, 0, 0]
    assert result["false_positives"].tolist() == [3, 3, 2, 1]
    assert result["false_negatives"].tolist() == [1, 2, 2, 2]
    assert result["precision"].tolist() == [0.25, 0, 0, 0]
    assert result["recall"].tolist() == [0.5, 0, 0, 0]
    assert result["f1"].iloc[0] == pytest.approx(1 / 3)
    assert result["max_f1"].tolist() == [True, False, False, False]


def test_ties_and_no_predictions() -> None:
    forecast = forecast_fixture()
    forecast["probability"] = 0.01
    records = pd.DataFrame({"date": pd.to_datetime(["2024-10-16"]), "species": [SPECIES_NAMES[0]]})
    result = analyze_thresholds(forecast, records, date(2024, 10, 15))
    assert result["f1"].tolist() == [0, 0, 0, 0]
    assert result["max_f1"].tolist() == [True] * 4
    assert result["false_negatives"].tolist() == [1] * 4


def test_rejects_empty_observations_and_incomplete_forecast() -> None:
    records = pd.DataFrame({"date": pd.to_datetime(["2024-10-15"]), "species": [SPECIES_NAMES[0]]})
    with pytest.raises(ValueError, match="No observations"):
        analyze_thresholds(forecast_fixture(), records, date(2024, 10, 15))
    with pytest.raises(ValueError, match="every species"):
        analyze_thresholds(forecast_fixture().iloc[:-1], records, date(2024, 10, 15))


def test_command_writes_analysis_csv(tmp_path) -> None:
    output = tmp_path / "output" / "threshold_analysis.csv"
    records = pd.DataFrame({"date": pd.to_datetime(["2024-10-16"]), "species": [SPECIES_NAMES[0]]})
    with (
        patch("sys.argv", ["seabird_threshold_analysis", "2024-10-15"]),
        patch("src.seabird_threshold_analysis.OUTPUT_FILE", output),
        patch("src.seabird_threshold_analysis.load_observation_records", return_value=records),
        patch("src.seabird_threshold_analysis.build_seabird_backtest", return_value={"species": forecast_fixture()}),
    ):
        main()
    report = pd.read_csv(output)
    assert report["threshold"].tolist() == [0.05, 0.10, 0.15, 0.20]
    assert report["analysis_date"].eq("2024-10-15").all()
