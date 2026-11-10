"""Validated operational weather support from existing forecast products."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
MAX_FORECAST_AGE = timedelta(hours=48)
PRODUCTS = {
    "atlantic": ("atlantic_vagrancy", "Atlantic Vagrancy Index", "atlantic_vagrancy_forecast.csv", 0.20),
    "eastern": ("eastern_vagrancy", "Eastern Vagrancy Index", "eastern_vagrancy_forecast.csv", 0.50),
    "pelagic": ("seabird_index", "Seabird Index", "seabird_forecast.csv", 0.50),
    "seabird": ("seabird_index", "Seabird Index", "seabird_forecast.csv", 0.50),
}


@dataclass(frozen=True)
class WeatherSupport:
    source: str
    forecast_date: str | None
    generated_at: str | None
    weather_source: str | None
    raw_probability: float | None
    scaled_score: float | None
    status: str
    explanation: str


def _unavailable(source: str, reason: str) -> WeatherSupport:
    LOGGER.warning("%s Weather Support unavailable: %s", source, reason)
    return WeatherSupport(source, None, None, None, None, None, "unavailable", reason)


def load_weather_support(
    output_dir: Path = ROOT / "outputs", now: datetime | None = None,
) -> dict[str, WeatherSupport]:
    """Load each pathway once; failures are explicit and isolated by product."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Weather snapshot time must include a timezone.")
    now = now.astimezone(timezone.utc)
    try:
        with (output_dir / "yellow_browed_run.json").open(encoding="utf-8") as handle:
            metadata = json.load(handle)
        if not isinstance(metadata, dict):
            raise ValueError("Run metadata must be an object.")
        generated = datetime.fromisoformat(metadata["generated_at"].replace("Z", "+00:00"))
        if generated.tzinfo is None:
            raise ValueError("Run generation time has no timezone.")
        generated = generated.astimezone(timezone.utc)
        if generated > now or now - generated > MAX_FORECAST_AGE:
            raise ValueError("Forecast run is in the future or older than 48 hours.")
        weather_source = metadata["weather_source"]
        if not isinstance(weather_source, str) or not weather_source.strip():
            raise ValueError("Run metadata has no weather source.")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return {
            key: _unavailable(product[1], f"Invalid or unavailable run metadata: {exc}")
            for key, product in PRODUCTS.items()
        }

    results = {}
    for key, (metadata_key, source, filename, threshold) in PRODUCTS.items():
        if key == "seabird" and "pelagic" in results:
            results[key] = results["pelagic"]
            continue
        try:
            product = metadata[metadata_key]
            if not isinstance(product, dict) or product.get("forecast_csv") != f"outputs/{filename}":
                raise ValueError("Product metadata does not identify the expected forecast file.")
            start = pd.Timestamp(product["forecast_start"]).date()
            end = pd.Timestamp(product["forecast_end"]).date()
            frame = pd.read_csv(output_dir / filename)
            if frame.empty or not {"date", "probability"}.issubset(frame.columns):
                raise ValueError("Forecast has no rows or required columns.")
            dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
            if dates.isna().any() or dates.duplicated().any():
                raise ValueError("Forecast dates are missing or duplicated.")
            if dates.min().date() != start or dates.max().date() != end:
                raise ValueError("Forecast date range does not match run metadata.")
            eligible = frame.loc[dates.dt.date >= now.date()].copy()
            if eligible.empty:
                raise ValueError("Forecast contains no current or future dates.")
            eligible = eligible.sort_values("date")
            row = eligible.iloc[0]
            if pd.Timestamp(row["date"]).date() > now.date() + timedelta(days=1):
                raise ValueError("No forecast is available for today or tomorrow.")
            probability = float(row["probability"])
            if not np.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError("Forecast probability must be between 0 and 1.")
            score = min(100.0, 100.0 * probability / threshold)
            explanation = (
                f"{source} probability {probability:.4f} on {row['date']}; "
                f"scaled against the {threshold:.2f} high-risk threshold. "
                "Pooled pathway signal; not species-specific or calibrated."
            )
            results[key] = WeatherSupport(
                source, str(row["date"]), generated.isoformat(), weather_source,
                probability, score, "available", explanation,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, pd.errors.ParserError) as exc:
            results[key] = _unavailable(source, f"Invalid or unavailable forecast: {exc}")
    return results


def weather_for_pathway(pathway: str, snapshot: dict[str, WeatherSupport]) -> WeatherSupport:
    key = pathway.strip().casefold() if isinstance(pathway, str) else ""
    if key in snapshot:
        return snapshot[key]
    return WeatherSupport(
        "Unknown pathway", None, None, None, None, 50.0, "neutral",
        "Unknown pathway: neutral Weather Support of 50; no forecast applied.",
    )
