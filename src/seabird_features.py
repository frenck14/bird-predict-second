"""Seabird-specific storm, wind and marine proxy features.

KNMI data here are daily, so the hourly quantities requested for seawatching
(gust, gale hours, wave state) are approximated with daily proxies:

* "gust speed" is coast_FHX_max, the strongest daily maximum of the hourly-mean
  wind across stations (not an instantaneous gust).
* "consecutive gale hours" becomes consecutive gale days, capped at
  MAX_GALE_RUN_DAYS so training and forecasting windows agree.
* wave and fetch values are geometric proxies from wind direction and speed,
  not modelled sea state.

Wind speeds in the source data are 0.1 m/s and pressure is 0.1 hPa.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

if __package__:
    from .build_dataset_v2 import STATION_FILES, add_coastal_features
else:
    from build_dataset_v2 import STATION_FILES, add_coastal_features


GALE_GUST_THRESHOLD = 140.0  # 14 m/s daily maximum hourly-mean wind
STORM_EXCESS_BASE = 100.0  # 10 m/s; wind above this adds to the storm score
MAX_GALE_RUN_DAYS = 7
FETCH_PEAK_DIRECTION = 320.0  # NNW: open North Sea fetch for the Dutch coast
ONSHORE_DIRECTION = 290.0  # the Dutch coast faces WNW
STANDARD_PRESSURE = 10130.0


def _component(dataset: pd.DataFrame, from_direction: float) -> pd.Series:
    """Mean wind speed (m/s) blowing from from_direction across stations."""
    parts = []
    for station_id in STATION_FILES:
        direction = dataset[f"DDVEC_{station_id}"].where(
            dataset[f"DDVEC_{station_id}"] != 0
        )
        angle = np.deg2rad(direction - from_direction)
        parts.append(dataset[f"FG_{station_id}"] * np.cos(angle) / 10.0)
    return pd.concat(parts, axis=1).mean(axis=1)


def _consecutive_run(flags: pd.Series, cap: int) -> pd.Series:
    run = 0
    values = []
    for flag in flags.to_numpy():
        run = run + 1 if flag else 0
        values.append(min(run, cap))
    return pd.Series(values, index=flags.index, dtype=float)


def add_seabird_features(dataset: pd.DataFrame) -> pd.DataFrame:
    """Add seabird features to the output of add_coastal_features."""
    data = dataset.copy()
    if "coast_FG_mean" not in data.columns:
        data = add_coastal_features(data)
    wind = data["coast_FG_mean"] / 10.0
    gust = data["coast_FHX_max"] / 10.0

    data["coast_wind_speed"] = wind
    data["coast_gust_speed"] = gust
    data["coast_westerly_wind_component"] = _component(data, 270.0)
    data["coast_southwest_wind_component"] = _component(data, 225.0)
    data["coast_northwest_wind_component"] = _component(data, 315.0)

    data["coast_pressure_tendency_24h"] = data["pressure_change_24h"] / 10.0
    data["coast_atlantic_storm_index"] = (
        (STANDARD_PRESSURE - data["coast_PX_min"]) / 10.0
    ).clip(lower=0.0)

    for days in (1, 2, 3):
        data[f"coast_wind_rolling_mean_{days * 24}h"] = wind.rolling(
            days, min_periods=days
        ).mean()
    for days in (1, 2):
        data[f"coast_max_gust_{days * 24}h"] = gust.shift(1).rolling(
            days, min_periods=days
        ).max()

    excess = (data["coast_FHX_max"] - STORM_EXCESS_BASE).clip(lower=0.0) / 10.0
    data["coast_cumulative_storm_score"] = excess.rolling(3, min_periods=3).sum()
    gale = data["coast_FHX_max"].ge(GALE_GUST_THRESHOLD)
    data["coast_consecutive_gale_days"] = _consecutive_run(
        gale, MAX_GALE_RUN_DAYS
    ).where(data["coast_FHX_max"].notna())

    direction = np.rad2deg(np.arctan2(data["coast_wind_sin"], data["coast_wind_cos"]))
    fetch = 0.5 * (1.0 + np.cos(np.deg2rad(direction - FETCH_PEAK_DIRECTION)))
    data["coast_fetch_proxy"] = fetch
    data["coast_wave_proxy"] = fetch * wind**2

    onshore = _component(data, ONSHORE_DIRECTION).clip(lower=0.0)
    data["coast_sustained_onshore_flow"] = onshore.rolling(3, min_periods=3).mean()
    return data
