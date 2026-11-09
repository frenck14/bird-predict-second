"""Goose-specific winter weather features for the Winter Goose Module.

Inputs are the shared KNMI-style daily station columns (0.1 degC, 0.1 m/s,
0.1 mm, 0.1 hPa) after ``add_coastal_features``. All goose columns are prefixed
``goose_`` so they can be told apart from the shared features.

Daily data cannot capture hourly cold snaps, so the migration triggers are
daily proxies:

* ``goose_cold_outbreak``: the daily mean is at or below COLD_OUTBREAK_MEAN_C
  and fell by at least COLD_OUTBREAK_DROP_C over three days, or it is an ice day
  (maximum below 0 degC) after a mild week.
* ``goose_rapid_temp_drop``: the daily mean fell by at least RAPID_DROP_C in 24h.

Consecutive frost days are capped at MAX_FROST_RUN_DAYS and start counting at
the first day of the supplied weather, so a 14-day forecast window
under-counts frost runs that began before it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

if __package__:
    from .build_dataset_v2 import STATION_FILES, add_coastal_features
else:
    from build_dataset_v2 import STATION_FILES, add_coastal_features


MAX_FROST_RUN_DAYS = 14
FROST_THRESHOLD_C = 0.0
COLD_OUTBREAK_MEAN_C = 2.0
COLD_OUTBREAK_DROP_C = 5.0
RAPID_DROP_C = 4.0
MILD_WEEK_C = 4.0

SEASONALITY_COLUMNS = ["month", "day_of_year", "week_of_year", "day_of_year_sin", "day_of_year_cos"]
GOOSE_FEATURE_COLUMNS = [
    "goose_temp_mean_c", "goose_temp_min_c", "goose_temp_max_c",
    "goose_frost", "goose_consecutive_frost_days", "goose_frost_days_7d",
    "goose_wind_speed_ms", "goose_wind_direction_deg", "goose_easterly_wind_ms",
    "goose_pressure_hpa", "goose_pressure_change_24h_hpa",
    "goose_precipitation_mm", "goose_precipitation_3d_mm",
    "goose_temp_change_24h_c", "goose_temp_change_72h_c", "goose_temp_mean_7d_c",
    "goose_cold_outbreak", "goose_rapid_temp_drop",
]


def _station_mean(data: pd.DataFrame, variable: str) -> pd.Series:
    return data[[f"{variable}_{station}" for station in STATION_FILES]].mean(axis=1)


def _consecutive_run(flags: pd.Series, cap: int) -> pd.Series:
    run = 0
    values = []
    for flag in flags.to_numpy():
        run = run + 1 if flag else 0
        values.append(min(run, cap))
    return pd.Series(values, index=flags.index, dtype=float)


def seasonality(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Calendar features of the *target* date (known in advance)."""
    dates = pd.DatetimeIndex(dates)
    phase = 2 * np.pi * dates.dayofyear / 365.2425
    return pd.DataFrame(
        {
            "month": dates.month,
            "day_of_year": dates.dayofyear,
            "week_of_year": dates.isocalendar().week.to_numpy().astype(int),
            "day_of_year_sin": np.sin(phase),
            "day_of_year_cos": np.cos(phase),
        }
    )


def add_goose_features(dataset: pd.DataFrame) -> pd.DataFrame:
    """Add goose features to the output of add_coastal_features."""
    data = dataset.copy()
    if "coast_FG_mean" not in data.columns:
        data = add_coastal_features(data)

    temp_mean = data["coast_TG_mean"] / 10.0
    temp_min = _station_mean(data, "TN") / 10.0
    temp_max = data["coast_TX_mean"] / 10.0
    frost = temp_min.lt(FROST_THRESHOLD_C)
    valid = temp_min.notna()

    data["goose_temp_mean_c"] = temp_mean
    data["goose_temp_min_c"] = temp_min
    data["goose_temp_max_c"] = temp_max
    data["goose_frost"] = frost.astype(float).where(valid)
    data["goose_consecutive_frost_days"] = _consecutive_run(
        frost, MAX_FROST_RUN_DAYS
    ).where(valid)
    data["goose_frost_days_7d"] = frost.astype(float).where(valid).rolling(
        7, min_periods=1
    ).sum()

    data["goose_wind_speed_ms"] = data["coast_FG_mean"] / 10.0
    direction = np.rad2deg(np.arctan2(data["coast_wind_sin"], data["coast_wind_cos"])) % 360
    data["goose_wind_direction_deg"] = direction
    # coast_west_wind_component = FG * sin(from-direction), so it is positive for easterlies
    data["goose_easterly_wind_ms"] = data["coast_west_wind_component"] / 10.0

    pressure = data["coast_PX_mean"] / 10.0
    data["goose_pressure_hpa"] = pressure
    data["goose_pressure_change_24h_hpa"] = pressure.diff()
    precipitation = data["coast_RH_mean"].clip(lower=0) / 10.0
    data["goose_precipitation_mm"] = precipitation
    data["goose_precipitation_3d_mm"] = precipitation.rolling(3, min_periods=1).sum()

    change_24h = temp_mean.diff()
    change_72h = temp_mean.diff(3)
    mean_7d = temp_mean.rolling(7, min_periods=3).mean()
    data["goose_temp_change_24h_c"] = change_24h
    data["goose_temp_change_72h_c"] = change_72h
    data["goose_temp_mean_7d_c"] = mean_7d
    previous_week = mean_7d.shift(3)
    ice_day = temp_max.lt(0.0) & previous_week.ge(MILD_WEEK_C)
    outbreak = (
        temp_mean.le(COLD_OUTBREAK_MEAN_C) & change_72h.le(-COLD_OUTBREAK_DROP_C)
    ) | ice_day
    data["goose_cold_outbreak"] = outbreak.astype(float).where(temp_mean.notna())
    data["goose_rapid_temp_drop"] = change_24h.le(-RAPID_DROP_C).astype(float).where(
        change_24h.notna()
    )
    return data
