from __future__ import annotations

import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import app


def _rows() -> pd.DataFrame:
    return pd.DataFrame([
        {"country": "NL", "location": "Texel", "forecast_probability": 0.30,
         "center_latitude": 53.0, "center_longitude": 4.8},
        {"country": "NL", "location": "Texel", "forecast_probability": 0.10,
         "center_latitude": 53.1, "center_longitude": 4.8},
        {"country": "NL", "location": "Schiermonnikoog (SW)", "forecast_probability": 0.20,
         "center_latitude": 53.4, "center_longitude": 6.1},
        {"country": "NL", "location": "IJmuiden", "forecast_probability": 0.25,
         "center_latitude": 52.5, "center_longitude": 4.6},
        {"country": "NL", "location": "Maasvlakte", "forecast_probability": 0.15,
         "center_latitude": 51.9, "center_longitude": 4.0},
        {"country": "NL", "location": "Westkapelle", "forecast_probability": 0.05,
         "center_latitude": 51.5, "center_longitude": 3.4},
        {"country": "NL", "location": "Vlieland and Terschelling", "forecast_probability": 0.10,
         "center_latitude": 53.3, "center_longitude": 5.1},
        {"country": "NL", "location": "52.00N 4.00E (NL)", "forecast_probability": 0.08,
         "center_latitude": 52.0, "center_longitude": 4.0},
        {"country": "GB", "location": "Fair Isle", "forecast_probability": 0.99,
         "center_latitude": 59.5, "center_longitude": -1.6},
    ])


def _recommendations_script() -> None:
    import pandas as pd

    import app
    from tests.test_dutch_species_recommendations import _rows

    app.show_dutch_species_recommendations(
        "Test Bird", _rows(), "forecast_probability", "Atlantic vagrants",
        pd.Timestamp("2026-01-02"),
    )


def _empty_script() -> None:
    import pandas as pd

    import app

    day = pd.DataFrame([{
        "country": "GB", "location": "Fair Isle", "forecast_probability": 0.9,
    }])
    app.show_dutch_species_recommendations(
        "Test Bird", day, "forecast_probability", "Eastern vagrants",
        pd.Timestamp("2026-01-01"),
    )


