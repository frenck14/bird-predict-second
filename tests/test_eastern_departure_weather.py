import numpy as np
import pandas as pd

from src import eastern_departure_weather as edw


def test_bearing_to_netherlands_from_finland_is_south_west() -> None:
    value = edw.bearing(edw.region_centre(edw.REGIONS["Finland"]), edw.NETHERLANDS)
    assert 220 < value < 260


def test_tailwind_and_crosswind_components() -> None:
    index = pd.date_range("2020-10-01", periods=3)
    track = edw.bearing(edw.region_centre(edw.REGIONS["Finland"]), edw.NETHERLANDS)
    from_dir = (track + 180) % 360  # wind from behind, blowing toward the Netherlands
    daily = pd.DataFrame({"temperature": 5.0, "pressure": 1010.0, "precipitation": 0.0,
                          "speed": 10.0, "direction_from": from_dir}, index=index)
    out = edw.region_features(daily, edw.REGIONS["Finland"])
    assert np.allclose(out["tailwind"], 10.0)
    assert np.allclose(out["crosswind"], 0.0, atol=1e-9)


def test_days_since_cold_front_resets_and_caps() -> None:
    flag = pd.Series([False, True, False, False, True, False])
    assert edw.days_since_event(flag, cap=3).tolist() == [3, 0, 1, 2, 0, 1]


def test_event_flags_use_top_decile_with_minimum_one() -> None:
    index = pd.date_range("2020-09-15", periods=60)
    counts = pd.Series(0, index=index)
    counts.iloc[[3, 10]] = 2
    flags = edw.event_flags(counts)
    assert flags.sum() == 2 and flags.iloc[3]


def test_lag_alignment_uses_weather_before_the_target_day() -> None:
    index = pd.date_range("2011-01-01", "2025-12-31")
    rng = np.random.default_rng(1)
    signal = pd.Series(rng.normal(size=len(index)), index=index)
    features = pd.DataFrame({("Finland", "tailwind"): signal})
    counts = pd.DataFrame({"A": (signal.shift(1) > 1).astype(int).fillna(0)}, index=index)
    table = edw.audit(features, counts).set_index("lag_days")
    assert table.loc[1, "mean_yearly_rho"] > 0.5
    assert abs(table.loc[2, "mean_yearly_rho"]) < 0.2 and abs(table.loc[3, "mean_yearly_rho"]) < 0.2


def test_benjamini_hochberg_adjusts_in_rank_order() -> None:
    q = edw.benjamini_hochberg(np.array([0.01, 0.04, 0.03, 0.5]))
    assert np.allclose(q, [0.04, 0.0533333, 0.0533333, 0.5])
