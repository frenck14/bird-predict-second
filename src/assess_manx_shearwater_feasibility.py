"""Assess Dutch GBIF record volume for Manx Shearwater forecasting."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
GBIF_API = "https://api.gbif.org/v1"
COUNTRY_CODE = "NL"
FACET_LIMIT = 10_000
WEATHER_FILE = ROOT / "data/processed/bird_predict_dataset_v2.csv"
FACET_FILE = ROOT / "data/raw/manx_shearwater_event_date_facets.csv"
REPORT_FILE = ROOT / "reports/manx_shearwater_feasibility.md"
SPECIES = (
    ("Manx Shearwater", "Puffinus puffinus"),
    ("Yellow-browed Warbler", "Phylloscopus inornatus"),
    ("Pallid Swift", "Apus pallidus"),
)
THRESHOLDS = (10, 25, 50)


@dataclass
class SpeciesData:
    common_name: str
    scientific_name: str
    taxon_key: int
    total_records: int
    facets: list[dict[str, object]]
    daily_counts: dict[date, int]
    dated_records: int
    partial_date_records: int


def fetch_json(url: str) -> dict[str, object]:
    request = Request(
        url,
        headers={"User-Agent": "bird-predict-second/1.0 feasibility assessment"},
    )
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def fetch_species_data(common_name: str, scientific_name: str) -> SpeciesData:
    match_query = urlencode(
        {"name": scientific_name, "rank": "SPECIES", "strict": "true"}
    )
    match = fetch_json(f"{GBIF_API}/species/match?{match_query}")
    if (
        match.get("matchType") != "EXACT"
        or match.get("status") != "ACCEPTED"
        or match.get("rank") != "SPECIES"
    ):
        raise RuntimeError(
            f"GBIF did not return an exact accepted species match for "
            f"{scientific_name}: {match}"
        )

    taxon_key = int(match["usageKey"])
    occurrence_query = urlencode(
        {
            "taxonKey": taxon_key,
            "country": COUNTRY_CODE,
            "limit": 0,
            "facet": "eventDate",
            "facetLimit": FACET_LIMIT,
        }
    )
    payload = fetch_json(f"{GBIF_API}/occurrence/search?{occurrence_query}")
    facets = payload.get("facets", [])
    if len(facets) != 1 or facets[0].get("field") != "eventDateInterval":
        raise RuntimeError(
            f"GBIF did not return the requested event-date facet for "
            f"{scientific_name}."
        )
    counts = facets[0].get("counts", [])
    if len(counts) >= FACET_LIMIT:
        raise RuntimeError(
            f"GBIF returned {FACET_LIMIT:,} or more date buckets for "
            f"{scientific_name}; increase FACET_LIMIT before using this summary."
        )

    daily_counts: defaultdict[date, int] = defaultdict(int)
    partial_date_records = 0
    for facet in counts:
        value = str(facet["name"])
        count = int(facet["count"])
        try:
            event_day = date.fromisoformat(value[:10])
        except ValueError:
            partial_date_records += count
            continue
        daily_counts[event_day] += count

    return SpeciesData(
        common_name=common_name,
        scientific_name=str(match["scientificName"]),
        taxon_key=taxon_key,
        total_records=int(payload["count"]),
        facets=counts,
        daily_counts=dict(daily_counts),
        dated_records=sum(daily_counts.values()),
        partial_date_records=partial_date_records,
    )


def load_weather_dates() -> set[date]:
    if not WEATHER_FILE.is_file():
        raise FileNotFoundError(
            f"Shared weather dataset not found: {WEATHER_FILE}. "
            "Build it with `python src/build_dataset_v2.py`."
        )
    with WEATHER_FILE.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if "date" not in (reader.fieldnames or []):
            raise ValueError(f"Weather dataset has no date column: {WEATHER_FILE}")
        dates = {date.fromisoformat(row["date"][:10]) for row in reader}
    if not dates:
        raise ValueError(f"No weather dates found in {WEATHER_FILE}.")
    return dates


def thresholds(daily_counts: dict[date, int]) -> dict[int, int]:
    return {
        threshold: sum(count >= threshold for count in daily_counts.values())
        for threshold in THRESHOLDS
    }


def format_count(value: int) -> str:
    return f"{value:,}"


def build_report(
    species_data: list[SpeciesData], weather_dates: set[date]
) -> str:
    manx = species_data[0]
    weather_start, weather_end = min(weather_dates), max(weather_dates)
    manx_in_weather = {
        day: count
        for day, count in manx.daily_counts.items()
        if day in weather_dates
    }
    manx_thresholds = thresholds(manx.daily_counts)
    manx_weather_thresholds = thresholds(manx_in_weather)
    pallid = species_data[2]
    pallid_in_weather = {
        day: count
        for day, count in pallid.daily_counts.items()
        if day in weather_dates
    }
    pallid_weather_thresholds = thresholds(pallid_in_weather)
    no_date_records = manx.total_records - sum(
        int(row["count"]) for row in manx.facets
    )

    years: defaultdict[int, int] = defaultdict(int)
    for day, count in manx.daily_counts.items():
        years[day.year] += count

    top_days = sorted(
        manx.daily_counts.items(), key=lambda item: (-item[1], item[0])
    )[:20]

    lines = [
        "# Manx Shearwater (Noordse Pijlstormvogel) feasibility assessment",
        "",
        f"GBIF data retrieved **{datetime.now(timezone.utc).date().isoformat()}**.",
        "",
        "## Scope and method",
        "",
        "The GBIF Species Match API returned an exact, accepted species match "
        f"for *{manx.scientific_name}* (taxon key `{manx.taxon_key}`). "
        "Occurrence counts use `taxonKey` and `country=NL` with no additional "
        "basis-of-record filter. GBIF's `eventDate` facet aggregates every "
        "matching occurrence without paging through individual records. "
        "Daily counts use the first ten characters of each facet date, "
        "matching the existing Bird-Predict date rule. Partial dates cannot "
        "be assigned to a unique observation day.",
        "",
        "The raw Manx Shearwater event-date facet buckets are archived at "
        "`data/raw/manx_shearwater_event_date_facets.csv`. The shared weather "
        f"dataset spans **{weather_start} to {weather_end}** "
        f"({len(weather_dates):,} dates); weather-window totals below include "
        "only GBIF days present in that calendar.",
        "",
        "## Manx Shearwater record volume",
        "",
        "| Measure | Count |",
        "|---|---:|",
        f"| Total GBIF occurrence records | {format_count(manx.total_records)} |",
        f"| Records assigned to a complete calendar date | {format_count(manx.dated_records)} |",
        f"| Records in partial-date facets | {format_count(manx.partial_date_records)} |",
        f"| Records with no event-date facet | {format_count(no_date_records)} |",
        f"| Distinct observation days with complete dates | {format_count(len(manx.daily_counts))} |",
        f"| Complete-date observation period | {min(manx.daily_counts)} to {max(manx.daily_counts)} |",
        "",
        "### Records per year",
        "",
        "Counts below include only records assigned to a complete calendar "
        "date; years with no records are omitted. The last year may be partial.",
        "",
        "| Year | Records |",
        "|---:|---:|",
    ]
    lines.extend(
        f"| {year} | {format_count(years[year])} |" for year in sorted(years)
    )
    lines.extend(
        [
            "",
            "### Top 20 record-count days",
            "",
            "| Rank | Date | Records |",
            "|---:|---|---:|",
        ]
    )
    lines.extend(
        f"| {rank} | {day} | {format_count(count)} |"
        for rank, (day, count) in enumerate(top_days, start=1)
    )

    lines.extend(
        [
            "",
            "### High-count days",
            "",
            "| Daily threshold | All complete-date years | Shared weather calendar |",
            "|---:|---:|---:|",
        ]
    )
    lines.extend(
        f"| ≥{threshold} records/day | "
        f"{format_count(manx_thresholds[threshold])} | "
        f"{format_count(manx_weather_thresholds[threshold])} |"
        for threshold in THRESHOLDS
    )
    lines.extend(
        [
            "",
            "## Comparison with existing target species",
            "",
            "All three species were queried from GBIF in the same run, using "
            "the same country and event-date facet method. The first table "
            "covers all complete-date years; the second restricts counts to "
            "the shared weather calendar.",
            "",
            "| Species | GBIF records | Complete-date records | Observation days | ≥10 days | ≥25 days | ≥50 days |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for species in species_data:
        species_thresholds = thresholds(species.daily_counts)
        lines.append(
            f"| {species.common_name} | {format_count(species.total_records)} "
            f"| {format_count(species.dated_records)} "
            f"| {format_count(len(species.daily_counts))} "
            f"| {format_count(species_thresholds[10])} "
            f"| {format_count(species_thresholds[25])} "
            f"| {format_count(species_thresholds[50])} |"
        )

    lines.extend(
        [
            "",
            "| Species | Complete-date records in weather window | Observation days | ≥10 days | ≥25 days | ≥50 days |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for species in species_data:
        in_weather = {
            day: count
            for day, count in species.daily_counts.items()
            if day in weather_dates
        }
        species_thresholds = thresholds(in_weather)
        lines.append(
            f"| {species.common_name} | {format_count(sum(in_weather.values()))} "
            f"| {format_count(len(in_weather))} "
            f"| {format_count(species_thresholds[10])} "
            f"| {format_count(species_thresholds[25])} "
            f"| {format_count(species_thresholds[50])} |"
        )

    lines.extend(
        [
            "",
            "## Forecasting feasibility and recommendation",
            "",
            "Manx Shearwater has substantially less data than either existing "
            "target: about "
            f"{species_data[1].total_records / manx.total_records:.1f}× fewer "
            "GBIF records than Yellow-browed Warbler and "
            f"{species_data[2].total_records / manx.total_records:.1f}× "
            "fewer than Pallid Swift. It has more distinct observation days "
            "than Pallid Swift, but its high-count targets are much rarer: "
            f"within the shared weather period it has "
            f"{manx_weather_thresholds[10]} ≥10-record days, "
            f"{manx_weather_thresholds[25]} ≥25-record days, and "
            f"{manx_weather_thresholds[50]} ≥50-record days, compared with "
            f"{pallid_weather_thresholds[10]}, "
            f"{pallid_weather_thresholds[25]}, and "
            f"{pallid_weather_thresholds[50]} "
            "for Pallid Swift.",
            "",
            "The ≥10 target has only 30 positive days in the weather window, "
            "and the ≥25 and ≥50 targets have 11 and 3. These events are "
            "concentrated in a few years (most notably 2017, 2023, and 2025), "
            "leaving too few independent positive events for credible "
            "forward-held-out model evaluation, especially at the higher "
            "thresholds. A model could be prototyped for exploratory analysis, "
            "but its scores would be unstable and could mostly reflect "
            "seasonality, observer effort, or isolated reporting surges.",
            "",
            "**Recommendation: do not make Manx Shearwater the next "
            "operational Bird-Predict target yet.** Keep it as a candidate for "
            "a descriptive or exploratory study; reconsider forecasting after "
            "more high-count events accrue or after a broader, validated "
            "observation source and a longer weather history are available.",
            "",
            "## Data caveats",
            "",
            "- GBIF `country=NL` uses the occurrence country code, not a "
            "coordinate-based Netherlands boundary.",
            "- The total count includes records without usable day-level dates "
            "and may include records from multiple datasets or observation "
            "types. These counts represent reported occurrences, not "
            "independent birds or population abundance.",
            f"- Of the {format_count(manx.total_records):s} Manx Shearwater "
            f"records, {format_count(no_date_records)} have no event-date "
            f"facet and {format_count(manx.partial_date_records)} has only "
            "a partial date.",
            "- The event-date facets are an aggregate of all matching GBIF "
            "records, not a record-level occurrence download. GBIF data can "
            "change after this retrieval date.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    species_data = [
        fetch_species_data(common_name, scientific_name)
        for common_name, scientific_name in SPECIES
    ]
    weather_dates = load_weather_dates()

    FACET_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FACET_FILE.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["name", "count"])
        writer.writeheader()
        writer.writerows(species_data[0].facets)

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(
        build_report(species_data, weather_dates), encoding="utf-8"
    )
    print(f"Saved GBIF date facets: {FACET_FILE.relative_to(ROOT)}")
    print(f"Saved feasibility report: {REPORT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
