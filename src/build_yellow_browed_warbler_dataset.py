"""Build Yellow-browed Warbler daily counts from GBIF occurrence facets."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPECIES_NAME = "Phylloscopus inornatus"
GBIF_TAXON_KEY = 2493095
COUNTRY_CODE = "NL"
FACET_LIMIT = 10_000
GBIF_SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"
KNMI_FILE = ROOT / "data/raw/result (1).txt"
FACET_OUTPUT = ROOT / "data/raw/yellow_browed_warbler_event_date_facets.csv"
DAILY_OUTPUT = ROOT / "data/processed/yellow_browed_warbler_daily_counts.csv"
KNMI_COLUMNS = ["STN", "DATE", "DDVEC", "FG", "FHX", "TG", "TN", "TX", "RH", "PX"]


def fetch_event_date_facets() -> tuple[int, pd.DataFrame]:
    """Fetch GBIF's grouped event-date counts for the species and country."""
    query = urlencode(
        {
            "taxonKey": GBIF_TAXON_KEY,
            "country": COUNTRY_CODE,
            "limit": 0,
            "facet": "eventDate",
            "facetLimit": FACET_LIMIT,
        }
    )
    request = Request(
        f"{GBIF_SEARCH_URL}?{query}",
        headers={"User-Agent": "bird-predict-second/1.0"},
    )
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)

    if len(payload["facets"]) != 1:
        raise RuntimeError("GBIF did not return the requested event-date facet.")
    facet = payload["facets"][0]
    if facet["field"] != "eventDateInterval":
        raise RuntimeError(
            f"Unexpected GBIF date facet field: {facet['field']!r}."
        )
    if len(facet["counts"]) >= FACET_LIMIT:
        raise RuntimeError(
            f"GBIF returned {FACET_LIMIT:,} or more date buckets; "
            "increase FACET_LIMIT before using this summary."
        )

    date_facets = pd.DataFrame(facet["counts"]).rename(
        columns={"name": "gbif_event_date", "count": "record_count"}
    )
    return int(payload["count"]), date_facets


def build_daily_counts(
    date_facets: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, int]:
    """Apply the Pallid Swift event-date rule and KNMI weather calendar."""
    if not KNMI_FILE.is_file():
        raise FileNotFoundError(f"KNMI daily data file not found: {KNMI_FILE}")

    knmi = pd.read_csv(
        KNMI_FILE,
        comment="#",
        header=None,
        names=KNMI_COLUMNS,
        skipinitialspace=True,
    )
    knmi_dates = pd.to_datetime(
        knmi["DATE"].astype("string"), format="%Y%m%d", errors="coerce"
    ).dropna()
    if knmi_dates.empty:
        raise ValueError(f"No valid KNMI dates were found in {KNMI_FILE}.")
    weather_calendar = pd.date_range(knmi_dates.min(), knmi_dates.max(), freq="D")

    parsed_dates = pd.to_datetime(
        date_facets["gbif_event_date"].astype("string").str[:10],
        errors="coerce",
    )
    dated_facets = date_facets.assign(parsed_date=parsed_dates).dropna(
        subset=["parsed_date"]
    )
    observed_daily_counts = dated_facets.groupby("parsed_date")[
        "record_count"
    ].sum()
    daily_counts = (
        observed_daily_counts.reindex(weather_calendar, fill_value=0)
        .rename_axis("date")
        .rename("record_count")
        .to_frame()
    )
    yearly_counts = observed_daily_counts.groupby(
        observed_daily_counts.index.year
    ).sum()
    outside_calendar_counts = observed_daily_counts.loc[
        ~observed_daily_counts.index.isin(weather_calendar)
    ]
    return (
        daily_counts,
        yearly_counts,
        observed_daily_counts,
        int(outside_calendar_counts.sum()),
    )


def main() -> None:
    record_total, date_facets = fetch_event_date_facets()
    (
        daily_counts,
        yearly_counts,
        observed_daily_counts,
        outside_calendar_records,
    ) = build_daily_counts(date_facets)

    FACET_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DAILY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    date_facets.to_csv(FACET_OUTPUT, index=False)
    daily_counts.to_csv(DAILY_OUTPUT, date_format="%Y-%m-%d")

    top_20 = (
        daily_counts.reset_index()
        .sort_values(
            ["record_count", "date"],
            ascending=[False, True],
            kind="stable",
        )
        .head(20)
    )
    dated_record_total = int(date_facets["record_count"].sum())
    valid_dated_record_total = int(observed_daily_counts.sum())
    print(f"Species: {SPECIES_NAME} (GBIF taxon key {GBIF_TAXON_KEY})")
    print(f"Country filter: {COUNTRY_CODE}")
    print(f"Total GBIF records: {record_total:,}")
    print(f"Records with valid parsed event dates: {valid_dated_record_total:,}")
    print(f"Unique observation days: {len(observed_daily_counts):,}")
    print(
        f"Daily count calendar: {daily_counts.index.min().date()} to "
        f"{daily_counts.index.max().date()} "
        f"({len(daily_counts):,} days; based on KNMI station-235 coverage)"
    )
    print(
        f"Valid-date records outside the KNMI calendar: "
        f"{outside_calendar_records:,}"
    )
    print(
        f"Records in year-only/unparseable GBIF date facets: "
        f"{dated_record_total - valid_dated_record_total:,}"
    )
    print(
        f"Records without an event-date facet: "
        f"{record_total - dated_record_total:,}"
    )
    print("\nYearly counts (records with valid parsed event dates):")
    print(yearly_counts.rename("records").to_string())
    print("\nTop 20 influx dates within the KNMI calendar:")
    print(top_20.to_string(index=False))
    for threshold in (10, 25, 50):
        calendar_dates = int(daily_counts["record_count"].ge(threshold).sum())
        all_dates = int(observed_daily_counts.ge(threshold).sum())
        print(
            f"Dates with >= {threshold} records: {calendar_dates:,} "
            f"within KNMI calendar; {all_dates:,} across all valid-date years"
        )
    print(f"\nSaved event-date facets: {FACET_OUTPUT.relative_to(ROOT)}")
    print(f"Saved daily count dataset: {DAILY_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
