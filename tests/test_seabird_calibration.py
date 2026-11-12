import numpy as np
import pandas as pd
import pytest

from src import seabird_calibration as cal


def _series(values):
    return pd.Series(values, dtype=float)


def test_bins_use_left_closed_edges_and_include_one_in_last_bin() -> None:
    bins = cal.assign_bins(_series([0.0, 0.0999, 0.1, 0.95, 1.0]))
    assert bins.tolist() == [0, 0, 1, 9, 9]


def test_bin_counts_means_and_frequencies() -> None:
    bins = cal.calibration_bins(_series([0.05, 0.05, 0.15, 0.95]), _series([0, 1, 0, 1]))
    assert bins["forecast_count"].tolist() == [2, 1, 0, 0, 0, 0, 0, 0, 0, 1]
    first = bins.iloc[0]
    assert first["mean_predicted_probability"] == pytest.approx(0.05)
    assert first["observed_event_frequency"] == pytest.approx(0.5)
    assert np.isnan(bins.iloc[2]["mean_predicted_probability"])


def test_perfectly_calibrated_constant_forecast() -> None:
    p = _series([0.25] * 4)
    y = _series([1, 0, 0, 0])
    m = cal.calibration_metrics(p, y)
    assert m["brier_score"] == pytest.approx(0.1875)
    assert m["uncertainty"] == pytest.approx(0.1875)
    assert m["reliability"] == pytest.approx(0.0)
    assert m["resolution"] == pytest.approx(0.0)
    assert m["ece"] == pytest.approx(0.0)
    assert m["brier_skill_score"] == pytest.approx(0.0)
    assert m["decomposition_residual"] == pytest.approx(0.0)


def test_overconfident_forecast_metrics_and_decomposition() -> None:
    # Always forecasts 0.9 but the event happens half the time.
    p = _series([0.9] * 10)
    y = _series([1] * 5 + [0] * 5)
    m = cal.calibration_metrics(p, y)
    assert m["reliability"] == pytest.approx(0.16)
    assert m["ece"] == pytest.approx(0.4)
    assert m["mce"] == pytest.approx(0.4)
    assert m["brier_score"] == pytest.approx(0.41)
    assert m["brier_skill_score"] == pytest.approx(1 - 0.41 / 0.25)
    # Constant forecasts within one bin make the decomposition exact.
    assert m["brier_score"] == pytest.approx(
        m["reliability"] - m["resolution"] + m["uncertainty"]
    )


def test_perfect_sharp_forecast_has_full_resolution() -> None:
    p = _series([0.0, 0.0, 1.0, 1.0])
    y = _series([0, 0, 1, 1])
    m = cal.calibration_metrics(p, y)
    assert m["brier_score"] == pytest.approx(0.0)
    assert m["resolution"] == pytest.approx(m["uncertainty"])
    assert m["brier_skill_score"] == pytest.approx(1.0)
    assert m["ece"] == pytest.approx(0.0)


def test_mce_is_worst_populated_bin_and_ece_is_count_weighted() -> None:
    p = _series([0.05] * 8 + [0.85] * 2)
    y = _series([0] * 8 + [0, 0])
    m = cal.calibration_metrics(p, y)
    assert m["mce"] == pytest.approx(0.85)
    assert m["ece"] == pytest.approx(0.8 * 0.05 + 0.2 * 0.85)


def test_classification_labels() -> None:
    base = {"ece": 0.01, "weighted_slope_gap": 1.0}
    assert cal.classify(base) == "well calibrated"
    assert cal.classify({"ece": 0.1, "weighted_slope_gap": 0.4}) == "overconfident"
    assert cal.classify({"ece": 0.1, "weighted_slope_gap": 1.6}) == "underconfident"


def test_rare_events_get_insufficient_verdict() -> None:
    metrics = {"event_days": 5, "ece": 0.0, "weighted_slope_gap": 1.0}
    assert cal.classify(metrics) == "insufficient events"
