import pandas as pd
import pytest

from src.seabird_guidance import (
    COAST_RANKING_COLUMNS,
    build_recommendations,
    coast_ranking_frame,
    coast_scores,
    explain_rating,
    recommend,
)


@pytest.mark.parametrize(
    "rating,rarity,expected",
    [
        (70, 0, "GO"),
        (50, 70, "GO"),
        (69, 69, "MAYBE"),
        (50, 69, "MAYBE"),
        (35, 0, "MAYBE"),
        (0, 50, "MAYBE"),
        (34, 49, "STAY HOME"),
        (49, 70, "MAYBE"),
    ],
)
def test_recommend_thresholds(rating, rarity, expected):
    assert recommend(rating, rarity) == expected


def test_coast_scores_ranked_with_four_regions():
    sites = {
        "Texel": 40, "Vlieland": 25, "Den Helder": 30, "Maasvlakte": 10,
        "Neeltje Jans": 35, "Westkapelle": 25,
    }
    ranking = coast_scores(sites)
    assert [row["coast"] for row in ranking] == [
        "Wadden Islands", "Delta Coast", "North Holland Coast", "South Holland Coast",
    ]
    assert [row["rank"] for row in ranking] == [1, 2, 3, 4]
    scores = [row["score"] for row in ranking]
    assert scores == sorted(scores, reverse=True)
    assert ranking[0]["top_site"] == "Texel"


def test_ranking_frame_and_recommendations():
    horizon = {
        "date": "2026-10-18", "label": "Tomorrow", "forecast_day": 1, "score": 55,
        "coast_ranking": coast_scores({"Texel": 50, "Maasvlakte": 10}),
    }
    frame = coast_ranking_frame([horizon])
    assert list(frame.columns) == COAST_RANKING_COLUMNS
    assert frame["rank"].tolist() == [1, 2]
    items = build_recommendations(
        {"horizons": [horizon]},
        {"horizons": [{"date": "2026-10-18", "rarity_index": 75}]},
    )
    assert items[0]["decision"] == "GO"
    assert items[0]["best_coast"] == "Wadden Islands"
    assert items[0]["best_site"] == "Texel"


def test_explain_rating_splits_drivers():
    weights = {"European Storm-petrel": 0.3, "Manx Shearwater": 0.2, "Sooty Shearwater": 0.1}
    probabilities = {"European Storm-petrel": 0.5, "Manx Shearwater": 0.05, "Sooty Shearwater": 0.3}
    bonuses = {"strong_westerly_wind": 10, "deep_atlantic_low": 10, "increasing_wind": 5, "peak_seawatching_season": 5}
    applied = {"strong_westerly_wind": 10, "deep_atlantic_low": 0, "increasing_wind": 0, "peak_seawatching_season": 5}
    result = explain_rating(
        probabilities, weights, bonuses, applied,
        {"wind_speed_kt": 25, "wind_direction": "W", "minimum_pressure_hpa": 1010, "wind_change_ms": -1},
    )
    positive = {d["name"] for d in result["positive_drivers"]}
    negative = {d["name"] for d in result["negative_drivers"]}
    assert positive == {"strong_westerly_wind", "peak_seawatching_season", "storm_petrel_signal", "sooty_signal"}
    assert negative == {"deep_atlantic_low", "increasing_wind", "manx_signal"}
    assert all(d["points"] < 0 for d in result["negative_drivers"])
