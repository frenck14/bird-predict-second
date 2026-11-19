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
        show_ship_assistance_audit=lambda: st.write("ship assistance audit page"),
        show_methods=lambda: st.write("methods page"),
    ):
        app.main()


def _methods_script() -> None:
    from pathlib import Path
    from unittest.mock import patch

    import streamlit as st

    import app

    with patch.multiple(
        app,
        show_validation_dashboard=lambda: st.write("validation overview"),
        show_validation_insights=lambda: st.write("validation insights"),
        show_validation_benchmarks=lambda: st.write("validation benchmarks"),
        REPORT_FILE=Path("missing-report.md"),
    ):
        app.show_methods()


def _ship_assistance_script(directory: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import app

    root = Path(directory)
    with patch.multiple(
        app,
        SHIP_ASSISTANCE_AUDIT_FILE=root / "audit.csv",
        SHIP_ASSISTANCE_SUMMARY_FILE=root / "summary.md",
    ):
        app.show_ship_assistance_audit()


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


def _rare_birds_script() -> None:
    from unittest.mock import patch

    import streamlit as st

    import app

    with patch.multiple(
        app,
        forecast_ready=lambda: True,
        forecast_panel=lambda title, *_: st.write(title),
        show_species_leaderboard=lambda *_: st.write("Atlantic species ranking"),
        show_eastern_target_species=lambda: st.write("Eastern species ranking"),
        show_next_dutch_firsts=lambda: st.write("Next Dutch Firsts view"),
        show_rare_hotspot_sites=lambda *_: st.write("Requested site outlook"),
        show_atlantic_location_forecasts=lambda: st.write("Atlantic hotspot map"),
        show_eastern_hotspots=lambda: st.write("Eastern hotspot map"),
    ):
        app.show_rare_birds()


def _rare_hotspot_sites_script(path: str) -> None:
    from pathlib import Path

    import app

    app.show_rare_hotspot_sites(
        Path(path),
        ("Texel", "Maasvlakte", "IJmuiden"),
    )


def _atmospheric_index_script(directory: str, family: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import app

    root = Path(directory)
    with patch.multiple(
        app,
        WEATHER_FORECAST_FILE=root / "weather.csv",
        EASTERN_EVENTS_FILE=root / "eastern_events.csv",
        ATLANTIC_EVENTS_FILE=root / "atlantic_events.csv",
    ):
        app.show_atmospheric_index(family)


def _prediction_status_script() -> None:
    import app

    app.show_prediction_status("Hotspot Prediction Model", "Low")


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_sidebar_navigation_routes_to_each_page(tmp_path: Path) -> None:
    at = AppTest.from_function(
        _navigation_script, args=(str(tmp_path),), default_timeout=30
    ).run()
    pages = {
        "🏠 Dashboard": "dashboard page",
        "🌍 Rare Birds": "rare birds page",
        "🌊 Seawatching": "seawatching page",
        "🦆 Migration": "migration page",
        "🎯 Species Explorer": "species explorer page",
        "🛳 Ship Assistance Audit": "ship assistance audit page",
        "🔬 Methods": "methods page",
    }
    assert at.sidebar.radio[0].options == list(pages)
    options = at.sidebar.radio[0].options
    assert options.count("Ship Assistance Audit 🇳🇱") == 0
    for label, content in pages.items():
        at.sidebar.radio[0].set_value(label).run()
        assert not at.exception
        assert any(item.value == content for item in at.markdown)


def test_methods_groups_validation_content_in_nested_tabs() -> None:
    at = AppTest.from_function(_methods_script, default_timeout=30).run()

    assert not at.exception
    assert [tab.label for tab in at.tabs] == [
        "Forecasting",
        "Validation",
        "Overview",
        "Insights",
        "Benchmarks",
        "Data Sources",
    ]
    assert any(item.value == "validation overview" for item in at.markdown)
    assert any(item.value == "validation insights" for item in at.markdown)
    assert any(item.value == "validation benchmarks" for item in at.markdown)


def test_ship_assistance_page_uses_saved_event_audit(tmp_path: Path) -> None:
    pd.DataFrame(
        [
            {
                "key": 1,
                "species": "Red-eyed Vireo",
                "date": "2026-01-01",
                "country": "Netherlands",
                "countryCode": "NL",
                "location": "52, 5",
                "decimalLatitude": 52.0,
                "decimalLongitude": 5.0,
                "weather_support_score": 0.2,
                "possible_ship_assistance_score": 0.7,
                "nearest_requested_harbour": "IJmuiden",
                "nearest_requested_harbour_distance_km": 5.0,
                "distance_to_emodnet_route_cell_km": 1.0,
                "preliminary_interpretation": "possible_ship_assisted",
            },
            {
                "key": 2,
                "species": "Red-eyed Vireo",
                "date": "2026-01-01",
                "country": "Netherlands",
                "countryCode": "NL",
                "location": "52.001, 5.001",
                "decimalLatitude": 52.001,
                "decimalLongitude": 5.001,
                "weather_support_score": 0.6,
                "possible_ship_assistance_score": 0.5,
                "nearest_requested_harbour": "IJmuiden",
                "nearest_requested_harbour_distance_km": 7.0,
                "distance_to_emodnet_route_cell_km": 3.0,
                "preliminary_interpretation": "weather_supported",
            },
            {
                "key": 3,
                "species": "Blackpoll Warbler",
                "date": "2026-01-02",
                "country": "Belgium",
                "countryCode": "BE",
                "location": "51, 3",
                "decimalLatitude": 51.0,
                "decimalLongitude": 3.0,
                "weather_support_score": 0.8,
                "possible_ship_assistance_score": 0.3,
                "nearest_requested_harbour": "Zeebrugge",
                "nearest_requested_harbour_distance_km": 8.0,
                "distance_to_emodnet_route_cell_km": 2.0,
                "preliminary_interpretation": "weather_supported",
            },
        ]
    ).to_csv(tmp_path / "audit.csv", index=False)

    at = AppTest.from_function(
        _ship_assistance_script, args=(str(tmp_path),), default_timeout=30
    ).run()

    assert not at.exception
    assert [metric.value for metric in at.metric[:4]] == [
        "Netherlands",
        "2",
        "1",
        "1",
    ]
    assert at.selectbox[0].value == "Netherlands"
    at.selectbox[0].set_value("Atlantic (all records)").run()
    assert [metric.value for metric in at.metric[:4]] == [
        "Atlantic (all records)",
        "3",
        "2",
        "2",
    ]
    assert [tab.label for tab in at.tabs] == [
        "Species Ranking",
        "Recent Atlantic Events",
        "Top Ship Assistance Candidates",
        "Species Profile",
        "Map",
        "🌍 Ship Assistance by Region",
    ]
    assert at.number_input[0].value == 10
    at.number_input[0].set_value(1).run()
    ranking = at.dataframe[0].value
    assert "Possible Ship Assistance %" in ranking.columns
    assert "Ship Assisted %" not in ranking.columns
    assert ranking["Species"].tolist() == ["Red-eyed Vireo", "Blackpoll Warbler"]
    assert ranking["Event Count"].tolist() == [1, 1]
    assert ranking["Observation Count"].tolist() == [2, 1]
    assert ranking["Natural Arrival Index"].iloc[0] == 0.4
    assert ranking["Ship Assistance Index"].iloc[0] == 0.6
    latest = at.dataframe[1].value
    assert len(latest) == 2
    assert latest["species"].tolist() == ["Blackpoll Warbler", "Red-eyed Vireo"]
    assert latest["country"].tolist() == ["Belgium", "Netherlands"]
    assert latest["locality"].tolist() == ["51, 3", "52, 5"]
    assert latest["observation_count"].tolist() == [1, 2]
    candidates = at.dataframe[2].value
    assert len(candidates) == 2
    assert candidates["species"].tolist() == ["Red-eyed Vireo", "Blackpoll Warbler"]
    assert candidates["country"].tolist() == ["Netherlands", "Belgium"]
    assert candidates["locality"].tolist() == ["52, 5", "51, 3"]
    assert candidates["classification"].tolist() == ["Ambiguous", "Weather-supported"]
    import app

    comparison = app._ship_assistance_region_comparison(
        pd.read_csv(tmp_path / "audit.csv")
    )
    assert comparison.columns.tolist() == [
        "Region",
        "Observations",
        "Events",
        "Species",
        "Weather Supported %",
        "Possible Ship Assistance %",
        "Mean Natural Arrival Index",
        "Mean Ship Assistance Index",
    ]
    assert comparison["Possible Ship Assistance %"].dropna().is_monotonic_decreasing
    comparison_by_region = comparison.set_index("Region")
    assert comparison_by_region.loc["Belgium", "Observations"] == 1
    assert comparison_by_region.loc["Netherlands + Belgium", "Observations"] == 3


def test_ship_assistance_page_handles_missing_outputs(tmp_path: Path) -> None:
    at = AppTest.from_function(
        _ship_assistance_script, args=(str(tmp_path),), default_timeout=30
    ).run()

    assert not at.exception
    assert any("No ship-assistance audit data is available" in item.value for item in at.info)


def test_ship_assistance_page_filters_each_selected_region(
    tmp_path: Path,
) -> None:
    pd.DataFrame(
        [
            {
                "species": "Red-eyed Vireo",
                "date": "2026-01-03",
                "countryCode": "NL",
                "location": "Texel",
                "decimalLatitude": 53.15,
                "decimalLongitude": 4.85,
                "weather_support_score": 0.30,
                "possible_ship_assistance_score": 0.75,
                "preliminary_interpretation": "possible_ship_assisted",
            },
            {
                "species": "Red-eyed Vireo",
                "date": "2026-01-03",
                "countryCode": "NL",
                "location": "Texel duplicate observer",
                "decimalLatitude": 53.151,
                "decimalLongitude": 4.849,
                "weather_support_score": 0.50,
                "possible_ship_assistance_score": 0.55,
                "preliminary_interpretation": "ambiguous",
            },
            {
                "species": "Blackpoll Warbler",
                "date": "2026-01-02",
                "countryCode": "NL",
                "location": "IJmuiden",
                "decimalLatitude": 52.46,
                "decimalLongitude": 4.58,
                "weather_support_score": 0.65,
                "possible_ship_assistance_score": 0.25,
                "preliminary_interpretation": "weather_supported",
            },
            {
                "species": "Red-eyed Vireo",
                "date": "2026-01-01",
                "countryCode": "NL",
                "location": "Maasvlakte",
                "decimalLatitude": 51.95,
                "decimalLongitude": 4.02,
                "weather_support_score": 0.40,
                "possible_ship_assistance_score": 0.45,
                "preliminary_interpretation": "ambiguous",
            },
            {
                "species": "Blackpoll Warbler",
                "date": "2026-01-04",
                "countryCode": "BE",
                "location": "Zeebrugge",
                "decimalLatitude": 51.36,
                "decimalLongitude": 3.19,
                "weather_support_score": 0.95,
                "possible_ship_assistance_score": 0.05,
                "preliminary_interpretation": "weather_supported",
            },
            {
                "species": "Red-eyed Vireo",
                "date": "2026-01-05",
                "countryCode": "GB",
                "location": "Scilly",
                "decimalLatitude": 49.9,
                "decimalLongitude": -6.3,
                "weather_support_score": 0.35,
                "possible_ship_assistance_score": 0.65,
                "preliminary_interpretation": "possible_ship_assisted",
            },
            {
                "species": "Red-eyed Vireo",
                "date": "2026-01-06",
                "countryCode": "IE",
                "location": "Cork",
                "decimalLatitude": 51.9,
                "decimalLongitude": -8.5,
                "weather_support_score": 0.45,
                "possible_ship_assistance_score": 0.55,
                "preliminary_interpretation": "ambiguous",
            },
            {
                "species": "Red-eyed Vireo",
                "date": "2026-01-07",
                "countryCode": "IS",
                "location": "Reykjavik",
                "decimalLatitude": 64.1,
                "decimalLongitude": -21.9,
                "weather_support_score": 0.55,
                "possible_ship_assistance_score": 0.45,
                "preliminary_interpretation": "weather_supported",
            },
        ]
    ).to_csv(tmp_path / "audit.csv", index=False)
    at = AppTest.from_function(
        _ship_assistance_script, args=(str(tmp_path),), default_timeout=30
    ).run()

    assert not at.exception
    assert at.title[0].value == "🛳 Ship Assistance Audit"
    assert at.selectbox[0].options == [
        "Netherlands",
        "Netherlands + Belgium",
        "Belgium",
        "Atlantic (all records)",
        "UK",
        "Ireland",
        "Iceland",
    ]
    assert at.selectbox[0].value == "Netherlands"
    assert [metric.value for metric in at.metric[:4]] == [
        "Netherlands",
        "4",
        "3",
        "2",
    ]
    assert [tab.label for tab in at.tabs] == [
        "Species Ranking",
        "Recent Atlantic Events",
        "Top Ship Assistance Candidates",
        "Species Profile",
        "Map",
        "🌍 Ship Assistance by Region",
    ]
    assert at.selectbox[1].value == "Ship Assistance Index"
    assert at.number_input[0].value == 10
    at.number_input[0].set_value(1).run()
    ranking = at.dataframe[0].value
    assert ranking["Species"].tolist() == ["Red-eyed Vireo", "Blackpoll Warbler"]
    assert ranking["Event Count"].tolist() == [2, 1]
    assert ranking["Observation Count"].tolist() == [3, 1]
    assert ranking["Rank"].tolist() == [1, 2]
    assert ranking["Natural Arrival Index"].round(3).tolist() == [0.4, 0.65]
    assert ranking["Ship Assistance Index"].round(3).tolist() == [0.55, 0.25]
    at.selectbox[1].set_value("Natural Arrival Index").run()
    assert at.dataframe[0].value["Species"].tolist() == [
        "Blackpoll Warbler",
        "Red-eyed Vireo",
    ]
    at.selectbox[1].set_value("Ship Assistance Index").run()
    latest = at.dataframe[1].value
    assert latest["locality"].tolist() == [
        "Texel",
        "IJmuiden",
        "Maasvlakte",
    ]
    assert latest.columns.tolist() == [
        "date",
        "species",
        "country",
        "locality",
        "observation_count",
        "weather support score",
        "ship assistance score",
        "classification",
    ]
    assert latest["observation_count"].tolist() == [2, 1, 1]
    assert set(latest["country"]) == {"Netherlands"}
    assert set(at.dataframe[2].value["country"]) == {"Netherlands"}
    assert latest["classification"].tolist() == ["Ambiguous", "Weather-supported", "Ambiguous"]
    assert len(at.dataframe[2].value) == 3

    at.selectbox[0].set_value("Belgium").run()
    assert [metric.value for metric in at.metric[:4]] == ["Belgium", "1", "1", "1"]
    at.number_input[0].set_value(1).run()
    assert at.dataframe[0].value["Species"].tolist() == ["Blackpoll Warbler"]
    assert set(at.dataframe[1].value["country"]) == {"Belgium"}

    at.selectbox[0].set_value("Netherlands + Belgium").run()
    assert [metric.value for metric in at.metric[:4]] == [
        "Netherlands + Belgium",
        "5",
        "4",
        "2",
    ]
    assert set(at.dataframe[1].value["country"]) == {"Netherlands", "Belgium"}
    import app

    comparison = app._ship_assistance_region_comparison(
        pd.read_csv(tmp_path / "audit.csv")
    ).set_index("Region")
    low_countries = comparison.loc["Netherlands + Belgium"]
    netherlands = comparison.loc["Netherlands"]
    belgium = comparison.loc["Belgium"]
    assert low_countries["Observations"] >= netherlands["Observations"]
    assert low_countries["Observations"] >= belgium["Observations"]

    at.number_input[0].set_value(2).run()
    assert at.dataframe[0].value["Species"].tolist() == [
        "Red-eyed Vireo",
        "Blackpoll Warbler",
    ]
    at.number_input[0].set_value(1)
    at.text_input[0].set_value("blackpoll").run()
    assert at.dataframe[0].value["Species"].tolist() == ["Blackpoll Warbler"]

    at.selectbox[0].set_value("Atlantic (all records)").run()
    assert [metric.value for metric in at.metric[:4]] == [
        "Atlantic (all records)",
        "8",
        "7",
        "2",
    ]
    assert len(at.dataframe[1].value) == 7
    assert set(at.dataframe[1].value["country"]) == {
        "Netherlands",
        "Belgium",
        "United Kingdom",
        "Ireland",
        "IS",
    }

    for region, expected_country in [
        ("UK", "United Kingdom"),
        ("Ireland", "Ireland"),
        ("Iceland", "IS"),
    ]:
        at.selectbox[0].set_value(region).run()
        assert [metric.value for metric in at.metric[:4]] == [
            region,
            "1",
            "1",
            "1",
        ]
        assert set(at.dataframe[1].value["country"]) == {expected_country}


def test_ship_assistance_map_has_one_marker_per_event() -> None:
    import app
    from src.atlantic_ship_assistance_audit import deduplicate_ship_assistance_events

    observations = pd.DataFrame(
        [
            {
                "species": "Blackpoll Warbler",
                "date": "2020-10-27",
                "decimalLatitude": 53.151,
                "decimalLongitude": 4.849,
                "weather_support_score": 0.4,
                "possible_ship_assistance_score": 0.5,
                "preliminary_interpretation": "ambiguous",
            }
            for _ in range(3)
        ]
    )
    events = deduplicate_ship_assistance_events(observations)

    deck = app._ship_assistance_map(events)

    assert len(deck.layers) == 1
    assert deck.layers[0].type == "ScatterplotLayer"
    assert len(deck.layers[0].data) == 1
    marker = deck.layers[0].data[0]
    assert marker["event_id"] == "Blackpoll Warbler|2020-10-27|53.15|4.85"
    assert marker["observation_count"] == 3
    assert marker["marker_color"] == [242, 193, 24, 220]
    assert {key for key in marker if "polygon" in key or "geometry" in key} == set()
    assert "Country: {country}" in deck._tooltip["html"]
    assert "Locality: {locality}" in deck._tooltip["html"]
    assert "Weather support score: {weather_support_score}" in deck._tooltip["html"]
    assert (
        "Possible ship assistance score: {possible_ship_assistance_score}"
        in deck._tooltip["html"]
    )


def test_dutch_ship_assistance_events_filter_before_deduplication() -> None:
    import app

    observations = pd.DataFrame(
        [
            {
                "species": "Red-eyed Vireo",
                "date": "2020-10-27",
                "countryCode": "NL",
                "location": "Dutch coast",
                "decimalLatitude": 51.361,
                "decimalLongitude": 3.191,
                "weather_support_score": 0.4,
                "possible_ship_assistance_score": 0.5,
                "preliminary_interpretation": "ambiguous",
            },
            {
                "species": "Red-eyed Vireo",
                "date": "2020-10-27",
                "countryCode": "BE",
                "location": "Zeebrugge",
                "decimalLatitude": 51.359,
                "decimalLongitude": 3.189,
                "weather_support_score": 0.4,
                "possible_ship_assistance_score": 0.5,
                "preliminary_interpretation": "ambiguous",
            },
        ]
    )

    events = app._ship_assistance_events(observations, {"NL"})

    assert len(events) == 1
    assert events["countryCode"].eq("NL").all()
    assert events["observation_count"].tolist() == [1]
    assert events["country"].tolist() == ["Netherlands"]
    assert events["classification"].tolist() == ["Ambiguous"]


def test_rare_birds_has_nested_views_for_all_three_sections() -> None:
    at = AppTest.from_function(_rare_birds_script).run()
    assert not at.exception
    assert at.radio[0].options == ["Atmospheric Indices", "Forecasts", "Hotspots"]
    assert at.segmented_control[0].options == [
        "Atlantic Index",
        "Eastern Drift Index",
        "Blocking Index",
    ]

    at.segmented_control[0].set_value("🧭 Blocking Index").run()
    assert not at.exception
    assert any("Scandinavian pressure field" in item.value for item in at.info)
    assert any("Forecast Model" in item.value for item in at.markdown)
    assert any("Confidence: Experimental" in item.value for item in at.markdown)

    at.radio[0].set_value("Forecasts").run()
    assert not at.exception
    assert at.segmented_control[0].options == [
        "Atlantic Vagrant Watch",
        "Eastern Vagrant Watch",
        "Next Dutch Firsts",
    ]
    at.segmented_control[0].set_value("🌏 Eastern Vagrant Watch").run()
    assert not at.exception
    assert any("Finland, Sweden" in item.value for item in at.info)
    assert any(item.value == "Eastern species ranking" for item in at.markdown)
    assert any("Confidence: Medium" in item.value for item in at.markdown)

    at.segmented_control[0].set_value("⭐ Next Dutch Firsts").run()
    assert not at.exception
    assert any(item.value == "Next Dutch Firsts view" for item in at.markdown)

    at.radio[0].set_value("Hotspots").run()
    assert not at.exception
    assert at.segmented_control[0].options == [
        "Atlantic Hotspots",
        "Eastern Hotspots",
    ]
    at.segmented_control[0].set_value("🌏 Eastern Hotspots").run()
    assert not at.exception
    assert any(item.value == "Requested site outlook" for item in at.markdown)
    assert any(item.value == "Eastern hotspot map" for item in at.markdown)
    assert any("Hotspot Prediction Model" in item.value for item in at.markdown)
    assert any("Confidence: Low" in item.value for item in at.markdown)


def test_prediction_status_shows_category_description_and_confidence() -> None:
    at = AppTest.from_function(_prediction_status_script).run()
    assert not at.exception
    status = at.markdown[0].value
    assert "📍 Hotspot Prediction Model" in status
    assert "Confidence: Low" in status
    assert "Forecasts where rarity arrivals are most likely." in status


def test_rare_hotspot_site_table_shows_requested_horizons_and_missing_sites(
    tmp_path: Path,
) -> None:
    dates = pd.date_range("2026-01-01", periods=14)
    pd.DataFrame(
        [
            {"date": date, "location": "Texel", "forecast_probability": 0.2}
            for date in dates
        ]
        + [
            {"date": date, "location": "Maasvlakte", "forecast_probability": 0.1}
            for date in dates
        ]
    ).to_csv(tmp_path / "locations.csv", index=False)
    at = AppTest.from_function(
        _rare_hotspot_sites_script, args=(str(tmp_path / "locations.csv"),)
    ).run()
    assert not at.exception
    table = at.dataframe[0].value
    assert table["Site"].tolist() == ["Texel", "Maasvlakte", "IJmuiden"]
    assert table.iloc[0, 1:].tolist() == ["20.0%", "20.0%", "20.0%", "20.0%"]
    assert table.iloc[2, 1:].tolist() == ["Unavailable"] * 4


def test_atmospheric_index_ui_displays_composite_component_and_signal_scores(
    tmp_path: Path,
) -> None:
    dates = pd.date_range("2026-01-01", periods=14)
    weather_rows = []
    for date in dates:
        for station in (225, 235, 242, 310):
            weather_rows.append(
                {
                    "date": date,
                    "station_id": station,
                    "DDVEC": 90,
                    "FG": 100,
                    "FHX": 150,
                    "TG": 50,
                    "TN": 20,
                    "TX": 80,
                    "RH": 0,
                    "PX": 10000,
                }
            )
    pd.DataFrame(weather_rows).to_csv(tmp_path / "weather.csv", index=False)
    events = pd.DataFrame(
        [
            {"date": pd.Timestamp(year, month, 10), "count": month, "species_count": 1}
            for year in range(2016, 2026)
            for month in range(1, 13)
        ]
    )
    events.to_csv(tmp_path / "eastern_events.csv", index=False)
    events.to_csv(tmp_path / "atlantic_events.csv", index=False)

    at = AppTest.from_function(
        _atmospheric_index_script,
        args=(str(tmp_path), "Eastern"),
        default_timeout=30,
    ).run()
    assert not at.exception
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Eastern Drift Index · 01 Jan"] != "Unavailable"
    assert metrics["Component score"] != "0/100"
    assert "Contribution to index" in metrics
    assert len(at.dataframe) == 3
    assert set(at.dataframe[0].value["Driver"]) == {
        "Wind direction",
        "Wind speed",
        "Persistence",
        "Transport connectivity",
    }


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
