"""Downscale national Yellow-browed Warbler forecasts to 10 km grid cells."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from pyproj import Transformer


logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
GBIF_SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"
LOCATION_OCCURRENCES_FILE = (
    ROOT / "data/cache/yellow_browed_warbler_locations.csv"
)
LOCATION_FORECAST_FILE = ROOT / "outputs/yellow_browed_location_forecast.csv"
NATIONAL_HISTORY_FILE = (
    ROOT / "data/processed/yellow_browed_warbler_daily_counts.csv"
)
GBIF_TAXON_KEY = 2493095
COUNTRY_CODE = "NL"
PAGE_SIZE = 300
PAGE_TIMEOUT_SECONDS = 60
MAX_REQUEST_RETRIES = 3
CACHE_MAX_AGE_DAYS = 30
GRID_SIZE_METERS = 10_000
DAY_OF_YEAR_WINDOW = 7
EUROPEAN_NETHERLANDS_BOUNDS = {
    "min_latitude": 50.6,
    "max_latitude": 53.8,
    "min_longitude": 3.1,
    "max_longitude": 7.3,
}
WGS84_TO_RD = Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True)
RD_TO_WGS84 = Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True)


def _gbif_query_url(*, limit: int, offset: int = 0) -> str:
    query = urlencode(
        {
            "taxonKey": GBIF_TAXON_KEY,
            "country": COUNTRY_CODE,
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",
            "limit": limit,
            "offset": offset,
        }
    )
    return f"{GBIF_SEARCH_URL}?{query}"


def _request_json(url: str) -> dict[str, object]:
    request = Request(
        url,
        headers={"User-Agent": "Bird-Predict/1.0 (GBIF occurrence cache)"},
    )
    logger.info(
        "Requesting GBIF Occurrence Search API URL %s (timeout=%ss)",
        url,
        PAGE_TIMEOUT_SECONDS,
    )
    try:
        with urlopen(request, timeout=PAGE_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
            logger.info(
                "Received GBIF response with HTTP status %s", response.status
            )
    except HTTPError as error:
        logger.exception("GBIF request failed with HTTP status %s", error.code)
        raise RuntimeError(
            f"GBIF Occurrence Search API returned HTTP {error.code}."
        ) from error
    except URLError as error:
        logger.exception("Could not reach the GBIF Occurrence Search API")
        raise RuntimeError(
            f"Could not reach the GBIF Occurrence Search API: {error}"
        ) from error
    except TimeoutError:
        logger.exception(
            "GBIF request timed out after %s seconds", PAGE_TIMEOUT_SECONDS
        )
        raise
    except json.JSONDecodeError as error:
        logger.exception("GBIF returned invalid JSON")
        raise ValueError("GBIF returned invalid JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError("GBIF returned an unexpected JSON response.")
    return payload


def _request_json_with_retries(
    url: str, *, page_number: int | None
) -> tuple[dict[str, object], float]:
    page_label = str(page_number) if page_number is not None else "count query"
    elapsed_total = 0.0
    total_attempts = MAX_REQUEST_RETRIES + 1
    for attempt in range(1, total_attempts + 1):
        started_at = perf_counter()
        try:
            payload = _request_json(url)
        except (RuntimeError, TimeoutError, ValueError) as error:
            elapsed = perf_counter() - started_at
            elapsed_total += elapsed
            logger.warning(
                "GBIF request failed: URL=%s page=%s attempt=%s/%s "
                "elapsed=%.2fs error=%s",
                url,
                page_label,
                attempt,
                total_attempts,
                elapsed,
                error,
            )
            if page_number is not None:
                print(
                    f"Request for page {page_number} failed "
                    f"(attempt {attempt} of {total_attempts}): {error}"
                )
            else:
                print(
                    f"GBIF count request failed "
                    f"(attempt {attempt} of {total_attempts}): {error}"
                )
            if attempt == total_attempts:
                raise
        else:
            elapsed = perf_counter() - started_at
            elapsed_total += elapsed
            logger.info(
                "GBIF request completed: URL=%s page=%s attempt=%s/%s "
                "elapsed=%.2fs",
                url,
                page_label,
                attempt,
                total_attempts,
                elapsed,
            )
            return payload, elapsed_total

    raise RuntimeError("GBIF request attempts exhausted unexpectedly.")


def download_location_occurrences(
    output_path: Path = LOCATION_OCCURRENCES_FILE,
) -> pd.DataFrame:
    """Fetch all coordinate-bearing GBIF records and cache their location/date."""
    download_started_at = perf_counter()
    count_url = _gbif_query_url(limit=0)
    count_payload, _ = _request_json_with_retries(count_url, page_number=None)
    record_count = count_payload.get("count")
    if not isinstance(record_count, int) or record_count < 0:
        raise ValueError("GBIF returned an invalid occurrence count.")

    page_count = math.ceil(record_count / PAGE_SIZE)
    records_downloaded = 0
    pages_attempted: set[int] = set()
    page_request_elapsed = 0.0
    columns = [
        "eventDate",
        "decimalLatitude",
        "decimalLongitude",
        "coordinateUncertaintyInMeters",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.is_file() and output_path.stat().st_size > 0:
        cached_observations = pd.read_csv(output_path)
        if cached_observations.columns.tolist() != columns:
            raise ValueError("GBIF location cache has an unexpected format.")
        cached_records = len(cached_observations)
    else:
        cached_observations = pd.DataFrame(columns=columns)
        cached_records = 0

    if cached_records > record_count:
        raise RuntimeError(
            "GBIF location cache contains more records than GBIF reports."
        )

    completed_pages = min(cached_records // PAGE_SIZE, page_count)
    if cached_records == record_count:
        completed_pages = page_count
    completed_records = min(completed_pages * PAGE_SIZE, record_count)
    if cached_records != completed_records:
        cached_observations.iloc[:completed_records].to_csv(
            output_path, index=False
        )
        cached_records = completed_records
    elif not output_path.is_file() or output_path.stat().st_size == 0:
        cached_observations.to_csv(output_path, index=False)

    print(
        f"GBIF total record count: {record_count}; page size: {PAGE_SIZE}; "
        f"total pages: {page_count}"
    )
    print(f"Cached records: {cached_records}")
    print(f"Completed pages: {completed_pages}")
    print(f"Remaining pages: {page_count - completed_pages}")
    try:
        with output_path.open("a", encoding="utf-8", newline="") as cache_file:
            for page_number, offset in enumerate(
                range(completed_pages * PAGE_SIZE, record_count, PAGE_SIZE),
                start=completed_pages + 1,
            ):
                print(f"Downloading page {page_number} of {page_count}")
                page_url = _gbif_query_url(limit=PAGE_SIZE, offset=offset)
                pages_attempted.add(page_number)
                page, elapsed = _request_json_with_retries(
                    page_url, page_number=page_number
                )
                page_request_elapsed += elapsed
                if page.get("count") != record_count:
                    raise RuntimeError(
                        "GBIF occurrence count changed during pagination; "
                        "retry the location forecast."
                    )
                results = page.get("results")
                if not isinstance(results, list):
                    raise ValueError("GBIF returned an invalid occurrence page.")

                page_records: list[dict[str, object]] = []
                for result in results:
                    if not isinstance(result, dict):
                        raise ValueError("GBIF returned a malformed occurrence.")
                    page_records.append(
                        {
                            "eventDate": result.get("eventDate"),
                            "decimalLatitude": result.get("decimalLatitude"),
                            "decimalLongitude": result.get("decimalLongitude"),
                            "coordinateUncertaintyInMeters": result.get(
                                "coordinateUncertaintyInMeters"
                            ),
                        }
                    )

                page_observations = pd.DataFrame.from_records(
                    page_records, columns=columns
                )
                page_observations.to_csv(
                    cache_file,
                    index=False,
                    header=False,
                )
                cache_file.flush()
                records_downloaded += len(page_records)
                saved_records = cached_records + records_downloaded
                print(
                    f"Downloaded {saved_records} of {record_count} records"
                )
                logger.info(
                    "Downloaded %s of %s GBIF records after page %s of %s",
                    saved_records,
                    record_count,
                    page_number,
                    page_count,
                )
    finally:
        total_runtime = perf_counter() - download_started_at
        average_page_time = (
            page_request_elapsed / len(pages_attempted)
            if pages_attempted
            else 0.0
        )
        cache_size = output_path.stat().st_size if output_path.is_file() else 0
        saved_records = cached_records + records_downloaded
        print(
            f"GBIF download summary: downloaded {saved_records} of "
            f"{record_count} records; cache={output_path}; "
            f"cache size={cache_size} bytes; saved records={saved_records}; "
            f"total runtime={total_runtime:.2f}s; "
            f"average time per page={average_page_time:.2f}s"
        )
        logger.info(
            "GBIF download summary: downloaded=%s total=%s pages=%s "
            "cache=%s cache_size=%s bytes saved_records=%s "
            "total_runtime=%.2fs average_time_per_page=%.2fs",
            saved_records,
            record_count,
            page_count,
            output_path,
            cache_size,
            saved_records,
            total_runtime,
            average_page_time,
        )

    saved_records = cached_records + records_downloaded
    if saved_records != record_count:
        raise RuntimeError(
            f"GBIF returned {saved_records:,} of {record_count:,} "
            "requested coordinate-bearing records."
        )

    return pd.read_csv(output_path)


def load_location_occurrences(
    path: Path = LOCATION_OCCURRENCES_FILE,
) -> pd.DataFrame:
    """Load the cached GBIF locations, refreshing the cache when it is stale."""
    cache_is_stale = (
        not path.is_file()
        or (
            datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
            > CACHE_MAX_AGE_DAYS * 24 * 60 * 60
        )
    )
    if cache_is_stale:
        return download_location_occurrences(path)
    return pd.read_csv(path)


def _calendar_day_numbers(dates: pd.Series) -> np.ndarray:
    return pd.to_datetime(
        "2000-" + dates.dt.strftime("%m-%d"), errors="raise"
    ).dt.dayofyear.to_numpy()


def _calendar_day_number(day: pd.Timestamp) -> int:
    return int(pd.Timestamp(year=2000, month=day.month, day=day.day).dayofyear)


def _day_distance(first: np.ndarray, second: int) -> np.ndarray:
    distance = np.abs(first - second)
    return np.minimum(distance, 366 - distance)


def _prepare_occurrences(observations: pd.DataFrame) -> pd.DataFrame:
    required = {
        "eventDate",
        "decimalLatitude",
        "decimalLongitude",
        "coordinateUncertaintyInMeters",
    }
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(
            f"Location occurrences are missing columns: {sorted(missing)}"
        )

    source_dates = observations["eventDate"].astype("string").str.strip()
    has_full_date = source_dates.str.match(r"^\d{4}-\d{2}-\d{2}", na=False)
    dates = pd.to_datetime(
        source_dates.str.slice(0, 10),
        format="%Y-%m-%d",
        errors="coerce",
    )
    latitude = pd.to_numeric(observations["decimalLatitude"], errors="coerce")
    longitude = pd.to_numeric(observations["decimalLongitude"], errors="coerce")
    uncertainty = pd.to_numeric(
        observations["coordinateUncertaintyInMeters"], errors="coerce"
    )
    bounds = EUROPEAN_NETHERLANDS_BOUNDS
    valid = (
        has_full_date
        & dates.notna()
        & latitude.between(bounds["min_latitude"], bounds["max_latitude"])
        & longitude.between(bounds["min_longitude"], bounds["max_longitude"])
        & (uncertainty.isna() | uncertainty.between(0, GRID_SIZE_METERS))
    )
    result = pd.DataFrame(
        {
            "date": dates.loc[valid],
            "latitude": latitude.loc[valid],
            "longitude": longitude.loc[valid],
        }
    ).reset_index(drop=True)
    if result.empty:
        raise ValueError(
            "GBIF location data contains no dated, usable coordinates in "
            "European Netherlands."
        )

    eastings, northings = WGS84_TO_RD.transform(
        result["longitude"].to_numpy(),
        result["latitude"].to_numpy(),
    )
    result["grid_easting"] = (
        np.floor(np.asarray(eastings) / GRID_SIZE_METERS).astype(int)
        * GRID_SIZE_METERS
    )
    result["grid_northing"] = (
        np.floor(np.asarray(northings) / GRID_SIZE_METERS).astype(int)
        * GRID_SIZE_METERS
    )
    result["cell_id"] = (
        result["grid_easting"].astype(str)
        + "-"
        + result["grid_northing"].astype(str)
    )
    result["year"] = result["date"].dt.year
    result["calendar_day"] = _calendar_day_numbers(result["date"])
    return result


def _logit(probability: float) -> float:
    bounded = min(max(probability, 1e-9), 1 - 1e-9)
    return math.log(bounded / (1 - bounded))


def _expit(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1 + exp_value)


def _prepare_national_history(history: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "record_count"}
    missing = required.difference(history.columns)
    if missing:
        raise ValueError(
            f"National history is missing columns: {sorted(missing)}"
        )
    result = history.loc[:, ["date", "record_count"]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result["record_count"] = pd.to_numeric(
        result["record_count"], errors="coerce"
    )
    if (
        result["date"].isna().any()
        or result["date"].duplicated().any()
        or result["record_count"].isna().any()
        or not np.isfinite(result["record_count"]).all()
        or result["record_count"].lt(0).any()
    ):
        raise ValueError(
            "National history must contain unique valid dates and "
            "non-negative record counts."
        )
    result["year"] = result["date"].dt.year
    result["calendar_day"] = _calendar_day_numbers(result["date"])
    return result


def calculate_location_forecast(
    observations: pd.DataFrame,
    national_history: pd.DataFrame,
    national_forecast: pd.DataFrame,
    target_threshold: int,
) -> pd.DataFrame:
    """Calculate observed-cell seasonal baselines and nationally adjusted risk."""
    if target_threshold < 1:
        raise ValueError("The national target threshold must be positive.")
    required_forecast = {"date", "probability"}
    missing = required_forecast.difference(national_forecast.columns)
    if missing:
        raise ValueError(
            f"National forecast is missing columns: {sorted(missing)}"
        )

    forecast = national_forecast.loc[:, ["date", "probability"]].copy()
    forecast["date"] = pd.to_datetime(forecast["date"], errors="coerce").dt.normalize()
    forecast["probability"] = pd.to_numeric(
        forecast["probability"], errors="coerce"
    )
    if (
        forecast.empty
        or forecast["date"].isna().any()
        or forecast["date"].duplicated().any()
        or forecast["probability"].isna().any()
        or not forecast["probability"].between(0, 1).all()
    ):
        raise ValueError(
            "National forecast must contain unique dates and probabilities "
            "between zero and one."
        )

    spatial = _prepare_occurrences(observations)
    history = _prepare_national_history(national_history)
    forecast_rows: list[pd.DataFrame] = []
    for target in forecast.itertuples(index=False):
        target_date = pd.Timestamp(target.date)
        target_year = target_date.year
        target_calendar_day = _calendar_day_number(target_date)
        spatial_history = spatial.loc[spatial["year"].lt(target_year)]
        national_dates = history.loc[history["year"].lt(target_year)]
        if spatial_history.empty or national_dates.empty:
            raise ValueError(
                f"Insufficient earlier-year history for target date "
                f"{target_date.date()}."
            )

        spatial_window = spatial_history.loc[
            _day_distance(
                spatial_history["calendar_day"].to_numpy(),
                target_calendar_day,
            )
            <= DAY_OF_YEAR_WINDOW
        ]
        national_window = national_dates.loc[
            _day_distance(
                national_dates["calendar_day"].to_numpy(),
                target_calendar_day,
            )
            <= DAY_OF_YEAR_WINDOW
        ]
        if national_window.empty:
            raise ValueError(
                f"No national seasonal history for target date "
                f"{target_date.date()}."
            )

        history_year_count = int(spatial_history["year"].nunique())
        successful_years = (
            spatial_window.groupby("cell_id")["year"]
            .nunique()
            .rename("cell_success_years")
        )
        cells = (
            spatial_history.drop_duplicates("cell_id")
            .loc[
                :,
                ["cell_id", "grid_easting", "grid_northing"],
            ]
            .set_index("cell_id")
        )
        cells = cells.join(successful_years, how="left")
        cells["cell_success_years"] = (
            cells["cell_success_years"].fillna(0).astype(int)
        )
        cells["baseline_history_years"] = history_year_count
        cells["expected_probability"] = (
            cells["cell_success_years"] + 0.5
        ) / (history_year_count + 1)

        national_successes = int(
            national_window["record_count"].ge(target_threshold).sum()
        )
        national_expected = (national_successes + 0.5) / (
            len(national_window) + 1
        )
        national_probability = float(target.probability)
        log_odds_shift = _logit(national_probability) - _logit(
            national_expected
        )
        cells["forecast_probability"] = cells["expected_probability"].map(
            lambda probability: _expit(_logit(float(probability)) + log_odds_shift)
        )
        cells["anomaly_score"] = (
            cells["forecast_probability"] - cells["expected_probability"]
        )
        cells["date"] = target_date
        cells["national_forecast_probability"] = national_probability
        cells["national_expected_probability"] = national_expected

        centers_easting = cells["grid_easting"].to_numpy() + GRID_SIZE_METERS / 2
        centers_northing = cells["grid_northing"].to_numpy() + GRID_SIZE_METERS / 2
        longitudes, latitudes = RD_TO_WGS84.transform(
            centers_easting, centers_northing
        )
        cells["center_longitude"] = longitudes
        cells["center_latitude"] = latitudes
        forecast_rows.append(cells.reset_index())

    result = pd.concat(forecast_rows, ignore_index=True)
    columns = [
        "date",
        "cell_id",
        "grid_easting",
        "grid_northing",
        "center_latitude",
        "center_longitude",
        "expected_probability",
        "forecast_probability",
        "anomaly_score",
        "cell_success_years",
        "baseline_history_years",
        "national_expected_probability",
        "national_forecast_probability",
    ]
    return result.loc[:, columns].sort_values(
        ["date", "cell_id"], kind="stable"
    ).reset_index(drop=True)


def build_location_forecast(
    national_forecast: pd.DataFrame,
    artifact: dict[str, object],
    *,
    output_path: Path = LOCATION_FORECAST_FILE,
    occurrence_path: Path = LOCATION_OCCURRENCES_FILE,
    national_history_path: Path = NATIONAL_HISTORY_FILE,
) -> pd.DataFrame:
    """Load histories, calculate location forecasts, and write the CSV output."""
    threshold = artifact.get("target_threshold")
    if not isinstance(threshold, int) or threshold < 1:
        raise ValueError("Model artifact has an invalid target threshold.")
    if not national_history_path.is_file():
        raise FileNotFoundError(
            f"National history not found: {national_history_path}"
        )
    observations = load_location_occurrences(occurrence_path)
    history = pd.read_csv(national_history_path)
    location_forecast = calculate_location_forecast(
        observations, history, national_forecast, threshold
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    location_forecast.to_csv(
        output_path, index=False, date_format="%Y-%m-%d"
    )
    return location_forecast


def cell_polygon(grid_easting: int, grid_northing: int) -> list[list[float]]:
    """Return a 10 km EPSG:28992 grid square as closed WGS84 coordinates."""
    east = float(grid_easting)
    north = float(grid_northing)
    x = [
        east,
        east + GRID_SIZE_METERS,
        east + GRID_SIZE_METERS,
        east,
        east,
    ]
    y = [
        north,
        north,
        north + GRID_SIZE_METERS,
        north + GRID_SIZE_METERS,
        north,
    ]
    longitudes, latitudes = RD_TO_WGS84.transform(x, y)
    return [
        [float(longitude), float(latitude)]
        for longitude, latitude in zip(longitudes, latitudes)
    ]
