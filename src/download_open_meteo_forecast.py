"""Download Open-Meteo forecasts and adapt them to the model input schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

if __package__:
    from .build_dataset_v2 import WEATHER_VARIABLES
else:
    from build_dataset_v2 import WEATHER_VARIABLES


ROOT = Path(__file__).resolve().parents[1]
OPEN_METEO_API = "https://api.open-meteo.com/v1/forecast"
DEFAULT_FORECAST_FILE = ROOT / "inputs/open_meteo_forecast_current.csv"
FORECAST_DAYS = 14
REQUEST_TIMEOUT_SECONDS = 60
OUTPUT_COLUMNS = ("date", "station_id", *WEATHER_VARIABLES)

# Open-Meteo grid points approximate the locations used by the KNMI model data.
STATION_COORDINATES = {
    235: (52.923, 4.790),  # De Kooy
    242: (53.240, 4.920),  # Vlieland
    225: (52.463, 4.555),  # IJmuiden
    310: (51.442, 3.596),  # Vlissingen
}
HOURLY_VARIABLES = (
    "temperature_2m",
    "precipitation",
    "pressure_msl",
    "wind_speed_10m",
    "wind_direction_10m",
)


@dataclass(frozen=True)
class DownloadedForecast:
    path: Path
    source_description: str


def _request_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "Bird-Predict/1.0"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise RuntimeError(
            f"Open-Meteo Forecast API returned HTTP {error.code}."
        ) from error
    except URLError as error:
        raise RuntimeError(
            f"Could not reach the Open-Meteo Forecast API: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise ValueError("Open-Meteo returned invalid JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError("Open-Meteo returned an unexpected JSON response.")
    return payload


def _daily_direction(
    direction: pd.Series, speed: pd.Series
) -> float:
    valid = direction.notna() & speed.notna() & speed.ge(0)
    if not valid.any():
        return np.nan

    angles = np.deg2rad(direction.loc[valid].to_numpy(dtype=float))
    weights = speed.loc[valid].to_numpy(dtype=float)
    east_component = np.sum(weights * np.sin(angles))
    north_component = np.sum(weights * np.cos(angles))
    if np.hypot(east_component, north_component) < 1e-8:
        return 0.0
    return float(np.rad2deg(np.arctan2(east_component, north_component)) % 360)


def normalize_hourly_forecast(
    payload: dict[str, object], station_id: int
) -> pd.DataFrame:
    """Aggregate one forecast point to daily rows in the trained model's units."""
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("Open-Meteo response is missing hourly forecast data.")
    missing_fields = set(("time", *HOURLY_VARIABLES)).difference(hourly)
    if missing_fields:
        raise ValueError(
            f"Open-Meteo hourly response is missing fields: "
            f"{sorted(missing_fields)}"
        )

    lengths = {
        len(values)
        for values in hourly.values()
        if isinstance(values, list)
    }
    if len(lengths) != 1 or not lengths:
        raise ValueError(
            "Open-Meteo hourly fields must be equally sized lists."
        )
    expected_length = lengths.pop()
    if any(
        not isinstance(hourly[field], list)
        or len(hourly[field]) != expected_length
        for field in ("time", *HOURLY_VARIABLES)
    ):
        raise ValueError(
            "Open-Meteo hourly fields must be equally sized lists."
        )

    frame = pd.DataFrame(hourly)
    frame["date"] = pd.to_datetime(frame["time"], errors="coerce").dt.normalize()
    if frame["date"].isna().any():
        raise ValueError("Open-Meteo response contains invalid hourly dates.")
    for variable in HOURLY_VARIABLES:
        frame[variable] = pd.to_numeric(frame[variable], errors="coerce")

    daily = frame.groupby("date", sort=True)
    normalized = pd.DataFrame(
        {
            "date": list(daily.groups),
            "station_id": station_id,
            "DDVEC": [
                _daily_direction(group["wind_direction_10m"], group["wind_speed_10m"])
                for _, group in daily
            ],
            "FG": daily["wind_speed_10m"].mean().to_numpy() * 10,
            "FHX": daily["wind_speed_10m"].max().to_numpy() * 10,
            "TG": daily["temperature_2m"].mean().to_numpy() * 10,
            "TN": daily["temperature_2m"].min().to_numpy() * 10,
            "TX": daily["temperature_2m"].max().to_numpy() * 10,
            "RH": daily["precipitation"].sum(min_count=1).to_numpy() * 10,
            "PX": daily["pressure_msl"].max().to_numpy() * 10,
        }
    )
    if normalized[list(WEATHER_VARIABLES)].isna().all(axis=None):
        raise ValueError(
            f"Open-Meteo returned no usable weather values for station "
            f"{station_id}."
        )
    return normalized.loc[:, OUTPUT_COLUMNS]


def download_open_meteo_forecast(
    output_path: Path = DEFAULT_FORECAST_FILE,
) -> DownloadedForecast:
    station_frames = []
    for station_id, (latitude, longitude) in STATION_COORDINATES.items():
        params = urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": ",".join(HOURLY_VARIABLES),
                "forecast_days": FORECAST_DAYS,
                "timezone": "Europe/Amsterdam",
                "wind_speed_unit": "ms",
                "temperature_unit": "celsius",
                "precipitation_unit": "mm",
            }
        )
        payload = _request_json(f"{OPEN_METEO_API}?{params}")
        station_frames.append(
            normalize_hourly_forecast(payload, station_id)
        )

    forecast = pd.concat(station_frames, ignore_index=True)
    dates_by_station = {
        station_id: pd.DatetimeIndex(
            sorted(forecast.loc[forecast["station_id"].eq(station_id), "date"])
        )
        for station_id in STATION_COORDINATES
    }
    date_index = dates_by_station[235]
    expected_dates = pd.date_range(
        date_index.min(), periods=FORECAST_DAYS, freq="D"
    )
    if not date_index.equals(expected_dates):
        raise ValueError(
            "Open-Meteo did not return 14 consecutive daily dates for station 235."
        )
    for station_id, dates in dates_by_station.items():
        if not dates.equals(date_index):
            raise ValueError(
                "Open-Meteo stations returned inconsistent forecast dates; "
                f"station {station_id} differs."
            )
    if forecast.duplicated(["date", "station_id"]).any():
        raise ValueError(
            "Open-Meteo aggregation produced duplicate date/station rows."
        )
    if forecast[list(WEATHER_VARIABLES)].isna().all(axis=None):
        raise ValueError("Open-Meteo forecast contains no usable weather values.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    forecast.sort_values(["date", "station_id"]).to_csv(
        output_path, index=False, date_format="%Y-%m-%d"
    )
    return DownloadedForecast(
        path=output_path,
        source_description=(
            "Open-Meteo Forecast API (best-match forecast model; hourly "
            "forecast aggregated to local daily values at four coastal grid "
            "points approximating KNMI stations)"
        ),
    )


if __name__ == "__main__":
    downloaded = download_open_meteo_forecast()
    print(f"Downloaded {downloaded.source_description}")
    print(f"Saved daily model-input CSV to {downloaded.path}")
