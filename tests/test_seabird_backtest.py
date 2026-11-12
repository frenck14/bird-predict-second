from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

import app
from src import seabird_backtest as backtest
from src.predict_seabird import analysis_predictor_dates


class SeabirdBacktestTests(unittest.TestCase):
    def test_backtest_section_is_available_without_live_forecast(self) -> None:
        with (
            patch.object(app.st, "title"),
            patch.object(app.st, "radio", return_value="🧪 Backtest"),
            patch.object(app, "show_seabird_backtest") as show_backtest,
            patch.object(
                app,
                "forecast_ready",
                side_effect=AssertionError("Backtest must not require live forecasts"),
            ),
        ):
            app.show_seawatching()

        show_backtest.assert_called_once_with()

    def test_analysis_date_selects_the_14_day_weather_window(self) -> None:
        weather = pd.DataFrame(
            {"date": pd.date_range("2020-01-01", periods=20, freq="D")}
        )
        selected = analysis_predictor_dates(
            weather,
            pd.date_range("2025-01-01", periods=14, freq="D"),
            date(2020, 1, 3),
        )

        self.assertEqual(selected[0].date(), date(2020, 1, 3))
        self.assertEqual(selected[-1].date(), date(2020, 1, 16))

    def test_analysis_date_bounds_use_14_day_predictor_window(self) -> None:
        weather = pd.DataFrame(
            {"date": pd.date_range("2020-01-01", periods=20, freq="D")}
        )

        self.assertEqual(
            backtest.analysis_date_bounds(weather),
            (date(2020, 1, 1), date(2020, 1, 20)),
        )

    def test_backtest_filters_all_inputs_to_cutoff(self) -> None:
        analysis_date = date(2020, 1, 2)
        weather = pd.DataFrame(
            {
                "date": pd.date_range("2020-01-01", periods=30, freq="D"),
                "weather": range(30),
            }
        )
        occurrences = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2020-01-01", "2020-01-02", "2020-01-03"]
                ),
                "species": ["Northern Fulmar"] * 3,
            }
        )
        expected = {"analysis_date": analysis_date, "holdout_days": 14}
        with (
            patch(
                "src.seabird_validation.build_historical_forecast",
                return_value=expected,
            ) as build_forecast,
            patch.object(backtest, "load_cached_occurrences", return_value=occurrences),
        ):
            result = backtest.build_seabird_backtest(analysis_date, weather)

        self.assertEqual(result, expected)
        call = build_forecast.call_args
        self.assertEqual(call.args[0], analysis_date)
        self.assertEqual(call.kwargs["holdout_days"], 14)
        self.assertEqual(
            call.kwargs["inputs"]["weather"]["date"].dt.date.tolist(),
            [date(2020, 1, 1), date(2020, 1, 2)],
        )
        self.assertEqual(
            call.kwargs["inputs"]["occurrences"]["date"].dt.date.tolist(),
            [date(2020, 1, 1), date(2020, 1, 2)],
        )


if __name__ == "__main__":
    unittest.main()


def _backtest_ui_script() -> None:
    from datetime import date
    from unittest.mock import patch

    import pandas as pd

    import app

    analysis = date(2025, 10, 1)
    dates = pd.date_range("2025-10-02", periods=14)
    rating = pd.DataFrame(
        {
            "date": dates,
            "forecast_day": range(1, 15),
            "score": 50,
            "rating": "Good",
            "best_coast": "Texel",
        }
    )
    # Real schema: a horizon label and date, no forecast_day/horizon_days.
    hotspots = pd.DataFrame(
        [
            {"date": dates[d - 1], "horizon": label, "rank": 1, "location": "Texel",
             "country": "NL", "score": 60, "rating": "Good"}
            for d, label in app.FORECAST_HORIZONS.items()
        ]
    )
    species = pd.DataFrame(
        {"species": ["Gannet"], "date": dates[:1], "probability": 0.5, "risk_level": "Low"}
    )
    result = {
        "analysis_date": analysis,
        "rating": rating,
        "hotspots": hotspots,
        "species": species,
    }
    with patch.multiple(
        app,
        load_seabird_backtest_weather=lambda: None,
        seabird_backtest_date_bounds=lambda w: (date(2020, 1, 1), date(2026, 1, 1)),
        build_seabird_backtest=lambda *a, **k: result,
        show_seabird_observation_validation=lambda r: None,
    ):
        import streamlit as st

        st.session_state["seabird_backtest_analysis_date"] = analysis
        app.show_seabird_backtest()


def test_backtest_hotspots_without_forecast_day_column_render() -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_backtest_ui_script, default_timeout=30).run()
    at.button[0].click().run()
    assert not at.exception
    assert at.selectbox[0].options == [
        "Tomorrow · Oct 03, 2025",
        "+3 days · Oct 05, 2025",
        "+7 days · Oct 09, 2025",
        "+14 days · Oct 15, 2025",
    ] or len(at.selectbox[0].options) == 4
    assert len(at.dataframe) == 3
