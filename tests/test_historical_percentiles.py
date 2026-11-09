import pandas as pd
import pytest

from src.historical_percentiles import (
    HISTORICAL_PERCENTILE_COLUMNS,
    apply_percentile_context,
    context,
    historical_percentile,
    percentile_label,
    rank_text,
)


@pytest.mark.parametrize(
    "value,label",
    [(0, "Common Conditions"), (49.9, "Common Conditions"), (50, "Above Average"),
     (75, "Strong"), (89.9, "Strong"), (90, "Exceptional"), (95, "Historic"), (100, "Historic")],
)
def test_labels(value, label):
    assert percentile_label(value) == label


def test_percentile_is_share_strictly_lower():
    history = pd.Series(range(100), dtype=float)
    assert historical_percentile(50, history) == 50.0
    assert historical_percentile(-1, history) == 0.0
    assert historical_percentile(1000, history) == 100.0
    assert rank_text(91.4) == "Higher than 91% of historical forecast days"
    assert context(91, history)["historical_label"] == "Exceptional"


def test_apply_percentile_context_updates_documents():
    rating = {"horizons": [{
        "date": "2026-10-18", "forecast_day": 1, "score": 91,
        "component_points": {"a": 80.0}, "weather_bonuses": {"b": 10},
    }]}
    rarity = {"horizons": [{"date": "2026-10-18", "rarity_index": 71.0, "rarity_raw": 1.0}]}
    swh = pd.Series(range(100), dtype=float)
    rrh = pd.Series([i / 50 for i in range(100)])
    frame = apply_percentile_context(rating, rarity, swh, rrh)
    assert list(frame.columns) == HISTORICAL_PERCENTILE_COLUMNS
    row = frame.iloc[0]
    assert row["seawatch_percentile"] == 90.0 and row["seawatch_label"] == "Exceptional"
    assert row["rarity_percentile"] == 50.0 and row["rarity_label"] == "Above Average"
    assert rating["horizons"][0]["historical_rank_text"].startswith("Higher than 90%")
    assert "historical_percentile" in rarity["horizons"][0]
    assert "historical_context" in rating and "historical_context" in rarity
