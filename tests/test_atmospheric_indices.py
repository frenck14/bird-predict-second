from __future__ import annotations

import pandas as pd
import pytest

from src.atmospheric_indices import calculate_atmospheric_indices


def _weather(direction: float = 90.0, speed_tenths: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=14)
    row = {"date": dates}
    for station in (225, 235, 242, 310):
        row[f"DDVEC_{station}"] = direction
        row[f"FG_{station}"] = speed_tenths
        row[f"PX_{station}"] = 10000.0
    return pd.DataFrame(row)


def _events() -> pd.DataFrame:
    rows = []
    for year in range(2016, 2026):
        for month in range(1, 13):
            rows.append(
                {
                    "date": pd.Timestamp(year=year, month=month, day=10),
                    "count": month,
                    "species_count": max(1, month // 2),
                }
            )
    return pd.DataFrame(rows)


@pytest.mark.parametrize(
    ("direction", "expected_family", "opposite_family"),
    [
        (90.0, "Easterly Airflow", "Westerly Transport"),
        (270.0, "Westerly Transport", "Easterly Airflow"),
    ],
)
def test_indices_are_bounded_and_component_contributions_sum(
    direction: float, expected_family: str, opposite_family: str
) -> None:
    forecasts = calculate_atmospheric_indices(_weather(direction), _events(), _events())

    assert len(forecasts) == 14
    for forecast in forecasts:
        assert 0.0 <= forecast["eastern_drift_index"] <= 100.0
        assert 0.0 <= forecast["atlantic_index"] <= 100.0
        for score_column, components_column in (
            ("eastern_drift_index", "eastern_components"),
            ("atlantic_index", "atlantic_components"),
        ):
            components = forecast[components_column]
            assert sum(component.contribution for component in components) == pytest.approx(
                forecast[score_column]
            )
            assert all(0.0 <= component.score <= 100.0 for component in components)
            assert all(
                0.0 <= signal.score <= 100.0
                for component in components
                for signal in component.signals
            )

    eastern = forecasts[0]["eastern_components"]
    atlantic = forecasts[0]["atlantic_components"]
    components = {component.name: component for component in (*eastern, *atlantic)}
    assert components[expected_family].score > components[opposite_family].score
    assert [component.name for component in eastern] == [
        "Easterly Airflow",
        "Siberian Drift Potential",
        "Continental Influx Risk",
    ]
    assert [component.name for component in atlantic] == [
        "Westerly Transport",
        "Cyclone Support",
        "Hurricane Remnant Influence",
        "Azores Arrival Signal",
    ]


def test_regional_subscores_disclose_proxy_data_limits() -> None:
    forecast = calculate_atmospheric_indices(_weather(), _events(), _events())[0]
    eastern = {
        component.name: component for component in forecast["eastern_components"]
    }
    atlantic = {
        component.name: component for component in forecast["atlantic_components"]
    }

    scandinavian = next(
        signal
        for signal in eastern["Continental Influx Risk"].signals
        if signal.name == "Scandinavian arrival reports proxy"
    )
    azores = next(
        signal
        for signal in atlantic["Azores Arrival Signal"].signals
        if signal.name == "Historical Atlantic arrival seasonality"
    )
    blocking = next(
        signal
        for signal in eastern["Siberian Drift Potential"].signals
        if signal.name == "Scandinavian blocking proxy"
    )
    assert "Scandinavian reports are not in the source data" in scandinavian.explanation
    assert "no Azores records are included" in azores.explanation
    assert "no Scandinavian pressure field is available" in blocking.explanation


def test_weather_inputs_must_contain_all_required_station_features() -> None:
    weather = _weather().drop(columns="PX_310")
    with pytest.raises(ValueError, match="PX_310"):
        calculate_atmospheric_indices(weather, _events(), _events())


def test_historical_baseline_must_include_complete_pre_forecast_years() -> None:
    events = _events().loc[lambda rows: rows["date"].dt.year.eq(2026)]
    with pytest.raises(ValueError, match="No occurrence history"):
        calculate_atmospheric_indices(_weather(), events, _events())
