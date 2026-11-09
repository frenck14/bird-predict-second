"""Species-level Seabird Index forecasts and hotspot layers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypedDict

import joblib
import pandas as pd

if __package__:
    from . import build_seabird_dataset as dataset
    from . import forecast_atlantic_locations as framework
    from . import forecast_atlantic_species_locations as species_framework
    from .forecast_seabird_locations import (
        SEABIRD_BOOSTS,
        SEABIRD_KIND_WEIGHTS,
        SEABIRD_SITES,
        SEABIRD_EXPOSURE_SCALE_KM,
        _build_seabird_features,
    )
    from .predict_seabird import risk_level
    from .predict_yellow_browed import make_predictions as shared_make_predictions
    from .train_seabird_species_models import (
        MODEL_DIRECTORY,
        SLUGS,
        SPECIES_NAMES,
        model_path,
    )
else:
    import build_seabird_dataset as dataset
    import forecast_atlantic_locations as framework
    import forecast_atlantic_species_locations as species_framework
    from forecast_seabird_locations import (
        SEABIRD_BOOSTS,
        SEABIRD_KIND_WEIGHTS,
        SEABIRD_SITES,
        SEABIRD_EXPOSURE_SCALE_KM,
        _build_seabird_features,
    )
    from predict_seabird import risk_level
    from predict_yellow_browed import make_predictions as shared_make_predictions
    from train_seabird_species_models import (
        MODEL_DIRECTORY,
        SLUGS,
        SPECIES_NAMES,
        model_path,
    )


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
SPECIES_COUNTS_FILE = OUTPUTS / "seabird_species_daily_counts.csv"
SPECIES_MODEL_PATHS = {name: model_path(name) for name in SPECIES_NAMES}
SPECIES_LOCATION_SITES = SEABIRD_SITES


class SpeciesProfile(TypedDict):
    kind_weights: dict[str, float]
    exposure_scale_km: float
    boosts: dict[str, float]


SPECIES_PROFILES: dict[str, SpeciesProfile] = {
    "European Storm-petrel": {
        "kind_weights": {**SEABIRD_KIND_WEIGHTS, "island": 1.15, "headland": 1.1},
        "exposure_scale_km": 380.0,
        "boosts": {**SEABIRD_BOOSTS, "Fair Isle": 1.65, "Shetland": 1.6},
    },
    "Northern Fulmar": {
        "kind_weights": {**SEABIRD_KIND_WEIGHTS, "headland": 1.15, "seafront": 0.85},
        "exposure_scale_km": 460.0,
        "boosts": {**SEABIRD_BOOSTS, "Outer Hebrides": 1.5, "Shetland": 1.55},
    },
    "Sooty Shearwater": {
        "kind_weights": {**SEABIRD_KIND_WEIGHTS, "headland": 1.15, "island": 1.1},
        "exposure_scale_km": 520.0,
        "boosts": {**SEABIRD_BOOSTS, "Scilly Isles": 1.6, "Outer Hebrides": 1.5},
    },
    "Manx Shearwater": {
        "kind_weights": {**SEABIRD_KIND_WEIGHTS, "island": 1.15, "headland": 1.1},
        "exposure_scale_km": 480.0,
        "boosts": {**SEABIRD_BOOSTS, "Scilly Isles": 1.5, "Outer Hebrides": 1.5},
    },
    "Great Shearwater": {
        "kind_weights": {**SEABIRD_KIND_WEIGHTS, "headland": 1.2, "island": 1.1},
        "exposure_scale_km": 560.0,
        "boosts": {**SEABIRD_BOOSTS, "Scilly Isles": 1.65, "Outer Hebrides": 1.55},
    },
}
TOP_N = 10


def species_output_paths(
    species: str, directory: Path = OUTPUTS
) -> dict[str, Path]:
    slug = SLUGS[species]
    return {
        "forecast": directory / f"{slug}_forecast.csv",
        "location": directory / f"{slug}_location_forecast.csv",
        "detail": directory / f"{slug}_location_forecast_detail.csv",
        "hotspots": directory / f"{slug}_hotspots.csv",
        "map": directory / f"{slug}_location_forecast.png",
        "model": MODEL_DIRECTORY / f"{slug}_model.joblib",
    }


def predict_species_forecasts(
    weather: pd.DataFrame,
    predictor_dates: pd.DatetimeIndex,
    model_paths: dict[str, Path] = SPECIES_MODEL_PATHS,
) -> dict[str, pd.DataFrame]:
    """Apply the independently trained species models to common weather."""
    forecasts: dict[str, pd.DataFrame] = {}
    for species in SPECIES_NAMES:
        path = model_paths[species]
        if not path.is_file():
            raise FileNotFoundError(
                f"Seabird species model not found: {path}. "
                "Build the dataset and run "
                "`python src/train_seabird_species_models.py`."
            )
        artifact = joblib.load(path)
        if artifact.get("species") != species:
            raise ValueError(f"Model artifact at {path} is not for {species}.")
        predictions = shared_make_predictions(
            weather,
            predictor_dates,
            artifact,
            feature_builder=_build_seabird_features,
        )
        forecasts[species] = pd.DataFrame(
            {
                "date": predictions["date"],
                "probability": predictions["probability"],
                "risk_level": predictions["probability"].map(
                    lambda probability: risk_level(float(probability))
                ),
            }
        )
    return forecasts


def _species_cells(records: pd.DataFrame, species: str) -> pd.DataFrame:
    profile = SPECIES_PROFILES[species]
    cells = framework.add_suitability(
        framework.build_grid(records, sites=SPECIES_LOCATION_SITES),
        kind_weights=profile["kind_weights"],
        west_facing_bonus=0.15,
        anchors=[
            (51.44, -9.50),
            (53.61, -10.22),
            (55.27, -8.25),
            (57.81, -8.58),
            (49.92, -6.30),
            (59.53, -1.63),
            (54.50, 2.00),
        ],
        exposure_scale_km=float(profile["exposure_scale_km"]),
        boosts=profile["boosts"],
        sites=SPECIES_LOCATION_SITES,
    )
    recent = records.loc[records["date"].dt.year.ge(2010)].copy()
    if recent.empty:
        raise ValueError(f"No post-2010 occurrence records for {species}.")
    cells = species_framework.cell_occupancy(recent, cells)
    maximum = float(cells["cell_occupancy"].max())
    if maximum <= 0:
        raise ValueError(f"Cannot derive historical cell occupancy for {species}.")
    cells["species_suitability"] = cells["cell_occupancy"] / maximum
    return cells


def _species_daily_counts(species: str, path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(
            f"Species daily counts not found: {path}. "
            "Run `python src/build_seabird_dataset.py` first."
        )
    counts = pd.read_csv(path, parse_dates=["date"])
    if not {"date", "species", "count"}.issubset(counts.columns):
        raise ValueError(f"Invalid species daily counts schema: {path}")
    counts = counts.loc[counts["species"].eq(species), ["date", "count"]].copy()
    if counts.empty:
        raise ValueError(f"No species-specific historical counts for {species}.")
    counts["date"] = pd.to_datetime(counts["date"]).dt.normalize()
    counts["count"] = pd.to_numeric(counts["count"], errors="raise")
    if (
        counts["date"].isna().any()
        or counts["date"].duplicated().any()
        or counts["count"].isna().any()
        or counts["count"].lt(0).any()
    ):
        raise ValueError(f"Invalid dates or counts for {species} in {path}.")
    return counts[["date", "count"]]


def build_species_location_forecast(
    species: str,
    records: pd.DataFrame,
    national_forecast: pd.DataFrame,
    *,
    daily_counts_path: Path = SPECIES_COUNTS_FILE,
    output_directory: Path = OUTPUTS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create one species' cell-level forecast and its horizon top-10 table."""
    if species not in SPECIES_PROFILES:
        raise ValueError(f"No Seabird hotspot profile is configured for {species}.")
    species_records = records.loc[records["species"].eq(species)].copy()
    if species_records.empty:
        raise ValueError(f"No cached occurrence records are available for {species}.")
    species_records["date"] = pd.to_datetime(species_records["date"]).dt.normalize()
    species_records = species_records.loc[species_records["date"].dt.year.ge(2010)]
    cells = _species_cells(species_records, species)
    curve = species_framework.seasonal_curve(species_records["date"])
    target_dates = pd.to_datetime(national_forecast["date"]).dt.normalize()
    weights = {
        pd.Timestamp(day): float(
            curve[species_framework._calendar_day_number(pd.Timestamp(day)) - 1]
        )
        for day in target_dates
    }
    detailed = framework.calculate_atlantic_location_forecast(
        cells,
        _species_daily_counts(species, daily_counts_path),
        national_forecast,
        date_weights=weights,
        risk_function=risk_level,
        sites=SPECIES_LOCATION_SITES,
    )
    horizons = framework.top_hotspots(detailed, TOP_N)
    hotspots = pd.concat(
        [
            frame.assign(horizon_days=horizon, horizon=framework.HORIZONS[horizon])
            for horizon, frame in horizons.items()
        ],
        ignore_index=True,
    )
    paths = species_output_paths(species, output_directory)
    paths["forecast"].parent.mkdir(parents=True, exist_ok=True)
    framework.simple_location_forecast(detailed).to_csv(
        paths["location"], index=False, date_format="%Y-%m-%d"
    )
    detailed.to_csv(paths["detail"], index=False, date_format="%Y-%m-%d")
    hotspots.to_csv(paths["hotspots"], index=False, date_format="%Y-%m-%d")
    framework.save_location_map(
        detailed, paths["map"], title=f"{species} seawatch hotspots"
    )
    return detailed, hotspots


