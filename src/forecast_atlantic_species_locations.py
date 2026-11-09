"""Species-specific hotspot layers for the Atlantic Vagrancy Index.

For each species in SPECIES_LAYERS:

    forecast_probability = Atlantic Index probability
                           x species_suitability
                           x coastal_suitability
                           x regional_suitability

species_suitability combines the species' own historical cell occupancy with its
seasonal occurrence curve (both from cached GBIF records). The coastal and
Atlantic-landfall terms reuse the guild site registry with per-species profiles.
Profiles are expert heuristics, not trained or validated against observations.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .build_atlantic_vagrancy_dataset import (
        TARGET_COUNTRIES,
        _drop_duplicate_occurrences,
        download_species_country,
        resolve_taxon_key,
    )
    from .forecast_atlantic_locations import (
        ATLANTIC_DAILY_COUNTS_FILE,
        KIND_WEIGHTS,
        WEST_FACING_BONUS,
        _grid_coordinates,
        add_suitability,
        build_grid,
        calculate_atlantic_location_forecast,
    )
    from .forecast_location import _calendar_day_number, _calendar_day_numbers
else:
    from build_atlantic_vagrancy_dataset import (
        TARGET_COUNTRIES,
        _drop_duplicate_occurrences,
        download_species_country,
        resolve_taxon_key,
    )
    from forecast_atlantic_locations import (
        ATLANTIC_DAILY_COUNTS_FILE,
        KIND_WEIGHTS,
        WEST_FACING_BONUS,
        _grid_coordinates,
        add_suitability,
        build_grid,
        calculate_atlantic_location_forecast,
    )
    from forecast_location import _calendar_day_number, _calendar_day_numbers


LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = ROOT / "outputs"
SPECIES_SUMMARY_FILE = OUTPUT_DIRECTORY / "atlantic_vagrancy_species_layers_summary.csv"
HISTORY_START_YEAR = 2000
SEASONAL_WINDOW_DAYS = 7
SEASONAL_FLOOR = 0.02
TOP_N = 20
MIN_RECORDS = 200
MIN_YEARS = 5

# Eastern landfall anchors (Shetland, Fair Isle, Spurn, Norfolk, Texel, Blavand, Skagen).
EASTERN_ANCHORS = [
    (60.20, -1.30),
    (59.53, -1.63),
    (53.58, 0.12),
    (52.96, 1.05),
    (53.07, 4.78),
    (55.56, 8.10),
    (57.74, 10.60),
]

# Add species here. Profile keys are optional overrides of the guild defaults:
# kind_weights, west_facing_bonus, eastern (bool), exposure_scale_km,
# boost_strength. Junco hyemalis stays out of ATLANTIC_VAGRANCY_SPECIES (the
# guild) and is only a stand-alone layer.
SPECIES_LAYERS = [
    {
        "species": "Yellow-browed Warbler",
        "scientific_name": "Phylloscopus inornatus",
        "slug": "yellow_browed_warbler",
        "profile": {
            "kind_weights": {"island": 0.9, "headland": 0.8, "trap": 0.95},
            "west_facing_bonus": 0.0,
            "eastern": True,
            "exposure_scale_km": 400.0,
            "boost_strength": 0.5,
        },
        "note": "Siberian vagrant; scored with eastern landfall anchors.",
    },
    {
        "species": "Red-eyed Vireo",
        "scientific_name": "Vireo olivaceus",
        "slug": "red_eyed_vireo",
        "profile": {"west_facing_bonus": 0.10, "exposure_scale_km": 400.0},
    },
    {
        "species": "Blackpoll Warbler",
        "scientific_name": "Setophaga striata",
        "slug": "blackpoll_warbler",
        "profile": {"west_facing_bonus": 0.10, "exposure_scale_km": 350.0},
    },
    {
        "species": "American Redstart",
        "scientific_name": "Setophaga ruticilla",
        "slug": "american_redstart",
        "profile": {"west_facing_bonus": 0.10, "exposure_scale_km": 450.0},
    },
    {
        "species": "Blackburnian Warbler",
        "scientific_name": "Setophaga fusca",
        "slug": "blackburnian_warbler",
        "profile": {"west_facing_bonus": 0.08, "exposure_scale_km": 450.0},
    },
    {
        "species": "Northern Parula",
        "scientific_name": "Setophaga americana",
        "slug": "northern_parula",
        "profile": {"west_facing_bonus": 0.08, "exposure_scale_km": 450.0},
    },
    {
        "species": "Tennessee Warbler",
        "scientific_name": "Leiothlypis peregrina",
        "slug": "tennessee_warbler",
        "profile": {"west_facing_bonus": 0.08, "exposure_scale_km": 450.0},
    },
    {
        "species": "Bobolink",
        "scientific_name": "Dolichonyx oryzivorus",
        "slug": "bobolink",
        "profile": {
            "kind_weights": {"island": 1.0, "headland": 0.8, "trap": 0.85},
            "exposure_scale_km": 500.0,
        },
    },
    {
        "species": "American Robin",
        "scientific_name": "Turdus migratorius",
        "slug": "american_robin",
        "profile": {"exposure_scale_km": 600.0, "boost_strength": 0.75},
        "note": "Escape and non-wild-origin records cannot be ruled out.",
    },
    {
        "species": "Dark-eyed Junco",
        "scientific_name": "Junco hyemalis",
        "slug": "dark_eyed_junco",
        "profile": {"exposure_scale_km": 700.0, "boost_strength": 0.5},
        "note": (
            "Excluded from the Atlantic guild; many records are winter "
            "garden birds, so this is a stand-alone layer."
        ),
    },
]


def species_output_paths(
    slug: str, directory: Path = OUTPUT_DIRECTORY
) -> dict[str, Path]:
    return {
        "location": directory / f"{slug}_location_forecast.csv",
        "hotspots": directory / f"{slug}_hotspots.csv",
        "anomalies": directory / f"{slug}_anomalies.csv",
    }


def load_species_occurrences(species: dict[str, object]) -> pd.DataFrame:
    """Download (or load cached) GBIF records for one species in all target countries."""
    common_name = str(species["species"])
    scientific_name = str(species["scientific_name"])
    LOGGER.info("Downloading %s", common_name)
    taxon_key = resolve_taxon_key(scientific_name)
    frames = []
    for country_code in TARGET_COUNTRIES:
        frame = download_species_country(
            common_name, scientific_name, country_code, taxon_key
        )
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return _drop_duplicate_occurrences(
        pd.concat(frames, ignore_index=True)
    ).reset_index(drop=True)


def seasonal_curve(dates: pd.Series) -> np.ndarray:
    """Circularly smoothed record counts by calendar day, scaled to a peak of 1."""
    counts = np.bincount(_calendar_day_numbers(dates), minlength=367)[1:367]
    smoothed = sum(
        np.roll(counts, shift)
        for shift in range(-SEASONAL_WINDOW_DAYS, SEASONAL_WINDOW_DAYS + 1)
    ).astype(float)
    if smoothed.max() <= 0:
        raise ValueError("Cannot build a seasonal curve without records.")
    return np.maximum(smoothed / smoothed.max(), SEASONAL_FLOOR)


def cell_occupancy(records: pd.DataFrame, cells: pd.DataFrame) -> pd.DataFrame:
    """Add shrunk occupancy: the share of years in which each cell had a record."""
    years = records["date"].dt.year
    year_count = int(years.max() - years.min()) + 1
    easting, northing = _grid_coordinates(
        pd.to_numeric(records["decimalLatitude"]).to_numpy(),
        pd.to_numeric(records["decimalLongitude"]).to_numpy(),
    )
    occupied = (
        pd.DataFrame(
            {
                "cell_id": pd.Series(easting).astype(str).to_numpy()
                + "-"
                + pd.Series(northing).astype(str).to_numpy(),
                "year": years.to_numpy(),
            }
        )
        .groupby("cell_id")["year"]
        .nunique()
        .rename("occupied_years")
    )
    result = cells.merge(occupied, on="cell_id", how="left")
    result["occupied_years"] = result["occupied_years"].fillna(0).astype(int)
    result["cell_occupancy"] = (result["occupied_years"] + 0.5) / (year_count + 1)
    return result


def species_cells(records: pd.DataFrame, profile: dict[str, object]) -> pd.DataFrame:
    """Build the species grid with occupancy and species-specific suitability."""
    cells = add_suitability(
        build_grid(records),
        kind_weights=profile.get("kind_weights", KIND_WEIGHTS),
        west_facing_bonus=float(
            profile.get("west_facing_bonus", WEST_FACING_BONUS)
        ),
        anchors=EASTERN_ANCHORS if profile.get("eastern") else None,
        exposure_scale_km=float(profile.get("exposure_scale_km", 500.0)),
        boost_strength=float(profile.get("boost_strength", 1.0)),
    )
    cells = cell_occupancy(records, cells)
    cells["species_suitability"] = cells["cell_occupancy"] / cells[
        "cell_occupancy"
    ].max()
    return cells


def rank_layers(
    forecast: pd.DataFrame, top_n: int = TOP_N
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (hotspots + coldspots, positive anomalies) for each date."""
    columns = [
        "date",
        "ranking_type",
        "rank",
        "cell_id",
        "country",
        "nearest_site",
        "center_latitude",
        "center_longitude",
        "forecast_probability",
        "expected_probability",
        "anomaly_score",
        "risk_level",
    ]
    hotspot_frames: list[pd.DataFrame] = []
    anomaly_frames: list[pd.DataFrame] = []
    for _, day in forecast.groupby("date", sort=True):
        ordered = day.sort_values(
            ["forecast_probability", "cell_id"], ascending=[False, True]
        )
        hot = ordered.head(top_n).assign(ranking_type="HOTSPOT")
        cold = day.sort_values(
            ["forecast_probability", "cell_id"], ascending=[True, True]
        ).head(top_n).assign(ranking_type="COLDSPOT")
        for frame in (hot, cold):
            frame["rank"] = range(1, len(frame) + 1)
            hotspot_frames.append(frame)
        positive = (
            day.loc[day["anomaly_score"].gt(0)]
            .sort_values(["anomaly_score", "cell_id"], ascending=[False, True])
            .head(top_n)
            .assign(ranking_type="POSITIVE_ANOMALY")
        )
        positive["rank"] = range(1, len(positive) + 1)
        anomaly_frames.append(positive)
    hotspots = pd.concat(hotspot_frames, ignore_index=True)[columns]
    anomalies = (
        pd.concat(anomaly_frames, ignore_index=True)[columns]
        if anomaly_frames
        else pd.DataFrame(columns=columns)
    )
    return hotspots, anomalies


