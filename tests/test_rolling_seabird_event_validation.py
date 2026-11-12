from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src import rolling_seabird_event_validation as rolling
from src.forecast_seabird_locations import _build_seabird_features
from src.seabird_backtest import load_historical_weather


def test_summary_uses_pooled_event_counts_and_brier() -> None:
    rows = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=4),
            "actual_event": [1, 0, 1, 0],
            "probability": [0.8, 0.3, 0.1, 0.0],
            "baseline_probability": [0.25] * 4,
            "event_threshold_count": [3] * 4,
        }
    )
    result = rolling.summarize_rows(rows, "Northern Fulmar", "2020")
    assert (result["true_positive"], result["false_positive"], result["false_negative"]) == (1, 1, 1)
    assert result["event_days"] == 2
    assert result["event_prevalence"] == 0.5
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["brier_score"] == pytest.approx((0.04 + 0.09 + 0.81) / 4)
    assert result["baseline_brier_score"] == pytest.approx((0.75**2 * 2 + 0.25**2 * 2) / 4)


def test_annual_cutoff_and_previous_day_weather() -> None:
    weather = pd.DataFrame(
        {"date": pd.date_range("2010-01-01", "2015-01-02")}
    )
    weather["weather"] = np.arange(len(weather))
    occurrences = pd.DataFrame(
        {"date": pd.to_datetime(["2014-12-30", "2015-01-01"]), "species": ["Northern Fulmar"] * 2}
    )
    observations = pd.DataFrame(
        {
            "date": pd.to_datetime(["2015-01-01", "2015-01-02", "2015-01-03"]),
            "species": ["Northern Fulmar"] * 3,
            "count": [2, 1, 3],
        }
    )

    class Model:
        def predict_proba(self, inputs: pd.DataFrame) -> np.ndarray:
            assert inputs["weather"].tolist() == weather["weather"].iloc[-3:].tolist()
            return np.array([[0.7, 0.3], [0.9, 0.1], [0.6, 0.4]])

    def fit(train_weather, train_occurrences, cutoff, species, horizon, *, engineered_weather):
        assert str(cutoff) == "2014-12-31"
        assert train_weather["date"].max() == pd.Timestamp(cutoff)
        assert train_occurrences["date"].max() < pd.Timestamp(cutoff)
        assert engineered_weather["date"].max() == pd.Timestamp(cutoff)
        assert horizon == 1
        return {
            "model": Model(), "feature_columns": ["weather"], "weather_feature_columns": ["weather"],
            "influx_threshold_count": 2, "training_positive_days": 1, "training_rows": 4,
            "training_end_date": "2014-12-31",
        }

    with (
        patch.object(rolling, "SPECIES_NAMES", ("Northern Fulmar",)),
        patch.object(rolling, "_build_seabird_features", side_effect=lambda frame: frame),
        patch.object(rolling, "_fit_cutoff_model", side_effect=fit),
    ):
        result = rolling.evaluate_rolling(weather, occurrences, observations)
    assert result["year"].tolist() == ["2015", "all"]
    row = result.iloc[0]
    assert (row["start_date"], row["end_date"], row["evaluated_days"]) == ("2015-01-01", "2015-01-03", 3)
    assert (row["event_days"], row["true_positive"], row["false_positive"], row["false_negative"]) == (2, 2, 0, 0)


def test_engineered_weather_is_prefix_invariant() -> None:
    weather = load_historical_weather()
    prefix = weather.loc[weather["date"].le("2020-06-30")]
    expected = _build_seabird_features(prefix)
    full = _build_seabird_features(weather)
    pd.testing.assert_frame_equal(
        expected.reset_index(drop=True),
        full.loc[full["date"].le("2020-06-30")].reset_index(drop=True),
    )
