"""Species-specific hotspot layers for the Eastern Vagrancy Index.

For each species in EASTERN_SPECIES_LAYERS:

    forecast_probability = Eastern Index probability
                           x species_suitability
                           x coastal_suitability
                           x regional_suitability

Suitability reuses the Eastern hotspot framework (eastern landfall anchors and
boosts); species_suitability combines the species' own historical cell
occupancy with its seasonal occurrence curve from GBIF records. Weights are
expert heuristics, not trained or validated against observations.

Multi-species selections are combined per cell and date with the maximum
species probability (see combine_species_forecasts).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

if __package__:
    from . import forecast_atlantic_locations as framework
    from .build_eastern_vagrancy_dataset import load_all_occurrences
    from .forecast_atlantic_species_locations import (
        EASTERN_ANCHORS,
        HISTORY_START_YEAR,
        MIN_RECORDS,
        MIN_YEARS,
        cell_occupancy,
        rank_layers,
        seasonal_curve,
    )
    from .forecast_eastern_locations import (
        EASTERN_BONUS_BOOSTS,
        EASTERN_DAILY_COUNTS_FILE,
        EASTERN_EXPOSURE_SCALE_KM,
        EASTERN_KIND_WEIGHTS,
        EASTERN_SITES,
    )
    from .forecast_location import _calendar_day_number
    from .predict_eastern_vagrancy import risk_level
else:
    import forecast_atlantic_locations as framework
    from build_eastern_vagrancy_dataset import load_all_occurrences
    from forecast_atlantic_species_locations import (
        EASTERN_ANCHORS,
        HISTORY_START_YEAR,
        MIN_RECORDS,
        MIN_YEARS,
        cell_occupancy,
        rank_layers,
        seasonal_curve,
    )
    from forecast_eastern_locations import (
        EASTERN_BONUS_BOOSTS,
        EASTERN_DAILY_COUNTS_FILE,
        EASTERN_EXPOSURE_SCALE_KM,
        EASTERN_KIND_WEIGHTS,
        EASTERN_SITES,
    )
    from forecast_location import _calendar_day_number
    from predict_eastern_vagrancy import risk_level

LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = ROOT / "outputs"
EASTERN_SPECIES_SUMMARY_FILE = (
    OUTPUT_DIRECTORY / "eastern_vagrancy_species_layers_summary.csv"
)
EASTERN_GUILD_LAYER = "All Eastern Species"

EASTERN_SPECIES_LAYERS = [
    {"species": "Yellow-browed Warbler", "scientific_name": "Phylloscopus inornatus", "slug": "eastern_yellow_browed_warbler"},
    {"species": "Pallas's Leaf Warbler", "scientific_name": "Phylloscopus proregulus", "slug": "eastern_pallass_leaf_warbler"},
    {"species": "Dusky Warbler", "scientific_name": "Phylloscopus fuscatus", "slug": "eastern_dusky_warbler"},
    {"species": "Radde's Warbler", "scientific_name": "Phylloscopus schwarzi", "slug": "eastern_raddes_warbler"},
    {"species": "Two-barred Warbler", "scientific_name": "Phylloscopus plumbeitarsus", "slug": "eastern_two_barred_warbler"},
    {
        "species": "Siberian Chiffchaff",
        "scientific_name": "Phylloscopus collybita tristis",
        "slug": "eastern_siberian_chiffchaff",
        "rank": "SUBSPECIES",
    },
    {"species": "Red-flanked Bluetail", "scientific_name": "Tarsiger cyanurus", "slug": "eastern_red_flanked_bluetail"},
    {"species": "Olive-backed Pipit", "scientific_name": "Anthus hodgsoni", "slug": "eastern_olive_backed_pipit"},
    {"species": "Rustic Bunting", "scientific_name": "Emberiza rustica", "slug": "eastern_rustic_bunting"},
]


def eastern_species_output_paths(
    slug: str, directory: Path = OUTPUT_DIRECTORY
) -> dict[str, Path]:
    return {
        "location": directory / f"{slug}_location_forecast.csv",
        "hotspots": directory / f"{slug}_hotspots.csv",
        "anomalies": directory / f"{slug}_anomalies.csv",
    }


def eastern_species_cells(records: pd.DataFrame) -> pd.DataFrame:
    cells = framework.add_suitability(
        framework.build_grid(records),
        kind_weights=EASTERN_KIND_WEIGHTS,
        west_facing_bonus=0.0,
        anchors=EASTERN_ANCHORS,
        exposure_scale_km=EASTERN_EXPOSURE_SCALE_KM,
        boosts=EASTERN_BONUS_BOOSTS,
        sites=EASTERN_SITES,
    )
    # Same peak scaling as the Eastern guild layer, so boosts do not clip at 1.
    cells["regional_suitability"] /= cells["regional_suitability"].max()
    cells = cell_occupancy(records, cells)
    cells["species_suitability"] = (
        cells["cell_occupancy"] / cells["cell_occupancy"].max()
    )
    return cells


def calculate_eastern_species_layer(
    records: pd.DataFrame,
    daily_counts: pd.DataFrame,
    national_forecast: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    recent = records.loc[records["date"].dt.year.ge(HISTORY_START_YEAR)]
    if recent.empty:
        raise ValueError(f"No records since {HISTORY_START_YEAR}.")
    cells = eastern_species_cells(recent)
    curve = seasonal_curve(recent["date"])
    dates = pd.to_datetime(national_forecast["date"]).dt.normalize()
    weights = {
        pd.Timestamp(day): float(curve[_calendar_day_number(day) - 1])
        for day in dates
    }
    forecast = framework.calculate_atlantic_location_forecast(
        cells,
        daily_counts,
        national_forecast,
        date_weights=weights,
        risk_function=risk_level,
        sites=EASTERN_SITES,
    )
    hotspots, anomalies = rank_layers(forecast)
    return forecast, hotspots, anomalies


def build_eastern_species_layers(
    national_forecast: pd.DataFrame,
    species_registry: list[dict[str, object]] = EASTERN_SPECIES_LAYERS,
    *,
    output_directory: Path = OUTPUT_DIRECTORY,
    daily_counts_path: Path = EASTERN_DAILY_COUNTS_FILE,
    summary_path: Path = EASTERN_SPECIES_SUMMARY_FILE,
) -> pd.DataFrame:
    """Build every Eastern species layer, write CSVs and return a summary."""
    daily_counts = pd.read_csv(daily_counts_path)
    rows: list[dict[str, object]] = []
    for number, species in enumerate(species_registry, start=1):
        name = str(species["species"])
        LOGGER.info("Eastern species layer %s of %s: %s", number, len(species_registry), name)
        entry = {**species, "core": True}
        records = load_all_occurrences([entry])
        row: dict[str, object] = {
            "species": name,
            "slug": species["slug"],
            "records": len(records),
        }
        if records.empty:
            LOGGER.warning("No qualifying GBIF records for %s; layer skipped", name)
            row.update(status="NO_DATA", data_quality="none")
            rows.append(row)
            continue
        forecast, hotspots, anomalies = calculate_eastern_species_layer(
            records, daily_counts, national_forecast
        )
        paths = eastern_species_output_paths(str(species["slug"]), output_directory)
        paths["location"].parent.mkdir(parents=True, exist_ok=True)
        forecast.to_csv(paths["location"], index=False, date_format="%Y-%m-%d")
        hotspots.to_csv(paths["hotspots"], index=False, date_format="%Y-%m-%d")
        anomalies.to_csv(paths["anomalies"], index=False, date_format="%Y-%m-%d")
        recent = records.loc[records["date"].dt.year.ge(HISTORY_START_YEAR)]
        years = int(recent["date"].dt.year.nunique())
        row.update(
            records_since_start=len(recent),
            record_years=years,
            top_cell=str(hotspots.iloc[0]["cell_id"]),
            top_probability=float(hotspots.iloc[0]["forecast_probability"]),
            status="OK",
            data_quality=(
                "sufficient" if len(recent) >= MIN_RECORDS and years >= MIN_YEARS
                else "sparse"
            ),
        )
        rows.append(row)
    summary = pd.DataFrame(rows)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    return summary


def combine_species_forecasts(forecasts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combine species layers per cell and date by maximum probability.

    The winning species' row supplies the other columns, so suitability,
    occupancy, anomaly and risk stay consistent with the combined score;
    selected_species lists all species and driving_species names the winner.
    """
    if not forecasts:
        raise ValueError("Select at least one species.")
    stacked = pd.concat(
        [frame.assign(driving_species=name) for name, frame in forecasts.items()],
        ignore_index=True,
    )
    winners = stacked.sort_values(
        ["date", "cell_id", "forecast_probability", "driving_species"],
        ascending=[True, True, False, True],
    ).drop_duplicates(["date", "cell_id"])
    winners = winners.sort_values(["date", "cell_id"]).reset_index(drop=True)
    winners["selected_species"] = ", ".join(forecasts)
    return winners


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if __package__:
        from .predict_eastern_vagrancy import DEFAULT_OUTPUT
    else:
        from predict_eastern_vagrancy import DEFAULT_OUTPUT
    print(
        build_eastern_species_layers(pd.read_csv(DEFAULT_OUTPUT)).to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
