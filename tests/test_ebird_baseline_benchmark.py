import numpy as np
import pandas as pd
import pytest

from src import ebird_baseline_benchmark as eb


def _daily(values, start="2020-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values)), dtype=float)


def test_activity_window_ends_the_day_before_the_forecast_date() -> None:
    daily = _daily([0] * 10 + [100] + [0] * 10)
    features = eb.activity_features(daily, 7)["log_activity"]
    spike_day = daily.index[10]
    assert features.loc[spike_day] == 0.0
    assert features.loc[spike_day + pd.Timedelta(days=1)] == pytest.approx(np.log1p(100))
    assert features.loc[spike_day + pd.Timedelta(days=7)] == pytest.approx(np.log1p(100))
    assert features.loc[spike_day + pd.Timedelta(days=8)] == 0.0


def test_features_ignore_future_records() -> None:
    base = _daily(np.arange(60) % 5)
    changed = base.copy()
    changed.iloc[40:] += 1000
    left = eb.activity_features(base, 7)["log_activity"].iloc[:40]
    right = eb.activity_features(changed, 7)["log_activity"].iloc[:40]
    pd.testing.assert_series_equal(left, right)


def test_persistence_ignores_labels_after_the_forecast_origin() -> None:
    index = pd.date_range("2020-01-01", periods=20)
    labels = pd.Series([1, 1, 0, 0] * 5, index=index, dtype=float)
    later = labels.copy()
    later.iloc[10:] = 1 - later.iloc[10:]
    targets = pd.DatetimeIndex([index[10]])
    train_end = index[7]
    np.testing.assert_array_equal(
        eb.fit_predict_persistence(labels, train_end, targets),
        eb.fit_predict_persistence(later, train_end, targets),
    )


def test_persistence_rates_use_training_days_only() -> None:
    index = pd.date_range("2020-01-01", periods=12)
    labels = pd.Series([1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1], index=index, dtype=float)
    # Training pairs (prev, y) up to index 5: 1->1, 1->1, 1->0, 0->0, 0->0 => P(1|1)=2/3, P(1|0)=0.
    probability = eb.fit_predict_persistence(labels, index[5], pd.DatetimeIndex([index[9], index[7]]))
    assert probability == pytest.approx([2 / 3, 0.0])


def test_activity_model_probability_rises_with_activity() -> None:
    index = pd.date_range("2020-01-01", periods=400)
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(size=400), index=index, name="x")
    y = pd.Series((x + rng.normal(scale=0.5, size=400) > 0).astype(float), index=index)
    targets = pd.DatetimeIndex(index[300:])
    probability = eb.fit_predict_activity(x, y, index[299], targets)
    assert np.corrcoef(probability, x.loc[targets])[0, 1] > 0.9


def test_activity_end_and_score() -> None:
    activity = pd.DataFrame({"date": pd.to_datetime(["2025-03-01", "2025-06-01"])})
    assert eb.activity_end(activity) == pd.Timestamp("2025-12-31")
    rows = pd.DataFrame(
        {
            "probability": [0.9, 0.1, 0.9, 0.1],
            "actual_event": [True, True, False, False],
            "baseline_probability": [0.5] * 4,
        }
    )
    result = eb.score(rows)
    assert (result["precision"], result["recall"], result["f1"]) == (0.5, 0.5, 0.5)
    assert result["brier_score"] == pytest.approx(0.41)
    assert result["brier_skill_vs_training_prevalence"] == pytest.approx(1 - 0.41 / 0.25)