def calculate_species_layer(
    records: pd.DataFrame,
    profile: dict[str, object],
    daily_counts: pd.DataFrame,
    national_forecast: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    recent = records.loc[records["date"].dt.year.ge(HISTORY_START_YEAR)]
    if recent.empty:
        raise ValueError(f"No records since {HISTORY_START_YEAR}.")
    cells = species_cells(recent, profile)
    curve = seasonal_curve(recent["date"])
    dates = pd.to_datetime(national_forecast["date"]).dt.normalize()
    weights = {
        pd.Timestamp(day): float(curve[_calendar_day_number(day) - 1])
        for day in dates
    }
    forecast = calculate_atlantic_location_forecast(
        cells, daily_counts, national_forecast, date_weights=weights
    )
    hotspots, anomalies = rank_layers(forecast)
    return forecast, hotspots, anomalies


def build_species_layers(
    national_forecast: pd.DataFrame,
    species_registry: list[dict[str, object]] = SPECIES_LAYERS,
    *,
    output_directory: Path = OUTPUT_DIRECTORY,
    daily_counts_path: Path = ATLANTIC_DAILY_COUNTS_FILE,
    summary_path: Path = SPECIES_SUMMARY_FILE,
) -> pd.DataFrame:
    """Download data, build every species layer, write CSVs, return a summary."""
    daily_counts = pd.read_csv(daily_counts_path)
    summary_rows: list[dict[str, object]] = []
    total = len(species_registry)
    for number, species in enumerate(species_registry, start=1):
        name = str(species["species"])
        LOGGER.info("Species layer %s of %s: %s", number, total, name)
        records = load_species_occurrences(species)
        row: dict[str, object] = {
            "species": name,
            "slug": species["slug"],
            "records": len(records),
        }
        if records.empty:
            LOGGER.warning("No qualifying GBIF records for %s; layer skipped", name)
            row.update(status="NO_DATA", data_quality="none")
            summary_rows.append(row)
            continue
        forecast, hotspots, anomalies = calculate_species_layer(
            records, species.get("profile", {}), daily_counts, national_forecast
        )
        paths = species_output_paths(str(species["slug"]), output_directory)
        paths["location"].parent.mkdir(parents=True, exist_ok=True)
        forecast.to_csv(paths["location"], index=False, date_format="%Y-%m-%d")
        hotspots.to_csv(paths["hotspots"], index=False, date_format="%Y-%m-%d")
        anomalies.to_csv(paths["anomalies"], index=False, date_format="%Y-%m-%d")
        recent = records.loc[records["date"].dt.year.ge(HISTORY_START_YEAR)]
        years = int(recent["date"].dt.year.nunique())
        curve = seasonal_curve(recent["date"])
        peak_day = pd.Timestamp("2000-01-01") + pd.Timedelta(days=int(curve.argmax()))
        sufficient = len(recent) >= MIN_RECORDS and years >= MIN_YEARS
        row.update(
            records_since_start=len(recent),
            record_years=years,
            countries=",".join(sorted(recent["countryCode"].dropna().unique())),
            occupied_cells=int(
                forecast.loc[
                    forecast["date"].eq(forecast["date"].min()), "occupied_years"
                ]
                .gt(0)
                .sum()
            ),
            seasonal_peak=peak_day.strftime("%m-%d"),
            top_cell=str(hotspots.iloc[0]["cell_id"]),
            top_probability=float(hotspots.iloc[0]["forecast_probability"]),
            positive_anomaly_rows=len(anomalies),
            status="OK",
            data_quality="sufficient" if sufficient else "sparse",
        )
        LOGGER.info(
            "%s: %s records, %s cells, quality=%s",
            name,
            f"{len(recent):,}",
            row["occupied_cells"],
            row["data_quality"],
        )
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if __package__:
        from .predict_atlantic_vagrancy import DEFAULT_OUTPUT
    else:
        from predict_atlantic_vagrancy import DEFAULT_OUTPUT

    print(build_species_layers(pd.read_csv(DEFAULT_OUTPUT)).to_string(index=False))


if __name__ == "__main__":
    main()