def _seabird_script(directory: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import app

    root = Path(directory)
    support = {"horizons": [
        {"horizon_days": horizon, "wind": {"text": "Test wind"}}
        for horizon in (1, 3, 7, 14)
    ]}
    with patch.object(app, "seabird_species_output_paths", return_value={
        "forecast": root / "forecast.csv", "location": root / "location.csv",
    }):
        app.show_seabird_species_product("Test Bird", support, dutch_recommendations=True)


def _vagrant_explorer_script(directory: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import app

    root = Path(directory)
    layers = [{"species": "Test Bird", "slug": "test"}]
    with patch.multiple(
        app,
        RUN_METADATA=root / "run.json",
        EASTERN_LOCATION_FORECAST_FILE=root / "family.csv",
        ATLANTIC_LOCATION_FORECAST_FILE=root / "family.csv",
        EASTERN_SPECIES_LAYERS=layers,
        SPECIES_LAYERS=layers,
        eastern_species_output_paths=lambda slug: {"location": root / "forecast.csv"},
        species_output_paths=lambda slug: {"location": root / "forecast.csv"},
    ):
        app.show_species_explorer()


def test_dutch_ranking_uses_best_cell_and_existing_coast_groups() -> None:
    dutch = app.dutch_species_locations(_rows(), "forecast_probability", "Atlantic vagrants")
    assert len(dutch) == 7
    assert dutch.iloc[0]["location"] == "Texel"
    assert dutch.iloc[0]["rating_nl"] == "VERY_HIGH"
    assert "Fair Isle" not in dutch["location"].tolist()
    coasts = app.dutch_species_coasts(dutch, "forecast_probability")
    assert coasts["Coast"].tolist() == [
        "North Holland Coast", "Wadden Islands", "South Holland Coast", "Delta Coast",
    ]
    assert coasts["Score"].tolist() == pytest.approx([25, 20, 15, 5])
    assert coasts["Sites represented"].tolist() == [1, 3, 1, 1]


def test_dutch_recommendations_render_all_locations_and_map() -> None:
    at = AppTest.from_function(_recommendations_script, default_timeout=30).run()
    assert not at.exception
    assert any("2026-01-02" in caption.value for caption in at.caption)
    assert any("Texel and IJmuiden" in item.value for item in at.markdown)
    assert len(at.dataframe[1].value) == 7
    assert len(at.get("deck_gl_json_chart")) == 1
    deck = at.get("deck_gl_json_chart")[0].proto.json
    assert '"Fair Isle"' not in deck
    assert len(json.loads(deck)["layers"][0]["data"]) == 8


def test_no_dutch_locations_is_explicit() -> None:
    at = AppTest.from_function(_empty_script, default_timeout=30).run()
    assert not at.exception
    assert any("No Dutch location forecast" in item.value for item in at.info)
    assert not at.dataframe


def test_missing_coasts_and_map_coordinates_are_not_invented() -> None:
    day = _rows().iloc[:1].drop(columns=["center_latitude", "center_longitude"])
    dutch = app.dutch_species_locations(day, "forecast_probability", "Eastern vagrants")
    coasts = app.dutch_species_coasts(dutch, "forecast_probability")
    assert coasts["Score"].notna().sum() == 1
    assert coasts.loc[coasts["Coast"].eq("Wadden Islands"), "Score"].iloc[0] == 30


@pytest.mark.parametrize("family", ["Atlantic vagrants", "Eastern vagrants"])
def test_core_dutch_sites_are_ranked_individually_without_combined_inference(family: str) -> None:
    ranking = app.core_dutch_species_ranking(_rows(), family)
    assert ranking["Site"].tolist() == ["Texel", "IJmuiden", "Schiermonnikoog", "Maasvlakte", "Vlieland"]
    assert ranking["Forecast score"].iloc[:4].tolist() == pytest.approx([30, 25, 20, 15])
    assert ranking["Rank"].iloc[:4].tolist() == [1, 2, 3, 4]
    assert pd.isna(ranking["Forecast score"].iloc[4])
    assert ranking["Rating"].iloc[4] == "Unavailable"
    assert pd.isna(ranking["Rank"].iloc[4])
    assert ranking["Rating"].iloc[0] == ("VERY_HIGH" if family == "Atlantic vagrants" else "HIGH")


@pytest.mark.parametrize("family", ["Atlantic vagrants", "Eastern vagrants"])
def test_explorer_places_dutch_then_international_then_plot(tmp_path, family: str) -> None:
    (tmp_path / "run.json").write_text('{"forecast_start": "2026-01-01"}', encoding="utf-8")
    frame = _rows().assign(date="2026-01-01", anomaly_score=0.0)
    frame.to_csv(tmp_path / "family.csv", index=False)
    later = pd.DataFrame([
        {"country": "GB", "location": "Barra", "forecast_probability": 0.4,
         "date": "2026-01-02", "anomaly_score": 0.0},
    ])
    pd.concat([frame, later], ignore_index=True).to_csv(tmp_path / "forecast.csv", index=False)
    at = AppTest.from_function(_vagrant_explorer_script, args=(str(tmp_path),), default_timeout=30).run()
    at.radio[0].set_value(family).run()
    assert not at.exception
    family_ranking = at.dataframe[0].value
    assert family_ranking["Site"].tolist() == ["Texel", "IJmuiden", "Schiermonnikoog", "Maasvlakte", "Vlieland"]
    ranking = at.dataframe[2].value
    assert ranking["Site"].tolist() == ["Texel", "IJmuiden", "Schiermonnikoog", "Maasvlakte", "Vlieland"]
    assert at.dataframe[3].value["location"].tolist() == ["Fair Isle"]
    elements = list(at)
    family_header = next(i for i, e in enumerate(elements) if e.type == "subheader" and e.value == "🇳🇱 Dutch Birding Recommendations")
    family_table = next(i for i, e in enumerate(elements) if e.type == "dataframe")
    family_summary = next(i for i, e in enumerate(elements) if e.type == "markdown" and e.value == "**Recommendation Summary**")
    species_leaderboard = next(i for i, e in enumerate(elements) if e.type == "subheader" and e.value == "Species leaderboard")
    search = next(i for i, e in enumerate(elements) if e.type == "selectbox" and e.label == "Search species")
    dutch = next(i for i, e in enumerate(elements) if e.type == "subheader" and "Best Dutch Locations" in e.value)
    recommendation = next(i for i, e in enumerate(elements) if e.type == "markdown" and "Dutch recommendation" in e.value)
    international = next(i for i, e in enumerate(elements) if e.type == "subheader" and "International Hotspots" in e.value)
    time_series = next(i for i, e in enumerate(elements) if e.type == "subheader" and "Time-series forecast" in e.value)
    plot = next(i for i, e in enumerate(elements) if e.type == "vega_lite_chart")
    dutch_map = next(i for i, e in enumerate(elements) if e.type == "deck_gl_json_chart")
    assert family_header < family_table < family_summary < species_leaderboard < search < dutch < recommendation < international < time_series < plot < dutch_map
    assert any("Texel and IJmuiden" in item.value for item in at.markdown)

    next(widget for widget in at.selectbox if widget.label == "Forecast date").select_index(1).run()
    assert not at.exception
    assert at.dataframe[0].value["Forecast score"].notna().sum() == 4
    assert at.dataframe[2].value["Forecast score"].isna().all()
    assert any("No core Dutch location forecast" in item.value for item in at.info)
    assert at.dataframe[3].value["location"].tolist() == ["Barra"]


def test_family_overview_never_uses_wrong_forecast_date(tmp_path) -> None:
    (tmp_path / "run.json").write_text('{"forecast_start": "2026-01-02"}', encoding="utf-8")
    frame = _rows().assign(date="2026-01-01", anomaly_score=0.0)
    frame.to_csv(tmp_path / "family.csv", index=False)
    frame.to_csv(tmp_path / "forecast.csv", index=False)
    at = AppTest.from_function(_vagrant_explorer_script, args=(str(tmp_path),), default_timeout=30).run()
    assert not at.exception
    assert any("No family-level location forecast is available for 2026-01-02" in item.value for item in at.info)
    assert at.dataframe[0].value.columns[1] == "Species"


def test_seabird_horizons_render_date_specific_dutch_recommendations(tmp_path) -> None:
    dates = pd.date_range("2026-01-01", periods=14)
    pd.DataFrame({
        "date": dates, "probability": [0.2] * 14, "risk_level": ["LOW"] * 14,
    }).to_csv(tmp_path / "forecast.csv", index=False)
    pd.DataFrame([
        {"date": date, "location": "Texel", "country": "NL", "latitude": 53.0,
         "longitude": 4.8, "probability": 0.1, "rank": 1, "anomaly_score": 0.0}
        for date in dates
    ]).to_csv(tmp_path / "location.csv", index=False)
    at = AppTest.from_function(_seabird_script, args=(str(tmp_path),), default_timeout=30).run()
    assert not at.exception
    dates_found = [caption.value for caption in at.caption if "Forecast for 2026" in caption.value]
    assert len(dates_found) == 3
    assert all(date in " ".join(dates_found) for date in ("2026-01-03", "2026-01-07", "2026-01-14"))
