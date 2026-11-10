from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.next_dutch_firsts_ebird import EBirdAdapter, RECORD_COLUMNS, refresh
from src.next_dutch_firsts_probability import ProbabilityModel
from src.next_dutch_firsts_weather import WeatherSupport


class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status_code = status
        self.headers = {}

    def json(self):
        return self.data


class Session:
    def __init__(self, fail_region=None):
        self.calls = []
        self.fail_region = fail_region

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/ref/taxonomy/" in url:
            return Response([{"sciName": "Testus birdus", "speciesCode": "test1"}])
        if f"/{self.fail_region}/" in url:
            return Response([], status=403)
        if "/GB/" in url:
            return Response([{
                "speciesCode": "test1", "obsDt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "locName": "Test location", "howMany": 3,
            }])
        return Response([])


def _fixtures(tmp_path: Path) -> tuple[Path, Path]:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    pd.DataFrame([{
        "species": "Test Bird", "scientific_name": "Testus birdus",
        "pathway": "Atlantic", "dutch_status": "no_dutch_record",
    }]).to_csv(input_dir / "species_master.csv", index=False)
    pd.DataFrame(columns=["species"]).to_csv(input_dir / "dutch_avifauna_records.csv", index=False)
    pd.DataFrame(columns=["species", "country", "record_count", "source"]).to_csv(
        input_dir / "western_europe_occurrences.csv", index=False,
    )
    pd.DataFrame(columns=["species", "country", "date", "location", "source"]).to_csv(
        input_dir / "current_season_records.csv", index=False,
    )
    pd.DataFrame(columns=["species"]).to_csv(input_dir / "species_traits.csv", index=False)
    model = ProbabilityModel()
    baseline = model.calculate_all_probabilities(str(input_dir))
    baseline.to_csv(output_dir / "probabilities.csv", index=False)
    return input_dir, output_dir


def test_refresh_writes_all_products_and_uses_real_activity(tmp_path):
    input_dir, output_dir = _fixtures(tmp_path)
    session = Session()
    refresh(EBirdAdapter("test-token", session, request_interval=0), input_dir, output_dir)
    assert len(session.calls) == 6
    for url, args in session.calls:
        assert args["headers"]["X-eBirdApiToken"] == "test-token"
        assert "test-token" not in url
        assert args["allow_redirects"] is False
    assert {url.split("/data/obs/")[1].split("/")[0] for url, _ in session.calls[1:]} == {"GB", "IE", "BE", "DE", "DK"}
    assert all(call[1]["params"]["back"] == 30 for call in session.calls[1:])
    records = pd.read_csv(input_dir / "current_season_records.csv")
    assert records.columns.tolist() == RECORD_COLUMNS
    assert records.iloc[0]["species"] == "Test Bird"
    assert records.iloc[0]["country"] == "United Kingdom"
    assert records.iloc[0]["observation_count"] == 3
    summary = pd.read_csv(output_dir / "ebird_activity_summary.csv").iloc[0]
    assert summary["observation_records"] == 1
    assert summary["countries"] == 1
    assert summary["individuals_reported"] == 3
    assert summary["combined_current_activity_score"] == pytest.approx(0.57)
    influence = pd.read_csv(output_dir / "ebird_influence_report.csv").iloc[0]
    assert influence["change"] == pytest.approx(0.57 * 0.03 * 2.5)
    assert influence["new_probability_5yr"] - influence["old_probability_5yr"] == pytest.approx(influence["change"])
    assert pd.read_csv(output_dir / "probabilities.csv").iloc[0]["probability_5yr"].endswith("%")

    refresh(EBirdAdapter("test-token", Session(), request_interval=0), input_dir, output_dir)
    assert len(pd.read_csv(input_dir / "current_season_records.csv")) == 1


