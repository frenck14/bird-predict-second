import pytest

from src.rarity_index import RARITY_WEIGHTS
from src.target_species import TARGET_SPECIES_COLUMNS, build_target_species


def _document():
    probabilities = {
        "Northern Fulmar": 0.5, "Manx Shearwater": 0.2,
        "European Storm-petrel": 0.1, "Sooty Shearwater": 0.1,
        "Great Shearwater": 0.01,
    }
    return {"horizons": [
        {"date": "2026-10-18", "forecast_day": 1, "species_probabilities": probabilities},
        {"date": "2026-10-20", "forecast_day": 3, "species_probabilities": probabilities},
    ]}


def test_target_scores_and_ranking():
    frame = build_target_species(_document())
    assert list(frame.columns) == TARGET_SPECIES_COLUMNS
    assert len(frame) == 10
    day = frame[frame["horizon_days"] == 1]
    assert day["rank"].tolist() == [1, 2, 3, 4, 5]
    assert day["target_score"].is_monotonic_decreasing
    assert day.iloc[0]["species"] == "Sooty Shearwater"
    for row in day.itertuples():
        assert row.target_score == pytest.approx(
            row.probability * RARITY_WEIGHTS[row.species]
        )
