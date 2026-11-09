"""Combine species-level seabird forecasts into a separately scaled Rarity Index."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

if __package__:
    from .forecast_atlantic_locations import HORIZONS
    from .forecast_seabird_species import SPECIES_MODEL_PATHS
    from .predict_yellow_browed import make_predictions
    from .train_seabird_model import WEATHER_FILE
    from .forecast_seabird_locations import _build_seabird_features
else:
    from forecast_atlantic_locations import HORIZONS
    from forecast_seabird_species import SPECIES_MODEL_PATHS
    from predict_yellow_browed import make_predictions
    from train_seabird_model import WEATHER_FILE
    from forecast_seabird_locations import _build_seabird_features


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
RARITY_WEIGHTS = {
    "Northern Fulmar": 0.5,
    "Manx Shearwater": 1.0,
    "European Storm-petrel": 2.0,
    "Sooty Shearwater": 3.0,
    "Great Shearwater": 6.0,
}
SPECIES_FORECAST_FILES = {
    species: OUTPUTS / path.name.replace("_model.joblib", "_forecast.csv")
    for species, path in SPECIES_MODEL_PATHS.items()
}
RARITY_INDEX_OUTPUT = OUTPUTS / "rarity_index.csv"
RARITY_INDEX_JSON_OUTPUT = OUTPUTS / "rarity_index.json"
SPECIES_EVALUATION_FILE = OUTPUTS / "seabird_species_evaluation.csv"
LOWER_PERCENTILE = 5
UPPER_PERCENTILE = 95
HORIZONS_BY_OFFSET = {days - 1: (days, label) for days, label in HORIZONS.items()}


def historical_rarity_raw(
    historical_weather: pd.DataFrame,
    model_paths: dict[str, Path] = SPECIES_MODEL_PATHS,
) -> pd.Series:
    """Predict each trained model over historical weather to derive raw scores."""
    if "date" not in historical_weather:
        raise ValueError("Historical weather must contain a date column.")
    weather = historical_weather.copy()
    weather["date"] = pd.to_datetime(weather["date"], errors="raise").dt.normalize()
    weather = weather.sort_values("date").reset_index(drop=True)
    weather = weather.drop(
        columns=[
            "month",
            "day_of_year",
            "day_of_year_sin",
            "day_of_year_cos",
        ],
        errors="ignore",
    )
    dates = pd.DatetimeIndex(weather["date"].drop_duplicates())
    if len(dates) < 2 or dates.has_duplicates:
        raise ValueError("Historical weather needs at least two unique dates.")
    expected = pd.date_range(dates[0], dates[-1], freq="D")
    if not dates.equals(expected):
        raise ValueError("Historical weather dates must form a continuous daily series.")
    predictor_dates = dates[:-1]
    outputs: dict[str, pd.DataFrame] = {}
    for species in RARITY_WEIGHTS:
        model_path = model_paths[species]
        if not model_path.is_file():
            raise FileNotFoundError(f"Rarity model artifact not found: {model_path}")
        artifact = joblib.load(model_path)
        if artifact.get("species") != species:
            raise ValueError(f"Model artifact {model_path} is not for {species}.")
        outputs[species] = make_predictions(
            weather,
            predictor_dates,
            artifact,
            feature_builder=_build_seabird_features,
        )
    return combine_rarity_raw(outputs).set_index("date")["rarity_raw"]


def combine_rarity_raw(
    species_forecasts: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Validate the five species forecasts and sum p × configured rarity weight."""
    if set(species_forecasts) != set(RARITY_WEIGHTS):
        raise ValueError(
            f"Species forecasts must contain exactly {list(RARITY_WEIGHTS)}."
        )
    combined: pd.DataFrame | None = None
    for species, weight in RARITY_WEIGHTS.items():
        frame = species_forecasts[species]
        if not {"date", "probability"}.issubset(frame.columns):
            raise ValueError(f"{species} forecast must contain date and probability.")
        current = frame.loc[:, ["date", "probability"]].copy()
        current["date"] = pd.to_datetime(current["date"], errors="raise").dt.normalize()
        current["probability"] = pd.to_numeric(current["probability"], errors="raise")
        if (
            current.empty
            or current["date"].isna().any()
            or current["date"].duplicated().any()
            or current["probability"].isna().any()
            or not current["probability"].between(0, 1).all()
        ):
            raise ValueError(
                f"{species} must have unique dates and finite probabilities in [0, 1]."
            )
        current = current.rename(columns={"probability": f"{species}_probability"})
        if combined is None:
            combined = current
        else:
            combined = combined.merge(
                current, on="date", how="outer", validate="one_to_one"
            )
    if combined is None:
        raise ValueError("Could not combine species forecasts.")
    probability_columns = [f"{species}_probability" for species in RARITY_WEIGHTS]
    if combined[probability_columns].isna().any().any():
        raise ValueError("All species forecasts must cover the same dates.")
    combined["rarity_raw"] = sum(
        combined[f"{species}_probability"] * weight
        for species, weight in RARITY_WEIGHTS.items()
    )
    return combined.sort_values("date").reset_index(drop=True)


