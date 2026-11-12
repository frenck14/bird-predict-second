"""Strict cutoff hindcasts for historical Seabird forecasts."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

if __package__:
    from .build_atlantic_vagrancy_dataset import (
        CACHE_READ_CHUNK_ROWS,
        CACHE_READ_COLUMNS,
        TARGET_COUNTRIES,
        _cache_path,
        filter_occurrences,
    )
    from .build_dataset_v2 import STATION_FILES, WEATHER_VARIABLES
    from .build_seabird_dataset import OCCURRENCE_YEAR_RANGE, SEABIRD_SPECIES
    from .train_seabird_model import WEATHER_FILE
else:
    from build_atlantic_vagrancy_dataset import (
        CACHE_READ_CHUNK_ROWS,
        CACHE_READ_COLUMNS,
        TARGET_COUNTRIES,
        _cache_path,
        filter_occurrences,
    )
    from build_dataset_v2 import STATION_FILES, WEATHER_VARIABLES
    from build_seabird_dataset import OCCURRENCE_YEAR_RANGE, SEABIRD_SPECIES
    from train_seabird_model import WEATHER_FILE


FORECAST_DAYS = 14


def load_historical_weather(path: Path = WEATHER_FILE) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Historical weather data not found: {path}")
    weather = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
    weather_columns = [
        "date",
        *(
            f"{variable}_{station_id}"
            for variable in WEATHER_VARIABLES
            for station_id in STATION_FILES
        ),
    ]
    missing_columns = set(weather_columns).difference(weather.columns)
    if missing_columns:
        raise ValueError(
            f"Historical weather is missing columns: {sorted(missing_columns)}"
        )
    weather = weather.loc[:, weather_columns]
    weather["date"] = pd.to_datetime(weather["date"], errors="raise").dt.normalize()
    if weather.empty or weather["date"].isna().any() or weather["date"].duplicated().any():
        raise ValueError("Historical weather must contain unique, valid daily dates.")
    return weather.reset_index(drop=True)


def analysis_date_bounds(weather: pd.DataFrame) -> tuple[date, date]:
    dates = pd.DatetimeIndex(pd.to_datetime(weather["date"]).dt.normalize())
    earliest = dates.min().date()
    latest = dates.max().date()
    if latest < earliest:
        raise ValueError("Historical weather contains no valid dates.")
    return earliest, latest


def load_cached_occurrences() -> pd.DataFrame:
    frames = []
    for species in SEABIRD_SPECIES:
        common_name = str(species["species"])
        scientific_name = str(species["scientific_name"])
        for country_code in TARGET_COUNTRIES:
            path = _cache_path(
                scientific_name, country_code, OCCURRENCE_YEAR_RANGE
            )
            if not path.is_file():
                raise FileNotFoundError(
                    f"Cached seabird occurrence data not found: {path}. "
                    "Build the seabird dataset before running a backtest."
                )
            taxon_counts: Counter[int] = Counter()
            chunks = pd.read_csv(
                path,
                usecols=lambda column: column in CACHE_READ_COLUMNS,
                low_memory=False,
                chunksize=CACHE_READ_CHUNK_ROWS,
            )
            for raw in chunks:
                matching_name = (
                    raw["scientificName"]
                    .astype("string")
                    .str.split("(", n=1)
                    .str[0]
                    .str.strip()
                    .eq(scientific_name)
                )
                key_counts = pd.to_numeric(
                    raw.loc[matching_name, "taxonKey"], errors="coerce"
                ).dropna().astype(int).value_counts()
                taxon_counts.update(key_counts.to_dict())
            if not taxon_counts:
                continue
            ranked_keys = taxon_counts.most_common()
            if len(ranked_keys) > 1 and ranked_keys[0][1] == ranked_keys[1][1]:
                raise ValueError(f"Occurrence cache has ambiguous species records: {path}")
            taxon_key = ranked_keys[0][0]
            occurrences_by_chunk = []
            for raw in pd.read_csv(
                path,
                usecols=lambda column: column in CACHE_READ_COLUMNS,
                low_memory=False,
                chunksize=CACHE_READ_CHUNK_ROWS,
            ):
                occurrences = filter_occurrences(raw, taxon_key, country_code)
                if not occurrences.empty:
                    occurrences_by_chunk.append(occurrences)
            if occurrences_by_chunk:
                species_records = pd.concat(
                    occurrences_by_chunk, ignore_index=True
                )
                species_records["species"] = common_name
                species_records["scientific_name"] = scientific_name
                frames.append(species_records)
    if not frames:
        raise ValueError("No cached seabird occurrence records are available.")
    return pd.concat(frames, ignore_index=True)


def build_seabird_backtest(
    analysis_date: date | None = None,
    weather: pd.DataFrame | None = None,
) -> dict[str, object]:
    analysis_date = analysis_date or date.today()
    if weather is None:
        if __package__:
            from .seabird_validation import build_historical_forecast
        else:
            from seabird_validation import build_historical_forecast

        return build_historical_forecast(
            analysis_date, holdout_days=FORECAST_DAYS
        )

    if __package__:
        from .seabird_validation import (
            build_historical_forecast,
            filter_to_cutoff_date,
        )
    else:
        from seabird_validation import build_historical_forecast, filter_to_cutoff_date

    cutoff_weather = filter_to_cutoff_date(weather, analysis_date)
    cutoff_occurrences = filter_to_cutoff_date(
        load_cached_occurrences(), analysis_date
    )
    return build_historical_forecast(
        analysis_date,
        inputs={
            "analysis_date": analysis_date,
            "data_cutoff_date": analysis_date,
            "weather": cutoff_weather,
            "occurrences": cutoff_occurrences,
        },
        holdout_days=FORECAST_DAYS,
    )
