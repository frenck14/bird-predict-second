import numpy as np
import pandas as pd
import pytest

from src import weather_vs_persistence as wp


def _rows(actual, pred_a, pred_b, prob_a=None, prob_b=None):
    n = len(actual)
    return pd.DataFrame(
        {
            "actual_event": actual, "pred_a": pred_a, "pred_b": pred_b,
            "prob_a": prob_a if prob_a is not None else np.array(pred_a, float),
            "prob_b": prob_b if prob_b is not None else np.array(pred_b, float),
        },
        index=range(n),
    )


def test_metrics_confusion_and_scores() -> None:
    rows = _rows([True, True, False, False], [True, False, True, False], [True, True, False, False])
    a = wp.metrics(rows, "A")
    assert (a["tp"], a["fp"], a["fn"], a["tn"]) == (1, 1, 1, 1)
    assert a["f1"] == 0.5 and a["brier"] == 0.5
    b = wp.metrics(rows, "B")
    assert (b["precision"], b["recall"], b["f1"], b["brier"]) == (1.0, 1.0, 1.0, 0.0)


def test_event_runs_lengths() -> None:
    actual = pd.Series([False, True, False, True, True, True, False])
    assert wp.event_runs(actual).tolist() == [0, 1, 0, 3, 3, 3, 0]


def test_persistence_cannot_find_onsets_but_weather_can() -> None:
    dates = pd.date_range("2020-01-01", periods=6)
    frame = pd.DataFrame(
        {
            "species": "Northern Fulmar",
            "date": dates,
            "actual_event": [False, True, True, False, True, False],
            "yesterday_event": [False, False, True, True, False, True],
            "pred_a": [False, True, True, False, True, False],
            "pred_b": [False, False, True, True, False, True],
        }
    )
    row = wp.overlap(frame).iloc[0]
    assert row["onset_days"] == 2
    assert row["onsets_found_by_weather"] == 2
    assert row["onsets_found_by_persistence"] == 0
    assert (row["both_found"], row["weather_only_found"], row["persistence_only_found"]) == (1, 2, 0)
    assert row["persistence_false_alarms"] == 2 and row["weather_false_alarms"] == 0


def test_build_forecasts_uses_yesterdays_label_only(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = pd.date_range("2015-01-01", "2015-01-10")
    predictions = pd.DataFrame(
        {
            "date": dates, "probability": 0.1, "actual_event": [False, True] * 5,
            "event_threshold_count": 2.0, "baseline_probability": 0.3, "species": "Northern Fulmar",
        }
    )
    history = pd.date_range("2014-01-01", "2014-12-31")
    observations = pd.concat(
        [
            pd.DataFrame({"date": history, "species": "Northern Fulmar", "count": [3, 0] * 182 + [3]}),
            pd.DataFrame({"date": dates, "species": "Northern Fulmar", "count": [0, 3] * 5}),
        ]
    )
    monkeypatch.setattr(wp, "SPECIES_ORDER", ["Northern Fulmar"])
    out = wp.build_forecasts(predictions, observations)
    assert out["yesterday_event"].tolist() == [True] + [False, True] * 4 + [False]
    assert out["pred_a"].sum() == 0
    assert out["prob_b"].between(0, 1).all()
