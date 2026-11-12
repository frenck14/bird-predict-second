import pandas as pd

from src import weather_persistence_model as wpm


def _daily(values):
    return pd.Series(values, index=pd.date_range("2020-01-01", periods=len(values)), dtype=float)


def test_persistence_features_use_only_prior_days() -> None:
    daily = _daily([0, 5, 0, 5, 5, 0, 0, 0, 5, 0])
    targets = pd.DatetimeIndex(["2020-01-04", "2020-01-09"])
    out = wpm.persistence_features(daily, 5, targets)
    assert out.loc["2020-01-04"].tolist() == [0.0, 1.0, 1.0]
    # Days 2-8 are Jan 2..Jan 8: events on Jan 2, 4, 5.
    assert out.loc["2020-01-09"].tolist() == [0.0, 0.0, 3.0]


def test_persistence_features_ignore_target_day_and_future() -> None:
    daily = _daily([0, 5, 0, 5, 5, 0])
    changed = daily.copy()
    changed.iloc[3:] = 0
    target = pd.DatetimeIndex(["2020-01-04"])
    assert wpm.persistence_features(daily, 5, target).equals(wpm.persistence_features(changed, 5, target))


def test_build_frame_requires_full_coverage(monkeypatch) -> None:
    frame = pd.DataFrame({"date": pd.to_datetime(["2020-01-01"]), "species": ["Northern Fulmar"]})
    monkeypatch.setattr(wpm, "build_forecasts", lambda *_: frame)
    combined = pd.DataFrame({"date": pd.to_datetime(["2020-01-02"]), "species": ["Northern Fulmar"],
                             "prob_c": [0.5], "combined_threshold": [3.0]})
    try:
        wpm.build_frame(pd.DataFrame(), combined, pd.DataFrame())
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_verdict_flags_uncertain_species() -> None:
    rows = []
    for model, f1, brier in [("Weather", 0.2, 0.2), ("Persistence", 0.3, 0.1), ("Weather + Persistence", 0.4, 0.05)]:
        rows.append({"species": "Great Shearwater", "group": "Overall", "model": model,
                     "f1": f1, "brier": brier, "uncertain": True})
    text = wpm.verdict(pd.DataFrame(rows), "Great Shearwater")
    assert "best on F1 and Brier" in text and "uncertain" in text
