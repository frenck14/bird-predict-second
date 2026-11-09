"""Download and summarize GBIF occurrences for the Seabird Index."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from . import build_atlantic_vagrancy_dataset as shared
    from . import build_eastern_vagrancy_dataset as eastern
else:
    import build_atlantic_vagrancy_dataset as shared
    import build_eastern_vagrancy_dataset as eastern


ROOT = Path(__file__).resolve().parents[1]
TARGET_COUNTRIES = shared.TARGET_COUNTRIES
SPECIES_SUMMARY_OUTPUT = ROOT / "outputs/seabird_species_summary.csv"
EVENTS_OUTPUT = ROOT / "outputs/seabird_events.csv"
DAILY_OUTPUT = ROOT / "outputs/seabird_daily_counts.csv"
SPECIES_DAILY_OUTPUT = ROOT / "outputs/seabird_species_daily_counts.csv"
THRESHOLD_OUTPUT = ROOT / "outputs/seabird_threshold.json"
INFLUX_PERCENTILE = 90
OCCURRENCE_YEAR_RANGE = (2010, date.today().year)

# Add future seabird taxa here. Names must be the GBIF-accepted names: the
# resolver rejects synonyms, so Leach's Storm-petrel is Oceanodroma leucorhoa,
# Sooty and Great Shearwater are Puffinus griseus / Puffinus gravis, and Cory's
# Shearwater is listed as Calonectris diomedea (Scopoli's/Cory's combined).
SEABIRD_SPECIES = [
    {"species": "Northern Fulmar", "scientific_name": "Fulmarus glacialis", "core": True},
    {"species": "European Storm-petrel", "scientific_name": "Hydrobates pelagicus", "core": True},
    {"species": "Leach's Storm-petrel", "scientific_name": "Oceanodroma leucorhoa", "core": True},
    {"species": "Sooty Shearwater", "scientific_name": "Puffinus griseus", "core": True},
    {"species": "Great Shearwater", "scientific_name": "Puffinus gravis", "core": True},
    {"species": "Manx Shearwater", "scientific_name": "Puffinus puffinus", "core": True},
    {"species": "Balearic Shearwater", "scientific_name": "Puffinus mauretanicus", "core": True},
    {"species": "Pomarine Skua", "scientific_name": "Stercorarius pomarinus", "core": True},
    {"species": "Arctic Skua", "scientific_name": "Stercorarius parasiticus", "core": True},
    {"species": "Great Skua", "scientific_name": "Stercorarius skua", "core": True},
    {"species": "Sabine's Gull", "scientific_name": "Xema sabini", "core": True},
    {"species": "Long-tailed Skua", "scientific_name": "Stercorarius longicaudus", "core": False},
    {"species": "Grey Phalarope", "scientific_name": "Phalaropus fulicarius", "core": False},
    {"species": "Wilson's Storm-petrel", "scientific_name": "Oceanites oceanicus", "core": False},
    {"species": "Cory's Shearwater", "scientific_name": "Calonectris diomedea", "core": False},
]

LOGGER = logging.getLogger(__name__)


def load_all_occurrences(
    species_registry: list[dict[str, object]] = SEABIRD_SPECIES,
) -> pd.DataFrame:
    """Download (or read from cache) the seabird guild, keeping memory small."""
    return eastern.load_all_occurrences(
        species_registry,
        compact=True,
        year_range=OCCURRENCE_YEAR_RANGE,
    )


def build_outputs(
    occurrences: pd.DataFrame,
    species_registry: list[dict[str, object]] = SEABIRD_SPECIES,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return shared.build_outputs(occurrences, species_registry)


def build_species_daily_counts(occurrences: pd.DataFrame) -> pd.DataFrame:
    """Return pooled-country per-species daily counts for dedicated models."""
    columns = ["date", "species", "count"]
    if occurrences.empty:
        return pd.DataFrame(columns=columns)
    if not {"date", "species"}.issubset(occurrences.columns):
        raise ValueError("Seabird occurrences must contain date and species.")
    result = (
        occurrences.groupby(
            [pd.to_datetime(occurrences["date"]).dt.normalize(), "species"],
            as_index=False,
        )
        .size()
        .rename(columns={"date": "date", "size": "count"})
    )
    result["date"] = pd.to_datetime(result["date"])
    return result.loc[:, columns].sort_values(["species", "date"]).reset_index(drop=True)


def threshold_summary(
    daily: pd.DataFrame, percentile: int = INFLUX_PERCENTILE
) -> dict[str, float]:
    """Descriptive P90 over event days; the model recomputes it on train data."""
    counts = daily["count"].to_numpy(dtype=float)
    if not len(counts):
        return {
            "percentile": percentile,
            "threshold_count": 1,
            "positive_days": 0,
            "prevalence": 0.0,
        }
    threshold = max(float(np.percentile(counts, percentile)), 1.0)
    positive = int((counts >= threshold).sum())
    return {
        "percentile": percentile,
        "threshold_count": threshold,
        "positive_days": positive,
        "prevalence": positive / len(counts),
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    occurrences = load_all_occurrences()
    summary, events, daily = build_outputs(occurrences)
    for path in (
        SPECIES_SUMMARY_OUTPUT,
        EVENTS_OUTPUT,
        DAILY_OUTPUT,
        SPECIES_DAILY_OUTPUT,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SPECIES_SUMMARY_OUTPUT, index=False)
    events.to_csv(EVENTS_OUTPUT, index=False, date_format="%Y-%m-%d")
    daily.to_csv(DAILY_OUTPUT, index=False, date_format="%Y-%m-%d")
    build_species_daily_counts(occurrences).to_csv(
        SPECIES_DAILY_OUTPUT, index=False, date_format="%Y-%m-%d"
    )
    LOGGER.info(
        "Saved %s event days / %s records to %s",
        f"{len(daily):,}",
        f"{int(daily['count'].sum()) if not daily.empty else 0:,}",
        DAILY_OUTPUT.relative_to(ROOT),
    )
    LOGGER.info("Species records:\n%s", summary.to_string(index=False))


if __name__ == "__main__":
    main()
