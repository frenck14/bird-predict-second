"""Compare forecast seabird species with independent observations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

if __package__:
    from .forecast_seabird_species import SPECIES_NAMES
else:
    from forecast_seabird_species import SPECIES_NAMES

OBSERVATIONS_FILE = Path("validation/seabirds/observations.csv")
REPORT_FILE = Path("outputs/seabird_validation/validation_report.csv")
PROBABILITY_THRESHOLD = 0.20

PREDICTED_CORRECT = "✅ correctly predicted"
PREDICTED_ABSENT = "❌ predicted but absent"
OBSERVED_MISSED = "⚠ observed but missed"
REPORT_COLUMNS = [
    "analysis_date",
    "window_start",
    "window_end",
    "species",
    "max_probability",
    "predicted",
    "observed",
    "observation_days",
    "outcome",
]


class ObservationsUnavailable(RuntimeError):
    pass


def load_observation_records(path: Path = OBSERVATIONS_FILE) -> pd.DataFrame:
    """Load observations.csv; requires `date` and `species` columns."""
    if not path.is_file():
        raise ObservationsUnavailable(
            f"Observation file not found: {path}. Add a CSV with at least "
            "`date` and `species` columns (optional `count`, `location`)."
        )
    records = pd.read_csv(path)
    if not {"date", "species"}.issubset(records.columns):
        raise ObservationsUnavailable(
            f"{path} must contain `date` and `species` columns."
        )
    records["date"] = pd.to_datetime(records["date"], errors="raise").dt.normalize()
    records["species"] = records["species"].astype(str).str.strip()
    if "count" in records.columns:
        records = records.loc[pd.to_numeric(records["count"], errors="coerce").fillna(1) > 0]
    return records.reset_index(drop=True)


def holdout_observations(records: pd.DataFrame, target_dates) -> pd.DataFrame:
    dates = pd.DatetimeIndex(pd.to_datetime(list(target_dates))).normalize()
    return records.loc[records["date"].isin(dates)].reset_index(drop=True)


def _canonical_species(name: str) -> str | None:
    lookup = {species.casefold(): species for species in SPECIES_NAMES}
    return lookup.get(str(name).strip().casefold())


def match_species(
    species_forecast: pd.DataFrame,
    observations: pd.DataFrame,
    *,
    probability_threshold: float = PROBABILITY_THRESHOLD,
) -> pd.DataFrame:
    """One row per modelled species with predicted/observed outcome."""
    forecast = species_forecast.assign(
        date=pd.to_datetime(species_forecast["date"]).dt.normalize()
    )
    max_probability = forecast.groupby("species")["probability"].max()
    observed = observations.assign(
        species=observations["species"].map(_canonical_species)
    ).dropna(subset=["species"])
    observed_days = observed.groupby("species")["date"].nunique()
    rows = []
    for species in SPECIES_NAMES:
        probability = float(max_probability.get(species, 0.0))
        predicted = probability >= probability_threshold
        seen = species in observed_days.index
        outcome = (
            PREDICTED_CORRECT
            if predicted and seen
            else PREDICTED_ABSENT
            if predicted
            else OBSERVED_MISSED
            if seen
            else "correctly absent"
        )
        rows.append(
            {
                "species": species,
                "max_probability": round(probability, 4),
                "predicted": predicted,
                "observed": seen,
                "observation_days": int(observed_days.get(species, 0)),
                "outcome": outcome,
            }
        )
    return pd.DataFrame(rows)


def calculate_metrics(
    matches: pd.DataFrame,
    species_forecast: pd.DataFrame,
    observations: pd.DataFrame,
    *,
    probability_threshold: float = PROBABILITY_THRESHOLD,
) -> dict[str, float]:
    tp = int((matches["predicted"] & matches["observed"]).sum())
    fp = int((matches["predicted"] & ~matches["observed"]).sum())
    fn = int((~matches["predicted"] & matches["observed"]).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    # Hit rate: share of days with at least one predicted species on which a
    # species predicted for that day was actually observed that day.
    forecast = species_forecast.assign(
        date=pd.to_datetime(species_forecast["date"]).dt.normalize()
    )
    predicted_days = forecast.loc[forecast["probability"] >= probability_threshold]
    observed = observations.assign(
        species=observations["species"].map(_canonical_species)
    ).dropna(subset=["species"])
    observed_pairs = set(zip(observed["date"], observed["species"]))
    days = predicted_days.groupby("date")["species"].apply(set)
    hits = sum(
        any((day, name) in observed_pairs for name in names)
        for day, names in days.items()
    )
    hit_rate = hits / len(days) if len(days) else 0.0
    return {
        "hit_rate": hit_rate,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
    }


def build_validation_report(
    result: dict[str, object],
    records: pd.DataFrame,
    path: Path = REPORT_FILE,
) -> dict[str, object]:
    target_dates = pd.DatetimeIndex(pd.to_datetime(result["target_dates"])).normalize()
    observations = holdout_observations(records, target_dates)
    matches = match_species(result["species"], observations)
    metrics = calculate_metrics(matches, result["species"], observations)
    report = matches.assign(
        analysis_date=pd.Timestamp(result["analysis_date"]).date(),
        window_start=target_dates[0].date(),
        window_end=target_dates[-1].date(),
    )[REPORT_COLUMNS]
    path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(path, index=False)
    return {
        "observation_count": len(observations),
        "matches": matches,
        "metrics": metrics,
        "report": report,
        "report_path": path,
    }
