"""Rank seabird species by probability x rarity weight for each horizon."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

if __package__:
    from .rarity_index import RARITY_WEIGHTS
else:
    from rarity_index import RARITY_WEIGHTS

ROOT = Path(__file__).resolve().parents[1]
TARGET_SPECIES_OUTPUT = ROOT / "outputs/target_species.csv"
TARGET_SPECIES_COLUMNS = [
    "date", "horizon_days", "rank", "species",
    "probability", "rarity_weight", "target_score",
]


def build_target_species(rarity_document: dict[str, object]) -> pd.DataFrame:
    """target_score = forecast probability x existing rarity weight."""
    rows = []
    for horizon in rarity_document["horizons"]:
        scored = []
        for species, weight in RARITY_WEIGHTS.items():
            probability = float(horizon["species_probabilities"][species])
            scored.append(
                {
                    "date": horizon["date"],
                    "horizon_days": int(horizon["forecast_day"]),
                    "species": species,
                    "probability": probability,
                    "rarity_weight": weight,
                    "target_score": probability * weight,
                }
            )
        scored.sort(key=lambda row: (-row["target_score"], row["species"]))
        for rank, row in enumerate(scored, start=1):
            rows.append({**row, "rank": rank})
    return pd.DataFrame(rows, columns=TARGET_SPECIES_COLUMNS)


def save_target_species(
    frame: pd.DataFrame, path: Path = TARGET_SPECIES_OUTPUT
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
