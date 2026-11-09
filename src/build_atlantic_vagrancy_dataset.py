"""Download and summarize GBIF occurrences for the Atlantic Vagrancy Index."""

from __future__ import annotations

import json
import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
GBIF_API = "https://api.gbif.org/v1"
TARGET_COUNTRIES = {
    "GB": "United Kingdom",
    "IE": "Ireland",
    "NL": "Netherlands",
    "BE": "Belgium",
    "DK": "Denmark",
}
PAGE_SIZE = 300
MAX_SEARCH_OFFSET = 100_000
YEAR_PARTITION_THRESHOLD = 5_000
REQUEST_TIMEOUT_SECONDS = 60
PAGE_WORKERS = 1
CACHE_READ_CHUNK_ROWS = 10_000
RETRY_ATTEMPTS = 5
RETRY_STATUS_CODES = {429, *range(500, 600)}
RAW_DIRECTORY = ROOT / "data/raw/atlantic_vagrancy_occurrences"
SPECIES_SUMMARY_OUTPUT = ROOT / "outputs/atlantic_vagrancy_species_summary.csv"
EVENTS_OUTPUT = ROOT / "outputs/atlantic_vagrancy_events.csv"
DAILY_OUTPUT = ROOT / "outputs/atlantic_vagrancy_daily_counts.csv"
OCCURRENCE_COLUMNS = (
    "key",
    "scientificName",
    "taxonKey",
    "eventDate",
    "decimalLatitude",
    "decimalLongitude",
    "basisOfRecord",
    "countryCode",
)

CACHE_READ_COLUMNS = {
    *OCCURRENCE_COLUMNS,
    "degreeOfEstablishment",
    "establishmentMeans",
}

CACHE_COLUMN_ORDER = tuple(CACHE_READ_COLUMNS)

# Optional taxa are included when GBIF has qualifying records. Add future taxa
# here; Junco hyemalis is intentionally excluded from this guild.
ATLANTIC_VAGRANCY_SPECIES = [
    {"species": "Red-eyed Vireo", "scientific_name": "Vireo olivaceus", "core": True},
    {
        "species": "Northern Waterthrush",
        "scientific_name": "Parkesia noveboracensis",
        "core": True,
    },
    {
        "species": "Blackpoll Warbler",
        "scientific_name": "Setophaga striata",
        "core": True,
    },
    {"species": "Ovenbird", "scientific_name": "Seiurus aurocapilla", "core": True},
    {
        "species": "Connecticut Warbler",
        "scientific_name": "Oporornis agilis",
        "core": True,
    },
    {
        "species": "Black-and-white Warbler",
        "scientific_name": "Mniotilta varia",
        "core": False,
    },
    {
        "species": "Prothonotary Warbler",
        "scientific_name": "Protonotaria citrea",
        "core": False,
    },
    {
        "species": "American Redstart",
        "scientific_name": "Setophaga ruticilla",
        "core": False,
    },
    {
        "species": "Yellow-rumped Warbler",
        "scientific_name": "Setophaga coronata",
        "core": False,
    },
]
EXCLUDED_SPECIES = {"Junco hyemalis"}

LOGGER = logging.getLogger(__name__)


def _fetch_json(url: str) -> dict[str, object]:
    request = Request(
        url,
        headers={"User-Agent": "bird-predict-second/1.0 atlantic-vagrancy"},
    )
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.load(response)
            break
        except HTTPError as error:
            if error.code in RETRY_STATUS_CODES and attempt < RETRY_ATTEMPTS - 1:
                error.close()
                LOGGER.warning(
                    "GBIF returned HTTP %s; retrying attempt %s/%s",
                    error.code,
                    attempt + 2,
                    RETRY_ATTEMPTS,
                )
                time.sleep(2**attempt)
                continue
            raise RuntimeError(
                f"GBIF API returned HTTP {error.code}: {url}"
            ) from error
        except (URLError, TimeoutError) as error:
            if attempt < RETRY_ATTEMPTS - 1:
                LOGGER.warning(
                    "GBIF request failed; retrying attempt %s/%s: %s",
                    attempt + 2,
                    RETRY_ATTEMPTS,
                    error,
                )
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"Could not reach the GBIF API: {error}") from error
        except ValueError as error:
            raise ValueError(f"GBIF returned invalid JSON for {url}.") from error
    if not isinstance(payload, dict):
        raise ValueError(f"GBIF returned an unexpected response for {url}.")
    return payload


