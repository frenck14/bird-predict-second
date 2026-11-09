"""Assess GBIF support for Bird-Predict candidate species."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import csv

if __package__:
    from .assess_manx_shearwater_feasibility import (
        ROOT,
        SpeciesData,
        fetch_species_data,
        format_count,
        load_weather_dates,
        thresholds,
    )
else:
    from assess_manx_shearwater_feasibility import (
        ROOT,
        SpeciesData,
        fetch_species_data,
        format_count,
        load_weather_dates,
        thresholds,
    )


REPORT_FILE = ROOT / "reports/candidate_species_assessment.md"
FORECAST_METRICS_FILE = ROOT / "data/processed/species_forecast_metrics.csv"
RAW_DIRECTORY = ROOT / "data/raw"
TARGET_SPECIES = (
    ("Blauwstaart", "Tarsiger cyanurus"),
    ("Citroenkwikstaart", "Motacilla citreola"),
    ("Kleine Spotvogel", "Iduna caligata"),
    ("Veldrietzanger", "Acrocephalus agricola"),
)
COMPARISON_SPECIES = (
    ("Yellow-browed Warbler", "Phylloscopus inornatus"),
    ("Pallid Swift", "Apus pallidus"),
    ("Red-throated Pipit", "Anthus cervinus"),
    ("Manx Shearwater", "Puffinus puffinus"),
)
SPECIES = TARGET_SPECIES + COMPARISON_SPECIES
THRESHOLDS = (10, 25, 50)


def archive_facets(species: SpeciesData) -> Path:
    slug = species.common_name.lower().replace(" ", "_")
    filepath = RAW_DIRECTORY / f"{slug}_event_date_facets.csv"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["name", "count"])
        writer.writeheader()
        writer.writerows(species.facets)
    return filepath


def records_per_year(species: SpeciesData) -> dict[int, int]:
    yearly: defaultdict[int, int] = defaultdict(int)
    for event_day, count in species.daily_counts.items():
        yearly[event_day.year] += count
    return dict(sorted(yearly.items()))


def top_days(species: SpeciesData) -> list[tuple[date, int]]:
    return sorted(
        species.daily_counts.items(), key=lambda item: (-item[1], item[0])
    )[:20]


def weather_window_counts(
    species: SpeciesData, weather_dates: set[date]
) -> dict[str, int]:
    in_window = {
        day: count
        for day, count in species.daily_counts.items()
        if day in weather_dates
    }
    counts = thresholds(in_window)
    return {
        "complete_date_records": sum(in_window.values()),
        "observation_days": len(in_window),
        **{
            f"days_ge_{threshold}": counts[threshold]
            for threshold in THRESHOLDS
        },
        **{
            f"years_with_days_ge_{threshold}": len(
                {
                    day.year
                    for day, count in in_window.items()
                    if count >= threshold
                }
            )
            for threshold in THRESHOLDS
        },
    }


def load_forecast_benchmark_summary() -> dict[str, dict[str, float | int]] | None:
    if not FORECAST_METRICS_FILE.is_file():
        return None

    scenario_best: dict[tuple[str, int, int], tuple[float, float]] = {}
    with FORECAST_METRICS_FILE.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        required = {
            "species",
            "threshold",
            "horizon_days",
            "model",
            "pr_auc",
            "seasonal_baseline_pr_auc",
        }
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                f"Forecast metrics must include {sorted(required)}: "
                f"{FORECAST_METRICS_FILE}"
            )
        for row in reader:
            if row["model"] == "Seasonal baseline" or not row["pr_auc"]:
                continue
            pr_auc = float(row["pr_auc"])
            baseline_pr_auc = float(row["seasonal_baseline_pr_auc"])
            if not (pr_auc == pr_auc and baseline_pr_auc == baseline_pr_auc):
                continue
            key = (row["species"], int(row["threshold"]), int(row["horizon_days"]))
            current = scenario_best.get(key)
            if current is None or pr_auc > current[0]:
                scenario_best[key] = (pr_auc, baseline_pr_auc)

    grouped: defaultdict[str, list[float]] = defaultdict(list)
    wins: defaultdict[str, int] = defaultdict(int)
    for (species, _, _), (pr_auc, baseline_pr_auc) in scenario_best.items():
        lift = pr_auc - baseline_pr_auc
        grouped[species].append(lift)
        wins[species] += int(lift > 0)

    summary = {
        species: {
            "mean_pr_auc_lift": sum(lifts) / len(lifts),
            "scenarios_beating_seasonality": wins[species],
            "scenario_count": len(lifts),
        }
        for species, lifts in grouped.items()
        if lifts
    }
    if not summary:
        raise ValueError(
            f"No weather-model forecast benchmark rows found in "
            f"{FORECAST_METRICS_FILE}."
        )
    return summary


def format_yearly_table(species: SpeciesData) -> list[str]:
    yearly = records_per_year(species)
    lines = [
        "### Records per year",
        "",
        "Counts include records with complete calendar dates; years without "
        "records are omitted. The most recent year may be incomplete.",
        "",
        "| Year | Complete-date records |",
        "|---:|---:|",
    ]
    lines.extend(
        f"| {year} | {format_count(count)} |"
        for year, count in yearly.items()
    )
    return lines


def format_top_days_table(species: SpeciesData) -> list[str]:
    days = top_days(species)
    lines = [
        "### Top 20 record-count days",
        "",
        "| Rank | Date | Records |",
        "|---:|---|---:|",
    ]
    lines.extend(
        f"| {rank} | {event_day} | {format_count(count)} |"
        for rank, (event_day, count) in enumerate(days, start=1)
    )
    return lines


def build_report(
    species_data: list[SpeciesData],
    weather_dates: set[date],
    retrieved_date: date,
    forecast_benchmarks: dict[str, dict[str, float | int]] | None,
) -> str:
    by_name = {species.common_name: species for species in species_data}
    weather_start, weather_end = min(weather_dates), max(weather_dates)
    window_metrics = {
        species.common_name: weather_window_counts(species, weather_dates)
        for species in species_data
    }

    ranked = sorted(
        species_data,
        key=lambda species: (
            -window_metrics[species.common_name]["days_ge_10"],
            -window_metrics[species.common_name]["days_ge_25"],
            -window_metrics[species.common_name]["days_ge_50"],
            -window_metrics[species.common_name]["years_with_days_ge_10"],
            -window_metrics[species.common_name]["observation_days"],
            -window_metrics[species.common_name]["complete_date_records"],
            species.common_name,
        ),
    )

    lines = [
        "# Bird-Predict Candidate-Species Assessment",
        "",
        f"GBIF data retrieved **{retrieved_date.isoformat()}**.",
        "",
        "## Scope and method",
        "",
        "GBIF Species Match and the occurrence event-date facet API were "
        "queried for each taxon in the same run. Each match must be an exact, "
        "accepted species-level match; occurrence queries use `taxonKey` and "
        "`country=NL`, with no basis-of-record filter. Total records are the "
        "GBIF occurrence count. Complete-date records and observation days "
        "are derived from event-date facet buckets whose first ten characters "
        "form a valid ISO calendar date; partial dates are excluded from "
        "day-level metrics. Unfaceted records cannot be assigned a date.",
        "",
        f"The shared KNMI weather calendar spans **{weather_start} to "
        f"{weather_end}** ({len(weather_dates):,} dates). Candidate "
        "forecastability is assessed using only dated records that fall "
        "within this common weather window. The shared calendar's uncovered "
        "historical years are not treated as weather-supported events.",
        "",
        "## Candidate species: record summaries",
        "",
        "| Species | Scientific name | GBIF records | Complete-date records | Partial-date records | No-date records | Observation days | Complete-date period |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]

    for common_name, scientific_name in TARGET_SPECIES:
        species = by_name[common_name]
        facet_records = sum(int(row["count"]) for row in species.facets)
        no_date_records = species.total_records - facet_records
        period = (
            f"{min(species.daily_counts)} to {max(species.daily_counts)}"
            if species.daily_counts
            else "No complete dates"
        )
        lines.append(
            f"| {species.common_name} | *{scientific_name}* | "
            f"{format_count(species.total_records)} | "
            f"{format_count(species.dated_records)} | "
            f"{format_count(species.partial_date_records)} | "
            f"{format_count(no_date_records)} | "
            f"{format_count(len(species.daily_counts))} | {period} |"
        )

    lines.extend(
        [
            "",
            "## Candidate species: annual counts and peak days",
            "",
            "The following annual counts and top days cover all GBIF complete-"
            "date facets, including dates outside the KNMI weather calendar.",
            "",
        ]
    )
    for common_name, scientific_name in TARGET_SPECIES:
        species = by_name[common_name]
        lines.extend(
            [
                f"### {species.common_name} (*{scientific_name}*)",
                "",
                f"Archived date facets: "
                f"`data/raw/{common_name.lower().replace(' ', '_')}_event_date_facets.csv`.",
                "",
            ]
        )
        lines.extend(format_yearly_table(species))
        lines.append("")
        lines.extend(format_top_days_table(species))
        lines.extend(
            [
                "",
                "#### High-count days",
                "",
                "| Daily record threshold | All complete-date years | Shared KNMI weather calendar |",
                "|---:|---:|---:|",
            ]
        )
        all_counts = thresholds(species.daily_counts)
        window = window_metrics[species.common_name]
        lines.extend(
            f"| ≥{threshold} records/day | "
            f"{format_count(all_counts[threshold])} | "
            f"{format_count(window[f'days_ge_{threshold}'])} |"
            for threshold in THRESHOLDS
        )
        lines.append("")

    lines.extend(
        [
            "## Comparison with established Bird-Predict species",
            "",
            "The established comparison species were queried in the same GBIF "
            "run with the same country and event-date facet rules. This "
            "table's counts are limited to the common KNMI date range and "
            "are directly comparable across all eight taxa.",
            "",
            "| Rank by weather-window support | Species | GBIF records | Complete-date records (all dates) | Complete-date records (KNMI window) | Observation days (KNMI window) | ≥10 days | Years with ≥10 days | ≥25 days | ≥50 days |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    rank_lookup = {species.common_name: rank for rank, species in enumerate(ranked, 1)}
    for species in ranked:
        window = window_metrics[species.common_name]
        lines.append(
            f"| {rank_lookup[species.common_name]} | {species.common_name} | "
            f"{format_count(species.total_records)} | "
            f"{format_count(species.dated_records)} | "
            f"{format_count(window['complete_date_records'])} | "
            f"{format_count(window['observation_days'])} | "
            f"{format_count(window['days_ge_10'])} | "
            f"{format_count(window['years_with_days_ge_10'])} | "
            f"{format_count(window['days_ge_25'])} | "
            f"{format_count(window['days_ge_50'])} |"
        )

    lines.extend(
        [
            "",
            "## Forecast-potential ranking and recommendation",
            "",
            "The ranking above is a **data-support / feasibility ranking**, "
            "not a claim of measured forecast skill. It is ordered "
            "lexicographically by the number of ≥10-record days in the "
            "shared weather window, then ≥25 days, ≥50 days, the number of "
            "years with at least one ≥10-record day, observation days, and "
            "complete-date records in that window. The ≥10 target "
            "is the primary Bird-Predict event threshold; the higher "
            "thresholds indicate whether a taxon can support more selective "
            "targets. This transparent ordering avoids an arbitrary "
            "composite score.",
            "",
        ]
    )
    if forecast_benchmarks is None:
        lines.extend(
            [
                "No stored forward-chained benchmark was available at "
                "`data/processed/species_forecast_metrics.csv`; run "
                "`python src/forecast_species_comparison.py` to add the "
                "existing-species skill comparison. The newly assessed "
                "species have not yet been forecast-validated.",
                "",
            ]
        )
    else:
        benchmark_order = sorted(
            forecast_benchmarks,
            key=lambda name: (
                -float(forecast_benchmarks[name]["mean_pr_auc_lift"]),
                -int(forecast_benchmarks[name]["scenarios_beating_seasonality"]),
            ),
        )
        lines.extend(
            [
                "The four established species also have measured "
                "forward-chained results. Their ranking below is by mean "
                "best-model PR-AUC lift over the matched seasonal baseline "
                "across the 15 threshold/horizon scenarios. These results "
                "are empirical skill evidence; no such validation exists yet "
                "for the four new candidates.",
                "",
                "| Rank | Previously evaluated species | Mean PR-AUC lift | Scenarios beating seasonality |",
                "|---:|---|---:|---:|",
            ]
        )
        lines.extend(
            f"| {rank} | {species} | "
            f"{float(forecast_benchmarks[species]['mean_pr_auc_lift']):+.4f} | "
            f"{int(forecast_benchmarks[species]['scenarios_beating_seasonality'])}/"
            f"{int(forecast_benchmarks[species]['scenario_count'])} |"
            for rank, species in enumerate(benchmark_order, start=1)
        )
        lines.extend(
            [
                "",
                "Yellow-browed Warbler and Pallid Swift show stronger "
                "weather-model results than Red-throated Pipit and Manx "
                "Shearwater in the existing comparison. A high candidate "
                "rank by records alone cannot establish that weather "
                "improves its forecast.",
                "",
            ]
        )

    lines.extend(
        [
            "Among the four new candidates, the data-support ranking is "
            + (
                ", ".join(
                    f"{rank}. {species.common_name}"
                    for rank, species in enumerate(
                        [
                            species
                            for species in ranked
                            if species.common_name
                            in {name for name, _ in TARGET_SPECIES}
                        ],
                        start=1,
                    )
                )
                or "not available because no candidates were returned"
            )
            + ". Prioritize the top new candidate for a forward-chained "
            "experiment only if its ≥10 high-count dates span enough distinct "
            "years to permit meaningful held-out evaluation. If all four "
            "candidates have few or no ≥10 days in the KNMI window, their "
            "records are not yet adequate for this count-target methodology.",
            "",
            "### Interpretation and caveats",
            "",
            "- These are GBIF occurrence/reporting counts, not numbers of "
            "individual birds or population-abundance estimates.",
            "- GBIF reporting effort, data providers, and observer activity "
            "can vary by year and can be associated with both weather and "
            "season.",
            "- `country=NL` is GBIF's country-code filter and is not a "
            "coordinate-based Netherlands boundary.",
            "- The most recent year may be incomplete, date facets can change "
            "as GBIF is updated, and partial-date records do not count as "
            "complete-date observations.",
            "- Many top-count days may belong to one observation or reporting "
            "episode; positive dates should not be assumed independent.",
            "- The common KNMI calendar starts in 2010 and ends on "
            f"{weather_end}; older records are summarized but excluded from "
            "the weather-window feasibility ranking.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    weather_dates = load_weather_dates()
    species_data = [
        fetch_species_data(common_name, scientific_name)
        for common_name, scientific_name in SPECIES
    ]
    forecast_benchmarks = load_forecast_benchmark_summary()
    for common_name, _ in TARGET_SPECIES:
        archive_path = archive_facets(
            next(
                species
                for species in species_data
                if species.common_name == common_name
            )
        )
        print(f"Saved GBIF facets: {archive_path.relative_to(ROOT)}")

    report = build_report(
        species_data,
        weather_dates,
        datetime.now(timezone.utc).date(),
        forecast_benchmarks,
    )
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"Saved assessment: {REPORT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
