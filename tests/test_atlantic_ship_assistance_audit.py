import numpy as np
import pandas as pd
import pytest

from src import atlantic_ship_assistance_audit as audit


def test_weather_score_uses_only_event_seven_day_window() -> None:
    time = pd.date_range("2020-09-25", periods=9 * 24, freq="h")
    speed = np.zeros(len(time))
    direction = np.zeros(len(time))
    pressure = np.full(len(time), 1015.0)
    after_arrival = time >= pd.Timestamp("2020-10-02")
    speed[after_arrival] = 54.0
    direction[after_arrival] = 270.0
    pressure[after_arrival] = 900.0
    point_weather = [
        {
            "hourly": {
                "time": time.astype(str).tolist(),
                "wind_speed_10m": speed.tolist(),
                "wind_direction_10m": direction.tolist(),
                "pressure_msl": pressure.tolist(),
            }
        }
        for _ in range(audit.ROUTE_SAMPLE_COUNT)
    ]

    result = audit._route_weather_metrics(
        point_weather,
        np.full(audit.ROUTE_SAMPLE_COUNT, np.pi / 2),
        pd.Timestamp("2020-10-01"),
    )

    assert result["minimum_route_pressure_hpa"] == 1015.0
    assert result["weather_support_score"] == 0.0


def test_weather_collection_batches_occurrences_by_year(monkeypatch) -> None:
    records = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2020-01-03", "2020-01-10", "2020-01-10"]
            ),
            "species": ["Blackpoll Warbler", "Blackpoll Warbler", "Ovenbird"],
            "decimalLatitude": [51.0, 51.0, 52.0],
            "decimalLongitude": [-1.0, -1.0, 0.0],
        }
    )
    calls = []

    def fake_fetch(start_date, end_date, locations):
        calls.append((start_date, end_date, locations))
        return {
            (event_date.normalize(), *location): {"weather_support_score": 0.25}
            for location, event_dates in locations.items()
            for event_date in event_dates
        }

    monkeypatch.setattr(audit, "_fetch_weather_chunk", fake_fetch)

    result = audit._collect_weather_scores(records)

    assert len(calls) == 1
    start_date, end_date, locations = calls[0]
    assert start_date == pd.Timestamp("2019-12-28")
    assert end_date == pd.Timestamp("2020-01-10")
    assert len(locations) == 2
    assert len(result) == len(records)
    assert result["weather_support_score"].eq(0.25).all()


def test_weather_fetch_splits_oversized_route_batches(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(audit, "WEATHER_CACHE_DIRECTORY", tmp_path)
    monkeypatch.setattr(audit, "WEATHER_REQUEST_SPLIT_ROUTES", 2)
    monkeypatch.setattr(audit.time, "sleep", lambda _seconds: None)
    calls = []

    def fake_get_json(_url, params):
        coordinate_count = len(params["latitude"].split(","))
        calls.append(coordinate_count)
        return [
            {
                "hourly": {
                    "time": ["2020-10-01T00:00"],
                    "wind_speed_10m": [0.0],
                    "wind_direction_10m": [0.0],
                    "pressure_msl": [1015.0],
                }
            }
            for _ in range(coordinate_count)
        ]

    monkeypatch.setattr(audit, "_get_json", fake_get_json)
    locations = {
        (52.0 + index / 100, 4.0 + index / 100): [pd.Timestamp("2020-10-01")]
        for index in range(3)
    }

    result = audit._fetch_weather_chunk(
        pd.Timestamp("2020-10-01"),
        pd.Timestamp("2020-10-01"),
        locations,
    )

    assert len(result) == 3
    assert calls == [audit.ROUTE_SAMPLE_COUNT * 2, audit.ROUTE_SAMPLE_COUNT]


def test_cache_only_weather_fetch_never_requests_or_saves_partial_cache(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(audit, "WEATHER_CACHE_DIRECTORY", tmp_path)
    monkeypatch.setattr(audit, "WEATHER_REQUEST_SPLIT_ROUTES", 1)

    def fail_if_requested(*_args, **_kwargs):
        raise AssertionError("cache-only mode must not request weather")

    monkeypatch.setattr(audit, "_get_json", fail_if_requested)
    locations = {
        (52.0 + index / 100, 4.0 + index / 100): [pd.Timestamp("2020-10-01")]
        for index in range(2)
    }

    result = audit._fetch_weather_chunk(
        pd.Timestamp("2020-10-01"),
        pd.Timestamp("2020-10-01"),
        locations,
        cache_only=True,
    )

    assert result == {}
    assert not list(tmp_path.iterdir())


def test_cache_only_weather_collection_marks_missing_scores(monkeypatch) -> None:
    records = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-03"]),
            "species": ["Blackpoll Warbler"],
            "decimalLatitude": [51.0],
            "decimalLongitude": [-1.0],
        }
    )
    calls = []

    def fake_fetch(_start_date, _end_date, _locations, *, cache_only=False):
        calls.append(cache_only)
        return {}

    monkeypatch.setattr(audit, "_fetch_weather_chunk", fake_fetch)

    result = audit._collect_weather_scores(records, cache_only=True)

    assert calls == [True]
    assert pd.isna(result.loc[0, "weather_support_score"])


