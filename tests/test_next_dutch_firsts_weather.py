import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.next_dutch_firsts_probability import (
    ConfidenceLevel, FactorAnalysis, ProbabilityModel, ProbabilityOutput,
)
from src.next_dutch_firsts_probability_dashboard import ProbabilityDashboard
from src.next_dutch_firsts_weather import load_weather_support, weather_for_pathway


@pytest.fixture
def forecast_dir(tmp_path):
    now = datetime.now(timezone.utc)
    forecast_date = (now.date() + timedelta(days=1)).isoformat()
    metadata = {
        "generated_at": now.isoformat(),
        "weather_source": "Weather provider",
    }
    for key, filename, probability in [
        ("atlantic_vagrancy", "atlantic_vagrancy_forecast.csv", 0.1),
        ("eastern_vagrancy", "eastern_vagrancy_forecast.csv", 0.4),
        ("seabird_index", "seabird_forecast.csv", 0.5),
    ]:
        pd.DataFrame([{"date": forecast_date, "probability": probability}]).to_csv(
            tmp_path / filename, index=False
        )
        metadata[key] = {
            "forecast_csv": f"outputs/{filename}",
            "forecast_start": forecast_date,
            "forecast_end": forecast_date,
        }
    (tmp_path / "yellow_browed_run.json").write_text(json.dumps(metadata))
    return tmp_path, now, metadata


def calculate(model, pathway):
    master = pd.DataFrame([{
        "species": "Test Bird", "pathway": pathway, "dutch_status": "no_dutch_record",
        "western_europe_trend": "stable",
    }])
    dutch = pd.DataFrame(columns=["species"])
    western = pd.DataFrame(columns=["species", "country", "record_count"])
    empty = pd.DataFrame(columns=["species"])
    return model.calculate_probability("Test Bird", "Testus birdus", pathway, master, dutch, western, empty, empty)


@pytest.mark.parametrize(
    ("pathway", "raw", "score", "source"),
    [
        ("Atlantic", 0.1, 50, "Atlantic Vagrancy Index"),
        ("Eastern", 0.4, 80, "Eastern Vagrancy Index"),
        ("Pelagic", 0.5, 100, "Seabird Index"),
        ("Seabird", 0.5, 100, "Seabird Index"),
    ],
)
def test_weather_pathway_scaling_and_provenance(forecast_dir, pathway, raw, score, source):
    directory, now, _ = forecast_dir
    result = weather_for_pathway(pathway, load_weather_support(directory, now))
    assert result.raw_probability == raw
    assert result.scaled_score == pytest.approx(score)
    assert result.source == source
    assert result.forecast_date == (now.date() + timedelta(days=1)).isoformat()
    assert result.weather_source == "Weather provider"
    assert result.status == "available"
    assert "threshold" in result.explanation


def test_near_term_score_preserves_baseline_and_probabilities(forecast_dir):
    directory, _, _ = forecast_dir
    model = ProbabilityModel(directory)
    neutral = calculate(model, "Atlantic")
    strong = calculate(model, "Eastern")
    assert neutral.near_term_opportunity_score == pytest.approx(neutral.total_score)
    assert strong.near_term_opportunity_score == pytest.approx(strong.total_score + 7.5)
    assert len(strong.factor_breakdown) == 6
    assert strong.to_dict()["baseline_total_score"] == strong.total_score
    assert strong.to_dict()["weather_raw_probability"] == 0.4
    assert strong.to_dict()["weather_support"] == pytest.approx(80)
    baseline_factors = {k: v for k, v in strong.factor_breakdown.items() if k != "Weather Support"}
    assert (strong.probability_1yr, strong.probability_5yr, strong.probability_10yr) == (
        model.convert_factors_to_probabilities(baseline_factors, "Eastern")
    )
    assert strong.total_score == pytest.approx(
        100 * sum(f.normalized_score * f.contribution for f in baseline_factors.values())
    )


def test_weather_changes_score_not_long_term_outputs(forecast_dir):
    directory, _, _ = forecast_dir
    before = calculate(ProbabilityModel(directory), "Eastern")
    path = directory / "eastern_vagrancy_forecast.csv"
    frame = pd.read_csv(path)
    frame["probability"] = 0.0
    frame.to_csv(path, index=False)
    after = calculate(ProbabilityModel(directory), "Eastern")
    assert before.near_term_opportunity_score > after.near_term_opportunity_score
    assert before.total_score == after.total_score
    assert before.confidence == after.confidence
    assert before.confidence_score == after.confidence_score
    assert before.key_drivers == after.key_drivers
    assert (before.probability_1yr, before.probability_5yr, before.probability_10yr) == (
        after.probability_1yr, after.probability_5yr, after.probability_10yr
    )


def test_score_saturates_and_snapshot_is_reused(forecast_dir):
    directory, _, _ = forecast_dir
    model = ProbabilityModel(directory)
    first = calculate(model, "Seabird")
    assert first.to_dict()["weather_support"] == 100
    assert first.near_term_opportunity_score == pytest.approx(first.total_score + 12.5)
    (directory / "seabird_forecast.csv").unlink()
    assert calculate(model, "Seabird").to_dict()["weather_support"] == 100
    assert calculate(ProbabilityModel(directory), "Seabird").near_term_opportunity_score is None


