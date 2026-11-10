from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import app


def _show_firsts(path: str) -> None:
    from pathlib import Path
    from unittest.mock import patch

    import app

    with patch.object(app, "NEXT_DUTCH_FIRSTS_PROBABILITIES", Path(path)):
        app.show_next_dutch_firsts()


def _probabilities(path: Path) -> None:
    now = datetime.now(timezone.utc)
    date = (now.date() + timedelta(days=1)).isoformat()
    rows = [
        ("Alpha", "2%", "30%", "80%", 12, 80, 19.5, "available", now.isoformat(), date),
        ("Beta", "20%", "10%", "70%", 22, 50, 22, "available", now.isoformat(), date),
        ("Gamma", "10%", "20%", "40%", 15, 50, 15, "available", (now - timedelta(hours=49)).isoformat(), date),
    ]
    pd.DataFrame(rows, columns=[
        "species", "probability_1yr", "probability_5yr", "probability_10yr",
        "baseline_total_score", "weather_support", "near_term_opportunity_score",
        "weather_status", "weather_generated_at", "weather_forecast_date",
    ]).assign(confidence_score=0.6).to_csv(path, index=False)


def test_probability_loader_converts_and_expires_weather(tmp_path):
    path = tmp_path / "probabilities.csv"
    _probabilities(path)
    frame = app.load_next_dutch_firsts_probabilities(path).set_index("species")
    assert frame.loc["Alpha", "probability_5yr"] == pytest.approx(0.3)
    assert frame.loc["Alpha", "weather_support"] == 80
    assert frame.loc["Gamma", "weather_status"] == "unavailable"
    assert pd.isna(frame.loc["Gamma", "near_term_opportunity_score"])
    assert pd.isna(frame.loc["Gamma", "weather_support"])


@pytest.mark.parametrize("error", ["missing", "schema", "score", "probability", "duplicate"])
def test_probability_loader_rejects_invalid_data(tmp_path, error):
    path = tmp_path / "probabilities.csv"
    _probabilities(path)
    frame = pd.read_csv(path)
    if error == "missing":
        path.unlink()
    elif error == "schema":
        frame.drop(columns=["weather_status"]).to_csv(path, index=False)
    elif error == "score":
        frame.loc[0, "near_term_opportunity_score"] = 101
        frame.to_csv(path, index=False)
    elif error == "probability":
        frame.loc[0, "probability_1yr"] = "120%"
        frame.to_csv(path, index=False)
    elif error == "duplicate":
        frame.loc[1, "species"] = frame.loc[0, "species"]
        frame.to_csv(path, index=False)
    with pytest.raises((OSError, ValueError)):
        app.load_next_dutch_firsts_probabilities(path)


def test_probability_table_sorts_by_near_term_and_selected_horizon(tmp_path):
    path = tmp_path / "probabilities.csv"
    _probabilities(path)
    at = AppTest.from_function(_show_firsts, args=(str(path),), default_timeout=30).run()
    assert not at.exception
    assert at.radio(key="firsts_probability_sort").value == "Near-Term Opportunity"
    table = at.dataframe[0].value
    assert list(table.columns) == [
        "species", "probability_1yr", "probability_5yr", "probability_10yr",
        "baseline_total_score", "weather_support", "near_term_opportunity_score", "weather_status",
    ]
    assert table["species"].tolist() == ["Beta", "Alpha", "Gamma"]
    assert table.iloc[-1]["weather_status"] == "unavailable"
    assert any("unavailable for 1 species" in warning.value for warning in at.warning)
    assert at.radio(key="avw_filter").value == "All Species"

    at.radio(key="firsts_probability_sort").set_value("Long-Term Probability").run()
    assert not at.exception
    assert at.selectbox(key="firsts_probability_horizon").value == "5 years"
    assert at.dataframe[0].value["species"].tolist() == ["Alpha", "Gamma", "Beta"]
    at.selectbox(key="firsts_probability_horizon").set_value("1 year").run()
    assert at.dataframe[0].value["species"].tolist() == ["Beta", "Gamma", "Alpha"]
    at.selectbox(key="firsts_probability_horizon").set_value("10 years").run()
    assert at.dataframe[0].value["species"].tolist() == ["Alpha", "Beta", "Gamma"]

    at.radio(key="avw_filter").set_value("Corvo Pipeline").run()
    assert not at.exception
    assert at.dataframe[0].value["species"].tolist() == ["Alpha", "Beta", "Gamma"]
    assert at.radio(key="avw_filter").value == "Corvo Pipeline"
    assert any("Species detail" in select.label for select in at.selectbox)


def test_missing_probability_file_keeps_demo_available(tmp_path):
    at = AppTest.from_function(
        _show_firsts, args=(str(tmp_path / "missing.csv"),), default_timeout=30
    ).run()
    assert not at.exception
    assert any("probability forecasts are unavailable" in error.value for error in at.error)
    assert at.radio(key="avw_filter").value == "All Species"
    assert any("Species detail" in select.label for select in at.selectbox)