def resolve_taxon_key(scientific_name: str) -> int:
    query = urlencode(
        {"name": scientific_name, "rank": "SPECIES", "strict": "true"}
    )
    match = _fetch_json(f"{GBIF_API}/species/match?{query}")
    if (
        match.get("matchType") != "EXACT"
        or match.get("status") != "ACCEPTED"
        or match.get("rank") != "SPECIES"
    ):
        raise RuntimeError(
            f"GBIF did not return an exact accepted species match for "
            f"{scientific_name}: {match}"
        )
    try:
        return int(match["usageKey"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"GBIF species match for {scientific_name} has no valid usage key."
        ) from error


def _species_slug(scientific_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", scientific_name.lower()).strip("_")


def _cache_path(
    scientific_name: str,
    country_code: str,
    year_range: tuple[int, int] | None = None,
) -> Path:
    year_suffix = (
        f"_{year_range[0]}_{year_range[1]}" if year_range is not None else ""
    )
    return (
        RAW_DIRECTORY
        / f"{_species_slug(scientific_name)}_{country_code.lower()}"
        f"{year_suffix}_raw.csv"
    )


def _is_valid_date(value: object) -> bool:
    text = str(value)
    if len(text) < 10 or not re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return False
    try:
        date.fromisoformat(text[:10])
    except ValueError:
        return False
    return True


COMPACT_COLUMNS = ("key", "countryCode", "decimalLatitude", "decimalLongitude", "date")


def _compact(records: pd.DataFrame) -> pd.DataFrame:
    """Keep only the columns needed downstream to bound memory for large taxa."""
    return records.loc[:, [c for c in COMPACT_COLUMNS if c in records]]


def _drop_duplicate_occurrences(records: pd.DataFrame) -> pd.DataFrame:
    if "key" not in records:
        return records.drop_duplicates(
            subset=[
                column
                for column in (
                    "scientificName",
                    "countryCode",
                    "eventDate",
                    "date",
                    "decimalLatitude",
                    "decimalLongitude",
                    "basisOfRecord",
                )
                if column in records
            ]
        )
    keyed = records["key"].notna()
    keyed_records = records.loc[keyed].drop_duplicates(
        subset=["key"], keep="first"
    )
    unkeyed_records = records.loc[~keyed].drop_duplicates(
        subset=[
            column
            for column in (
                "scientificName",
                "countryCode",
                "eventDate",
                "date",
                "decimalLatitude",
                "decimalLongitude",
                "basisOfRecord",
            )
            if column in records
        ]
    )
    return pd.concat([keyed_records, unkeyed_records], ignore_index=True)


def filter_occurrences(
    records: pd.DataFrame, taxon_key: int, country_code: str
) -> pd.DataFrame:
    """Keep wild bird observations with valid dates and geographic coordinates."""
    if records.empty:
        return pd.DataFrame(columns=[*OCCURRENCE_COLUMNS, "date"])
    frame = records.copy()
    for column in OCCURRENCE_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA
    latitude = pd.to_numeric(frame["decimalLatitude"], errors="coerce")
    longitude = pd.to_numeric(frame["decimalLongitude"], errors="coerce")
    record_taxon_keys = pd.to_numeric(frame["taxonKey"], errors="coerce")
    valid = (
        frame["countryCode"].astype("string").str.upper().eq(country_code)
        & frame["basisOfRecord"].astype("string").eq("HUMAN_OBSERVATION")
        & record_taxon_keys.eq(taxon_key)
        & latitude.between(-90, 90)
        & longitude.between(-180, 180)
        & frame["eventDate"].map(_is_valid_date)
    )
    for column in ("degreeOfEstablishment", "establishmentMeans"):
        if column in frame:
            disallowed = frame[column].astype("string").str.upper().isin(
                {"CAPTIVE", "CULTIVATED", "MANAGED"}
            )
            valid &= ~disallowed
    filtered = frame.loc[valid].copy()
    filtered["decimalLatitude"] = latitude.loc[valid]
    filtered["decimalLongitude"] = longitude.loc[valid]
    filtered["date"] = pd.to_datetime(
        filtered["eventDate"].astype("string").str[:10],
        format="%Y-%m-%d",
        errors="raise",
    )
    return _drop_duplicate_occurrences(filtered).reset_index(drop=True)


def _year_partitions(
    query_parameters: dict[str, object], common_name: str, country_code: str
) -> list[tuple[int, int]]:
    """Return (year, count) pairs so large queries avoid slow deep offsets."""
    parameters = {
        **query_parameters,
        "limit": 0,
        "offset": 0,
        "facet": "year",
        "facetLimit": 500,
    }
    payload = _fetch_json(f"{GBIF_API}/occurrence/search?{urlencode(parameters)}")
    try:
        counts = payload["facets"][0]["counts"]
        partitions = sorted(
            (int(item["name"]), int(item["count"])) for item in counts
        )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError(
            f"GBIF returned an invalid year facet for {common_name} "
            f"({country_code})."
        ) from error
    return partitions


def _read_cached_occurrences(
    cache_path: Path,
    common_name: str,
    country_code: str,
    taxon_key: int,
    compact: bool,
) -> pd.DataFrame:
    """Filter a raw cache in chunks so very large taxa stay within memory."""
    chunks = pd.read_csv(
        cache_path,
        usecols=lambda column: column in CACHE_READ_COLUMNS,
        low_memory=False,
        chunksize=CACHE_READ_CHUNK_ROWS,
    )
    filtered_chunks = []
    raw_count = 0
    for chunk in chunks:
        raw_count += len(chunk)
        filtered = filter_occurrences(chunk, taxon_key, country_code)
        filtered_chunks.append(_compact(filtered) if compact else filtered)
    LOGGER.info(
        "%s (%s): loaded %s cached raw records",
        common_name,
        country_code,
        f"{raw_count:,}",
    )
    non_empty = [frame for frame in filtered_chunks if not frame.empty]
    if not non_empty:
        return pd.DataFrame(columns=[*OCCURRENCE_COLUMNS, "date"])
    return _drop_duplicate_occurrences(
        pd.concat(non_empty, ignore_index=True)
    ).reset_index(drop=True)


def download_species_country(
    common_name: str,
    scientific_name: str,
    country_code: str,
    taxon_key: int,
    compact: bool = False,
    year_range: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """Cache raw GBIF occurrence rows for a species/country query.

    Pages are streamed to disk, so memory does not grow with the record count.
    compact=True returns only the columns needed for counts and mapping.
    """
    if year_range is not None and (
        len(year_range) != 2 or year_range[0] > year_range[1]
    ):
        raise ValueError("year_range must contain an ascending start and end year.")
    cache_path = _cache_path(scientific_name, country_code, year_range)
    if cache_path.is_file():
        return _read_cached_occurrences(
            cache_path, common_name, country_code, taxon_key, compact
        )

    query_parameters = {
        "taxonKey": taxon_key,
        "country": country_code,
        "basisOfRecord": "HUMAN_OBSERVATION",
        "hasCoordinate": "true",
        "hasGeospatialIssue": "false",
        "occurrenceStatus": "PRESENT",
        "limit": PAGE_SIZE,
        "offset": 0,
    }
    if year_range is not None:
        query_parameters["year"] = f"{year_range[0]},{year_range[1]}"
    query = urlencode(query_parameters)
    first_page = _fetch_json(f"{GBIF_API}/occurrence/search?{query}")
    try:
        total = int(first_page["count"])
        first_results = first_page["results"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"GBIF returned an invalid occurrence response for "
            f"{common_name} ({country_code})."
        ) from error
    if not isinstance(first_results, list):
        raise ValueError(
            f"GBIF returned invalid occurrence results for "
            f"{common_name} ({country_code})."
        )
    if total > YEAR_PARTITION_THRESHOLD:
        partitions = _year_partitions(query_parameters, common_name, country_code)
        if sum(count for _, count in partitions) != total:
            LOGGER.warning(
                "%s (%s): %s of %s records have no year and are not requested",
                common_name,
                country_code,
                f"{total - sum(count for _, count in partitions):,}",
                f"{total:,}",
            )
        expected = sum(count for _, count in partitions)
        requests = [
            ({**query_parameters, "year": year}, count)
            for year, count in partitions
        ]
    else:
        expected = total
        requests = [(query_parameters, total)]
    for parameters, count in requests:
        if count > MAX_SEARCH_OFFSET:
            raise RuntimeError(
                f"GBIF reports {count:,} records for {common_name} in "
                f"{country_code}, beyond the search offset limit "
                f"{MAX_SEARCH_OFFSET:,}. Refusing to cache an incomplete result."
            )

    page_count = sum(math.ceil(count / PAGE_SIZE) for _, count in requests)
    RAW_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_suffix(".csv.tmp")
    if temporary_path.is_file():
        with temporary_path.open("r+b") as cache_file:
            cache_file.seek(0, 2)
            cache_size = cache_file.tell()
            if cache_size:
                cache_file.seek(-1, 2)
                if cache_file.read(1) != b"\n":
                    position = cache_size - 1
                    while position > 0:
                        position -= 1
                        cache_file.seek(position)
                        if cache_file.read(1) == b"\n":
                            cache_file.truncate(position + 1)
                            break
        with temporary_path.open(encoding="utf-8") as cache_file:
            cached_rows = max(sum(1 for _ in cache_file) - 1, 0)
        expected = sum(count for _, count in requests)
        if cached_rows > expected:
            raise RuntimeError(
                f"Partial cache contains more rows than GBIF reports for "
                f"{common_name} ({country_code}): {temporary_path}"
            )
        downloaded = 0
        found_resume_boundary = False
        for _, count in requests:
            for offset in range(0, count, PAGE_SIZE):
                page_rows = min(PAGE_SIZE, count - offset)
                if downloaded + page_rows > cached_rows:
                    found_resume_boundary = True
                    break
                downloaded += page_rows
            if found_resume_boundary:
                break
        if downloaded < cached_rows:
            resume_path = temporary_path.with_suffix(".csv.resume")
            with temporary_path.open("rb") as source, resume_path.open("wb") as target:
                target.write(source.readline())
                for _ in range(downloaded):
                    target.write(source.readline())
            resume_path.replace(temporary_path)
            LOGGER.warning(
                "Discarded %s incomplete cached rows before resuming %s (%s)",
                f"{cached_rows - downloaded:,}",
                common_name,
                country_code,
            )
        LOGGER.info(
            "Resuming %s (%s) from %s cached records",
            common_name,
            country_code,
            f"{downloaded:,}",
        )
    else:
        downloaded = 0
    page_number = 0
    processed = 0

    def fetch_page(parameters: dict[str, object], offset: int) -> list[object]:
        if offset == 0 and parameters is query_parameters:
            return first_results
        payload = _fetch_json(
            f"{GBIF_API}/occurrence/search?"
            f"{urlencode({**parameters, 'offset': offset})}"
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError(
                f"GBIF returned an invalid page for {common_name} ({country_code})."
            )
        return results

    with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as executor:
        for parameters, count in requests:
            offsets = list(range(0, count, PAGE_SIZE))
            for start in range(0, len(offsets), PAGE_WORKERS):
                batch = []
                for offset in offsets[start : start + PAGE_WORKERS]:
                    page_rows = min(PAGE_SIZE, count - offset)
                    if downloaded >= processed + page_rows:
                        processed += page_rows
                        page_number += 1
                        continue
                    if downloaded != processed and not batch:
                        raise RuntimeError(
                            f"Cannot resume a partially cached GBIF page for "
                            f"{common_name} ({country_code}); remove "
                            f"{temporary_path} to restart this query."
                        )
                    batch.append(offset)
                    processed += page_rows
                if not batch:
                    continue
                batch_results = list(
                    executor.map(lambda offset: fetch_page(parameters, offset), batch)
                )
                for offset, page_results in zip(batch, batch_results):
                    page_number += 1
                    LOGGER.info("Downloading %s", common_name)
                    LOGGER.info(
                        "Downloading page %s of %s (%s)",
                        page_number,
                        page_count,
                        country_code,
                    )
                    if not page_results:
                        raise RuntimeError(
                            f"GBIF returned empty page {page_number} of "
                            f"{page_count} for {common_name} ({country_code})."
                        )
                    page = pd.DataFrame(
                        [
                            {c: result.get(c) for c in CACHE_COLUMN_ORDER}
                            for result in page_results
                            if isinstance(result, dict)
                        ],
                        columns=CACHE_COLUMN_ORDER,
                    )
                    page.to_csv(
                        temporary_path,
                        mode="a" if downloaded else "w",
                        header=not downloaded,
                        index=False,
                    )
                    downloaded += len(page)
                LOGGER.info("Cached %s records so far", f"{downloaded:,}")
    if downloaded != expected:
        temporary_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"GBIF reported {expected:,} records for {common_name} in "
            f"{country_code}, but only {downloaded:,} were downloaded."
        )
    if not downloaded:
        pd.DataFrame(columns=CACHE_COLUMN_ORDER).to_csv(temporary_path, index=False)
    temporary_path.replace(cache_path)
    LOGGER.info(
        "Cached %s records for %s (%s)", f"{downloaded:,}", common_name, country_code
    )
    return _read_cached_occurrences(
        cache_path, common_name, country_code, taxon_key, compact
    )


def load_all_occurrences(
    species_registry: list[dict[str, object]] = ATLANTIC_VAGRANCY_SPECIES,
) -> pd.DataFrame:
    if not species_registry:
        raise ValueError("ATLANTIC_VAGRANCY_SPECIES must not be empty.")
    names = {
        str(species["scientific_name"]) for species in species_registry
    }
    if names.intersection(EXCLUDED_SPECIES):
        raise ValueError(
            f"Explicitly excluded species added to the Atlantic guild: "
            f"{sorted(names.intersection(EXCLUDED_SPECIES))}"
        )

    all_frames: list[pd.DataFrame] = []
    for species in species_registry:
        common_name = str(species["species"])
        scientific_name = str(species["scientific_name"])
        taxon_key = resolve_taxon_key(scientific_name)
        LOGGER.info("Downloading %s", common_name)
        for country_code in TARGET_COUNTRIES:
            LOGGER.info(
                "Retrieving %s in %s (%s)",
                common_name,
                TARGET_COUNTRIES[country_code],
                country_code,
            )
            occurrences = download_species_country(
                common_name,
                scientific_name,
                country_code,
                taxon_key,
            )
            if not occurrences.empty:
                occurrences["species"] = common_name
                occurrences["scientific_name"] = scientific_name
                all_frames.append(occurrences)

    if not all_frames:
        return pd.DataFrame(
            columns=[*OCCURRENCE_COLUMNS, "date", "species", "scientific_name"]
        )
    combined = pd.concat(all_frames, ignore_index=True)
    combined = _drop_duplicate_occurrences(combined)
    return combined.sort_values(["date", "species"]).reset_index(drop=True)


def build_outputs(
    occurrences: pd.DataFrame,
    species_registry: list[dict[str, object]] = ATLANTIC_VAGRANCY_SPECIES,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if occurrences.empty:
        summary = pd.DataFrame(
            [
                {
                    "species": species["species"],
                    "records": 0,
                    "unique_dates": 0,
                    "countries": "",
                }
                for species in species_registry
            ],
            columns=["species", "records", "unique_dates", "countries"],
        )
        empty_events = pd.DataFrame(columns=["date", "count", "species_count"])
        empty_daily = pd.DataFrame(columns=["date", "count"])
        return summary, empty_events, empty_daily

    rows: list[dict[str, object]] = []
    for species in species_registry:
        name = str(species["species"])
        records = occurrences.loc[occurrences["species"].eq(name)]
        rows.append(
            {
                "species": name,
                "records": len(records),
                "unique_dates": int(records["date"].nunique()),
                "countries": ";".join(
                    sorted(records["countryCode"].dropna().astype(str).unique())
                ),
            }
        )
    summary = pd.DataFrame(
        rows, columns=["species", "records", "unique_dates", "countries"]
    )
    events = (
        occurrences.groupby("date", as_index=False)
        .agg(count=("species", "size"), species_count=("species", "nunique"))
        .sort_values("date")
        .reset_index(drop=True)
    )
    daily = events[["date", "count"]].copy()
    return summary, events, daily


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    occurrences = load_all_occurrences()
    summary, events, daily = build_outputs(occurrences)
    for path in (SPECIES_SUMMARY_OUTPUT, EVENTS_OUTPUT, DAILY_OUTPUT):
        path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SPECIES_SUMMARY_OUTPUT, index=False)
    events.to_csv(EVENTS_OUTPUT, index=False, date_format="%Y-%m-%d")
    daily.to_csv(DAILY_OUTPUT, index=False, date_format="%Y-%m-%d")
    LOGGER.info("Saved species summary to %s", SPECIES_SUMMARY_OUTPUT.relative_to(ROOT))
    LOGGER.info("Saved event details to %s", EVENTS_OUTPUT.relative_to(ROOT))
    LOGGER.info(
        "Saved %s event days / %s records to %s",
        f"{len(daily):,}",
        f"{int(daily['count'].sum()) if not daily.empty else 0:,}",
        DAILY_OUTPUT.relative_to(ROOT),
    )
    LOGGER.info("Species records:\n%s", summary.to_string(index=False))


if __name__ == "__main__":
    main()