def build_all_species_location_forecasts(
    forecasts: dict[str, pd.DataFrame],
    occurrences: pd.DataFrame | None = None,
    *,
    daily_counts_path: Path = SPECIES_COUNTS_FILE,
    output_directory: Path = OUTPUTS,
) -> dict[str, pd.DataFrame]:
    """Write each requested species' forecast, location CSV, top-10 CSV and map."""
    occurrences = occurrences if occurrences is not None else dataset.load_all_occurrences()
    built: dict[str, pd.DataFrame] = {}
    for index, species in enumerate(SPECIES_NAMES, start=1):
        if species not in forecasts:
            raise ValueError(f"Missing national forecast for {species}.")
        LOGGER.info("Building Seabird hotspot layer %d/%d: %s", index, len(SPECIES_NAMES), species)
        result, _ = build_species_location_forecast(
            species,
            occurrences,
            forecasts[species],
            daily_counts_path=daily_counts_path,
            output_directory=output_directory,
        )
        built[species] = result
    return built


def generate_species_products(
    weather: pd.DataFrame,
    predictor_dates: pd.DatetimeIndex,
    occurrences: pd.DataFrame | None = None,
    *,
    model_paths: dict[str, Path] = SPECIES_MODEL_PATHS,
    daily_counts_path: Path = SPECIES_COUNTS_FILE,
    output_directory: Path = OUTPUTS,
) -> dict[str, pd.DataFrame]:
    """Predict species event probabilities and write their hotspot products."""
    forecasts = predict_species_forecasts(weather, predictor_dates, model_paths)
    for species, forecast in forecasts.items():
        output = species_output_paths(species, output_directory)["forecast"]
        output.parent.mkdir(parents=True, exist_ok=True)
        forecast.to_csv(output, index=False, date_format="%Y-%m-%d")
    build_all_species_location_forecasts(
        forecasts,
        occurrences,
        daily_counts_path=daily_counts_path,
        output_directory=output_directory,
    )
    return forecasts
