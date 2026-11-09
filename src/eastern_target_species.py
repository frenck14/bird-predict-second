"""Rank Eastern vagrant species by predicted probability for each horizon.

Species probability for a date = Eastern Index probability x the species'
seasonal occurrence weight x the species' peak cell suitability (coastal x
regional x occupancy), i.e. the strongest cell in the species hotspot layer.
Historical percentile = share of all historical model-output days with a
strictly lower species probability, using the Eastern model over the full
historical weather record (the Seawatch/Rarity percentile method).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import pandas as pd

if __package__:
    from .build_eastern_vagrancy_dataset import load_all_occurrences
    from .forecast_atlantic_species_locations import HISTORY_START_YEAR, seasonal_curve
    from .forecast_eastern_species_locations import (
        EASTERN_SPECIES_LAYERS,
        eastern_species_cells,
    )
    from .forecast_location import _calendar_day_numbers
    from .historical_percentiles import (
        CALENDAR_COLUMNS,
        context,
        historical_percentile,
    )
    from .predict_eastern_vagrancy import DEFAULT_MODEL, DEFAULT_OUTPUT, make_predictions
    from .train_eastern_vagrancy_model import WEATHER_FILE
else:
    from build_eastern_vagrancy_dataset import load_all_occurrences
    from forecast_atlantic_species_locations import HISTORY_START_YEAR, seasonal_curve
    from forecast_eastern_species_locations import (
        EASTERN_SPECIES_LAYERS,
        eastern_species_cells,
    )
    from forecast_location import _calendar_day_numbers
    from historical_percentiles import CALENDAR_COLUMNS, context, historical_percentile
    from predict_eastern_vagrancy import DEFAULT_MODEL, DEFAULT_OUTPUT, make_predictions
    from train_eastern_vagrancy_model import WEATHER_FILE

LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
EASTERN_TARGET_SPECIES_CSV = ROOT / "outputs/eastern_target_species.csv"
EASTERN_TARGET_SPECIES_JSON = ROOT / "outputs/eastern_target_species.json"
HORIZON_DAYS = (1, 3, 7, 14)
HORIZON_LABELS = {1: "Tomorrow", 3: "+3 days", 7: "+7 days", 14: "+14 days"}
COLUMNS = [
    "date", "horizon_days", "rank", "species",
    "probability", "historical_percentile", "historical_label", "star_rating",
]
# Lower percentile bound -> stars, matching the Seawatch/Rarity label bands.
STAR_BANDS = ((95, 5), (90, 4), (75, 3), (50, 2), (0, 1))


def star_rating(percentile: float) -> int:
    for lower, stars in STAR_BANDS:
        if percentile >= lower:
            return stars
    return 1


def stars_text(stars: int) -> str:
    return "★" * stars + "☆" * (5 - stars)


def historical_national_probabilities(artifact: dict[str, object]) -> pd.Series:
    """Eastern Index probability for every historical target date."""
    weather = pd.read_csv(WEATHER_FILE, parse_dates=["date"])
    weather["date"] = pd.to_datetime(weather["date"]).dt.normalize()
    weather = weather.sort_values("date").reset_index(drop=True)
    weather = weather.drop(columns=CALENDAR_COLUMNS, errors="ignore")
    predictions = make_predictions(
        weather, pd.DatetimeIndex(weather["date"])[:-1], artifact
    )
    return predictions.set_index("date")["probability"].astype(float)


def build_eastern_target_species(
    national_forecast: pd.DataFrame,
    artifact: dict[str, object] | None = None,
    historical_probabilities: pd.Series | None = None,
    horizons: tuple[int, ...] = HORIZON_DAYS,
) -> pd.DataFrame:
    forecast = national_forecast.copy()
    forecast["date"] = pd.to_datetime(forecast["date"]).dt.normalize()
    forecast = forecast.sort_values("date").reset_index(drop=True)
    if len(forecast) < max(horizons):
        raise ValueError("National forecast is shorter than the longest horizon.")
    if historical_probabilities is None:
        historical_probabilities = historical_national_probabilities(
            artifact if artifact is not None else joblib.load(DEFAULT_MODEL)
        )
    history_days = _calendar_day_numbers(historical_probabilities.index.to_series())

    scored: list[dict[str, object]] = []
    for species in EASTERN_SPECIES_LAYERS:
        name = str(species["species"])
        records = load_all_occurrences([{**species, "core": True}])
        recent = records.loc[records["date"].dt.year.ge(HISTORY_START_YEAR)]
        if recent.empty:
            LOGGER.warning("No records for %s; skipped", name)
            continue
        cells = eastern_species_cells(recent)
        peak = float(
            (
                cells["coastal_suitability"]
                * cells["regional_suitability"]
                * cells["species_suitability"]
            ).max()
        )
        curve = seasonal_curve(recent["date"])
        history = (
            historical_probabilities.to_numpy() * curve[history_days - 1] * peak
        ).clip(0, 1)
        history = pd.Series(history, index=historical_probabilities.index)
        for horizon in horizons:
            row = forecast.iloc[horizon - 1]
            day = pd.Timestamp(row["date"])
            probability = float(
                min(
                    1.0,
                    row["probability"]
                    * curve[_calendar_day_numbers(pd.Series([day]))[0] - 1]
                    * peak,
                )
            )
            percentile = historical_percentile(probability, history)
            scored.append(
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "horizon_days": horizon,
                    "species": name,
                    "probability": probability,
                    "historical_percentile": round(percentile, 1),
                    "historical_label": context(probability, history)[
                        "historical_label"
                    ],
                    "star_rating": star_rating(percentile),
                }
            )
    rows = []
    for horizon in horizons:
        group = sorted(
            (r for r in scored if r["horizon_days"] == horizon),
            key=lambda r: (-r["probability"], r["species"]),
        )
        rows.extend({**r, "rank": rank} for rank, r in enumerate(group, start=1))
    return pd.DataFrame(rows, columns=COLUMNS)


def target_species_document(frame: pd.DataFrame) -> dict[str, object]:
    horizons = []
    for horizon, group in frame.groupby("horizon_days", sort=True):
        horizons.append(
            {
                "horizon_days": int(horizon),
                "label": HORIZON_LABELS[int(horizon)],
                "date": str(group["date"].iloc[0]),
                "species": group.sort_values("rank")[
                    [
                        "rank", "species", "probability",
                        "historical_percentile", "historical_label", "star_rating",
                    ]
                ].to_dict(orient="records"),
            }
        )
    return {
        "product": "Eastern Target Species",
        "method": (
            "probability = Eastern Index probability x seasonal weight x peak "
            "cell suitability; percentile = share of historical model-output "
            "days with a lower probability"
        ),
        "star_bands": {"95+": 5, "90-95": 4, "75-90": 3, "50-75": 2, "<50": 1},
        "horizons": horizons,
    }


def save_eastern_target_species(
    frame: pd.DataFrame,
    csv_path: Path = EASTERN_TARGET_SPECIES_CSV,
    json_path: Path = EASTERN_TARGET_SPECIES_JSON,
) -> dict[str, object]:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    document = target_species_document(frame)
    json_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    frame = build_eastern_target_species(pd.read_csv(DEFAULT_OUTPUT))
    save_eastern_target_species(frame)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