def test_route_weather_scores_reward_tailwind_and_recent_low() -> None:
    time = pd.date_range("2020-10-01", periods=24, freq="h")
    point_weather = [
        {
            "hourly": {
                "time": time.astype(str).tolist(),
                "wind_speed_10m": [54.0] * 24,
                "wind_direction_10m": [270.0] * 24,
                "pressure_msl": [980.0] * 24,
            }
        }
        for _ in range(audit.ROUTE_SAMPLE_COUNT)
    ]
    bearings = np.full(audit.ROUTE_SAMPLE_COUNT, np.pi / 2)

    result = audit._route_weather_metrics(
        point_weather, bearings, pd.Timestamp("2020-10-01")
    )

    assert result["transatlantic_tailwind_corridor_present"]
    assert result["tailwind_corridor_score"] == 1.0
    assert result["mean_headwind_intensity_m_s"] == 0.0
    assert result["major_low_pressure_on_route"]
    assert result["days_before_arrival_of_min_pressure"] == 0
    assert result["weather_support_score"] == 1.0


def test_route_weather_score_is_zero_without_corridor_or_major_low() -> None:
    time = pd.date_range("2020-10-01", periods=24, freq="h")
    point_weather = [
        {
            "hourly": {
                "time": time.astype(str).tolist(),
                "wind_speed_10m": [0.0] * 24,
                "wind_direction_10m": [0.0] * 24,
                "pressure_msl": [1015.0] * 24,
            }
        }
        for _ in range(audit.ROUTE_SAMPLE_COUNT)
    ]

    result = audit._route_weather_metrics(
        point_weather,
        np.full(audit.ROUTE_SAMPLE_COUNT, np.pi / 2),
        pd.Timestamp("2020-10-01"),
    )

    assert not result["transatlantic_tailwind_corridor_present"]
    assert result["storm_track_support_score"] == 0.0
    assert result["arrival_timing_relative_to_low_score"] == 0.0
    assert result["weather_support_score"] == 0.0


def test_ship_indicator_requires_low_weather_for_possible_ship_flag() -> None:
    frame = pd.DataFrame(
        {
            "weather_support_score": [0.1, 0.8],
            "nearest_requested_harbour_distance_km": [1.0, 1.0],
            "species_ship_assistance_input": [0.5, 0.5],
            "arrival_isolation_score": [1.0, 1.0],
            "outside_observed_common_season": [True, True],
            "distance_to_emodnet_route_cell_km": [0.0, 0.0],
            "distance_to_container_port_km": [0.0, 0.0],
        }
    )

    scored = audit._score_ship_assistance(frame)

    assert scored.loc[0, "preliminary_interpretation"] == "possible_ship_assisted"
    assert scored.loc[1, "preliminary_interpretation"] == "weather_supported"
    assert scored["possible_ship_assistance_score"].between(0.0, 1.0).all()


def test_deduplicate_ship_assistance_events_merges_blackpoll_observations() -> None:
    observations = pd.DataFrame(
        {
            "key": range(1, 10),
            "species": ["Blackpoll Warbler"] * 9,
            "date": ["2020-10-27"] * 9,
            "decimalLatitude": [53.151] * 9,
            "decimalLongitude": [4.849] * 9,
            "location": ["53.15100, 4.84900"] * 9,
            "countryCode": ["NL"] * 9,
            "weather_support_score": [0.2 + index / 100 for index in range(9)],
            "possible_ship_assistance_score": [0.4 + index / 100 for index in range(9)],
            "tailwind_corridor_score": [0.3] * 9,
            "storm_track_support_score": [0.5] * 9,
            "distance_to_container_port_km": list(range(9)),
            "preliminary_interpretation": ["ambiguous"] * 9,
        }
    )

    events = audit.deduplicate_ship_assistance_events(observations)

    assert len(events) == 1
    event = events.iloc[0]
    assert event["event_id"] == "Blackpoll Warbler|2020-10-27|53.15|4.85"
    assert event["species"] == "Blackpoll Warbler"
    assert event["date"] == pd.Timestamp("2020-10-27")
    assert event["decimalLatitude"] == 53.15
    assert event["decimalLongitude"] == 4.85
    assert event["observation_count"] == 9
    assert event["weather_support_score"] == observations[
        "weather_support_score"
    ].mean()
    assert event["distance_to_container_port_km"] == 4.0
    assert len(audit.deduplicate_ship_assistance_events(events)) == 1
    assert audit.deduplicate_ship_assistance_events(events).loc[
        0, "observation_count"
    ] == 9


