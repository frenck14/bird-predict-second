"""Seawatching decision support derived from the Seabird Index forecasts.

Turns the national forecast, the hotspot grid and the weather inputs into one
record per forecast horizon (event status, trend, wind summary, best sites and
recommended Dutch watch coast) for the dashboard.

Heuristics, not trained models: the status bands reuse the Seabird risk cut
points, confidence is a lead-time rule, and the wind is the national coastal
wind that drives the model (it is the same for every site).
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .forecast_seabird_locations import _build_seabird_features
    from .predict_seabird import RISK_THRESHOLDS
else:
    from forecast_seabird_locations import _build_seabird_features
    from predict_seabird import RISK_THRESHOLDS


ROOT = Path(__file__).resolve().parents[1]
DECISION_SUPPORT_FILE = ROOT / "outputs/seabird_decision_support.json"
FORECAST_HISTORY_FILE = ROOT / "outputs/seabird_forecast_history.csv"
HORIZONS = {1: "Tomorrow", 3: "+3 days", 7: "+7 days", 14: "+14 days"}
COMPASS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)
# Score 100 is reached at the "major" probability, so score is comparable
# across days without implying a calibrated probability.
SCORE_FULL_SCALE = RISK_THRESHOLDS[2]
TREND_DEADBAND = 0.01  # probability points treated as "unchanged"
DUTCH_COASTS = {
    "Wadden islands": ("Texel", "Vlieland", "Terschelling", "Schiermonnikoog"),
    "North Holland coast": (
        "Den Helder", "Petten", "Camperduin", "IJmuiden", "Bloemendaal aan Zee",
    ),
    "Delta coast (Zeeland / South Holland)": (
        "Maasvlakte", "Neeltje Jans", "Westkapelle",
    ),
}


def event_status(probability: float) -> str:
    good, excellent, major = RISK_THRESHOLDS
    if probability < good:
        return "Normal"
    if probability < excellent:
        return "Good"
    if probability < major:
        return "Excellent"
    return "Major Seawatch Day"


def index_score(probability: float) -> int:
    return int(round(min(max(probability / SCORE_FULL_SCALE, 0.0), 1.0) * 100))


def confidence_label(horizon: int) -> str:
    """Lead-time confidence: weather-driven skill falls with forecast range."""
    if horizon <= 3:
        return "High"
    if horizon <= 7:
        return "Medium"
    return "Low"


def compass_label(degrees: float) -> str:
    return COMPASS[int((degrees % 360 + 11.25) // 22.5) % 16]


def trend_vs_yesterday(
    target_date: pd.Timestamp,
    probability: float,
    history: pd.DataFrame | None,
    issued_on: date,
) -> dict[str, object]:
    """Compare with the forecast issued before today for the same target day."""
    unavailable = {"direction": "n/a", "change": None}
    if history is None or history.empty:
        return unavailable
    earlier = history.loc[
        pd.to_datetime(history["date"]).dt.normalize().eq(target_date)
        & pd.to_datetime(history["issued_on"]).dt.date.lt(issued_on)
    ]
    if earlier.empty:
        return unavailable
    previous = earlier.sort_values("issued_on").iloc[-1]
    change = probability - float(previous["probability"])
    if abs(change) < TREND_DEADBAND:
        direction = "steady"
    else:
        direction = "up" if change > 0 else "down"
    return {"direction": direction, "change": change}


def wind_summary(
    engineered: pd.DataFrame | None, target_date: pd.Timestamp
) -> dict[str, object]:
    """Coastal wind for the weather day that feeds the target-day forecast."""
    empty = {
        "direction_degrees": None,
        "direction": "unknown",
        "speed_ms": None,
        "gust_ms": None,
        "text": "Wind forecast unavailable.",
    }
    if engineered is None or "date" not in engineered:
        return empty
    row = engineered.loc[
        pd.to_datetime(engineered["date"]).dt.normalize().eq(
            target_date - pd.Timedelta(days=1)
        )
    ]
    if row.empty:
        return empty
    row = row.iloc[0]
    sin, cos = float(row["coast_wind_sin"]), float(row["coast_wind_cos"])
    speed, gust = float(row["coast_wind_speed"]), float(row["coast_gust_speed"])
    if not all(np.isfinite([sin, cos, speed])):
        return empty
    degrees = math.degrees(math.atan2(sin, cos)) % 360
    label = compass_label(degrees)
    gust_text = f", gusting {gust:.0f} m/s" if np.isfinite(gust) else ""
    return {
        "direction_degrees": degrees,
        "direction": label,
        "speed_ms": speed,
        "gust_ms": gust if np.isfinite(gust) else None,
        "text": f"{label} wind {speed:.1f} m/s{gust_text}",
    }


def _base_name(location: str) -> str:
    return location.split(" (")[0]


def recommended_coast(day: pd.DataFrame) -> dict[str, object]:
    """Dutch coast with the highest mean hotspot probability on the day."""
    dutch = day.loc[day["country"].eq("NL")].copy()
    dutch["site"] = dutch["location"].map(_base_name)
    best: dict[str, object] | None = None
    for coast, sites in DUTCH_COASTS.items():
        subset = dutch.loc[dutch["site"].isin(sites)]
        if subset.empty:
            continue
        mean = float(subset["forecast_probability"].mean())
        if best is None or mean > best["mean_probability"]:
            best = {
                "coast": coast,
                "mean_probability": mean,
                "top_site": str(
                    subset.loc[subset["forecast_probability"].idxmax(), "location"]
                ),
            }
    return best or {"coast": "Unavailable", "mean_probability": 0.0, "top_site": ""}


def _site_records(frame: pd.DataFrame, limit: int) -> list[dict[str, object]]:
    return [
        {
            "rank": int(rank),
            "location": str(row["location"]),
            "country": str(row["country"]),
            "probability": float(row["forecast_probability"]),
            "score": index_score(float(row["forecast_probability"])),
            "risk_level": str(row["risk_level"]),
            "latitude": float(row["center_latitude"]),
            "longitude": float(row["center_longitude"]),
        }
        for rank, (_, row) in enumerate(frame.head(limit).iterrows(), start=1)
    ]


def build_decision_support(
    forecast: pd.DataFrame,
    locations: pd.DataFrame,
    weather: pd.DataFrame | None = None,
    history: pd.DataFrame | None = None,
    issued_on: date | None = None,
) -> dict[str, object]:
    """One record per horizon; `locations` is the detailed hotspot forecast."""
    issued_on = issued_on or date.today()
    forecast = forecast.assign(date=pd.to_datetime(forecast["date"]).dt.normalize())
    locations = locations.assign(date=pd.to_datetime(locations["date"]).dt.normalize())
    first = forecast["date"].min()
    engineered = _build_seabird_features(weather) if weather is not None else None
    horizons = []
    for horizon, label in HORIZONS.items():
        target = first + pd.Timedelta(days=horizon - 1)
        national = forecast.loc[forecast["date"].eq(target)]
        day = locations.loc[locations["date"].eq(target)]
        if national.empty or day.empty:
            raise ValueError(f"Seabird forecast is missing {target.date()}.")
        probability = float(national.iloc[0]["probability"])
        ranked = day.sort_values(
            ["forecast_probability", "cell_id"], ascending=[False, True]
        )
        dutch = ranked.loc[ranked["country"].eq("NL")]
        horizons.append(
            {
                "horizon_days": horizon,
                "label": label,
                "date": str(target.date()),
                "probability": probability,
                "score": index_score(probability),
                "status": event_status(probability),
                "risk_level": str(national.iloc[0]["risk_level"]),
                "confidence": confidence_label(horizon),
                "trend": trend_vs_yesterday(target, probability, history, issued_on),
                "wind": wind_summary(engineered, target),
                "recommended_coast": recommended_coast(day),
                "best_locations": _site_records(ranked, 10),
                "best_dutch_locations": _site_records(dutch, 5),
                "map_locations": _site_records(ranked, 40),
            }
        )
    return {"issued_on": issued_on.isoformat(), "horizons": horizons}


def update_history(
    forecast: pd.DataFrame,
    path: Path = FORECAST_HISTORY_FILE,
    issued_on: date | None = None,
) -> pd.DataFrame:
    """Append today's forecast so later runs can report the trend."""
    issued_on = issued_on or date.today()
    new = pd.DataFrame(
        {
            "issued_on": issued_on.isoformat(),
            "date": pd.to_datetime(forecast["date"]).dt.strftime("%Y-%m-%d"),
            "probability": forecast["probability"].to_numpy(),
        }
    )
    if path.is_file():
        previous = pd.read_csv(path, dtype={"issued_on": str, "date": str})
        history = pd.concat([previous, new], ignore_index=True)
    else:
        history = new
    history = history.drop_duplicates(["issued_on", "date"], keep="last")
    path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(path, index=False)
    return history


def save_decision_support(
    support: dict[str, object], path: Path = DECISION_SUPPORT_FILE
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(support, indent=2) + "\n", encoding="utf-8")


def load_history(path: Path = FORECAST_HISTORY_FILE) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    return pd.read_csv(path, dtype={"issued_on": str, "date": str})
