"""Download and summarize GBIF occurrences for the Eastern Vagrancy Index."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

if __package__:
    from . import build_atlantic_vagrancy_dataset as shared
else:
    import build_atlantic_vagrancy_dataset as shared


ROOT = Path(__file__).resolve().parents[1]
TARGET_COUNTRIES = shared.TARGET_COUNTRIES
SPECIES_SUMMARY_OUTPUT = ROOT / "outputs/eastern_vagrancy_species_summary.csv"
EVENTS_OUTPUT = ROOT / "outputs/eastern_vagrancy_events.csv"
DAILY_OUTPUT = ROOT / "outputs/eastern_vagrancy_daily_counts.csv"

# Add future eastern Palearctic taxa here. Set "rank" to SUBSPECIES for
# subspecies; records must then be identified to that subspecies in GBIF.
# Booted Warbler is listed as Acrocephalus dumetorum in the requirements,
# which is Blyth's Reed Warbler in GBIF, so Iduna caligata is a separate entry.
EASTERN_VAGRANCY_SPECIES = [
    {"species": "Yellow-browed Warbler", "scientific_name": "Phylloscopus inornatus", "core": True},
    {"species": "Red-flanked Bluetail", "scientific_name": "Tarsiger cyanurus", "core": True},
    {"species": "Olive-backed Pipit", "scientific_name": "Anthus hodgsoni", "core": True},
    {"species": "Pallas's Warbler", "scientific_name": "Phylloscopus proregulus", "core": True},
    {"species": "Dusky Warbler", "scientific_name": "Phylloscopus fuscatus", "core": True},
    {
        "species": "Siberian Chiffchaff",
        "scientific_name": "Phylloscopus collybita tristis",
        "core": True,
        "rank": "SUBSPECIES",
    },
    {"species": "Lanceolated Warbler", "scientific_name": "Locustella lanceolata", "core": False},
    {"species": "Blyth's Reed Warbler", "scientific_name": "Acrocephalus dumetorum", "core": False},
    {"species": "Paddyfield Warbler", "scientific_name": "Acrocephalus agricola", "core": False},
    {"species": "Citrine Wagtail", "scientific_name": "Motacilla citreola", "core": False},
    {"species": "Pechora Pipit", "scientific_name": "Anthus gustavi", "core": False},
    {"species": "Taiga Flycatcher", "scientific_name": "Ficedula albicilla", "core": False},
    {"species": "Booted Warbler", "scientific_name": "Iduna caligata", "core": False},
]

LOGGER = logging.getLogger(__name__)


def resolve_taxon_key(scientific_name: str, rank: str = "SPECIES") -> int:
    query = urlencode({"name": scientific_name, "rank": rank, "strict": "true"})
    match = shared._fetch_json(f"{shared.GBIF_API}/species/match?{query}")
    if (
        match.get("matchType") != "EXACT"
        or match.get("status") != "ACCEPTED"
        or match.get("rank") != rank
    ):
        raise RuntimeError(
            f"GBIF did not return an exact accepted {rank.lower()} match for "
            f"{scientific_name}: {match}"
        )
    return int(match["usageKey"])


def load_all_occurrences(
    species_registry: list[dict[str, object]] = EASTERN_VAGRANCY_SPECIES,
    compact: bool = False,
    year_range: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """Download (or read from cache) every registry species in every country.

    compact=True keeps only the columns needed for counts and mapping, which
    bounds memory for very large guilds.

    Species that GBIF cannot resolve exactly are logged and skipped so that an
    optional taxon never blocks the guild.
    """
    if not species_registry:
        raise ValueError("The species registry must not be empty.")
    frames: list[pd.DataFrame] = []
    for species in species_registry:
        common_name = str(species["species"])
        scientific_name = str(species["scientific_name"])
        try:
            taxon_key = resolve_taxon_key(
                scientific_name, str(species.get("rank", "SPECIES"))
            )
        except RuntimeError as error:
            if species.get("core"):
                raise
            LOGGER.warning("Skipping %s: %s", common_name, error)
            continue
        LOGGER.info("Downloading %s", common_name)
        for country_code, country_name in TARGET_COUNTRIES.items():
            LOGGER.info(
                "Retrieving %s in %s (%s)", common_name, country_name, country_code
            )
            occurrences = shared.download_species_country(
                common_name,
                scientific_name,
                country_code,
                taxon_key,
                compact,
                year_range,
            )
            if not occurrences.empty:
                occurrences["species"] = common_name
                occurrences["scientific_name"] = scientific_name
                frames.append(occurrences)
    if not frames:
        return pd.DataFrame(
            columns=[*shared.OCCURRENCE_COLUMNS, "date", "species", "scientific_name"]
        )
    combined = shared._drop_duplicate_occurrences(
        pd.concat(frames, ignore_index=True)
    )
    return combined.sort_values(["date", "species"]).reset_index(drop=True)


def build_outputs(
    occurrences: pd.DataFrame,
    species_registry: list[dict[str, object]] = EASTERN_VAGRANCY_SPECIES,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return shared.build_outputs(occurrences, species_registry)


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
    LOGGER.info(
        "Saved %s event days / %s records to %s",
        f"{len(daily):,}",
        f"{int(daily['count'].sum()) if not daily.empty else 0:,}",
        DAILY_OUTPUT.relative_to(ROOT),
    )
    LOGGER.info("Species records:\n%s", summary.to_string(index=False))


if __name__ == "__main__":
    main()