def test_run_audit_omits_records_before_weather_archive(monkeypatch) -> None:
    records = pd.DataFrame(
        {
            "key": [1, 2],
            "date": ["1939-10-01", "2020-10-01"],
            "species": ["Red-eyed Vireo", "Red-eyed Vireo"],
            "countryCode": ["GB", "GB"],
            "decimalLatitude": [52.0, 52.0],
            "decimalLongitude": [1.0, 1.0],
        }
    )
    monkeypatch.setattr(
        audit,
        "_collect_weather_scores",
        lambda frame: pd.DataFrame(
            {
                "transatlantic_tailwind_corridor_present": [False] * len(frame),
                "tailwind_corridor_fraction": [0.0] * len(frame),
                "tailwind_corridor_score": [0.0] * len(frame),
                "mean_headwind_intensity_m_s": [0.0] * len(frame),
                "minimum_route_pressure_hpa": [1015.0] * len(frame),
                "major_low_pressure_on_route": [False] * len(frame),
                "days_before_arrival_of_min_pressure": [0] * len(frame),
                "storm_track_support_score": [0.0] * len(frame),
                "arrival_timing_relative_to_low_score": [0.0] * len(frame),
                "weather_support_score": [0.0] * len(frame),
            },
            index=frame.index,
        ),
    )
    monkeypatch.setattr(
        audit,
        "_arrival_context",
        lambda frame: pd.DataFrame(
            {
                "simultaneous_species_within_100km": [1] * len(frame),
                "arrival_isolation_score": [1.0] * len(frame),
                "species_observed_common_months": ["10"] * len(frame),
                "outside_observed_common_season": [False] * len(frame),
            },
            index=frame.index,
        ),
    )
    monkeypatch.setattr(
        audit,
        "_fetch_feature_collection",
        lambda *_args, **_kwargs: [
            {
                "geometry": {"coordinates": [5.0, 52.0]},
                "properties": {"portname": "Test Port"},
            }
        ],
    )
    monkeypatch.setattr(
        audit,
        "_route_density_distance",
        lambda frame: np.ones(len(frame)),
    )

    result = audit.run_audit(records)

    assert len(result) == 1
    assert result.loc[0, "date"] == pd.Timestamp("2020-10-01")
    assert result.loc[0, "observation_count"] == 1


def test_arrival_context_counts_nearby_simultaneous_species() -> None:
    records = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-10-01", "2020-10-01", "2020-10-01"]),
            "species": ["Blackpoll Warbler", "Red-eyed Vireo", "Ovenbird"],
            "decimalLatitude": [51.0, 51.1, 56.0],
            "decimalLongitude": [-1.0, -1.0, 0.0],
        }
    )

    result = audit._arrival_context(records)

    assert result.loc[0, "simultaneous_species_within_100km"] == 2
    assert result.loc[0, "arrival_isolation_score"] == 0.5
    assert result.loc[2, "simultaneous_species_within_100km"] == 1
    assert result.loc[2, "arrival_isolation_score"] == 1.0


def test_registry_coverage_includes_absent_and_unsupported_species() -> None:
    species = [str(item["species"]) for item in audit.ATLANTIC_VAGRANCY_SPECIES]
    records = pd.DataFrame(
        {"species": [species[0], species[1]], "date": ["2020-01-01", "1939-01-01"]}
    )
    events = pd.DataFrame({"species": [species[0]]})

    coverage = audit._species_coverage(records, events).set_index("species")

    assert len(coverage) == len(audit.ATLANTIC_VAGRANCY_SPECIES)
    assert coverage.loc[species[0], "status"] == "processed"
    assert coverage.loc[species[1], "status"] == "skipped"
    assert "ERA5" in coverage.loc[species[1], "reason"]
    assert coverage.loc[species[2], "status"] == "no events"


def test_registry_coverage_rejects_missing_eligible_species() -> None:
    species = str(audit.ATLANTIC_VAGRANCY_SPECIES[-1]["species"])
    records = pd.DataFrame({"species": [species], "date": ["2020-01-01"]})

    with pytest.raises(ValueError, match="Eligible species missing"):
        audit._species_coverage(records, pd.DataFrame({"species": []}))


