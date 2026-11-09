"""Assess Dutch GBIF record volume for Red-throated Pipit forecasting."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from assess_manx_shearwater_feasibility import (
    ROOT,
    SpeciesData,
    fetch_species_data,
    format_count,
    load_weather_dates,
    thresholds,
)


FACET_FILE = ROOT / "data/raw/red_throated_pipit_event_date_facets.csv"
REPORT_FILE = ROOT / "reports/red_throated_pipit_feasibility.md"
SPECIES = (
    ("Red-throated Pipit", "Anthus cervinus"),
    ("Yellow-browed Warbler", "Phylloscopus inornatus"),
    ("Pallid Swift", "Apus pallidus"),
    ("Manx Shearwater", "Puffinus puffinus"),
)


def build_report(
    species_data: list[SpeciesData], weather_dates: set[date]
) -> str:
    pipit = species_data[0]
    weather_start, weather_end = min(weather_dates), max(weather_dates)
    pipit_weather = {
        day: count for day, count in pipit.daily_counts.items() if day in weather_dates
    }
    all_thresholds = thresholds(pipit.daily_counts)
    weather_thresholds = thresholds(pipit_weather)
    yearly_counts: defaultdict[int, int] = defaultdict(int)
    for day, count in pipit.daily_counts.items():
        yearly_counts[day.year] += count

    no_date_records = pipit.total_records - sum(
        int(row["count"]) for row in pipit.facets
    )
    top_days = sorted(
        pipit.daily_counts.items(), key=lambda row: (-row[1], row[0])
    )[:20]

    lines = [
        "# Red-throated Pipit (Anthus cervinus) feasibility assessment",
        "",
        f"GBIF data retrieved **{datetime.now(timezone.utc).date().isoformat()}**.",
        "",
        "## Scope and method",
        "",
        "GBIF Species Match returned an exact, accepted species match for "
        f"*{pipit.scientific_name}* (taxon key `{pipit.taxon_key}`). "
        "Occurrences use `taxonKey` and `country=NL`, without a basis-of-record "
        "filter. Counts were retrieved using GBIF's event-date facet, rather "
        "than paging through individual occurrences. Daily counts use the "
        "first ten characters of each date facet; partial dates cannot be "
        "assigned to a unique observation day.",
        "",
        "The Pipit facet buckets are archived at "
        "`data/raw/red_throated_pipit_event_date_facets.csv`. The project's "
        f"shared weather calendar spans **{weather_start} to {weather_end}** "
        f"({len(weather_dates):,} days). Weather-window counts include only "
        "observation dates present in that calendar.",
        "",
        "## Red-throated Pipit record volume",
        "",
        "| Measure | Count |",
        "|---|---:|",
        f"| Total GBIF records | {format_count(pipit.total_records)} |",
        f"| Records assigned to a complete calendar date | {format_count(pipit.dated_records)} |",
        f"| Records in partial-date facets | {format_count(pipit.partial_date_records)} |",
        f"| Records with no event-date facet | {format_count(no_date_records)} |",
        f"| Distinct observation days with complete dates | {format_count(len(pipit.daily_counts))} |",
        f"| Complete-date observation period | {min(pipit.daily_counts)} to {max(pipit.daily_counts)} |",
        "",
        "### Records per year",
        "",
        "Counts include records assigned to a complete calendar date; years "
        "with no records are omitted. The latest year may be partial.",
        "",
        "| Year | Records |",
        "|---:|---:|",
    ]
    lines.extend(
        f"| {year} | {format_count(yearly_counts[year])} |"
        for year in sorted(yearly_counts)
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
        f"| ≥{threshold} records/day | {format_count(all_thresholds[threshold])} "
        f"| {format_count(weather_thresholds[threshold])} |"
        for threshold in (10, 25, 50)
    )
    lines.extend(
        [
            "",
            "## Comparison with Bird-Predict candidate species",
            "",
            "Each species was queried from GBIF in the same run using the same "
            "country and event-date facet method. The first table covers all "
            "complete-date years; the second uses only the shared weather dates.",
            "",
            "| Species | GBIF records | Complete-date records | Observation days | ≥10 days | ≥25 days | ≥50 days |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for species in species_data:
        counts = thresholds(species.daily_counts)
        lines.append(
            f"| {species.common_name} | {format_count(species.total_records)} "
            f"| {format_count(species.dated_records)} "
            f"| {format_count(len(species.daily_counts))} "
            f"| {format_count(counts[10])} | {format_count(counts[25])} "
            f"| {format_count(counts[50])} |"
        )
    lines.extend(
        [
            "",
            "| Species | Complete-date records in weather window | Observation days | ≥10 days | ≥25 days | ≥50 days |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    weather_species_counts: dict[str, dict[int, int]] = {}
    for species in species_data:
        in_weather = {
            day: count
            for day, count in species.daily_counts.items()
            if day in weather_dates
        }
        counts = thresholds(in_weather)
        weather_species_counts[species.common_name] = counts
        lines.append(
            f"| {species.common_name} | {format_count(sum(in_weather.values()))} "
            f"| {format_count(len(in_weather))} "
            f"| {format_count(counts[10])} | {format_count(counts[25])} "
            f"| {format_count(counts[50])} |"
        )

    yellow_browed = species_data[1]
    pallid_swift = species_data[2]
    manx_shearwater = species_data[3]
    manx_10 = weather_species_counts[manx_shearwater.common_name][10]
    pallid_thresholds = weather_species_counts[pallid_swift.common_name]

    lines.extend(
        [
            "",
            "## Forecasting feasibility and recommendation",
            "",
            f"Red-throated Pipit has {format_count(pipit.total_records)} GBIF "
            f"records, versus {format_count(yellow_browed.total_records)} for "
            f"Yellow-browed Warbler, "
            f"{format_count(pallid_swift.total_records)} for Pallid Swift, and "
            f"{format_count(manx_shearwater.total_records)} for Manx Shearwater. "
            "Its target-event support in the common weather period is "
            f"{weather_thresholds[10]} ≥10-record days, "
            f"{weather_thresholds[25]} ≥25-record "
            f"days, and {weather_thresholds[50]} ≥50-record days.",
            "",
        ]
    )
    lines.extend(
        [
            "Against Manx Shearwater, the Pipit has more positive days at all "
            "three thresholds: "
            f"{weather_thresholds[10]} vs {manx_10} at ≥10, "
            f"{weather_thresholds[25]} vs "
            f"{weather_species_counts[manx_shearwater.common_name][25]} at ≥25, "
            f"and {weather_thresholds[50]} vs "
            f"{weather_species_counts[manx_shearwater.common_name][50]} at ≥50.",
            "Against Pallid Swift, the Pipit has more ≥10-record days "
            f"({weather_thresholds[10]} vs {pallid_thresholds[10]}), but fewer "
            f"≥25-record days ({weather_thresholds[25]} vs "
            f"{pallid_thresholds[25]}) and ≥50-record days "
            f"({weather_thresholds[50]} vs {pallid_thresholds[50]}).",
            "",
            "This makes the Pipit a better-supported next experiment than "
            "Manx Shearwater, particularly for the ≥10 target, but does not "
            "establish it as a better forecaster than Pallid Swift.",
            "",
        ]
    )
    lines.extend(
        [
            "",
            "GBIF volume and high-count-day totals indicate data availability, "
            "not forecast skill. Before choosing it over the existing targets, "
            "it would still need the same forward-chained evaluation against "
            "seasonal baselines, with enough positive events in the held-out "
            "years to make metrics interpretable.",
            "",
            "**Recommendation:** prioritize Red-throated Pipit over Manx "
            "Shearwater for the next exploratory Bird-Predict evaluation. "
            "Treat it as a plausible ≥10-event target, not as an established "
            "upgrade over Pallid Swift; do not promote it operationally until "
            "it passes the shared forward-chained evaluation.",
            "",
            "## Data caveats",
            "",
            "- GBIF `country=NL` is the country-code filter, not a coordinate-"
            "based Netherlands boundary.",
            "- GBIF records represent reported occurrences, not independent "
            "birds or population abundance. Reporting effort and data-source "
            "coverage can vary over time.",
            f"- Of {format_count(pipit.total_records)} total records, "
            f"{format_count(no_date_records)} have no event-date facet and "
            f"{format_count(pipit.partial_date_records)} have only a partial "
            "date.",
            "- The total is a GBIF count and includes records without usable "
            "day-level dates. Facets can change as GBIF is updated.",
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
