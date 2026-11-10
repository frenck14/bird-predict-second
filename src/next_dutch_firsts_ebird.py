"""Refresh Next Dutch Firsts using the official eBird recent-observations API."""

from __future__ import annotations

import argparse
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
from dotenv import load_dotenv

from src.next_dutch_firsts_probability import ProbabilityModel

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "inputs/next_dutch_firsts"
OUTPUT = ROOT / "outputs/next_dutch_firsts"
COUNTRIES = {
    "GB": "United Kingdom",
    "IE": "Ireland",
    "BE": "Belgium",
    "DE": "Germany",
    "DK": "Denmark",
}
RECORD_COLUMNS = [
    "species", "country", "observation_date", "location", "observation_count", "source",
]
API_BASE = "https://api.ebird.org/v2"
MAX_RESULTS = 10000
# Explicit scientific-name synonyms, verified against eBird's current taxonomy.
SCIENTIFIC_NAME_ALIASES = {
    "emberiza spodocephala": "schoeniclus spodocephalus",
    "emberiza aureola": "schoeniclus aureolus",
}


class EBirdAdapter:
    """Fetch a complete 30-day, valid-only snapshot for an explicit candidate list."""

    def __init__(self, api_key: str, session: requests.Session | None = None, request_interval: float = 0.1):
        if not api_key or not api_key.strip():
            raise ValueError("EBIRD_API_KEY is missing or empty.")
        self.api_key = api_key.strip()
        self.session = session or requests.Session()
        if request_interval < 0:
            raise ValueError("Request interval must not be negative.")
        self.request_interval = request_interval
        self._last_request = 0.0

    def _get(self, path: str, params: dict) -> list:
        for attempt in range(3):
            wait = self.request_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            try:
                self._last_request = time.monotonic()
                response = self.session.get(
                    f"{API_BASE}/{path}", params=params,
                    headers={"X-eBirdApiToken": self.api_key},
                    timeout=(10, 60), allow_redirects=False,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"eBird request failed for {path}: network error") from exc
                time.sleep(2 ** attempt)
                continue
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                retry_after = response.headers.get("Retry-After", "")
                delay = min(int(retry_after), 60) if retry_after.isdigit() else 2 ** attempt
                time.sleep(delay)
                continue
            if not 200 <= response.status_code < 300:
                raise RuntimeError(f"eBird request failed for {path}: HTTP {response.status_code}")
            try:
                payload = response.json()
            except requests.exceptions.JSONDecodeError as exc:
                raise ValueError(f"eBird returned invalid JSON for {path}") from exc
            if not isinstance(payload, list):
                raise ValueError(f"eBird returned an invalid response for {path}")
            return payload
        raise RuntimeError(f"eBird request failed for {path}")

    def fetch(self, master: pd.DataFrame) -> pd.DataFrame:
        if master.empty or not {"species", "scientific_name"}.issubset(master.columns):
            raise ValueError("Species master must contain species and scientific_name.")
        if master[["species", "scientific_name"]].isna().any().any() or master["species"].duplicated().any():
            raise ValueError("Species master contains missing identifiers or duplicate species.")
        taxonomy = self._get("ref/taxonomy/ebird", {"fmt": "json", "cat": "species"})
        codes: dict[str, set[str]] = {}
        for taxon in taxonomy:
            if not isinstance(taxon, dict) or not taxon.get("sciName") or not taxon.get("speciesCode"):
                raise ValueError("Invalid eBird taxonomy entry.")
            codes.setdefault(taxon["sciName"].strip().casefold(), set()).add(taxon["speciesCode"])
        resolved = []
        problems = []
        for row in master.itertuples(index=False):
            scientific_name = str(row.scientific_name).strip().casefold()
            matches = codes.get(SCIENTIFIC_NAME_ALIASES.get(scientific_name, scientific_name), set())
            if len(matches) != 1:
                problems.append(f"{row.species} ({row.scientific_name})")
            else:
                resolved.append((row.species, next(iter(matches))))
        if problems:
            raise ValueError("Unresolved or ambiguous eBird taxonomy: " + ", ".join(problems))

        rows = []
        for species, code in resolved:
            for region, country in COUNTRIES.items():
                path = f"data/obs/{region}/recent/{quote(code, safe='')}"
                records = self._get(path, {
                    "back": 30, "maxResults": MAX_RESULTS, "includeProvisional": "false",
                })
                if len(records) >= MAX_RESULTS:
                    raise ValueError(f"eBird results reached the limit for {species} in {country}; snapshot may be truncated.")
                for record in records:
                    if not isinstance(record, dict) or record.get("speciesCode") != code:
                        raise ValueError(f"Unexpected eBird species in response for {species} in {country}.")
                    date, location = record.get("obsDt"), record.get("locName")
                    if not isinstance(date, str) or not isinstance(location, str) or not location.strip():
                        raise ValueError(f"Invalid eBird observation for {species} in {country}.")
                    try:
                        timestamp = pd.Timestamp(date)
                    except (ValueError, TypeError) as exc:
                        raise ValueError(f"Invalid eBird observation date for {species} in {country}.") from exc
                    if pd.isna(timestamp):
                        raise ValueError(f"Missing eBird observation date for {species} in {country}.")
                    count = record.get("howMany")
                    if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
                        raise ValueError(f"Invalid eBird observation count for {species} in {country}.")
                    rows.append((species, country, timestamp.strftime("%Y-%m-%d"), location, count, "eBird"))
        return pd.DataFrame(rows, columns=RECORD_COLUMNS)