def test_registry_coverage_reports_cache_exclusions() -> None:
    species = str(audit.ATLANTIC_VAGRANCY_SPECIES[-1]["species"])
    records = pd.DataFrame({"species": [species, species], "date": ["2020-01-01"] * 2})
    events = pd.DataFrame({"species": [species]})

    coverage = audit._species_coverage(
        records,
        events,
        {species: 1},
        allow_incomplete=True,
    ).set_index("species")

    assert coverage.loc[species, "status"] == "partially processed"
    assert coverage.loc[species, "excluded_observations"] == 1
    assert "missing from the local cache" in coverage.loc[species, "reason"]


def test_weather_summary_counts_events_not_observations_and_includes_registry() -> None:
    species = str(audit.ATLANTIC_VAGRANCY_SPECIES[-1]["species"])
    observations = pd.DataFrame(
        {
            "species": [species] * 3,
            "date": ["2020-10-01", "2020-10-01", "2020-10-02"],
            "decimalLatitude": [52.0] * 3,
            "decimalLongitude": [4.0] * 3,
            "weather_support_score": [0.8, 0.8, 0.2],
            "possible_ship_assistance_score": [0.4, 0.4, 0.8],
            "tailwind_corridor_score": [0.6, 0.6, 0.2],
            "storm_track_support_score": [0.4, 0.4, 0.2],
        }
    )
    events = audit.deduplicate_ship_assistance_events(observations)

    metrics = audit._species_weather_support(events).set_index("species")

    assert len(metrics) == len(audit.ATLANTIC_VAGRANCY_SPECIES)
    assert metrics.loc[species, "event_count"] == 2
    assert metrics.loc[species, "observation_count"] == 3
    assert metrics.loc[species, "natural_arrival_index"] == 0.5
    assert np.isclose(metrics.loc[species, "ship_assistance_index"], 0.6)
    assert metrics.loc[species, "weather_supported_pct"] == 50
    assert metrics.loc[species, "possible_ship_assisted_pct"] == 50
    absent = str(audit.ATLANTIC_VAGRANCY_SPECIES[0]["species"])
    assert metrics.loc[absent, "event_count"] == 0
    assert pd.isna(metrics.loc[absent, "natural_arrival_index"])


def test_main_writes_registry_wide_reports(monkeypatch, tmp_path) -> None:
    species = str(audit.ATLANTIC_VAGRANCY_SPECIES[-1]["species"])
    records = pd.DataFrame({"species": [species], "date": ["2020-10-01"]})
    events = audit.deduplicate_ship_assistance_events(
        pd.DataFrame(
            {
                "species": [species],
                "date": ["2020-10-01"],
                "decimalLatitude": [52.0],
                "decimalLongitude": [4.0],
                "countryCode": ["NL"],
                "country": ["Netherlands"],
                "location": ["52, 4"],
                "weather_support_score": [0.2],
                "possible_ship_assistance_score": [0.8],
                "tailwind_corridor_score": [0.2],
                "storm_track_support_score": [0.3],
                "nearest_requested_harbour": ["Rotterdam"],
                "nearest_requested_harbour_distance_km": [10.0],
                "distance_to_emodnet_route_cell_km": [2.0],
            }
        )
    )
    monkeypatch.setattr(audit, "load_all_occurrences", lambda registry: records)
    monkeypatch.setattr(audit, "run_audit", lambda input_records: events)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "OUTPUT_DIRECTORY", tmp_path)
    for constant, filename in (
        ("AUDIT_OUTPUT", "ship_assistance_audit.csv"),
        ("EVENTS_OUTPUT", "ship_assistance_events.csv"),
        ("SUMMARY_OUTPUT", "ship_assistance_summary.md"),
        ("WEATHER_SUPPORT_OUTPUT", "species_weather_support.csv"),
        ("WEATHER_SUPPORT_SUMMARY_OUTPUT", "species_weather_support.md"),
        ("COVERAGE_OUTPUT", "ship_assistance_species_coverage.csv"),
    ):
        monkeypatch.setattr(audit, constant, tmp_path / filename)

    audit.main()

    metrics = pd.read_csv(tmp_path / "species_weather_support.csv")
    assert set(metrics["species"]) == {
        str(item["species"]) for item in audit.ATLANTIC_VAGRANCY_SPECIES
    }
    assert len(pd.read_csv(tmp_path / "ship_assistance_events.csv")) == 1
    summary = (tmp_path / "ship_assistance_summary.md").read_text()
    assert (
        f"Registry species processed: **{len(audit.ATLANTIC_VAGRANCY_SPECIES)}**; "
        "with events: **1**"
    ) in summary
    assert (tmp_path / "ship_assistance_audit.csv").is_file()
    assert (tmp_path / "species_weather_support.md").is_file()