def scale_rarity_scores(
    rarity_raw: pd.Series,
    historical_raw: pd.Series,
) -> tuple[pd.Series, dict[str, float | int | str]]:
    """Map historical P5–P95 raw range to 0–100, clipped to range."""
    history = pd.to_numeric(historical_raw, errors="raise").dropna()
    values = pd.to_numeric(rarity_raw, errors="raise")
    if history.empty or values.isna().any() or not np.isfinite(history).all():
        raise ValueError("Historical and forecast rarity scores must be finite and non-empty.")
    lower = float(np.percentile(history.to_numpy(dtype=float), LOWER_PERCENTILE))
    upper = float(np.percentile(history.to_numpy(dtype=float), UPPER_PERCENTILE))
    if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
        raise ValueError(
            "Historical rarity raw P95 must be greater than P5 to scale the index."
        )
    score = ((values.astype(float) - lower) / (upper - lower) * 100).clip(0, 100)
    metadata: dict[str, float | int | str] = {
        "lower_percentile": LOWER_PERCENTILE,
        "upper_percentile": UPPER_PERCENTILE,
        "historical_raw_p5": lower,
        "historical_raw_p95": upper,
        "historical_sample_size": int(len(history)),
        "historical_start_date": str(historical_raw.dropna().index.min().date())
        if isinstance(historical_raw.index, pd.DatetimeIndex)
        else "",
        "historical_end_date": str(historical_raw.dropna().index.max().date())
        if isinstance(historical_raw.index, pd.DatetimeIndex)
        else "",
    }
    return score, metadata


def rarity_index_frame(
    species_forecasts: dict[str, pd.DataFrame],
    historical_raw: pd.Series,
) -> tuple[pd.DataFrame, dict[str, float | int | str]]:
    """Build the national daily index and per-species rarity contributions."""
    result = combine_rarity_raw(species_forecasts)
    result["rarity_index"], scale = scale_rarity_scores(
        result["rarity_raw"], historical_raw
    )
    result["rarity_index"] = result["rarity_index"].round(1)
    contribution_columns: dict[str, str] = {}
    for species, weight in RARITY_WEIGHTS.items():
        column = f"{species}_rarity_contribution"
        result[column] = result[f"{species}_probability"] * weight
        contribution_columns[species] = column
    result["leading_rarity_species"] = result[
        list(contribution_columns.values())
    ].idxmax(axis=1).map(
        {column: species for species, column in contribution_columns.items()}
    )
    return result, scale


def build_rarity_document(
    daily: pd.DataFrame,
    scale: dict[str, float | int | str],
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Create JSON horizon details using tomorrow, +3, +7 and +14 days."""
    if daily.empty:
        raise ValueError("Rarity Index forecast is empty.")
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    first = frame["date"].min()
    horizons = []
    for offset, (forecast_day, label) in HORIZONS_BY_OFFSET.items():
        target = first + pd.Timedelta(days=offset)
        row = frame.loc[frame["date"].eq(target)]
        if row.empty:
            raise ValueError(f"Rarity Index forecast is missing {label} ({target.date()}).")
        row = row.iloc[0]
        contributions = {
            species: float(row[f"{species}_rarity_contribution"])
            for species in RARITY_WEIGHTS
        }
        horizons.append(
            {
                "label": label,
                "forecast_day": forecast_day,
                "date": str(target.date()),
                "rarity_raw": float(row["rarity_raw"]),
                "rarity_index": float(row["rarity_index"]),
                "leading_rarity_species": str(row["leading_rarity_species"]),
                "species_probabilities": {
                    species: float(row[f"{species}_probability"])
                    for species in RARITY_WEIGHTS
                },
                "rarity_contributions": contributions,
            }
        )
    model_sufficiency: dict[str, bool] = {}
    if SPECIES_EVALUATION_FILE.is_file():
        evaluation = pd.read_csv(SPECIES_EVALUATION_FILE)
        if {"product", "data_sufficient_for_meaningful_prediction"}.issubset(
            evaluation.columns
        ):
            model_sufficiency = {
                str(row["product"]).removesuffix(" Seabird Model"): bool(
                    row["data_sufficient_for_meaningful_prediction"]
                )
                for _, row in evaluation.iterrows()
            }
    return {
        "product": "Rarity Index",
        "description": "Weighted potential for unusually rare seabird records.",
        "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
        "rarity_weights": RARITY_WEIGHTS,
        "model_data_sufficiency": model_sufficiency,
        "scaling": {
            **scale,
            "method": "historical_raw_p5_p95_clipped_to_0_100",
        },
        "horizons": horizons,
    }


def save_rarity_outputs(
    daily: pd.DataFrame,
    document: dict[str, object],
    *,
    csv_path: Path = RARITY_INDEX_OUTPUT,
    json_path: Path = RARITY_INDEX_JSON_OUTPUT,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(csv_path, index=False, date_format="%Y-%m-%d")
    json_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def build_from_saved_forecasts(
    historical_weather: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build the rarity CSV and dashboard document using current model outputs."""
    species_forecasts = {
        species: pd.read_csv(path, parse_dates=["date"])
        for species, path in SPECIES_FORECAST_FILES.items()
    }
    if historical_weather is None:
        if not WEATHER_FILE.is_file():
            raise FileNotFoundError(f"Historical weather not found: {WEATHER_FILE}")
        historical_weather = pd.read_csv(WEATHER_FILE, parse_dates=["date"])
    history = historical_rarity_raw(historical_weather)
    daily, scale = rarity_index_frame(species_forecasts, history)
    document = build_rarity_document(daily, scale)
    return daily, document
