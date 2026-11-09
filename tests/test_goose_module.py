from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src import goose_module as gm
from src.goose_features import GOOSE_FEATURE_COLUMNS, add_goose_features, seasonality
from src.build_dataset_v2 import add_coastal_features
from src.build_goose_dataset import (
    EUROPEAN_COUNTRIES, GOOSE_SITES, GOOSE_SPECIES, REGIONS, countries_for,
    parse_day_facets,
)
from src.train_goose_models import (
    ACTIVITY_MODEL, build_comparison_report, build_supervised, evaluation_status,
    winter_id, winter_relative_labels,
)


def _weather(days: int = 40, start: str = "2025-12-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=days, freq="D")
    rng = np.random.default_rng(0)
    data = {"date": dates}
    for station in (235, 242, 225, 310):
        data[f"DDVEC_{station}"] = rng.uniform(10, 350, days)
        data[f"FG_{station}"] = rng.uniform(30, 120, days)
        data[f"FHX_{station}"] = rng.uniform(50, 160, days)
        data[f"TG_{station}"] = np.linspace(40, -60, days)
        data[f"TN_{station}"] = np.linspace(20, -90, days)
        data[f"TX_{station}"] = np.linspace(70, -20, days)
        data[f"RH_{station}"] = rng.integers(0, 40, days).astype(float)
        data[f"PX_{station}"] = rng.uniform(9900, 10400, days)
    return pd.DataFrame(data)


def _history(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    index = pd.date_range("2012-10-01", periods=n, freq="D")
    frame = pd.DataFrame(
        {name: rng.uniform(0.0, 0.5, n) for name in [ACTIVITY_MODEL, *gm.RARE_GOOSE_WEIGHTS]},
        index=index,
    )
    frame.index.name = "date"
    return frame


def _probabilities(activity: float, rare: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2026-10-19", periods=14, freq="D")
    frame = pd.DataFrame({"date": dates, ACTIVITY_MODEL: activity})
    for species in gm.RARE_GOOSE_WEIGHTS:
        frame[species] = rare
    conditions = pd.DataFrame(
        {"date": dates, "cold_outbreak": False, "rapid_temp_drop": False,
         "consecutive_frost_days": 0.0, "temperature_c": 5.0}
    )
    return frame, conditions


def test_weights_match_specification():
    assert gm.RARE_GOOSE_WEIGHTS == {
        "Lesser White-fronted Goose": 4.0, "Red-breasted Goose": 5.0,
        "Snow Goose": 5.0, "Ross's Goose": 8.0, "Black Brant": 3.0,
    }


@pytest.mark.parametrize("score,expected", [(0, "Quiet"), (24, "Quiet"), (25, "Moderate"), (50, "Good"),
                                            (70, "Strong"), (85, "Major Goose Day"), (100, "Major Goose Day")])
def test_activity_bands(score, expected):
    assert gm.band(score, gm.ACTIVITY_BANDS) == expected


@pytest.mark.parametrize("score,expected", [(10, "Low"), (25, "Moderate"), (55, "High"), (70, "Very High"), (90, "Exceptional")])
def test_rare_bands(score, expected):
    assert gm.band(score, gm.RARE_BANDS) == expected


@pytest.mark.parametrize("score,expected", [(10, "Poor"), (30, "Fair"), (60, "Good"), (75, "Excellent"), (90, "Major Goose Day")])
def test_rating_bands(score, expected):
    assert gm.band(score, gm.RATING_BANDS) == expected


@pytest.mark.parametrize(
    "rating,rare,decision",
    [(70, 0, "GO"), (69.9, 80, "GO"), (69.9, 79.9, "MAYBE"), (40, 0, "MAYBE"), (39.9, 10, "STAY HOME")],
)
def test_recommendation_thresholds(rating, rare, decision):
    result = gm.recommendation(rating, rare)
    assert result["decision"] == decision
    assert result["emoji"] == {"GO": "🟢", "MAYBE": "🟡", "STAY HOME": "🔴"}[decision]


def test_historical_context_labels_and_text():
    history = pd.Series(np.arange(100, dtype=float))
    context = gm.percentile_context(91.5, history)
    assert context["historical_percentile"] == 92.0
    assert context["historical_label"] == "Exceptional"
    assert context["historical_rank_text"] == "Higher than 92% of historical winter days"
    assert gm.percentile_context(-1, history)["historical_label"] == "Common Conditions"
    assert gm.percentile_context(500, history)["historical_label"] == "Historic"


def test_products_scores_and_target_ranking():
    probabilities, conditions = _probabilities(0.6, 0.2)
    probabilities.loc[0, "Red-breasted Goose"] = 0.9
    products = gm.build_goose_products(probabilities, conditions, _history())
    frames, document = products["frames"], products["document"]
    assert [h["forecast_day"] for h in document["horizons"]] == [1, 3, 7, 14]
    first = document["horizons"][0]
    assert first["goose_activity"]["score"] == 60
    expected = 0.7 * 60 + 0.3 * first["rare_goose_potential"]["score"]
    assert first["goose_day_rating"]["score"] == pytest.approx(expected, abs=1)
    targets = frames["targets"].query("horizon_days == 1")
    assert targets["rank"].tolist() == [1, 2, 3, 4, 5]
    assert targets["target_score"].is_monotonic_decreasing
    assert targets.iloc[0]["species"] == "Red-breasted Goose"
    for row in targets.itertuples():
        assert row.target_score == pytest.approx(row.probability * gm.RARE_GOOSE_WEIGHTS[row.species])
    assert len(frames["hotspots"].query("horizon_days == 7")) == 10
    assert set(frames["regions"]["region"]) <= set(REGIONS)
    assert frames["regions"].query("horizon_days == 1")["score"].is_monotonic_decreasing
    assert len(frames["european_influx"]) == 4
    assert len(frames["european_species_activity"]) == 20
    european = frames["european_influx"].set_index("horizon_days")
    expected_7d = (
        european.loc[7, "rare_goose_europe_index"]
        - european.loc[1, "rare_goose_europe_index"]
    )
    expected_14d = (
        european.loc[14, "rare_goose_europe_index"]
        - european.loc[1, "rare_goose_europe_index"]
    )
    assert np.allclose(european["change_7d_points"], expected_7d)
    assert np.allclose(european["change_14d_points"], expected_14d)


def test_european_influx_uses_species_percentiles_and_horizon_changes():
    probabilities, conditions = _probabilities(0.6, 0.2)
    for species in gm.RARE_GOOSE_WEIGHTS:
        probabilities[species] = np.linspace(0.01, 0.75, len(probabilities))
    products = gm.build_goose_products(probabilities, conditions, _history())
    index = products["frames"]["european_influx"].set_index("horizon_days")
    assert index.loc[7, "rare_goose_europe_index"] > index.loc[1, "rare_goose_europe_index"]
    assert index.loc[14, "rare_goose_europe_index"] > index.loc[7, "rare_goose_europe_index"]
    assert index.loc[7, "change_7d_points"] == pytest.approx(
        index.loc[7, "rare_goose_europe_index"] - index.loc[1, "rare_goose_europe_index"]
    )
    forecast = products["document"]["horizons"][0]["european_goose_influx"]
    assert len(forecast["species_activity"]) == 5
    assert all("european_percentile" in species for species in forecast["species_activity"])


def test_rare_index_is_clipped_to_historical_range():
    low, conditions = _probabilities(0.1, 0.0)
    high, _ = _probabilities(0.1, 1.0)
    history = _history()
    assert gm.build_goose_products(low, conditions, history)["document"]["horizons"][0]["rare_goose_potential"]["score"] == 0
    assert gm.build_goose_products(high, conditions, history)["document"]["horizons"][0]["rare_goose_potential"]["score"] == 100


def test_cold_outbreak_shifts_hotspots_to_zeeland():
    sites = gm.site_table(None)
    calm = pd.Series({"cold_outbreak": False, "consecutive_frost_days": 0.0})
    cold = pd.Series({"cold_outbreak": True, "consecutive_frost_days": 5.0})
    _, calm_regions = gm.build_hotspots(sites, 60, 40, calm)
    _, cold_regions = gm.build_hotspots(sites, 60, 40, cold)
    score = lambda frame, region: float(frame.set_index("region").loc[region, "score"])
    assert score(cold_regions, "Zeeland") > score(calm_regions, "Zeeland")
    assert score(cold_regions, "Flevoland") < score(calm_regions, "Flevoland")


def test_save_outputs_and_json(tmp_path):
    probabilities, conditions = _probabilities(0.5, 0.1)
    products = gm.build_goose_products(probabilities, conditions, _history())
    gm.save_goose_products(products, tmp_path)
    for name in ("goose_activity_index.csv", "rare_goose_potential.csv", "goose_day_rating.csv",
                 "goose_hotspots.csv", "goose_region_ranking.csv", "target_geese.csv",
                 "european_goose_influx.csv", "rare_goose_europe_index.csv", "goose_module.json"):
        assert (tmp_path / name).is_file()
    document = json.loads((tmp_path / "goose_module.json").read_text())
    assert document["product"] == "Winter Goose Module"


def test_missing_models_raise(tmp_path):
    with pytest.raises(FileNotFoundError, match="train_goose_models"):
        gm.load_artifacts(tmp_path)
    assert not gm.goose_models_available(tmp_path)


def test_goose_features_frost_and_triggers():
    features = add_goose_features(add_coastal_features(_weather()))
    assert set(GOOSE_FEATURE_COLUMNS).issubset(features.columns)
    assert features["goose_frost"].iloc[0] == 0 and features["goose_frost"].iloc[-1] == 1
    run = features["goose_consecutive_frost_days"]
    assert run.is_monotonic_increasing and run.iloc[-1] > 5
    assert features["goose_temp_min_c"].iloc[-1] < 0 <= features["goose_temp_min_c"].iloc[0]


def test_seasonality_columns():
    frame = seasonality(pd.DatetimeIndex(["2026-01-05"]))
    assert frame.loc[0, "month"] == 1 and frame.loc[0, "week_of_year"] == 2 and frame.loc[0, "day_of_year"] == 5


def test_winter_labels_are_relative_per_winter():
    dates = pd.date_range("2020-10-01", "2021-03-31").append(pd.date_range("2021-10-01", "2022-03-31"))
    counts = pd.Series(np.arange(len(dates), dtype=float) % 50 + 1, index=dates)
    labels, cutoffs = winter_relative_labels(dates, counts, 75)
    assert set(cutoffs) == {2020, 2021}
    assert 0.2 < labels.mean() < 0.35
    assert list(winter_id(pd.DatetimeIndex(["2021-01-10", "2021-11-01"]))) == [2020, 2021]


def test_supervised_alignment_uses_previous_day_weather():
    features = add_goose_features(add_coastal_features(_weather(30)))
    columns = ["month", "goose_temp_mean_c"]
    counts = pd.Series(1.0, index=features["date"])
    frame = build_supervised(features, columns, counts, 75)
    assert (frame["target_date"] - frame["origin_date"]).eq(pd.Timedelta(days=1)).all()
    first = frame.iloc[0]
    expected = features.loc[features["date"].eq(first["origin_date"]), "goose_temp_mean_c"].iloc[0]
    assert first["goose_temp_mean_c"] == pytest.approx(expected)


def test_status_rules():
    assert evaluation_status(True, 100, 40, 0.7) == "Production"
    assert evaluation_status(True, 100, 40, 0.6) == "Beta"
    assert evaluation_status(False, 5, 1, 0.9) == "Experimental"


def test_comparison_report_keeps_before_then_after_metric_order():
    current = pd.DataFrame(
        [{"model": "A", "roc_auc": 0.7, "pr_auc": 0.4}]
    )
    previous = pd.DataFrame(
        {"roc_auc_before": [0.6], "pr_auc_before": [0.3]},
        index=pd.Index(["A"], name="model"),
    )
    report = build_comparison_report(current, previous)
    assert report.columns.tolist() == [
        "model", "roc_auc_before", "roc_auc_after",
        "pr_auc_before", "pr_auc_after", "roc_auc_change", "pr_auc_change",
    ]
    assert report.loc[0, "roc_auc_change"] == pytest.approx(0.1)
    assert report.loc[0, "pr_auc_change"] == pytest.approx(0.1)


def test_facet_parser_ignores_multi_day_intervals():
    response = {"facets": [{"counts": [
        {"name": "2024-01-02", "count": 3}, {"name": "2024-01-02/2024-01-05", "count": 9},
    ]}]}
    assert parse_day_facets(response) == {"2024-01-02": 3}


def test_site_registry_covers_all_regions():
    assert {region for _, region, _, _ in GOOSE_SITES} == set(REGIONS)


def test_european_species_country_scopes():
    entries = {entry["species"]: entry for entry in GOOSE_SPECIES}
    for species, countries in EUROPEAN_COUNTRIES.items():
        assert countries_for(entries[species]) == countries
    assert countries_for(entries["Lesser White-fronted Goose"]) == ("NL", "BE", "DE", "DK")
    assert countries_for(entries["Black Brant"]) == ("NL", "BE", "DE", "DK")
