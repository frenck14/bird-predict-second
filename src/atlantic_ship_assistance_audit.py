"""Exploratory weather and shipping context for Atlantic vagrancy records."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import pickle
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from PIL import Image
from pyproj import Geod, Transformer
from scipy.ndimage import distance_transform_edt

from .build_atlantic_vagrancy_dataset import (
    ATLANTIC_VAGRANCY_SPECIES,
    ROOT,
    TARGET_COUNTRIES,
    load_all_occurrences,
)

OUTPUT_DIRECTORY = ROOT / "outputs/atlantic_vagrancy"
AUDIT_OUTPUT = OUTPUT_DIRECTORY / "ship_assistance_audit.csv"
EVENTS_OUTPUT = OUTPUT_DIRECTORY / "ship_assistance_events.csv"
ARRIVAL_EVENTS_OUTPUT = OUTPUT_DIRECTORY / "ship_assistance_arrival_events.csv"
ARRIVAL_EVENT_COMPARISON_OUTPUT = (
    OUTPUT_DIRECTORY / "ship_assistance_arrival_event_comparison.csv"
)
SUMMARY_OUTPUT = OUTPUT_DIRECTORY / "ship_assistance_summary.md"
WEATHER_SUPPORT_OUTPUT = OUTPUT_DIRECTORY / "species_weather_support.csv"
WEATHER_SUPPORT_SUMMARY_OUTPUT = OUTPUT_DIRECTORY / "species_weather_support.md"
COVERAGE_OUTPUT = OUTPUT_DIRECTORY / "ship_assistance_species_coverage.csv"

WEATHER_API = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_MODEL = "era5"
WEATHER_ARCHIVE_START = pd.Timestamp("1940-01-01")
ROUTE_DENSITY_WMS = "https://ows.emodnet-humanactivities.eu/wms"
EMODNET_WFS = "https://ows.emodnet-humanactivities.eu/wfs"
WEATHER_ORIGIN = (45.0, -55.0)
ROUTE_SAMPLE_COUNT = 7
ROUTE_WEATHER_DAYS = 7
WEATHER_REQUEST_ROUTES = 15
WEATHER_REQUEST_SPLIT_ROUTES = 2
MAX_WEATHER_WORKERS = 1
WEATHER_CACHE_DIRECTORY = ROOT / "data/cache/ship_audit_era5"
WEATHER_REQUEST_DELAY_S = 5.0
WEATHER_MAX_RETRIES = 10
PORT_PROXIMITY_SCALE_KM = 100.0
SHIPPING_ROUTE_PROXIMITY_SCALE_KM = 25.0
CONTAINER_PORT_PROXIMITY_SCALE_KM = 100.0
ISOLATION_RADIUS_KM = 100.0
ROUTE_BUFFER_KM = 50.0
ROUTE_PIXEL_SIZE_KM = 1.0

WEATHER_SCORE_COLUMNS = (
    "transatlantic_tailwind_corridor_present",
    "tailwind_corridor_fraction",
    "tailwind_corridor_score",
    "mean_headwind_intensity_m_s",
    "minimum_route_pressure_hpa",
    "major_low_pressure_on_route",
    "days_before_arrival_of_min_pressure",
    "storm_track_support_score",
    "arrival_timing_relative_to_low_score",
    "weather_support_score",
)

SPECIES_ORDER = [str(item["species"]) for item in ATLANTIC_VAGRANCY_SPECIES]
SPECIES_SHIP_ASSISTANCE_INPUT = {
    "Blackpoll Warbler": {
        "score": 0.15,
        "description": "Geolocator-tracked non-stop transoceanic migration is documented.",
    },
    **{
        species: {
            "score": 0.50,
            "description": (
                "Long-distance migrant; trans-Atlantic flight capability is "
                "not quantified here."
            ),
        }
        for species in SPECIES_ORDER
        if species != "Blackpoll Warbler"
    },
}

HARBOURS = {
    "Rotterdam": (51.9037, 4.4837),
    "IJmuiden": (52.4630, 4.5840),
    "Vlissingen": (51.4421, 3.5971),
    "Antwerp": (51.2417, 4.4082),
    "Zeebrugge": (51.3630, 3.1973),
    "Eemshaven": (53.4576, 6.8356),
}

GEOD = Geod(ellps="WGS84")
WGS84_TO_EPSG3035 = Transformer.from_crs(
    "EPSG:4326", "EPSG:3035", always_xy=True
)
EPSG3035_TO_WGS84 = Transformer.from_crs(
    "EPSG:3035", "EPSG:4326", always_xy=True
)
LOGGER = logging.getLogger(__name__)


def _get_json(url: str, params: dict[str, object], timeout: int = 90) -> object:
    request_url = f"{url}?{urlencode(params)}"
    request = Request(
        request_url,
        headers={"User-Agent": "bird-predict-second/1.0 ship-assistance-audit"},
    )
    for attempt in range(WEATHER_MAX_RETRIES):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code in {429, *range(500, 600)}:
                error.close()
                if attempt < WEATHER_MAX_RETRIES - 1:
                    backoff_s = min(60, 2 ** attempt + (attempt * 5))
                    LOGGER.warning(
                        "HTTP %d on attempt %d/%d; waiting %.0f seconds",
                        error.code,
                        attempt + 1,
                        WEATHER_MAX_RETRIES,
                        backoff_s,
                    )
                    time.sleep(backoff_s)
                    continue
            raise RuntimeError(
                f"Public data service returned HTTP {error.code}: {url}"
            ) from error
        except (URLError, TimeoutError) as error:
            if attempt < WEATHER_MAX_RETRIES - 1:
                backoff_s = min(60, 2 ** attempt)
                LOGGER.warning(
                    "Connection error on attempt %d/%d; waiting %.0f seconds: %s",
                    attempt + 1,
                    WEATHER_MAX_RETRIES,
                    backoff_s,
                    error,
                )
                time.sleep(backoff_s)
                continue
            raise RuntimeError(
                f"Could not reach public data service {url}: {error}"
            ) from error
        except ValueError as error:
            raise ValueError(f"Invalid JSON response from {url}.") from error
    raise RuntimeError(f"Request retries exhausted for {url}.")


def _route_points(latitude: float, longitude: float) -> list[tuple[float, float]]:
    origin_latitude, origin_longitude = WEATHER_ORIGIN
    azimuth, _, distance_m = GEOD.inv(
        origin_longitude, origin_latitude, longitude, latitude
    )
    points = []
    for fraction in np.linspace(0.0, 1.0, ROUTE_SAMPLE_COUNT):
        lon, lat, _ = GEOD.fwd(
            origin_longitude,
            origin_latitude,
            azimuth,
            distance_m * float(fraction),
        )
        points.append((float(lat), float(lon)))
    return points


def _sample_bearings(points: list[tuple[float, float]]) -> np.ndarray:
    bearings = []
    for index in range(len(points)):
        start = points[index]
        end = points[min(index + 1, len(points) - 1)]
        if index == len(points) - 1:
            start = points[index - 1]
            end = points[index]
        azimuth, _, _ = GEOD.inv(start[1], start[0], end[1], end[0])
        bearings.append(math.radians(azimuth))
    return np.asarray(bearings)


def _route_weather_metrics(
    location_weather: list[dict[str, object]],
    bearings: np.ndarray,
    arrival_date: pd.Timestamp,
) -> dict[str, object]:
    along_winds = []
    daily_pressures = []
    window_start = arrival_date.normalize() - pd.Timedelta(
        days=ROUTE_WEATHER_DAYS - 1
    )
    window_end = arrival_date.normalize() + pd.Timedelta(days=1)
    for point_weather, bearing in zip(location_weather, bearings, strict=True):
        hourly = point_weather.get("hourly")
        if not isinstance(hourly, dict):
            raise ValueError("ERA5 response is missing hourly weather values.")
        times = pd.to_datetime(hourly.get("time", []), errors="raise")
        speed = np.asarray(hourly.get("wind_speed_10m", []), dtype=float) / 3.6
        direction_from = np.deg2rad(
            np.asarray(hourly.get("wind_direction_10m", []), dtype=float)
        )
        pressure = np.asarray(hourly.get("pressure_msl", []), dtype=float)
        if not (len(times) == len(speed) == len(direction_from) == len(pressure)):
            raise ValueError("ERA5 hourly arrays have inconsistent lengths.")
        in_window = (times >= window_start) & (times < window_end)
        times = times[in_window]
        speed = speed[in_window]
        direction_from = direction_from[in_window]
        pressure = pressure[in_window]
        wind_east = -speed * np.sin(direction_from)
        wind_north = -speed * np.cos(direction_from)
        along_winds.extend(
            (wind_east * math.sin(bearing) + wind_north * math.cos(bearing)).tolist()
        )
        pressure_frame = pd.DataFrame({"date": times.normalize(), "pressure": pressure})
        daily_pressures.append(
            pressure_frame.groupby("date", as_index=False)["pressure"].mean()
        )

    along = np.asarray(along_winds, dtype=float)
    along = along[np.isfinite(along)]
    if not len(along):
        raise ValueError("ERA5 response contains no usable route wind values.")
    tailwind_share = float(np.mean(along >= 2.0))
    mean_tailwind = float(np.maximum(along, 0.0).mean())
    mean_headwind = float(np.maximum(-along, 0.0).mean())
    corridor_score = float(np.clip(mean_tailwind / 15.0, 0.0, 1.0) * tailwind_share)
    corridor_present = tailwind_share >= 0.35 and mean_tailwind >= 2.0

    pressure = pd.concat(daily_pressures, ignore_index=True)
    pressure = pressure.loc[np.isfinite(pressure["pressure"])]
    if pressure.empty:
        raise ValueError("ERA5 response contains no usable sea-level pressure values.")
    lowest = pressure.loc[pressure["pressure"].idxmin()]
    minimum_pressure = float(lowest["pressure"])
    days_before_arrival = int((arrival_date.normalize() - lowest["date"]).days)
    major_low_present = minimum_pressure <= 1000.0
    storm_strength = (
        float(np.clip((1000.0 - minimum_pressure) / 20.0, 0.0, 1.0))
        if major_low_present
        else 0.0
    )
    storm_timing = (
        float(np.clip(1.0 - days_before_arrival / (ROUTE_WEATHER_DAYS - 1), 0.0, 1.0))
        if major_low_present
        else 0.0
    )
    headwind_penalty = float(np.clip(1.0 - mean_headwind / 25.0, 0.0, 1.0))
    weather_score = float(
        np.clip(
            (
                0.60 * corridor_score
                + 0.25 * storm_strength
                + 0.15 * storm_timing
            )
            * headwind_penalty,
            0.0,
            1.0,
        )
    )
    return {
        "transatlantic_tailwind_corridor_present": corridor_present,
        "tailwind_corridor_fraction": tailwind_share,
        "tailwind_corridor_score": corridor_score,
        "mean_headwind_intensity_m_s": mean_headwind,
        "minimum_route_pressure_hpa": minimum_pressure,
        "major_low_pressure_on_route": major_low_present,
        "days_before_arrival_of_min_pressure": days_before_arrival,
        "storm_track_support_score": storm_strength,
        "arrival_timing_relative_to_low_score": storm_timing,
        "weather_support_score": weather_score,
    }


def _fetch_weather_chunk(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    locations: dict[tuple[float, float], list[pd.Timestamp]],
    *,
    cache_only: bool = False,
) -> dict[tuple[pd.Timestamp, float, float], dict[str, object]]:
    cache_key = hashlib.sha256(
        repr(
            (
                WEATHER_MODEL,
                ROUTE_SAMPLE_COUNT,
                start_date.date(),
                end_date.date(),
                [(loc, [d.date() for d in dates]) for loc, dates in locations.items()],
            )
        ).encode()
    ).hexdigest()
    cache_path = WEATHER_CACHE_DIRECTORY / f"{cache_key}.pkl"
    if cache_path.exists():
        with cache_path.open("rb") as handle:
            return pickle.load(handle)
    if len(locations) > WEATHER_REQUEST_SPLIT_ROUTES:
        split_at = (len(locations) + 1) // 2
        location_items = list(locations.items())
        results = {}
        location_groups = [
            location_items[:split_at],
            location_items[split_at:],
        ]
        for group_number, location_group in enumerate(location_groups):
            results.update(
                _fetch_weather_chunk(
                    start_date,
                    end_date,
                    dict(location_group),
                    cache_only=cache_only,
                )
            )
            if group_number < len(location_groups) - 1 and not cache_only:
                time.sleep(WEATHER_REQUEST_DELAY_S)
        if not cache_only:
            WEATHER_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
            temporary_path = cache_path.with_suffix(".tmp")
            with temporary_path.open("wb") as handle:
                pickle.dump(results, handle)
            temporary_path.replace(cache_path)
        return results

    if cache_only:
        return {}

    route_locations = list(locations)
    route_points = [_route_points(lat, lon) for lat, lon in locations]
    points = [point for path in route_points for point in path]
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
        "start_date": start_date.date().isoformat(),
        "end_date": end_date.date().isoformat(),
        "hourly": "wind_speed_10m,wind_direction_10m,pressure_msl",
        "timezone": "GMT",
        "models": WEATHER_MODEL,
    }
    response = _get_json(WEATHER_API, params)
    if not isinstance(response, list) or len(response) != len(points):
        raise ValueError("ERA5 did not return one hourly response per requested route point.")

    results: dict[tuple[pd.Timestamp, float, float], dict[str, object]] = {}
    offset = 0
    for location, path in zip(route_locations, route_points, strict=True):
        point_weather = response[offset : offset + ROUTE_SAMPLE_COUNT]
        offset += ROUTE_SAMPLE_COUNT
        if not all(isinstance(item, dict) for item in point_weather):
            raise ValueError("ERA5 returned an invalid point response.")
        bearings = _sample_bearings(path)
        for event_date in locations[location]:
            metrics = _route_weather_metrics(point_weather, bearings, event_date)
            results[(event_date.normalize(), *location)] = metrics
    WEATHER_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_suffix(".tmp")
    with temporary_path.open("wb") as handle:
        pickle.dump(results, handle)
    temporary_path.replace(cache_path)
    return results


def _collect_weather_scores(
    records: pd.DataFrame, *, cache_only: bool = False
) -> pd.DataFrame:
    work = records.copy()
    work["_weather_latitude"] = work["decimalLatitude"].round(2)
    work["_weather_longitude"] = work["decimalLongitude"].round(2)
    tasks: list[
        tuple[
            pd.Timestamp,
            pd.Timestamp,
            dict[tuple[float, float], list[pd.Timestamp]],
        ]
    ] = []
    for _, year_group in work.groupby(work["date"].dt.year, sort=True):
        location_dates: dict[tuple[float, float], set[pd.Timestamp]] = {}
        for event_date, latitude, longitude in year_group[
            ["date", "_weather_latitude", "_weather_longitude"]
        ].drop_duplicates().itertuples(index=False, name=None):
            location = (float(latitude), float(longitude))
            location_dates.setdefault(location, set()).add(pd.Timestamp(event_date))
        locations = sorted(location_dates)
        start_date = pd.Timestamp(year_group["date"].min()) - pd.Timedelta(
            days=ROUTE_WEATHER_DAYS - 1
        )
        end_date = pd.Timestamp(year_group["date"].max())
        for start in range(0, len(locations), WEATHER_REQUEST_ROUTES):
            location_chunk = locations[start : start + WEATHER_REQUEST_ROUTES]
            tasks.append(
                (
                    start_date,
                    end_date,
                    {
                        location: sorted(location_dates[location])
                        for location in location_chunk
                    },
                )
            )

    scores: dict[tuple[pd.Timestamp, float, float], dict[str, object]] = {}
    total_tasks = len(tasks)
    LOGGER.info(
        "Processing %d weather batches (yearly strategy, %d locations per batch)",
        total_tasks,
        WEATHER_REQUEST_ROUTES,
    )
    for index, (start_date, end_date, locations) in enumerate(tasks, start=1):
        LOGGER.info(
            "Processing weather batch %d/%d (%d locations, %s to %s)",
            index,
            total_tasks,
            len(locations),
            start_date.date(),
            end_date.date(),
        )
        if cache_only:
            chunk_scores = _fetch_weather_chunk(
                start_date, end_date, locations, cache_only=True
            )
        else:
            chunk_scores = _fetch_weather_chunk(start_date, end_date, locations)
        scores.update(chunk_scores)
        if index < total_tasks and not cache_only:
            time.sleep(WEATHER_REQUEST_DELAY_S)

    rows = []
    for event_date, latitude, longitude in zip(
        work["date"],
        work["_weather_latitude"],
        work["_weather_longitude"],
        strict=True,
    ):
        key = (
            pd.Timestamp(event_date).normalize(),
            float(latitude),
            float(longitude),
        )
        if cache_only and key not in scores:
            rows.append({column: np.nan for column in WEATHER_SCORE_COLUMNS})
        else:
            rows.append(scores[key])
    return pd.DataFrame(rows, index=records.index)


def _fetch_feature_collection(type_name: str, *, cql_filter: str | None = None) -> list[dict[str, object]]:
    params: dict[str, object] = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_name,
        "count": "2000",
        "outputFormat": "application/json",
    }
    if cql_filter:
        params["CQL_FILTER"] = cql_filter
    result = _get_json(EMODNET_WFS, params)
    if not isinstance(result, dict) or not isinstance(result.get("features"), list):
        raise ValueError(f"EMODnet returned invalid features for {type_name}.")
    if int(result.get("numberMatched", len(result["features"]))) > len(result["features"]):
        raise ValueError(f"EMODnet feature query was truncated for {type_name}.")
    return result["features"]


def _port_frame(features: list[dict[str, object]], *, container_only: bool = False) -> pd.DataFrame:
    rows = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates")
        properties = feature.get("properties") or {}
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            continue
        longitude, latitude = map(float, coordinates[:2])
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        name = (
            properties.get("portname")
            or properties.get("port")
            or properties.get("source")
            or properties.get("port_id")
        )
        if not name:
            continue
        rows.append(
            {
                "name": str(name),
                "latitude": latitude,
                "longitude": longitude,
                "port_id": str(properties.get("port_id") or ""),
                "vessel_count": properties.get("nofvessels"),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("EMODnet port layer returned no usable port coordinates.")
    frame["_lat_key"] = frame["latitude"].round(3)
    frame["_lon_key"] = frame["longitude"].round(3)
    if container_only:
        frame = frame.drop_duplicates(["_lat_key", "_lon_key"], keep="first")
    else:
        frame = frame.drop_duplicates(["_lat_key", "_lon_key", "name"], keep="first")
    return frame.reset_index(drop=True)


def _route_density_distance(records: pd.DataFrame) -> np.ndarray:
    eastings, northings = WGS84_TO_EPSG3035.transform(
        records["decimalLongitude"].to_numpy(),
        records["decimalLatitude"].to_numpy(),
    )
    eastings = np.asarray(eastings)
    northings = np.asarray(northings)
    buffer_m = ROUTE_BUFFER_KM * 1000.0
    minimum_x = math.floor((eastings.min() - buffer_m) / 1000.0) * 1000.0
    maximum_x = math.ceil((eastings.max() + buffer_m) / 1000.0) * 1000.0
    minimum_y = math.floor((northings.min() - buffer_m) / 1000.0) * 1000.0
    maximum_y = math.ceil((northings.max() + buffer_m) / 1000.0) * 1000.0
    pixel_m = ROUTE_PIXEL_SIZE_KM * 1000.0
    width = int(math.ceil((maximum_x - minimum_x) / pixel_m))
    height = int(math.ceil((maximum_y - minimum_y) / pixel_m))
    if width > 4096 or height > 4096:
        raise ValueError("EMODnet route-density request exceeds WMS image dimensions.")
    params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetMap",
        "layers": "routedensity_allavg",
        "styles": "",
        "crs": "EPSG:3035",
        "bbox": f"{minimum_x},{minimum_y},{maximum_x},{maximum_y}",
        "width": width,
        "height": height,
        "format": "image/png",
        "transparent": "true",
    }
    request = Request(
        f"{ROUTE_DENSITY_WMS}?{urlencode(params)}",
        headers={"User-Agent": "bird-predict-second/1.0 ship-assistance-audit"},
    )
    try:
        with urlopen(request, timeout=120) as response:
            image = Image.open(response).convert("RGBA")
            image.load()
    except (OSError, URLError, HTTPError, ValueError) as error:
        raise RuntimeError("Could not retrieve EMODnet route-density map.") from error
    if image.size != (width, height):
        raise ValueError("EMODnet returned an unexpected route-density image size.")
    route_cells = np.asarray(image)[:, :, 3] > 0
    if not route_cells.any():
        raise ValueError("EMODnet route-density map contains no mapped route cells.")
    distance_km = distance_transform_edt(
        ~route_cells,
        sampling=(pixel_m / 1000.0, pixel_m / 1000.0),
    )
    columns = np.clip(
        ((eastings - minimum_x) / pixel_m).astype(int), 0, width - 1
    )
    rows = np.clip(
        ((maximum_y - northings) / pixel_m).astype(int), 0, height - 1
    )
    return distance_km[rows, columns]


def _distance_to_points(
    latitude: float,
    longitude: float,
    points: pd.DataFrame,
) -> np.ndarray:
    _, _, distance_m = GEOD.inv(
        np.full(len(points), longitude),
        np.full(len(points), latitude),
        points["longitude"].to_numpy(),
        points["latitude"].to_numpy(),
    )
    return np.asarray(distance_m) / 1000.0


def _arrival_context(records: pd.DataFrame) -> pd.DataFrame:
    species_common_months = {}
    for species, group in records.groupby("species"):
        monthly = (
            group[["date"]]
            .assign(month=lambda frame: frame["date"].dt.month)
            .groupby("month")
            .size()
            .sort_values(ascending=False, kind="stable")
        )
        selected = []
        total = int(monthly.sum())
        accumulated = 0
        for month, count in monthly.items():
            selected.append(int(month))
            accumulated += int(count)
            if accumulated / total >= 0.80:
                break
        species_common_months[species] = sorted(selected)

    rows = []
    for row in records.itertuples(index=False):
        same_day = records.loc[records["date"].eq(row.date)]
        _, _, distances = GEOD.inv(
            np.full(len(same_day), row.decimalLongitude),
            np.full(len(same_day), row.decimalLatitude),
            same_day["decimalLongitude"].to_numpy(),
            same_day["decimalLatitude"].to_numpy(),
        )
        nearby_species = int(
            same_day.loc[
                np.asarray(distances) / 1000.0 <= ISOLATION_RADIUS_KM,
                "species",
            ].nunique()
        )
        common_months = species_common_months[row.species]
        rows.append(
            {
                "simultaneous_species_within_100km": nearby_species,
                "arrival_isolation_score": 1.0 / max(nearby_species, 1),
                "species_observed_common_months": ";".join(
                    f"{month:02d}" for month in common_months
                ),
                "outside_observed_common_season": row.date.month not in common_months,
            }
        )
    return pd.DataFrame(rows, index=records.index)


def _interpret_ship_assistance(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(
        np.select(
            [
                frame["weather_support_score"].isna(),
                frame["weather_support_score"].ge(0.60),
                frame["weather_support_score"].lt(0.35)
                & frame["possible_ship_assistance_score"].ge(0.60),
            ],
            [
                "weather unavailable",
                "weather_supported",
                "possible_ship_assisted",
            ],
            default="ambiguous",
        ),
        index=frame.index,
    )


def _score_ship_assistance(frame: pd.DataFrame) -> pd.DataFrame:
    port_score = np.exp(
        -frame["nearest_requested_harbour_distance_km"] / PORT_PROXIMITY_SCALE_KM
    )
    lane_score = np.exp(
        -frame["distance_to_emodnet_route_cell_km"]
        / SHIPPING_ROUTE_PROXIMITY_SCALE_KM
    )
    container_score = np.exp(
        -frame["distance_to_container_port_km"]
        / CONTAINER_PORT_PROXIMITY_SCALE_KM
    )
    frame["shipping_exposure_score"] = 0.60 * lane_score + 0.40 * container_score
    capability = frame["species_ship_assistance_input"]
    frame["possible_ship_assistance_score"] = (
        0.25 * (1.0 - frame["weather_support_score"])
        + 0.20 * port_score
        + 0.15 * capability
        + 0.15 * frame["arrival_isolation_score"]
        + 0.15 * frame["outside_observed_common_season"].astype(float)
        + 0.10 * frame["shipping_exposure_score"]
    ).clip(0.0, 1.0)
    frame["preliminary_interpretation"] = _interpret_ship_assistance(frame)
    return frame


def deduplicate_ship_assistance_events(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse observations into species-date-rounded-location events."""
    required = {
        "species",
        "date",
        "decimalLatitude",
        "decimalLongitude",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(
            f"Ship-assistance records are missing event columns: {sorted(missing)}"
        )
    if df.empty:
        result = df.copy()
        result["event_id"] = pd.Series(dtype="string")
        result["observation_count"] = pd.Series(dtype="int64")
        return result

    events = df.copy()
    events["date"] = pd.to_datetime(events["date"], errors="raise").dt.normalize()
    events["decimalLatitude"] = pd.to_numeric(
        events["decimalLatitude"], errors="raise"
    ).round(2)
    events["decimalLongitude"] = pd.to_numeric(
        events["decimalLongitude"], errors="raise"
    ).round(2)
    if events[
        ["species", "date", "decimalLatitude", "decimalLongitude"]
    ].isna().any().any():
        raise ValueError("Ship-assistance event keys must not contain missing values.")
    if events["species"].astype("string").str.strip().eq("").any():
        raise ValueError("Ship-assistance event species must not be empty.")

    events["event_id"] = (
        events["species"].astype("string")
        + "|"
        + events["date"].dt.strftime("%Y-%m-%d")
        + "|"
        + events["decimalLatitude"].map(lambda value: f"{value:.2f}")
        + "|"
        + events["decimalLongitude"].map(lambda value: f"{value:.2f}")
    )
    prior_observation_counts = None
    if "observation_count" in events:
        prior_observation_counts = pd.to_numeric(
            events["observation_count"], errors="raise"
        )
        if prior_observation_counts.isna().any() or prior_observation_counts.lt(1).any():
            raise ValueError("Observation counts must be positive integers.")
        if not prior_observation_counts.mod(1).eq(0).all():
            raise ValueError("Observation counts must be whole numbers.")

    numeric_columns = set(events.select_dtypes(include="number").columns)
    excluded_numeric = {
        "key",
        "decimalLatitude",
        "decimalLongitude",
        "observation_count",
    }
    aggregations: dict[str, str] = {}
    for column in events.columns:
        if column in {"event_id", "observation_count"}:
            continue
        if column in numeric_columns and column not in excluded_numeric:
            aggregations[column] = "mean"
        else:
            aggregations[column] = "first"

    grouped = events.groupby("event_id", sort=False, as_index=False).agg(
        aggregations
    )
    grouped["observation_count"] = (
        events.groupby("event_id", sort=False)["observation_count"].sum().to_numpy()
        if prior_observation_counts is not None
        else events.groupby("event_id", sort=False).size().to_numpy()
    )
    grouped["decimalLatitude"] = grouped["decimalLatitude"].round(2)
    grouped["decimalLongitude"] = grouped["decimalLongitude"].round(2)
    grouped["latitude"] = grouped["decimalLatitude"]
    grouped["longitude"] = grouped["decimalLongitude"]
    if {"weather_support_score", "possible_ship_assistance_score"}.issubset(grouped):
        grouped["natural_arrival_index"] = grouped["weather_support_score"]
        grouped["preliminary_interpretation"] = _interpret_ship_assistance(grouped)
        grouped["classification"] = grouped["preliminary_interpretation"].map(
            {
                "weather_supported": "Weather-supported",
                "possible_ship_assisted": "Possible ship-assisted",
                "ambiguous": "Ambiguous",
                "weather unavailable": "weather unavailable",
            }
        )
    return grouped


def build_arrival_events(
    observation_clusters: pd.DataFrame,
    *,
    maximum_distance_km: float = 10.0,
    maximum_gap_days: int = 7,
) -> pd.DataFrame:
    """Group observation clusters into spatially and temporally coherent arrivals."""
    required = {"species", "date", "decimalLatitude", "decimalLongitude"}
    missing = required.difference(observation_clusters.columns)
    if missing:
        raise ValueError(
            f"Ship-assistance clusters are missing arrival columns: {sorted(missing)}"
        )
    if (
        "country" not in observation_clusters
        and "countryCode" not in observation_clusters
    ):
        raise ValueError(
            "Ship-assistance arrival events require a country or countryCode."
        )
    if maximum_distance_km <= 0 or maximum_gap_days < 0:
        raise ValueError(
            "Arrival-event distance must be positive and the time limit non-negative."
        )

    output_columns = [
        "arrival_event_id",
        "event_id",
        "species",
        "country",
        "countryCode",
        "first_date",
        "last_date",
        "date",
        "duration_days",
        "observation_count",
        "record_count",
        "centroid_latitude",
        "centroid_longitude",
        "decimalLatitude",
        "decimalLongitude",
        "location",
        "weather_support_score",
        "ship_assistance_score",
        "possible_ship_assistance_score",
        "preliminary_interpretation",
        "classification",
        "classification_label",
    ]
    if observation_clusters.empty:
        return pd.DataFrame(columns=output_columns)

    events = observation_clusters.copy()
    country_codes = events.get(
        "countryCode", pd.Series(pd.NA, index=events.index, dtype="string")
    ).astype("string")
    mapped_countries = country_codes.map(TARGET_COUNTRIES).fillna(country_codes)
    events["country"] = (
        events["country"].fillna(mapped_countries)
        if "country" in events
        else mapped_countries
    )
    events["date"] = pd.to_datetime(events["date"], errors="raise").dt.normalize()
    for column in ("decimalLatitude", "decimalLongitude"):
        events[column] = pd.to_numeric(events[column], errors="raise")
    if events[
        ["species", "country", "date", "decimalLatitude", "decimalLongitude"]
    ].isna().any().any():
        raise ValueError("Arrival-event keys and coordinates must not be missing.")

    def positive_integer_counts(column: str, default: int) -> pd.Series:
        values = pd.to_numeric(
            events.get(column, pd.Series(default, index=events.index)),
            errors="raise",
        )
        if (
            values.isna().any()
            or values.lt(1).any()
            or not values.mod(1).eq(0).all()
        ):
            raise ValueError(
                f"Arrival-event {column} values must be positive integers."
            )
        return values.astype("int64")

    events["observation_count"] = positive_integer_counts("observation_count", 1)
    events["record_count"] = positive_integer_counts("record_count", 1)
    for column in ("weather_support_score", "possible_ship_assistance_score"):
        if column not in events:
            events[column] = np.nan
        events[column] = pd.to_numeric(events[column], errors="raise")

    grouped_arrivals: list[dict[str, object]] = []
    maximum_distance_m = maximum_distance_km * 1000.0
    for (species, country), group in events.groupby(
        ["species", "country"], sort=True, dropna=False
    ):
        group = group.sort_values(
            ["date", "decimalLatitude", "decimalLongitude"], kind="stable"
        )
        clusters: list[dict[str, object]] = []
        for record in group.to_dict(orient="records"):
            record_date = record["date"]
            latitude = float(record["decimalLatitude"])
            longitude = float(record["decimalLongitude"])
            eligible: list[tuple[float, float, int]] = []
            for cluster_index, cluster in enumerate(clusters):
                if (record_date - cluster["first_date"]).days > maximum_gap_days:
                    continue
                members = cluster["members"]
                member_latitudes = np.array(
                    [float(member["decimalLatitude"]) for member in members]
                )
                member_longitudes = np.array(
                    [float(member["decimalLongitude"]) for member in members]
                )
                _, _, distances = GEOD.inv(
                    member_longitudes,
                    member_latitudes,
                    np.full(len(members), longitude),
                    np.full(len(members), latitude),
                )
                maximum_member_distance = float(np.max(distances))
                if maximum_member_distance > maximum_distance_m:
                    continue
                centroid_latitude = float(member_latitudes.mean())
                centroid_longitude = float(member_longitudes.mean())
                _, _, centroid_distance = GEOD.inv(
                    centroid_longitude,
                    centroid_latitude,
                    longitude,
                    latitude,
                )
                eligible.append(
                    (
                        float(centroid_distance),
                        maximum_member_distance,
                        cluster_index,
                    )
                )

            if eligible:
                _, _, selected_index = min(eligible)
                selected = clusters[selected_index]
                selected["members"].append(record)
                selected["last_date"] = record_date
            else:
                clusters.append(
                    {
                        "first_date": record_date,
                        "last_date": record_date,
                        "members": [record],
                    }
                )

        for sequence, cluster in enumerate(clusters, start=1):
            members = pd.DataFrame(cluster["members"])
            weights = members["observation_count"].astype(float)

            def weighted_mean(column: str) -> float:
                values = members[column]
                valid = values.notna()
                if not valid.any():
                    return float("nan")
                return float(np.average(values[valid], weights=weights[valid]))

            centroid_latitude = float(members["decimalLatitude"].mean())
            centroid_longitude = float(members["decimalLongitude"].mean())
            weather_score = weighted_mean("weather_support_score")
            assistance_score = weighted_mean("possible_ship_assistance_score")
            preliminary_interpretation = str(
                _interpret_ship_assistance(
                    pd.DataFrame(
                        {
                            "weather_support_score": [weather_score],
                            "possible_ship_assistance_score": [assistance_score],
                        }
                    )
                ).iloc[0]
            )
            arrival_event_id = (
                f"{species}|{country}|"
                f"{cluster['first_date']:%Y-%m-%d}|{sequence:03d}"
            )
            first_date = cluster["first_date"]
            last_date = cluster["last_date"]
            grouped_arrivals.append(
                {
                    "arrival_event_id": arrival_event_id,
                    "event_id": arrival_event_id,
                    "species": species,
                    "country": country,
                    "countryCode": members["countryCode"].dropna().iloc[0]
                    if "countryCode" in members and members["countryCode"].notna().any()
                    else pd.NA,
                    "first_date": first_date,
                    "last_date": last_date,
                    "date": first_date,
                    "duration_days": int((last_date - first_date).days) + 1,
                    "observation_count": int(members["observation_count"].sum()),
                    "record_count": int(members["record_count"].sum()),
                    "centroid_latitude": centroid_latitude,
                    "centroid_longitude": centroid_longitude,
                    "decimalLatitude": centroid_latitude,
                    "decimalLongitude": centroid_longitude,
                    "location": (
                        f"Arrival centroid {centroid_latitude:.4f}, "
                        f"{centroid_longitude:.4f}"
                    ),
                    "weather_support_score": weather_score,
                    "ship_assistance_score": assistance_score,
                    "possible_ship_assistance_score": assistance_score,
                    "preliminary_interpretation": preliminary_interpretation,
                    "classification": preliminary_interpretation,
                    "classification_label": {
                        "weather_supported": "Weather-supported",
                        "possible_ship_assisted": "Possible ship-assisted",
                        "ambiguous": "Ambiguous",
                        "weather unavailable": "weather unavailable",
                    }[preliminary_interpretation],
                }
            )

    return pd.DataFrame(grouped_arrivals, columns=output_columns).sort_values(
        ["first_date", "species", "country", "arrival_event_id"],
        kind="stable",
        ignore_index=True,
    )


def arrival_event_species_comparison(
    observation_clusters: pd.DataFrame,
    arrival_events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Summarize observation-cluster and arrival-event counts by species."""
    if arrival_events is None:
        arrival_events = build_arrival_events(observation_clusters)
    cluster_counts = observation_clusters.groupby("species").size()
    arrival_counts = arrival_events.groupby("species").size()
    species_names = list(
        dict.fromkeys(
            [
                *SPECIES_ORDER,
                *cluster_counts.index.astype(str),
                *arrival_counts.index.astype(str),
            ]
        )
    )
    rows = []
    for species in species_names:
        cluster_count = int(cluster_counts.get(species, 0))
        arrival_count = int(arrival_counts.get(species, 0))
        rows.append(
            {
                "species": species,
                "observation_cluster_count": cluster_count,
                "arrival_event_count": arrival_count,
                "reduction_pct": (
                    100.0 * (cluster_count - arrival_count) / cluster_count
                    if cluster_count
                    else float("nan")
                ),
            }
        )
    return pd.DataFrame(rows)


def _species_coverage(
    records: pd.DataFrame,
    events: pd.DataFrame,
    excluded_observations: dict[str, int] | None = None,
    *,
    weather_unavailable_events: dict[str, int] | None = None,
    allow_incomplete: bool = False,
) -> pd.DataFrame:
    species_names = [str(item["species"]) for item in ATLANTIC_VAGRANCY_SPECIES]
    if len(set(species_names)) != len(species_names):
        raise ValueError("Atlantic vagrancy registry contains duplicate species names.")
    event_counts = events.groupby("species").size()
    record_counts = records.groupby("species").size()
    dates = pd.to_datetime(records["date"], errors="raise")
    eligible_records = records.loc[dates.ge(WEATHER_ARCHIVE_START)]
    eligible_species = set(eligible_records["species"])
    missing_species = eligible_species.difference(event_counts.index)
    if missing_species and not allow_incomplete:
        raise ValueError(f"Eligible species missing from audit events: {sorted(missing_species)}")
    rows = []
    for species in species_names:
        event_count = int(event_counts.get(species, 0))
        record_count = int(record_counts.get(species, 0))
        excluded_count = int((excluded_observations or {}).get(species, 0))
        unavailable_count = int((weather_unavailable_events or {}).get(species, 0))
        if excluded_count:
            status = "partially processed" if event_count else "excluded"
            reason = (
                f"{excluded_count:,} occurrence records excluded because their "
                "ERA5 route-weather data are missing from the local cache."
            )
        elif unavailable_count:
            status = "partially processed" if event_count else "excluded"
            reason = (
                f"{unavailable_count:,} events retained with null ERA5 route-weather "
                "data and classified as weather unavailable."
            )
        elif event_count:
            status, reason = "processed", ""
        elif record_count and not eligible_records["species"].eq(species).any():
            status, reason = "skipped", "All records predate the ERA5 archive."
        else:
            status, reason = "no events", "No eligible occurrence records."
        rows.append(
            {
                "species": species,
                "events": event_count,
                "excluded_observations": excluded_count,
                "weather_unavailable_events": unavailable_count,
                "status": status,
                "reason": reason,
            }
        )
    coverage = pd.DataFrame(rows)
    audit_species_count = coverage["species"].nunique()
    assert audit_species_count == len(ATLANTIC_VAGRANCY_SPECIES)
    return coverage


def _build_summary(frame: pd.DataFrame, coverage: pd.DataFrame) -> str:
    frame = deduplicate_ship_assistance_events(frame)
    species_counts = frame.groupby("species").size().reindex(
        SPECIES_ORDER, fill_value=0
    )
    coverage_lines = [
        f"| {row.species} | {row.events} | {row.weather_unavailable_events} | "
        f"{row.excluded_observations} | {row.status} | {row.reason or '—'} |"
        for row in coverage.itertuples(index=False)
    ]
    species_events = species_counts
    top_event_lines = [
        f"| {species} | {int(count)} |"
        for species, count in species_events.nlargest(10).items()
    ]
    country_counts = frame["countryCode"].value_counts().reindex(
        TARGET_COUNTRIES, fill_value=0
    )
    country_lines = [
        f"| {TARGET_COUNTRIES[country_code]} ({country_code}) | {int(count)} |"
        for country_code, count in country_counts.items()
    ]
    candidates = frame.loc[
        frame["weather_support_score"].lt(0.35)
    ].sort_values(
        ["possible_ship_assistance_score", "weather_support_score"],
        ascending=[False, True],
        kind="stable",
    ).head(20)
    candidate_lines = [
        f"| {row.species} | {row.date:%Y-%m-%d} | {row.location} | "
        f"{row.country} | {row.weather_support_score:.2f} | "
        f"{row.possible_ship_assistance_score:.2f} | "
        f"{row.nearest_requested_harbour} ({row.nearest_requested_harbour_distance_km:.0f} km) | "
        f"{row.distance_to_emodnet_route_cell_km:.1f} | {row.observation_count} |"
        for row in candidates.itertuples(index=False)
    ]
    candidate_table = "\n".join(candidate_lines) or "| None | | | | | | | | |"
    count_text = "\n".join(coverage_lines)
    with_events = int(coverage["events"].gt(0).sum())
    skipped = int(coverage["status"].eq("skipped").sum())
    without_events = len(coverage) - with_events
    excluded_observations = int(coverage["excluded_observations"].sum())
    excluded_species = coverage.loc[coverage["excluded_observations"].gt(0)]
    weather_unavailable_events = int(
        coverage["weather_unavailable_events"].sum()
    )
    weather_unavailable_observations = int(
        frame.loc[frame["weather_support_score"].isna(), "observation_count"].sum()
    )
    return "\n".join(
        [
            "# Atlantic vagrancy ship-assistance feasibility audit",
            "",
            "## Scope",
            "",
            f"The audit contains **{len(frame):,} unique events** from "
            f"**{int(frame['observation_count'].sum()):,} GBIF observations** for "
            f"{frame['species'].nunique()} species in the project's Atlantic Vagrancy Index. "
            f"Event dates span {frame['date'].min():%Y-%m-%d} to {frame['date'].max():%Y-%m-%d}. "
            "Each event is one species, date, and location rounded to two decimal degrees. "
            "Multiple GBIF observations of the same event are merged and counted in "
            "`observation_count`.",
            "Records before 1940 are omitted because the configured ERA5 archive begins in 1940.",
            *(
                [
                    "",
                    f"**Weather unavailable:** {weather_unavailable_events:,} events "
                    f"({weather_unavailable_observations:,} GBIF observations) are retained "
                    "with null weather fields and classified as `weather unavailable`.",
                ]
                if weather_unavailable_events
                else []
            ),
            *(
                [
                    "",
                    "**Partial cache-only rebuild:** "
                    f"{excluded_observations:,} occurrence records across "
                    f"{len(excluded_species)} species were omitted because their complete "
                    "ERA5 route-weather data were not present in the local cache. No weather "
                    "requests were made during this rebuild. The species and counts are listed "
                    "in the coverage table below.",
                ]
                if excluded_observations
                else []
            ),
            "",
            "These are **screening indicators, not causal classifications or probabilities**. "
            "The audit does not build or apply a predictive model, does not identify ships, and "
            "cannot prove that any individual bird was carried by a vessel.",
            "",
            "## Weather Support Score",
            "",
            "For each dated location, ERA5 hourly 10 m wind and mean sea-level pressure are sampled "
            "at seven points on a generic great-circle route from 45°N, 55°W (eastern North America) "
            "to the occurrence coordinate, during the seven calendar days ending on the record date. "
            "Tailwind uses wind projected onto the local route bearing; the corridor score combines "
            "mean positive along-route wind and the share of samples with tailwind ≥2 m/s. Headwind "
            "intensity is the mean opposing wind component. A major low is screened at ≤1000 hPa; "
            "its strength and proximity to the arrival date contribute to the composite. The final "
            "0–1 score is `0.60 × tailwind corridor + 0.25 × storm support + 0.15 × low timing`, "
            "reduced by the opposing-wind penalty. A score of 0 means no support in these proxies; "
            "1 is the maximum heuristic support.",
            "",
            "This is a coarse surface-weather corridor, **not an air-mass trajectory or bird-flight "
            "wind**: ERA5 surface winds are used because the public API does not provide the required "
            "multi-decadal route-level upper-air trajectory in this audit. Species may travel by "
            "different routes or arrive days after a weather event.",
            "",
            "## Harbour and shipping exposure",
            "",
            "Harbour distances are geodesic distances from each occurrence coordinate to the six "
            "requested port coordinates. Nearest major commercial port is selected from the current "
            "EMODnet main-port locations layer. Container ports are ports classified as `Container "
            "ship` in the EMODnet 2025 main-port vessel-traffic layer. Shipping-route distance is "
            "the distance to the nearest mapped cell in EMODnet/EMSA's all-vessel average route-density "
            "WMS layer. The map is a recent aggregate route network, not event-date AIS. Therefore "
            "shipping exposure is a present-day geographic proxy for records from every year; the "
            "audit does not infer a contemporaneous ship position.",
            "",
            "`distance_to_offshore_transfer_area_km` is blank for every row: no consistent public "
            "offshore ship-to-ship transfer-area layer was verified for this audit. Offshore oil/gas "
            "installations are not treated as transfer areas.",
            "",
            "The shipping exposure score combines exponential proximity to the mapped route-density "
            "network (25 km scale) and to a container port (100 km scale). It is not a measure of "
            "actual vessel exposure.",
            "",
            "## Preliminary Ship Assistance Indicator",
            "",
            "The 0–1 indicator is a transparent weighted checklist, not a probability: 25% low "
            "weather support, 20% proximity to one of the six requested harbours (100 km decay), "
            "15% species capability input, 15% isolated same-day arrival (distinct species within "
            "100 km), 15% outside the species' 80%-coverage months in this project record set, and "
            "10% shipping exposure. Blackpoll Warbler receives a low ship-assistance input because "
            "non-stop transoceanic migration has been documented; other species receive neutral "
            "inputs because their trans-Atlantic capability was not quantified here. The project "
            "record months are an effort-biased seasonal proxy, not an independent migration calendar.",
            "",
            "`weather_supported` means Weather Support Score ≥0.60. `possible_ship_assisted` requires "
            "Weather Support Score <0.35 and Ship Assistance Indicator ≥0.60. Other rows are "
            "`ambiguous`. These cutoffs are descriptive triage thresholds only.",
            "",
            "## Events most difficult to explain by weather alone",
            "",
            "The following are the highest Ship Assistance Indicator events among those with "
            "Weather Support Score <0.35. They are candidates for manual review, not ship-assistance "
            "findings.",
            "",
            "| Species | Date | Location (lat, lon) | Country | Weather support | Ship indicator | Nearest requested harbour | Route-cell distance (km) | GBIF observations |",
            "|---|---|---|---|---:|---:|---|---:|---:|",
            candidate_table,
            "",
            "## Species coverage",
            "",
            f"Registry species processed: **{len(coverage)}**; with events: **{with_events}**; "
            f"without events: **{without_events}**; skipped: **{skipped}** "
            "(included among species without events).",
            "",
            "| Species | Events | Weather-unavailable events | Excluded observations | Status | Reason |",
            "|---|---:|---:|---:|---|---|",
            count_text,
            "",
            "## Rarity events",
            "",
            f"The audit contains **{int(species_events.sum()):,} events**, where one event is a "
            "unique species, date, and location rounded to two decimal degrees.",
            "",
            "### Top 10 species by event count",
            "",
            "| Species | Events |",
            "|---|---:|",
            "\n".join(top_event_lines),
            "",
            "## Country breakdown",
            "",
            "| Country | Events |",
            "|---|---:|",
            "\n".join(country_lines),
            "",
            "## Data and method sources",
            "",
            "- [Project Atlantic Vagrancy Index occurrence builder](../../src/build_atlantic_vagrancy_dataset.py): species registry, countries and GBIF filters.",
            "- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api): ERA5 hourly historical weather; global reanalysis availability from 1940 at 0.25° and API usage terms.",
            "- [EMODnet/EMSA Route Density Map metadata](https://ows.emodnet-humanactivities.eu/geonetwork/srv/api/records/74eef9c6-13fe-4630-b935-f26871c8b661): 1 km AIS-derived route-density cells, CC BY 4.0; aggregate route restoration, not live ship tracks.",
            "- [EMODnet Human Activities WFS](https://ows.emodnet-humanactivities.eu/wfs): main-port locations and vessel traffic by vessel type; the latter includes data through 2025.",
            "- [DeLuca et al. (2015), Transoceanic migration by a 12 g songbird](https://repository.si.edu/items/0f7b5206-191b-446c-a6fd-9dbd38647f90): geolocator evidence for non-stop oceanic migration by Blackpoll Warblers.",
            "",
            "## Limitations",
            "",
            "- Record locations are GBIF occurrence coordinates; they do not establish where or when a bird arrived.",
            "- GBIF observation coverage and reporting effort vary by country, year, site, species and observer.",
            "- The generic North Atlantic route and ERA5 10 m winds simplify the species-specific flight path, flight altitude, wind selection, and storm-track timing.",
            "- Port and route proximity indicate geographic opportunity only. A landfall near a port does not show the bird was aboard a vessel.",
            "- EMODnet route density is spatially aggregated and recent; its route proximity is not historically matched to an occurrence date.",
            "- The season and same-day-arrival indicators are computed from this same record set and inherit its reporting biases.",
            "",
        ]
    )


def run_audit(
    records: pd.DataFrame | None = None, *, cache_only: bool = False
) -> pd.DataFrame:
    records = (
        load_all_occurrences(ATLANTIC_VAGRANCY_SPECIES)
        if records is None
        else records.copy()
    )
    required = {
        "key",
        "date",
        "species",
        "countryCode",
        "decimalLatitude",
        "decimalLongitude",
    }
    missing = required.difference(records.columns)
    if missing:
        raise ValueError(f"Occurrence records are missing columns: {sorted(missing)}")
    records["date"] = pd.to_datetime(records["date"], errors="raise").dt.normalize()
    records["decimalLatitude"] = pd.to_numeric(records["decimalLatitude"], errors="raise")
    records["decimalLongitude"] = pd.to_numeric(records["decimalLongitude"], errors="raise")
    records = records.drop_duplicates(subset=["key"]).reset_index(drop=True)
    if not records["species"].isin(SPECIES_ORDER).all():
        raise ValueError("Occurrence records include species outside the project guild.")
    if not records["countryCode"].isin(TARGET_COUNTRIES).all():
        raise ValueError("Occurrence records include countries outside the project target set.")
    if records[["date", "decimalLatitude", "decimalLongitude"]].isna().any().any():
        raise ValueError("Occurrence records must have valid dates and coordinates.")
    unsupported_weather = records["date"].lt(WEATHER_ARCHIVE_START)
    if unsupported_weather.any():
        LOGGER.warning(
            "Omitting %s records before the ERA5 archive starts on %s",
            f"{int(unsupported_weather.sum()):,}",
            WEATHER_ARCHIVE_START.strftime("%Y-%m-%d"),
        )
        records = records.loc[~unsupported_weather].copy().reset_index(drop=True)

    if records.empty:
        raise ValueError("No occurrence records are available within the ERA5 archive.")
    records = deduplicate_ship_assistance_events(records)
    if cache_only:
        weather = _collect_weather_scores(records, cache_only=True)
    else:
        weather = _collect_weather_scores(records)
    if cache_only:
        missing_weather_count = int(weather["weather_support_score"].isna().sum())
        if missing_weather_count:
            LOGGER.warning(
                "Retaining %s events with unavailable cached ERA5 route-weather data",
                f"{missing_weather_count:,}",
            )
    context = _arrival_context(records)
    features = pd.concat([records, weather, context], axis=1)

    ports = _port_frame(_fetch_feature_collection("emodnet:portlocations"))
    container_ports = _port_frame(
        _fetch_feature_collection(
            "emodnet:portvesselsbytype",
            cql_filter="vesseltype='Container ship' AND year=2025 AND tonnage='TOTAL'",
        ),
        container_only=True,
    )
    commercial_port_names = []
    commercial_port_distances = []
    container_names = []
    container_distances = []
    harbour_distances = {name: [] for name in HARBOURS}
    for row in features.itertuples(index=False):
        port_distances = _distance_to_points(
            row.decimalLatitude, row.decimalLongitude, ports
        )
        nearest_port_index = int(np.argmin(port_distances))
        commercial_port_names.append(ports.iloc[nearest_port_index]["name"])
        commercial_port_distances.append(float(port_distances[nearest_port_index]))
        container_distance = _distance_to_points(
            row.decimalLatitude, row.decimalLongitude, container_ports
        )
        nearest_container_index = int(np.argmin(container_distance))
        container_names.append(container_ports.iloc[nearest_container_index]["name"])
        container_distances.append(float(container_distance[nearest_container_index]))
        for harbour, (latitude, longitude) in HARBOURS.items():
            harbour_point = pd.DataFrame(
                {"latitude": [latitude], "longitude": [longitude]}
            )
            harbour_distances[harbour].append(
                float(
                    _distance_to_points(
                        row.decimalLatitude, row.decimalLongitude, harbour_point
                    )[0]
                )
            )
    features["nearest_major_commercial_port"] = commercial_port_names
    features["nearest_major_commercial_port_distance_km"] = commercial_port_distances
    features["nearest_container_port"] = container_names
    features["distance_to_container_port_km"] = container_distances
    for harbour, distances in harbour_distances.items():
        features[f"distance_to_{harbour.lower()}_km"] = distances
    harbour_columns = [f"distance_to_{name.lower()}_km" for name in HARBOURS]
    harbour_matrix = features[harbour_columns].to_numpy()
    nearest_harbour_indices = harbour_matrix.argmin(axis=1)
    features["nearest_requested_harbour"] = [
        list(HARBOURS)[index] for index in nearest_harbour_indices
    ]
    features["nearest_requested_harbour_distance_km"] = harbour_matrix.min(axis=1)

    features["distance_to_emodnet_route_cell_km"] = _route_density_distance(features)
    features["distance_to_offshore_transfer_area_km"] = np.nan
    features["offshore_transfer_area_data_available"] = False
    species_inputs = pd.DataFrame.from_dict(
        SPECIES_SHIP_ASSISTANCE_INPUT, orient="index"
    )
    features["species_ship_assistance_input"] = features["species"].map(
        species_inputs["score"]
    )
    features["species_transatlantic_capability_note"] = features["species"].map(
        species_inputs["description"]
    )
    features = _score_ship_assistance(features)
    features["location"] = features.apply(
        lambda row: f"{row['decimalLatitude']:.5f}, {row['decimalLongitude']:.5f}",
        axis=1,
    )
    features["country"] = features["countryCode"].map(TARGET_COUNTRIES)
    columns = [
        "key",
        "observation_count",
        "species",
        "date",
        "location",
        "country",
        "countryCode",
        "decimalLatitude",
        "decimalLongitude",
        "transatlantic_tailwind_corridor_present",
        "tailwind_corridor_fraction",
        "tailwind_corridor_score",
        "mean_headwind_intensity_m_s",
        "minimum_route_pressure_hpa",
        "major_low_pressure_on_route",
        "days_before_arrival_of_min_pressure",
        "storm_track_support_score",
        "arrival_timing_relative_to_low_score",
        "weather_support_score",
        *harbour_columns,
        "nearest_requested_harbour",
        "nearest_requested_harbour_distance_km",
        "nearest_major_commercial_port",
        "nearest_major_commercial_port_distance_km",
        "distance_to_emodnet_route_cell_km",
        "nearest_container_port",
        "distance_to_container_port_km",
        "distance_to_offshore_transfer_area_km",
        "offshore_transfer_area_data_available",
        "shipping_exposure_score",
        "species_ship_assistance_input",
        "species_transatlantic_capability_note",
        "simultaneous_species_within_100km",
        "arrival_isolation_score",
        "species_observed_common_months",
        "outside_observed_common_season",
        "possible_ship_assistance_score",
        "preliminary_interpretation",
    ]
    observations = features[columns].sort_values(
        ["date", "species", "key"], kind="stable"
    ).reset_index(drop=True)
    return deduplicate_ship_assistance_events(observations)


def _species_weather_support(events: pd.DataFrame) -> pd.DataFrame:
    events = deduplicate_ship_assistance_events(events)
    grouped = events.groupby("species")
    metrics = grouped.agg(
        event_count=("event_id", "size"),
        observation_count=("observation_count", "sum"),
        unique_event_days=("date", "nunique"),
        mean_weather_support_score=("weather_support_score", "mean"),
        median_weather_support_score=("weather_support_score", "median"),
        p95_weather_support_score=("weather_support_score", lambda values: values.quantile(0.95)),
        max_weather_support_score=("weather_support_score", "max"),
        mean_tailwind_corridor_score=("tailwind_corridor_score", "mean"),
        mean_storm_track_support_score=("storm_track_support_score", "mean"),
        mean_possible_ship_assistance_score=("possible_ship_assistance_score", "mean"),
    ).reindex(SPECIES_ORDER)
    for label, column in (
        ("weather_supported", "weather_supported_pct"),
        ("possible_ship_assisted", "possible_ship_assisted_pct"),
        ("ambiguous", "ambiguous_pct"),
        ("weather unavailable", "weather_unavailable_pct"),
    ):
        metrics[column] = grouped["preliminary_interpretation"].apply(
            lambda values: 100.0 * values.eq(label).mean()
        )
    metrics["natural_arrival_index"] = metrics["mean_weather_support_score"]
    metrics["ship_assistance_index"] = metrics["mean_possible_ship_assistance_score"]
    metrics["natural_arrival_rank"] = metrics["natural_arrival_index"].rank(
        ascending=False, method="min"
    ).astype("Int64")
    metrics["ship_assistance_rank"] = metrics["ship_assistance_index"].rank(
        ascending=False, method="min"
    ).astype("Int64")
    for column in ("event_count", "observation_count", "unique_event_days"):
        metrics[column] = metrics[column].fillna(0).astype(int)
    metrics.index.name = "species"
    return metrics.reset_index()[
        [
            "species", "event_count", "observation_count", "unique_event_days",
            "mean_weather_support_score", "median_weather_support_score",
            "p95_weather_support_score", "max_weather_support_score",
            "mean_tailwind_corridor_score", "mean_storm_track_support_score",
            "weather_supported_pct", "possible_ship_assisted_pct", "ambiguous_pct",
            "weather_unavailable_pct",
            "natural_arrival_index", "mean_possible_ship_assistance_score",
            "ship_assistance_index", "natural_arrival_rank", "ship_assistance_rank",
        ]
    ]


def _weather_support_summary(
    metrics: pd.DataFrame,
    events: pd.DataFrame,
    coverage: pd.DataFrame | None = None,
) -> str:
    ranked = metrics.loc[metrics["event_count"].gt(0)].sort_values(
        "natural_arrival_rank", kind="stable"
    )
    lines = [
        f"| {row.species} | {row.event_count} | {row.observation_count} | "
        f"{row.natural_arrival_index:.3f} | {row.ship_assistance_index:.3f} | "
        f"{row.weather_supported_pct:.2f}% | {row.possible_ship_assisted_pct:.2f}% | "
        f"{row.ambiguous_pct:.2f}% | {row.weather_unavailable_pct:.2f}% |"
        for row in ranked.itertuples(index=False)
    ]
    ship_ranked = ranked.sort_values("ship_assistance_rank", kind="stable")
    ship_lines = [
        f"| {row.ship_assistance_rank} | {row.species} | {row.ship_assistance_index:.3f} | "
        f"{row.possible_ship_assisted_pct:.2f}% | {row.event_count} | {row.observation_count} |"
        for row in ship_ranked.itertuples(index=False)
    ]
    excluded_observations = (
        int(coverage["excluded_observations"].sum())
        if coverage is not None
        else 0
    )
    weather_unavailable_events = (
        int(coverage["weather_unavailable_events"].sum())
        if coverage is not None
        else 0
    )
    exclusion_note = (
        [
            "",
            f"**Partial cache-only rebuild:** {excluded_observations:,} occurrence "
            "records without cached ERA5 weather were excluded. See the ship-assistance "
            "summary coverage table for species-level counts and reasons.",
        ]
        if excluded_observations
        else []
    )
    weather_unavailable_note = (
        [
            "",
            f"**Weather unavailable:** {weather_unavailable_events:,} events are retained "
            "with null weather fields and included in the species coverage table.",
        ]
        if weather_unavailable_events
        else []
    )
    return "\n".join(
        [
            "# Atlantic species-level weather support",
            "",
            f"Computed from {len(events):,} deduplicated events for "
            f"{len(ranked)} of {len(metrics)} registry species. Species without events "
            "are included in the CSV with zero counts and blank scores and ranks.",
            "",
            "The Natural Arrival Index is the mean event-level weather support score; "
            "the Ship Assistance Index is the mean event-level ship assistance score. "
            "Classification percentages use events, not observations, as the denominator. "
            "Weather-unavailable events are retained and reported separately.",
            "These indicators are screening heuristics, not probabilities or evidence of causation.",
            *exclusion_note,
            *weather_unavailable_note,
            "",
            "## Most ship-assistance-associated species",
            "",
            "| Rank | Species | Ship assistance index | Possible ship-assisted | Events | Observations |",
            "|---:|---|---:|---:|---:|---:|",
            *ship_lines,
            "",
            "## Species weather support",
            "",
            "| Species | Events | Observations | Natural arrival index | Ship assistance index | Weather-supported | Possible ship-assisted | Ambiguous | Weather unavailable |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            *lines,
            "",
        ]
    )


def main(*, cache_only: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    records = load_all_occurrences(ATLANTIC_VAGRANCY_SPECIES)
    records = records.drop_duplicates(subset=["key"]).reset_index(drop=True)
    if cache_only:
        result = run_audit(records, cache_only=True)
    else:
        result = run_audit(records)
    included_observations = result.groupby("species")["observation_count"].sum()
    record_dates = pd.to_datetime(records["date"], errors="raise")
    eligible_records = records.loc[record_dates.ge(WEATHER_ARCHIVE_START)]
    eligible_counts = eligible_records.groupby("species").size()
    excluded_observations = {
        species: int(
            eligible_counts.get(species, 0)
            - included_observations.get(species, 0)
        )
        for species in SPECIES_ORDER
    }
    weather_unavailable_events = (
        result.loc[result["weather_support_score"].isna()]
        .groupby("species")
        .size()
        .astype(int)
        .to_dict()
    )
    coverage = _species_coverage(
        records,
        result,
        excluded_observations if cache_only else None,
        weather_unavailable_events=weather_unavailable_events,
        allow_incomplete=cache_only,
    )
    arrival_events = build_arrival_events(result)
    arrival_comparison = arrival_event_species_comparison(
        result, arrival_events
    )
    weather_support = _species_weather_support(result)
    audit_species_count = weather_support["species"].nunique()
    assert audit_species_count == len(ATLANTIC_VAGRANCY_SPECIES)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    result.to_csv(AUDIT_OUTPUT, index=False, date_format="%Y-%m-%d")
    result.to_csv(EVENTS_OUTPUT, index=False, date_format="%Y-%m-%d")
    arrival_events.to_csv(
        ARRIVAL_EVENTS_OUTPUT, index=False, date_format="%Y-%m-%d"
    )
    arrival_comparison.to_csv(ARRIVAL_EVENT_COMPARISON_OUTPUT, index=False)
    SUMMARY_OUTPUT.write_text(_build_summary(result, coverage), encoding="utf-8")
    weather_support.to_csv(WEATHER_SUPPORT_OUTPUT, index=False)
    coverage.to_csv(COVERAGE_OUTPUT, index=False)
    WEATHER_SUPPORT_SUMMARY_OUTPUT.write_text(
        _weather_support_summary(weather_support, result, coverage), encoding="utf-8"
    )
    print(
        f"Wrote {AUDIT_OUTPUT.relative_to(ROOT)} "
        f"({len(result):,} events from {int(result['observation_count'].sum()):,} observations)"
    )
    print(
        f"Wrote {ARRIVAL_EVENTS_OUTPUT.relative_to(ROOT)} "
        f"({len(arrival_events):,} arrival events from {len(result):,} observation clusters)"
    )
    print(f"Wrote {ARRIVAL_EVENT_COMPARISON_OUTPUT.relative_to(ROOT)}")
    print(
        arrival_comparison.loc[
            arrival_comparison["observation_cluster_count"].gt(0)
        ].to_string(index=False)
    )
    print(f"Wrote {SUMMARY_OUTPUT.relative_to(ROOT)}")
    print(
        result.nlargest(10, "possible_ship_assistance_score")[
            [
                "species",
                "date",
                "observation_count",
                "country",
                "weather_support_score",
                "possible_ship_assistance_score",
                "preliminary_interpretation",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Use existing ERA5 cache only and report events missing cached weather.",
    )
    main(cache_only=parser.parse_args().cache_only)
