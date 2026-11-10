import pandas as pd
import pytest

from src.next_dutch_firsts_probability import ProbabilityModel


def occurrences(rows):
    return pd.DataFrame(
        rows, columns=["species", "country", "record_count", "source"]
    )


def master(trend=None):
    return pd.DataFrame([{
        "species": "Brown Shrike",
        "pathway": "Eastern",
        "dutch_status": "no_dutch_record",
        "western_europe_trend": trend,
        "uk_records": 9999,
    }])


def test_momentum_uses_occurrences_and_unique_neighbor_countries():
    df = occurrences([
        ("Brown Shrike", "United Kingdom", "10", "GBIF"),
        ("Brown Shrike", "United Kingdom", 5, "GBIF"),
        ("Brown Shrike", "Ireland", 2, "GBIF"),
        ("Brown Shrike", "Belgium", 0, "GBIF"),
        ("Brown Shrike", "Germany", None, "manual_review_required"),
        ("Brown Shrike", "Denmark", 20, "manual_review_required"),
        ("Brown Shrike", "France", 100, "GBIF"),
        ("Other", "Denmark", 100, "GBIF"),
    ])
    factor = ProbabilityModel().calculate_european_momentum_factor(
        "Brown Shrike", df, master("increasing")
    )
    assert factor.details == {
        "neighbor_records": 17,
        "total_neighbor_records": 17,
        "neighbors_with_records": 2,
        "country_diversity": 0.4,
        "trend": "Increasing",
    }
    assert factor.normalized_score == pytest.approx(0.5 * 0.4 + 0.3 + 0.2 * 17 / 50)


@pytest.mark.parametrize(
    ("trend", "label", "score"),
    [("stable", "Stable", 0.15), ("rare", "Decreasing", 0.06),
     (None, "Unknown", 0.0)],
)
def test_empty_occurrences_preserve_trend(trend, label, score):
    factor = ProbabilityModel().calculate_european_momentum_factor(
        "Brown Shrike", occurrences([]), master(trend)
    )
    assert factor.details["neighbor_records"] == 0
    assert factor.details["country_diversity"] == 0
    assert factor.details["trend"] == label
    assert factor.normalized_score == pytest.approx(score)


def test_occurrences_work_without_master_row():
    df = occurrences([("Brown Shrike", "Ireland", 1, "GBIF")])
    factor = ProbabilityModel().calculate_european_momentum_factor(
        "Brown Shrike", df, master().iloc[:0]
    )
    assert factor.details["neighbor_records"] == 1
    assert factor.details["neighbors_with_records"] == 1
    assert factor.normalized_score == pytest.approx(0.104)


@pytest.mark.parametrize("count", ["invalid", -1, 1.5, float("inf")])
def test_invalid_occurrence_counts_fail_explicitly(count):
    df = occurrences([("Brown Shrike", "Ireland", count, "GBIF")])
    with pytest.raises(ValueError):
        ProbabilityModel().calculate_european_momentum_factor(
            "Brown Shrike", df, master()
        )


def test_occurrences_increase_score_and_all_probability_horizons():
    model = ProbabilityModel()
    empty = occurrences([])
    present = occurrences([
        ("Brown Shrike", "United Kingdom", 603, "GBIF"),
        ("Brown Shrike", "Ireland", 6, "GBIF"),
        ("Brown Shrike", "Belgium", 49, "GBIF"),
        ("Brown Shrike", "Germany", 3, "GBIF"),
        ("Brown Shrike", "Denmark", 375, "GBIF"),
    ])
    dutch = pd.DataFrame(columns=["species"])
    season = pd.DataFrame(columns=["species"])
    traits = pd.DataFrame(columns=["species"])

    def calculate(data):
        return model.calculate_probability(
            "Brown Shrike", "Lanius cristatus", "Eastern", master(),
            dutch, data, season, traits,
        )

    before, after = calculate(empty), calculate(present)
    factor = after.factor_breakdown["European Momentum"]
    assert factor.details["neighbor_records"] == 1036
    assert factor.details["neighbors_with_records"] == 5
    assert factor.normalized_score == pytest.approx(0.7)
    assert after.total_score == pytest.approx(before.total_score + 14)
    assert after.to_dict()["total_score"] == after.total_score
    assert after.probability_1yr > before.probability_1yr
    assert after.probability_5yr > before.probability_5yr
    assert after.probability_10yr > before.probability_10yr