def _existing_records(path: Path) -> pd.DataFrame:
    records = pd.read_csv(path)
    if "date" in records.columns and "observation_date" not in records.columns:
        records = records.rename(columns={"date": "observation_date"})
    required = set(RECORD_COLUMNS) - {"observation_count"}
    if not required.issubset(records.columns):
        raise ValueError(f"Invalid current activity schema: {path}")
    if "observation_count" not in records:
        records["observation_count"] = pd.NA
    if records["source"].isna().any():
        raise ValueError(f"Missing source in {path}")
    return records.loc[records["source"].str.casefold().ne("ebird"), RECORD_COLUMNS].copy()


def _read_previous(path: Path, species: pd.Series) -> pd.DataFrame:
    previous = pd.read_csv(path)
    if not {"species", "probability_5yr"}.issubset(previous.columns) or previous["species"].duplicated().any():
        raise ValueError(f"Invalid prior probabilities: {path}")
    if set(previous["species"]) != set(species):
        raise ValueError("Prior probabilities do not match the current species master.")
    text = previous["probability_5yr"].astype(str).str.strip()
    numeric = pd.to_numeric(text.str.removesuffix("%"), errors="raise")
    previous["old_probability_5yr"] = numeric.where(~text.str.endswith("%"), numeric / 100)
    if previous["old_probability_5yr"].isna().any() or not previous["old_probability_5yr"].between(0, 1).all():
        raise ValueError("Prior five-year probabilities must be between zero and one.")
    return previous[["species", "old_probability_5yr"]]


def refresh(adapter: EBirdAdapter, input_dir: Path = INPUT, output_dir: Path = OUTPUT) -> None:
    model = ProbabilityModel()
    master, dutch, western, _, traits = model.load_data(str(input_dir))
    previous = _read_previous(output_dir / "probabilities.csv", master["species"])
    existing = _existing_records(input_dir / "current_season_records.csv")
    records = adapter.fetch(master)
    combined = pd.concat([existing, records], ignore_index=True)
    results = [
        model.calculate_probability(
            row.species, row.scientific_name, row.pathway,
            master, dutch, western, combined, traits,
        )
        for row in master.itertuples(index=False)
    ]
    probabilities = pd.DataFrame([result.to_dict() for result in results])
    summary = master[["species"]].merge(
        records.groupby("species").agg(
            observation_records=("species", "size"),
            countries=("country", "nunique"),
            latest_observation=("observation_date", "max"),
            individuals_reported=("observation_count", lambda values: values.sum(min_count=1)),
        ).reset_index(), how="left", on="species", validate="one_to_one",
    )
    summary[["observation_records", "countries"]] = summary[["observation_records", "countries"]].fillna(0).astype(int)
    summary["combined_current_activity_score"] = [
        result.factor_breakdown["Current Activity"].normalized_score for result in results
    ]
    influence = previous.merge(
        probabilities[["species", "probability_5yr"]], on="species", validate="one_to_one"
    ).rename(columns={"probability_5yr": "new_probability_5yr"})
    influence["change"] = influence["new_probability_5yr"] - influence["old_probability_5yr"]
    formatted = probabilities.copy()
    for column in ("probability_1yr", "probability_5yr", "probability_10yr"):
        formatted[column] = formatted[column].map(lambda value: f"{value:.1%}")
    formatted["confidence_score"] = formatted["confidence_score"].map(lambda value: f"{value:.2f}")

    output_dir.mkdir(parents=True, exist_ok=True)
    destinations = [
        (input_dir / "current_season_records.csv", combined),
        (output_dir / "ebird_activity_summary.csv", summary),
        (output_dir / "probabilities.csv", formatted),
        (output_dir / "ebird_influence_report.csv", influence),
    ]
    staged = []
    try:
        for destination, frame in destinations:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=destination.parent, delete=False) as handle:
                staged.append((Path(handle.name), destination))
                frame.to_csv(handle, index=False)
        for temporary, destination in staged:
            os.replace(temporary, destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    load_dotenv(ROOT / ".env")
    refresh(EBirdAdapter(os.environ.get("EBIRD_API_KEY", "")))
    print("eBird records, activity summary, probabilities and influence report updated.")


if __name__ == "__main__":
    main()
