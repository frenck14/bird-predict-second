from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


def _dashboard_script(directory: str, ready: bool) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import app

    root = Path(directory)
    with patch.multiple(
        app,
        RUN_METADATA=root / ("run.json" if ready else "missing.json"),
        EASTERN_FORECAST_FILE=root / "eastern.csv",
        ATLANTIC_FORECAST_FILE=root / "atlantic.csv",
        SEABIRD_FORECAST_FILE=root / "seabird.csv",
        RATING_JSON_OUTPUT=root / "rating.json",
        RATING_OUTPUT=root / "rating.csv",
        GOOSE_JSON_OUTPUT=root / "goose.json",
        DECISION_SUPPORT_FILE=root / "support.json",
        BOI_JSON=root / "boi.json",
        SPECIES_LAYERS=[
            {"species": "Atlantic Bird", "slug": "atlantic_bird"},
            {"species": "Skipped Bird", "slug": "skipped_bird"},
        ],
        EASTERN_SPECIES_LAYERS=[{"species": "Eastern Bird", "slug": "eastern_bird"}],
        species_output_paths=lambda slug: {"location": root / f"{slug}.csv"},
        eastern_species_output_paths=lambda slug: {"location": root / f"{slug}.csv"},
        show_birding_opportunity_index=lambda: None,
    ):
        app.show_dashboard()