@pytest.mark.parametrize(
    ("baseline", "weather", "expected"),
    [(5, 0, 0), (95, 1, 100), (40, 0, 27.5), (40, 1, 52.5)],
)
def test_score_adjustment_bounds(baseline, weather, expected):
    output = ProbabilityOutput(
        "Bird", "Birdus", "Atlantic", 0.1, 0.2, 0.3,
        ConfidenceLevel.LOW, 0.3, [],
        {
            "Baseline": FactorAnalysis("Baseline", baseline / 100, baseline / 100, 1.0),
            "Weather Support": FactorAnalysis("Weather Support", 0.1, weather, 0.25),
        },
    )
    assert output.total_score == pytest.approx(baseline)
    assert output.near_term_opportunity_score == pytest.approx(expected)


def test_unknown_is_explicitly_neutral_even_when_forecasts_are_missing(tmp_path):
    result = calculate(ProbabilityModel(tmp_path), "Unknown")
    assert result.near_term_opportunity_score == result.total_score
    assert result.to_dict()["weather_status"] == "neutral"
    assert result.to_dict()["weather_raw_probability"] is None


@pytest.mark.parametrize("failure", ["missing", "stale", "future", "range", "duplicate", "probability", "expired", "too_far"])
def test_unavailable_weather_never_fabricates_score(forecast_dir, failure):
    directory, now, metadata = forecast_dir
    path = directory / "atlantic_vagrancy_forecast.csv"
    if failure == "missing":
        path.unlink()
    elif failure in ("stale", "future"):
        delta = timedelta(hours=49) if failure == "stale" else -timedelta(hours=1)
        metadata["generated_at"] = (now - delta).isoformat()
        (directory / "yellow_browed_run.json").write_text(json.dumps(metadata))
    elif failure == "range":
        metadata["atlantic_vagrancy"]["forecast_end"] = "2000-01-01"
        (directory / "yellow_browed_run.json").write_text(json.dumps(metadata))
    elif failure == "duplicate":
        frame = pd.read_csv(path)
        pd.concat([frame, frame]).to_csv(path, index=False)
    elif failure == "probability":
        frame = pd.read_csv(path)
        frame["probability"] = 1.1
        frame.to_csv(path, index=False)
    elif failure == "expired":
        old_date = (now.date() - timedelta(days=1)).isoformat()
        metadata["atlantic_vagrancy"]["forecast_start"] = old_date
        metadata["atlantic_vagrancy"]["forecast_end"] = old_date
        (directory / "yellow_browed_run.json").write_text(json.dumps(metadata))
        pd.DataFrame([{"date": old_date, "probability": 0.1}]).to_csv(path, index=False)
    elif failure == "too_far":
        late_date = (now.date() + timedelta(days=2)).isoformat()
        metadata["atlantic_vagrancy"]["forecast_start"] = late_date
        metadata["atlantic_vagrancy"]["forecast_end"] = late_date
        (directory / "yellow_browed_run.json").write_text(json.dumps(metadata))
        pd.DataFrame([{"date": late_date, "probability": 0.1}]).to_csv(path, index=False)
    snapshot = load_weather_support(directory, now)
    assert snapshot["atlantic"].status == "unavailable"
    assert snapshot["atlantic"].scaled_score is None
    if failure not in ("stale", "future"):
        assert snapshot["eastern"].status == "available"
    result = calculate(ProbabilityModel(directory), "Atlantic")
    assert result.near_term_opportunity_score is None
    assert result.to_dict()["weather_explanation"]
    assert result.probability_1yr >= 0


def test_dashboard_shows_provenance_sorting_and_legacy_unavailability(forecast_dir, tmp_path):
    directory, _, _ = forecast_dir
    model = ProbabilityModel(directory)
    neutral = calculate(model, "Atlantic").to_dict()
    strong = calculate(model, "Eastern").to_dict()
    neutral["species"] = "Neutral"
    strong["species"] = "<Strong>"
    csv = tmp_path / "probabilities.csv"
    pd.DataFrame([neutral, strong]).to_csv(csv, index=False)
    dashboard = ProbabilityDashboard(str(csv))
    assert dashboard.get_opportunity_table()["species"].tolist() == ["<Strong>", "Neutral"]
    text = dashboard.render_text_status()
    assert "Baseline Total Score" in text
    assert "Weather Support 80.00" in text
    assert "Near-Term Opportunity Score" in text
    assert "Eastern Vagrancy Index" in text
    assert "raw probability: 0.4000" in text
    html = dashboard._opportunity_html()
    assert "&lt;Strong&gt;" in html
    assert "Weather provider" in html
    html_path = tmp_path / "dashboard.html"
    dashboard.render_html_dashboard(str(html_path))
    assert "Near-Term Opportunity Score" in html_path.read_text()
    legacy = pd.DataFrame([neutral]).drop(columns=[c for c in neutral if c.startswith("weather_") or c in ("baseline_total_score", "near_term_opportunity_score")])
    legacy.to_csv(csv, index=False)
    table = ProbabilityDashboard(str(csv)).get_opportunity_table()
    assert table.iloc[0]["weather_status"] == "unavailable"
    assert "regenerate" in table.iloc[0]["weather_explanation"]


def test_dashboard_marks_saved_weather_stale(forecast_dir, tmp_path):
    directory, now, _ = forecast_dir
    row = calculate(ProbabilityModel(directory), "Atlantic").to_dict()
    row["weather_generated_at"] = (now - timedelta(hours=49)).isoformat()
    path = tmp_path / "saved.csv"
    pd.DataFrame([row]).to_csv(path, index=False)
    table = ProbabilityDashboard(str(path)).get_opportunity_table()
    assert table.iloc[0]["weather_status"] == "unavailable"
    assert pd.isna(table.iloc[0]["near_term_opportunity_score"])
    assert "stale" in table.iloc[0]["weather_explanation"]
