"""Export real cached GBIF seabird occurrences as validation observations.

The cache has no individual-count field, so `count` is the number of occurrence
records for a species, day and country.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

if __package__:
    from .build_atlantic_vagrancy_dataset import TARGET_COUNTRIES
    from .seabird_backtest import load_cached_occurrences
    from .seabird_observation_validation import OBSERVATIONS_FILE
    from .forecast_seabird_species import SPECIES_NAMES
else:
    from forecast_seabird_species import SPECIES_NAMES
    from build_atlantic_vagrancy_dataset import TARGET_COUNTRIES
    from seabird_backtest import load_cached_occurrences
    from seabird_observation_validation import OBSERVATIONS_FILE

SOURCE = "GBIF occurrence cache (HUMAN_OBSERVATION)"


def build_observations(occurrences: pd.DataFrame) -> pd.DataFrame:
    frame = occurrences.loc[occurrences["species"].isin(SPECIES_NAMES)].assign(
        date=pd.to_datetime(occurrences["date"]).dt.strftime("%Y-%m-%d"),
        location=occurrences["countryCode"].astype(str).str.upper().map(TARGET_COUNTRIES),
    )
    observations = (
        frame.groupby(["date", "species", "location"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    observations["source"] = SOURCE
    return observations.sort_values(["date", "species", "location"]).reset_index(drop=True)


def main(path: Path = OBSERVATIONS_FILE) -> None:
    observations = build_observations(load_cached_occurrences())
    path.parent.mkdir(parents=True, exist_ok=True)
    observations.to_csv(path, index=False)
    print(f"Wrote {len(observations)} rows to {path}")
    print(f"Date range: {observations['date'].min()} to {observations['date'].max()}")
    print(observations.groupby("species").agg(
        days=("date", "nunique"), records=("count", "sum"),
        first=("date", "min"), last=("date", "max"),
    ))


if __name__ == "__main__":
    main()