def _species_script(directory: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import app

    root = Path(directory)
    with patch.multiple(
        app,
        RUN_METADATA=root / "run.json",
        EASTERN_LOCATION_FORECAST_FILE=root / "missing_family.csv",
        ATLANTIC_LOCATION_FORECAST_FILE=root / "missing_family.csv",
        EASTERN_SPECIES_LAYERS=[{"species": "Test Bird", "slug": "test"}],
        eastern_species_output_paths=lambda slug: {"location": root / "species.csv"},
    ):
        app.show_species_explorer()


def _leaderboard_script(directory: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import app

    root = Path(directory)
    layers = [
        {"species": "Alpha", "slug": "alpha"},
        {"species": "Beta", "slug": "beta"},
        {"species": "Missing", "slug": "missing"},
    ]
    with patch.multiple(
        app,
        RUN_METADATA=root / "run.json",
        EASTERN_LOCATION_FORECAST_FILE=root / "missing_family.csv",
        ATLANTIC_LOCATION_FORECAST_FILE=root / "missing_family.csv",
        DECISION_SUPPORT_FILE=root / "support.json",
        EASTERN_SPECIES_LAYERS=layers,
        SPECIES_LAYERS=layers,
        SEABIRD_SPECIES_NAMES=["Alpha", "Beta", "Missing"],
        eastern_species_output_paths=lambda slug: {"location": root / f"{slug}_location.csv"},
        species_output_paths=lambda slug: {"location": root / f"{slug}_location.csv"},
        seabird_species_output_paths=lambda name: {
            "location": root / f"{name.lower()}_location.csv",
            "forecast": root / f"{name.lower()}_forecast.csv",
        },
        show_seabird_species_product=lambda species, support, **kwargs: None,
    ):
        app.show_species_explorer()


def _navigation_script(directory: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import streamlit as st

    import app

    with patch.multiple(
        app,
        RUN_METADATA=Path(directory) / "missing.json",
        show_dashboard=lambda: st.write("dashboard page"),
        show_rare_birds=lambda: st.write("rare birds page"),
        show_seawatching=lambda: st.write("seawatching page"),
        show_migration=lambda: st.write("migration page"),
        show_species_explorer=lambda: st.write("species explorer page"),
        show_methods=lambda: st.write("methods page"),
    ):
        app.main()


def _seawatching_script(directory: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import app

    root = Path(directory)
    with patch.multiple(
        app,
        RUN_METADATA=root / "run.json",
        DECISION_SUPPORT_FILE=root / "support.json",
        SEABIRD_SPECIES_NAMES=["Great Shearwater"],
        seabird_species_output_paths=lambda name: {
            "location": root / "location.csv",
            "forecast": root / "forecast.csv",
        },
    ):
        app.show_seawatching()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_sidebar_navigation_routes_to_each_page(tmp_path: Path) -> None:
    at = AppTest.from_function(_navigation_script, args=(str(tmp_path),)).run()
    pages = {
        "🏠 Dashboard": "dashboard page",
        "🌍 Rare Birds": "rare birds page",
        "🌊 Seawatching": "seawatching page",
        "🪿 Migration": "migration page",
        "🎯 Species Explorer": "species explorer page",
        "🧪 Methods": "methods page",
    }
    assert at.sidebar.radio[0].options == list(pages)
    for label, content in pages.items():
        at.sidebar.radio[0].set_value(label).run()
        assert not at.exception
        assert any(item.value == content for item in at.markdown)


def test_dashboard_uses_product_values_and_compares_forecast_dates(tmp_path: Path) -> None:
    _write_json(tmp_path / "run.json", {
        "forecast_start": "2026-01-01",
        "atlantic_vagrancy": {"species_layers": [
            {"species": "Atlantic Bird", "slug": "atlantic_bird", "status": "OK"},
            {"species": "Skipped Bird", "slug": "skipped_bird", "status": "NO_DATA"},
        ]},
        "eastern_hotspots": {"species_layers": [
            {"species": "Eastern Bird", "slug": "eastern_bird", "status": "OK"},
        ]},
        "goose_module": {"status": "ok"},
    })
    dates = pd.date_range("2026-01-01", periods=7)
    for name, end in (("eastern", 0.3), ("atlantic", 0.6), ("seabird", 0.15)):
        pd.DataFrame({
            "date": dates,
            "probability": [0.1] * 6 + [end],
            "risk_level": ["LOW"] * 7,
        }).to_csv(tmp_path / f"{name}.csv", index=False)
    _write_json(tmp_path / "rating.json", {"horizons": [{
        "score": 70, "rating": "Good", "date": "2026-01-01",
        "best_coast": {"coast": "North Holland"},
        "component_points": {"General Seabird Index": 20, "Sooty Shearwater": 6, "Manx Shearwater": 3},
    }]})
    _write_json(tmp_path / "goose.json", {"horizons": [{
        "date": "2026-01-01", "goose_day_rating": {"score": 30, "rating": "Fair"},
        "off_season": True,
        "target_geese": [{"species": "Snow Goose", "target_score": 2}],
    }, {
        "date": "2025-12-31", "goose_day_rating": {"score": 25, "rating": "Fair"},
    }]})
    pd.DataFrame([
        {"date": "2026-01-01", "score": 70},
        {"date": "2025-12-31", "score": 60},
    ]).to_csv(tmp_path / "rating.csv", index=False)
    _write_json(tmp_path / "support.json", {"horizons": [{
        "date": "2026-01-01", "best_dutch_locations": [{"location": "Texel"}],
    }]})
    for slug, score in (("atlantic_bird", 0.21), ("eastern_bird", 0.13), ("skipped_bird", 0.99)):
        pd.DataFrame([
            {"date": "2026-01-01", "forecast_probability": score},
            {"date": "2025-12-31", "forecast_probability": score - 0.01},
        ]).to_csv(tmp_path / f"{slug}.csv", index=False)
    _write_json(tmp_path / "boi.json", {"horizons": [{
        "date": "2026-01-01", "best_hotspots": ["Fair Isle"],
        "target_species": ["Test Bird"], "main_module": "Eastern",
    }]})
    at = AppTest.from_function(_dashboard_script, args=(str(tmp_path), True)).run()
    assert not at.exception
    metrics = {m.label: (m.value, m.delta) for m in at.metric}
    assert metrics["🌊 North Sea Vagrancy Index"][0] == "10.0%"
    assert metrics["🔥 Atlantic Vagrant Watch"] == ("21.000%", "+1.0 pp vs previous forecast day")
    assert metrics["🌊 Seawatch Day Rating"] == ("70/100", "+10.0 points vs previous forecast day")
    assert metrics["🪿 Goose Forecast"] == ("30/100", "+5.0 points vs previous forecast day")
    assert metrics["📈 Largest improving index"] == ("Atlantic", "+50.0 pp")
    assert metrics["🌊 Best seawatch location"][0] == "Texel"
    assert any("Outside the winter season" in caption.value for caption in at.caption)
    captions = [caption.value for caption in at.caption]
    assert any("Leading species: Atlantic Bird" in c for c in captions)
    assert any("Leading species layer: Eastern Bird" in c for c in captions)
    assert any("Leading species contribution: Sooty Shearwater" in c for c in captions)
    assert any("Leading rare-goose target: Snow Goose" in c for c in captions)
    assert not any("demo" in c.lower() for c in captions)


def test_dashboard_does_not_show_forecasts_without_run_metadata(tmp_path: Path) -> None:
    _write_json(tmp_path / "rating.json", {"horizons": [{"score": 99}]})
    _write_json(tmp_path / "boi.json", {"horizons": [{
        "date": "2026-01-01",
        "best_hotspots": ["Stale hotspot"],
        "target_species": ["Stale bird"],
    }]})
    at = AppTest.from_function(_dashboard_script, args=(str(tmp_path), False)).run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["🌊 Seawatch Day Rating"] == "Unavailable"
    assert metrics["🪿 Goose Forecast"] == "Unavailable"
    assert metrics["🔥 Atlantic Vagrant Watch"] == "Unavailable"
    assert metrics["⭐ Best rarity hotspot"] == "Unavailable"
    assert metrics["🎯 Most promising target"] == "Unavailable"
    assert not any(expander.label == "Birding Opportunity Index details" for expander in at.expander)


def test_dashboard_does_not_use_skipped_or_mismatched_forecasts(tmp_path: Path) -> None:
    _write_json(tmp_path / "run.json", {
        "forecast_start": "2026-01-02",
        "goose_module": {"status": "skipped"},
        "seawatch_day_rating": {"generated_at": "current"},
    })
    _write_json(tmp_path / "goose.json", {"horizons": [{
        "date": "2026-01-02", "goose_day_rating": {"score": 99, "rating": "Good"},
    }]})
    _write_json(tmp_path / "rating.json", {"generated_at": "old", "horizons": [{
        "date": "2026-01-02", "score": 99, "rating": "Good",
    }]})
    pd.DataFrame([{
        "date": "2026-01-01", "probability": 0.9, "risk_level": "HIGH",
    }]).to_csv(tmp_path / "eastern.csv", index=False)
    at = AppTest.from_function(_dashboard_script, args=(str(tmp_path), True), default_timeout=30).run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    for label in ("🌊 North Sea Vagrancy Index", "🔥 Atlantic Vagrant Watch",
                  "🌊 Seawatch Day Rating", "🪿 Goose Forecast"):
        assert metrics[label] == "Unavailable"


def test_species_explorer_uses_selected_date_and_peak_cell(tmp_path: Path) -> None:
    _write_json(tmp_path / "run.json", {})
    pd.DataFrame([
        {"date": "2026-01-01", "location": "Texel", "country": "NL", "forecast_probability": 0.2, "anomaly_score": 0.01},
        {"date": "2026-01-01", "location": "IJmuiden", "country": "NL", "forecast_probability": 0.1, "anomaly_score": 0.0},
        {"date": "2026-01-02", "location": "Texel", "country": "NL", "forecast_probability": 0.15, "anomaly_score": 0.0},
        {"date": "2026-01-02", "location": "IJmuiden", "country": "NL", "forecast_probability": 0.3, "anomaly_score": 0.02},
    ]).to_csv(tmp_path / "species.csv", index=False)
    at = AppTest.from_function(_species_script, args=(str(tmp_path),)).run()
    assert not at.exception
    assert any("highest-scoring available core Dutch locations" in m.value and "Texel and IJmuiden" in m.value for m in at.markdown)
    date_selector = next(widget for widget in at.selectbox if widget.label == "Forecast date")
    date_selector.select_index(1).run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Best cell probability"] == "30.0%"
    assert metrics["Change from previous forecast day"] == "+10.0 pp"
    assert metrics["Best region"] == "IJmuiden"
    assert metrics["Best forecast date"] == "2026-01-02"
    assert any("2026-01-02" in m.value and "IJmuiden and Texel" in m.value for m in at.markdown)
    assert any("Map coordinates are unavailable" in item.value for item in at.info)


def _write_leaderboard_data(root: Path) -> None:
    _write_json(root / "run.json", {})
    _write_json(root / "support.json", {})
    for name, first, second in (("alpha", 0.2, 0.3), ("beta", 0.4, 0.2)):
        pd.DataFrame([
            {"date": "2026-01-01", "location": "First", "country": "NL",
             "forecast_probability": first, "probability": first, "anomaly_score": 0.0},
            {"date": "2026-01-02", "location": "Later", "country": "NL",
             "forecast_probability": second, "probability": second, "anomaly_score": 0.0},
        ]).to_csv(root / f"{name}_location.csv", index=False)
        pd.DataFrame([
            {"date": "2026-01-01", "probability": first},
            {"date": "2026-01-02", "probability": second},
        ]).to_csv(root / f"{name}_forecast.csv", index=False)


def test_leaderboard_ranks_all_families_and_keeps_missing_species(tmp_path: Path) -> None:
    _write_leaderboard_data(tmp_path)
    at = AppTest.from_function(_leaderboard_script, args=(str(tmp_path),), default_timeout=30).run()
    assert at.radio[0].options == ["Eastern vagrants", "Atlantic vagrants"]
    for family in ("Eastern vagrants", "Atlantic vagrants"):
        at.radio[0].set_value(family).run()
        assert not at.exception
        board = at.dataframe[0].value
        assert board["Species"].tolist() == ["Beta", "Alpha", "Missing"]
        assert board["Forecast score"].iloc[:2].tolist() == [40.0, 20.0]
        assert board["Rank"].iloc[:2].tolist() == [1, 2]
        assert pd.isna(board["Rank"].iloc[2])
        assert board["Trend"].tolist() == [
            "🔴 Declining (-20.0 pp)", "🟢 Improving (+10.0 pp)", "⚪ Unavailable"
        ]
        assert str(board["Best date"].iloc[1]) == "2026-01-02"
        assert board["Best region"].tolist() == ["First", "First", "Unavailable"]
        assert at.selectbox[0].label == "Search species"


def test_leaderboard_row_selection_opens_species_and_search_still_works(tmp_path: Path) -> None:
    _write_leaderboard_data(tmp_path)
    at = AppTest.from_function(_leaderboard_script, args=(str(tmp_path),), default_timeout=30).run()
    assert at.selectbox[0].value == "Alpha"
    states = at._tree.get_widget_states()
    selection = states.widgets.add()
    selection.id = at.dataframe[0].proto.id
    selection.string_value = json.dumps({"selection": {"rows": [0]}})
    at._run(states)
    assert not at.exception
    assert at.selectbox[0].value == "Beta"
    assert any(metric.label == "Best cell probability" and metric.value == "40.0%" for metric in at.metric)
    at.selectbox[0].select("Alpha").run()
    assert not at.exception
    assert at.selectbox[0].value == "Alpha"
    assert any(metric.label == "Best cell probability" and metric.value == "20.0%" for metric in at.metric)
    assert at.session_state["species_leaderboard_Eastern vagrants"]["selection"]["rows"] == []
    states = at._tree.get_widget_states()
    selection = states.widgets.add()
    selection.id = at.dataframe[0].proto.id
    selection.string_value = json.dumps({"selection": {"rows": [0]}})
    at._run(states)
    assert not at.exception
    assert at.selectbox[0].value == "Beta"


def test_leaderboard_stable_and_single_day_trends(tmp_path: Path, monkeypatch) -> None:
    import app

    pd.DataFrame([
        {"date": "2026-01-01", "location": "A", "forecast_probability": 0.2},
        {"date": "2026-01-02", "location": "A", "forecast_probability": 0.2004},
    ]).to_csv(tmp_path / "stable.csv", index=False)
    pd.DataFrame([
        {"date": "2026-01-01", "location": "B", "forecast_probability": 0.1},
    ]).to_csv(tmp_path / "single.csv", index=False)
    monkeypatch.setattr(app, "eastern_species_output_paths", lambda slug: {"location": tmp_path / f"{slug}.csv"})
    board = app.species_leaderboard("Eastern vagrants", {"Stable": "stable", "Single": "single"})
    assert board["Trend"].tolist() == ["🟡 Stable", "⚪ Unavailable"]


def test_leaderboard_refreshes_when_forecast_file_changes(tmp_path: Path, monkeypatch) -> None:
    import os

    import app

    path = tmp_path / "species.csv"
    pd.DataFrame([
        {"date": "2026-01-01", "location": "A", "forecast_probability": 0.1},
    ]).to_csv(path, index=False)
    monkeypatch.setattr(app, "eastern_species_output_paths", lambda slug: {"location": path})
    assert app.species_leaderboard("Eastern vagrants", {"Bird": "bird"})["Forecast score"].iloc[0] == 10.0
    modified = path.stat().st_mtime_ns
    pd.DataFrame([
        {"date": "2026-01-01", "location": "A", "forecast_probability": 0.4},
    ]).to_csv(path, index=False)
    os.utime(path, ns=(modified + 1_000_000_000, modified + 1_000_000_000))
    assert app.species_leaderboard("Eastern vagrants", {"Bird": "bird"})["Forecast score"].iloc[0] == 40.0


def test_seabird_leaderboard_uses_national_score_with_missing_site(tmp_path: Path, monkeypatch) -> None:
    import app

    pd.DataFrame([
        {"date": "2026-01-01", "probability": 0.25},
        {"date": "2026-01-02", "probability": 0.25},
    ]).to_csv(tmp_path / "forecast.csv", index=False)
    monkeypatch.setattr(app, "seabird_species_output_paths", lambda name: {
        "forecast": tmp_path / "forecast.csv",
        "location": tmp_path / "missing.csv",
    })
    monkeypatch.setattr(app, "SEABIRD_SPECIES_NAMES", ["Bird"])
    row = app.species_leaderboard("Seabirds", {"Bird": "Bird"}).iloc[0]
    assert row["Forecast score"] == 25.0
    assert row["Trend"] == "🟡 Stable"
    assert row["Best region"] == "Unavailable"


def test_seawatching_contains_species_leaderboard_and_detailed_forecast(tmp_path: Path) -> None:
    _write_json(tmp_path / "run.json", {})
    site = {
        "rank": 1, "location": "Texel", "country": "NL", "score": 20,
        "probability": 0.1, "latitude": 53.0, "longitude": 4.8,
    }
    _write_json(tmp_path / "support.json", {"horizons": [
        {"horizon_days": horizon, "wind": {"text": "Test wind"},
         "label": str(horizon), "date": f"2026-01-{horizon:02d}", "probability": 0.2,
         "trend": {"change": None}, "status": "Good", "score": 40,
         "recommended_coast": {"coast": "Wadden", "top_site": "Texel"},
         "confidence": "High", "best_locations": [site], "best_dutch_locations": [site],
         "map_locations": [site]}
        for horizon in (1, 3, 7, 14)
    ]})
    dates = pd.date_range("2026-01-01", periods=14)
    pd.DataFrame({
        "date": dates, "probability": [0.2] * 14, "risk_level": ["LOW"] * 14,
    }).to_csv(tmp_path / "forecast.csv", index=False)
    pd.DataFrame([
        {"date": date, "location": "Texel", "country": "NL", "latitude": 53.0,
         "longitude": 4.8, "probability": 0.1, "rank": 1, "anomaly_score": 0.0}
        for date in dates
    ]).to_csv(tmp_path / "location.csv", index=False)
    at = AppTest.from_function(_seawatching_script, args=(str(tmp_path),), default_timeout=30).run()
    at.radio[0].set_value("Species & sites").run()
    assert not at.exception
    board = at.dataframe[0].value
    assert board.iloc[0]["Species"] == "Great Shearwater"
    assert board.iloc[0]["Forecast score"] == 20.0
    for species in ("Leach's Storm-petrel", "Long-tailed Skua", "Sabine's Gull"):
        assert pd.isna(board.loc[board["Species"].eq(species), "Forecast score"].iloc[0])

    states = at._tree.get_widget_states()
    selection = states.widgets.add()
    selection.id = at.dataframe[0].proto.id
    selection.string_value = json.dumps({"selection": {"rows": [0]}})
    at._run(states)
    assert not at.exception
    assert at.selectbox[0].value == "Great Shearwater"
    assert any(metric.label == "First forecast day" and metric.value == "20.0%" for metric in at.metric)
    assert sum("Dutch Birding Recommendations" in h.value for h in at.subheader) == 4
    assert len(at.get("vega_lite_chart")) > 0
    assert len(at.get("deck_gl_json_chart")) > 0
    for species in ("Leach's Storm-petrel", "Long-tailed Skua", "Sabine's Gull"):
        at.selectbox[0].select(species).run()
        assert not at.exception
        assert any("No independent species forecast" in item.value for item in at.info)
    at.selectbox[0].select("Great Shearwater").run()
    assert not at.exception
    assert any(metric.label == "First forecast day" for metric in at.metric)
