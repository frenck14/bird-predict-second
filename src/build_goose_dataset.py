"""Download and summarise GBIF goose records for the Winter Goose Module.

Goose records are far too numerous to page through (Greylag Goose alone has
roughly a million Dutch records), so daily counts come from GBIF's ``eventDate``
facet instead. Raw facet responses are cached under ``data/raw/goose_facets`` so
reruns work offline. Counts are *records*, not individual geese, and are
affected by observer effort.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

if __package__:
    from . import build_atlantic_vagrancy_dataset as shared
else:
    import build_atlantic_vagrancy_dataset as shared


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
RAW_DIRECTORY = ROOT / "data/raw/goose_facets"
DAILY_OUTPUT = OUTPUTS / "goose_daily_counts.csv"
SITE_COUNTS_OUTPUT = OUTPUTS / "goose_site_counts.csv"
SPECIES_SUMMARY_OUTPUT = OUTPUTS / "goose_species_summary.csv"

WINTER_MONTHS = (10, 11, 12, 1, 2, 3)
FIRST_YEAR = 2010
SITE_FIRST_YEAR = 2015
FACET_LIMIT = 1000
DAY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GBIF_API = shared.GBIF_API

# Common geese are counted in the Netherlands only (the weather inputs are
# Dutch coastal stations). Rare geese are pooled across the Netherlands and its
# neighbours so that species-specific models have a chance of seeing events.
COMMON_COUNTRIES = ("NL",)
RARE_COUNTRIES = ("NL", "BE", "DE", "DK")
EUROPEAN_COUNTRIES = {
    "Red-breasted Goose": ("NL", "BE", "DE", "DK", "SE", "FI", "PL"),
    "Snow Goose": ("GB", "IE", "NL", "BE", "DE", "DK", "FR"),
    "Ross's Goose": ("GB", "IE", "NL", "BE", "DE", "DK", "FR"),
}

# taxon_keys override name resolution where GBIF only knows a subspecies.
GOOSE_SPECIES = [
    {"species": "Greater White-fronted Goose", "dutch": "Kolgans", "scientific_name": "Anser albifrons", "group": "common"},
    {"species": "Tundra Bean Goose", "dutch": "Toendrarietgans", "scientific_name": "Anser serrirostris", "group": "common"},
    {"species": "Barnacle Goose", "dutch": "Brandgans", "scientific_name": "Branta leucopsis", "group": "common"},
    {"species": "Greylag Goose", "dutch": "Grauwe Gans", "scientific_name": "Anser anser", "group": "common"},
    {"species": "Brent Goose", "dutch": "Rotgans", "scientific_name": "Branta bernicla", "group": "common"},
    {"species": "Pink-footed Goose", "dutch": "Kleine Rietgans", "scientific_name": "Anser brachyrhynchus", "group": "common"},
    {"species": "Red-breasted Goose", "dutch": "Roodhalsgans", "scientific_name": "Branta ruficollis", "group": "rare"},
    {"species": "Lesser White-fronted Goose", "dutch": "Dwerggans", "scientific_name": "Anser erythropus", "group": "rare"},
    {"species": "Snow Goose", "dutch": "Sneeuwgans", "scientific_name": "Anser caerulescens", "group": "rare"},
    {"species": "Ross's Goose", "dutch": "Ross' gans", "scientific_name": "Anser rossii", "group": "rare"},
    {"species": "Black Brant", "dutch": "Zwarte Rotgans", "scientific_name": "Branta bernicla nigricans", "group": "rare", "taxon_keys": [5232449]},
]

COMMON_GEESE = [row["species"] for row in GOOSE_SPECIES if row["group"] == "common"]
RARE_GEESE = [row["species"] for row in GOOSE_SPECIES if row["group"] == "rare"]

REGIONS = (
    "Lauwersmeer", "Friesland", "Groningen", "Texel",
    "Noord-Holland", "Flevoland", "IJsselmeergebied", "Zeeland",
)

# (site, region, latitude, longitude). Each site is a ~0.16 x 0.24 degree box
# around the centre; boxes are used only to weight sites by historical records.
GOOSE_SITES = [
    ("Lauwersmeer National Park", "Lauwersmeer", 53.37, 6.20),
    ("Zoutkamp & Oostpolder", "Lauwersmeer", 53.33, 6.30),
    ("Het Bildt", "Friesland", 53.27, 5.65),
    ("Friese Waddenkust (Koehool)", "Friesland", 53.35, 5.60),
    ("Friese Greide (Oudemirdum)", "Friesland", 52.85, 5.55),
    ("Ameland", "Friesland", 53.45, 5.75),
    ("Oldambt & Dollard", "Groningen", 53.25, 7.15),
    ("Reiderland", "Groningen", 53.17, 7.05),
    ("Pieterburen & Noordpolder", "Groningen", 53.40, 6.50),
    ("Eemshaven & Delfzijl", "Groningen", 53.33, 6.93),
    ("Texel Noord (Eierland)", "Texel", 53.17, 4.85),
    ("Texel Midden (Oosterend)", "Texel", 53.07, 4.90),
    ("Texel Zuid (Den Hoorn)", "Texel", 53.00, 4.77),
    ("Zwanenwater & Callantsoog", "Noord-Holland", 52.80, 4.70),
    ("Anna Paulowna Polder", "Noord-Holland", 52.87, 4.85),
    ("Schermer", "Noord-Holland", 52.62, 4.80),
    ("Wormer- en Jisperveld", "Noord-Holland", 52.50, 4.85),
    ("Oostvaardersplassen", "Flevoland", 52.45, 5.35),
    ("Markerwadden & Lelystad", "Flevoland", 52.55, 5.40),
    ("Swifterbant & Zuidelijk Flevoland", "Flevoland", 52.57, 5.65),
    ("Noordoostpolder (Kuinderbos)", "Flevoland", 52.75, 5.85),
    ("Afsluitdijk & Breezanddijk", "IJsselmeergebied", 53.05, 5.25),
    ("Makkum & Workum coast", "IJsselmeergebied", 52.98, 5.43),
    ("Wieringermeer", "IJsselmeergebied", 52.80, 5.05),
    ("Hoorn & Enkhuizen (Markermeer)", "IJsselmeergebied", 52.65, 5.15),
    ("Oosterschelde (Neeltje Jans)", "Zeeland", 51.63, 3.78),
    ("Zuid-Beveland (Kapelle)", "Zeeland", 51.47, 4.00),
    ("Grevelingen & Schouwen-Duiveland", "Zeeland", 51.72, 3.95),
    ("Walcheren & Veerse Meer", "Zeeland", 51.55, 3.65),
    ("Verdronken Land van Saeftinghe", "Zeeland", 51.35, 4.20),
]
SITE_HALF_LATITUDE = 0.08
SITE_HALF_LONGITUDE = 0.12

LOGGER = logging.getLogger(__name__)


def taxon_keys(entry: dict[str, object]) -> list[int]:
    if entry.get("taxon_keys"):
        return [int(key) for key in entry["taxon_keys"]]  # type: ignore[union-attr]
    return [shared.resolve_taxon_key(str(entry["scientific_name"]))]


def countries_for(entry: dict[str, object]) -> tuple[str, ...]:
    species = str(entry["species"])
    if species in EUROPEAN_COUNTRIES:
        return EUROPEAN_COUNTRIES[species]
    return COMMON_COUNTRIES if entry["group"] == "common" else RARE_COUNTRIES


def cache_path(entry: dict[str, object], year: int, raw_directory: Path) -> Path:
    species = str(entry["species"])
    countries = countries_for(entry)
    scope = (
        f"_{'-'.join(countries)}"
        if species in EUROPEAN_COUNTRIES
        else ""
    )
    return raw_directory / f"{_slug(species)}{scope}_{year}.csv"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _facet_query(
    keys: list[int],
    countries: tuple[str, ...],
    *,
    facet: str | None,
    year: int | str,
    extra: list[tuple[str, str]] | None = None,
) -> dict[str, object]:
    params: list[tuple[str, str]] = [("limit", "0"), ("hasCoordinate", "true"),
                                     ("basisOfRecord", "HUMAN_OBSERVATION"),
                                     ("year", str(year))]
    params += [("taxonKey", str(key)) for key in keys]
    params += [("country", code) for code in countries]
    params += [("month", str(month)) for month in WINTER_MONTHS]
    if facet:
        params += [("facet", facet), ("facetLimit", str(FACET_LIMIT))]
    params += extra or []
    return shared._fetch_json(f"{GBIF_API}/occurrence/search?{urlencode(params)}")


def parse_day_facets(response: dict[str, object]) -> dict[str, int]:
    """Keep exact-day eventDate buckets; GBIF also returns multi-day intervals."""
    counts: dict[str, int] = {}
    for facet in response.get("facets", []):  # type: ignore[union-attr]
        for bucket in facet.get("counts", []):
            name = str(bucket["name"])
            if DAY_PATTERN.match(name):
                counts[name] = counts.get(name, 0) + int(bucket["count"])
    return counts


def download_species_daily(
    entry: dict[str, object],
    years: range,
    raw_directory: Path = RAW_DIRECTORY,
    refresh_current_year: bool = True,
) -> pd.DataFrame:
    keys = taxon_keys(entry)
    countries = countries_for(entry)
    raw_directory.mkdir(parents=True, exist_ok=True)
    frames = []
    for year in years:
        path = cache_path(entry, year, raw_directory)
        stale = refresh_current_year and year == date.today().year
        if path.is_file() and not stale:
            frame = pd.read_csv(path)
        else:
            counts = parse_day_facets(
                _facet_query(keys, countries, facet="eventDate", year=year)
            )
            frame = pd.DataFrame({"date": list(counts), "count": list(counts.values())})
            frame.to_csv(path, index=False)
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["date", "count"]
    )
    combined["species"] = entry["species"]
    return combined.loc[:, ["date", "species", "count"]]


def build_daily_counts(
    registry: list[dict[str, object]] = GOOSE_SPECIES,
    years: range | None = None,
) -> pd.DataFrame:
    years = years or range(FIRST_YEAR, date.today().year + 1)
    frames = []
    for entry in registry:
        LOGGER.info("Downloading daily counts for %s", entry["species"])
        frames.append(download_species_daily(entry, years))
    daily = pd.concat(frames, ignore_index=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily = daily.dropna(subset=["date"])
    daily["count"] = daily["count"].astype(int)
    return (
        daily.groupby(["date", "species"], as_index=False)["count"].sum()
        .sort_values(["species", "date"]).reset_index(drop=True)
    )


def site_box(latitude: float, longitude: float) -> list[tuple[str, str]]:
    return [
        ("decimalLatitude", f"{latitude - SITE_HALF_LATITUDE:.4f},{latitude + SITE_HALF_LATITUDE:.4f}"),
        ("decimalLongitude", f"{longitude - SITE_HALF_LONGITUDE:.4f},{longitude + SITE_HALF_LONGITUDE:.4f}"),
    ]


def build_site_counts(registry: list[dict[str, object]] = GOOSE_SPECIES) -> pd.DataFrame:
    """Winter records per site for common and rare geese (weights hotspots)."""
    year_range = f"{SITE_FIRST_YEAR},{date.today().year}"
    groups = {
        group: [key for entry in registry if entry["group"] == group for key in taxon_keys(entry)]
        for group in ("common", "rare")
    }
    rows = []
    for site, region, latitude, longitude in GOOSE_SITES:
        row: dict[str, object] = {
            "site": site, "region": region,
            "latitude": latitude, "longitude": longitude,
        }
        for group, keys in groups.items():
            response = _facet_query(
                keys, ("NL",), facet=None, year=year_range,
                extra=site_box(latitude, longitude),
            )
            row[f"{group}_records"] = int(response.get("count", 0))
        rows.append(row)
        LOGGER.info("Site %s: %s", site, row)
    return pd.DataFrame(rows)


def species_summary(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame(columns=["species", "group", "records", "event_days", "first_date", "last_date"])
    groups = {row["species"]: row["group"] for row in GOOSE_SPECIES}
    summary = daily.groupby("species").agg(
        records=("count", "sum"), event_days=("date", "nunique"),
        first_date=("date", "min"), last_date=("date", "max"),
    ).reset_index()
    summary.insert(1, "group", summary["species"].map(groups))
    return summary.sort_values("records", ascending=False).reset_index(drop=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    daily = build_daily_counts()
    daily.to_csv(DAILY_OUTPUT, index=False, date_format="%Y-%m-%d")
    summary = species_summary(daily)
    summary.to_csv(SPECIES_SUMMARY_OUTPUT, index=False, date_format="%Y-%m-%d")
    build_site_counts().to_csv(SITE_COUNTS_OUTPUT, index=False)
    LOGGER.info("Goose species records:\n%s", summary.to_string(index=False))


if __name__ == "__main__":
    main()