def test_refresh_writes_weather_score_without_changing_influence(tmp_path, monkeypatch):
    weather = WeatherSupport(
        "Atlantic Vagrancy Index", (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat(),
        datetime.now(timezone.utc).isoformat(), "Test forecast", 0.16, 80.0,
        "available", "Test pathway support",
    )
    calls = []

    def load_snapshot():
        calls.append(True)
        return {"atlantic": weather}

    monkeypatch.setattr("src.next_dutch_firsts_probability.load_weather_support", load_snapshot)
    input_dir, output_dir = _fixtures(tmp_path)
    refresh(EBirdAdapter("test-token", Session(), request_interval=0), input_dir, output_dir)
    row = pd.read_csv(output_dir / "probabilities.csv").iloc[0]
    assert row["weather_support"] == 80
    assert row["weather_raw_probability"] == pytest.approx(0.16)
    assert row["weather_source"] == "Atlantic Vagrancy Index"
    assert row["near_term_opportunity_score"] == pytest.approx(row["baseline_total_score"] + 7.5)
    assert row["weather_explanation"] == "Test pathway support"
    influence = pd.read_csv(output_dir / "ebird_influence_report.csv").iloc[0]
    assert influence["change"] == pytest.approx(0.57 * 0.03 * 2.5)
    assert len(calls) == 2  # one snapshot per baseline or refresh model


def test_failed_country_does_not_replace_outputs(tmp_path):
    input_dir, output_dir = _fixtures(tmp_path)
    old_records = (input_dir / "current_season_records.csv").read_bytes()
    old_probabilities = (output_dir / "probabilities.csv").read_bytes()
    with pytest.raises(RuntimeError, match="HTTP 403"):
        refresh(EBirdAdapter("test-token", Session("DE"), request_interval=0), input_dir, output_dir)
    assert (input_dir / "current_season_records.csv").read_bytes() == old_records
    assert (output_dir / "probabilities.csv").read_bytes() == old_probabilities
    assert not (output_dir / "ebird_influence_report.csv").exists()


def test_presence_only_and_other_source_are_preserved(tmp_path):
    input_dir, output_dir = _fixtures(tmp_path)
    today = datetime.now(timezone.utc).date().isoformat()
    pd.DataFrame([
        {"species": "Test Bird", "country": "Ireland", "date": today,
         "location": "Manual site", "source": "Manual"},
        {"species": "Test Bird", "country": "Belgium", "date": today,
         "location": "Old eBird site", "source": "eBird"},
    ]).to_csv(input_dir / "current_season_records.csv", index=False)
    class PresenceSession(Session):
        def get(self, url, **kwargs):
            response = super().get(url, **kwargs)
            if "/GB/" in url and response.data:
                del response.data[0]["howMany"]
            return response
    refresh(EBirdAdapter("test-token", PresenceSession(), request_interval=0), input_dir, output_dir)
    records = pd.read_csv(input_dir / "current_season_records.csv")
    assert records["source"].tolist() == ["Manual", "eBird"]
    assert records["observation_count"].isna().all()
    summary = pd.read_csv(output_dir / "ebird_activity_summary.csv").iloc[0]
    assert pd.isna(summary["individuals_reported"])
    assert summary["observation_records"] == 1
    assert summary["combined_current_activity_score"] == pytest.approx(0.64)


def test_unresolved_taxonomy_aborts_before_country_requests():
    session = Session()
    master = pd.DataFrame([{"species": "Unknown", "scientific_name": "Unknown bird"}])
    with pytest.raises(ValueError, match="Unresolved"):
        EBirdAdapter("test-token", session, request_interval=0).fetch(master)
    assert len(session.calls) == 1


def test_empty_observations_create_valid_summary(tmp_path):
    input_dir, output_dir = _fixtures(tmp_path)
    class EmptySession(Session):
        def get(self, url, **kwargs):
            if "/ref/taxonomy/" in url:
                return super().get(url, **kwargs)
            return Response([])
    refresh(EBirdAdapter("test-token", EmptySession(), request_interval=0), input_dir, output_dir)
    assert pd.read_csv(input_dir / "current_season_records.csv").empty
    summary = pd.read_csv(output_dir / "ebird_activity_summary.csv").iloc[0]
    assert summary["observation_records"] == 0
    assert summary["countries"] == 0
    assert summary["combined_current_activity_score"] == 0


def test_activity_uses_observations_not_bird_counts_and_validates_dates():
    today = datetime.now(timezone.utc).date()
    rows = pd.DataFrame([{
        "species": "Test Bird", "country": "Denmark", "observation_date": today.isoformat(),
        "observation_count": 999,
    }])
    model = ProbabilityModel()
    factor = model.calculate_current_activity_factor("Test Bird", rows)
    assert factor.normalized_score == pytest.approx(0.57)
    assert factor.details["num_records"] == 1
    rows.loc[0, "observation_date"] = (today + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="Future observation"):
        model.calculate_current_activity_factor("Test Bird", rows)
    rows.loc[0, "observation_date"] = "not-a-date"
    with pytest.raises(ValueError):
        model.calculate_current_activity_factor("Test Bird", rows)


def test_missing_key_and_truncated_results_fail():
    with pytest.raises(ValueError, match="EBIRD_API_KEY"):
        EBirdAdapter("")
    class FullSession(Session):
        def get(self, url, **kwargs):
            if "/ref/taxonomy/" in url:
                return super().get(url, **kwargs)
            return Response([{}] * 10000)
    with pytest.raises(ValueError, match="truncated"):
        EBirdAdapter("test-token", FullSession(), request_interval=0).fetch(
            pd.DataFrame([{"species": "Test Bird", "scientific_name": "Testus birdus"}])
        )
