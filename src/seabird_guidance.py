"""Decision-support helpers: GO/MAYBE/STAY HOME, Dutch coast ranking, drivers."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COAST_RANKING_OUTPUT = ROOT / "outputs/dutch_coast_ranking.csv"
COAST_RANKING_COLUMNS = ["date", "horizon_days", "coast", "score", "rank"]

# Assumed site assignment. Den Helder is grouped with North Holland (mainland
# Marsdiep shore) and Maasvlakte is the only South Holland seawatch site.
DUTCH_COAST_REGIONS = {
    "Wadden Islands": ("Texel", "Vlieland", "Terschelling", "Schiermonnikoog"),
    "North Holland Coast": (
        "Den Helder", "Petten", "Camperduin", "IJmuiden", "Bloemendaal aan Zee",
    ),
    "South Holland Coast": ("Maasvlakte",),
    "Delta Coast": ("Neeltje Jans", "Westkapelle"),
}

GO_RATING = 70
GO_RATING_WITH_RARITY = 50
GO_RARITY = 70
MAYBE_RATING = 35
MAYBE_RARITY = 50
# Species signal counts as "elevated" at the MODERATE risk probability.
ELEVATED_SIGNAL = 0.25
SPECIES_LABELS = {
    "European Storm-petrel": "Storm-petrel",
    "Manx Shearwater": "Manx",
    "Sooty Shearwater": "Sooty",
}
BANNER_ICONS = {"GO": "🟢", "MAYBE": "🟡", "STAY HOME": "🔴"}


def recommend(rating: float, rarity: float) -> str:
    """GO / MAYBE / STAY HOME from Seawatch Day Rating and Rarity Index."""
    if rating >= GO_RATING or (
        rating >= GO_RATING_WITH_RARITY and rarity >= GO_RARITY
    ):
        return "GO"
    if rating >= MAYBE_RATING or rarity >= MAYBE_RARITY:
        return "MAYBE"
    return "STAY HOME"


def _site_name(location: str) -> str:
    return location.split(" (")[0]


def coast_scores(site_scores: dict[str, float]) -> list[dict[str, object]]:
    """Mean site score per region, ranked best first (ties by name)."""
    rows = []
    for coast, sites in DUTCH_COAST_REGIONS.items():
        present = {site: site_scores[site] for site in sites if site in site_scores}
        if present:
            top_site = min(present, key=lambda site: (-present[site], site))
            rows.append(
                {
                    "coast": coast,
                    "score": round(sum(present.values()) / len(present), 1),
                    "top_site": top_site,
                }
            )
    rows.sort(key=lambda row: (-row["score"], row["coast"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def dutch_site_scores(day: pd.DataFrame) -> dict[str, float]:
    """Best grid-cell score per Dutch site from a day's hotspot frame."""
    dutch = day.loc[day["country"].eq("NL")]
    scores: dict[str, float] = {}
    for location, score in zip(dutch["location"], dutch["score"]):
        name = _site_name(str(location))
        scores[name] = max(scores.get(name, float("-inf")), float(score))
    return scores


def coast_ranking_frame(horizons: list[dict[str, object]]) -> pd.DataFrame:
    """Dutch coast ranking rows for every horizon in the rating document."""
    rows = []
    for horizon in horizons:
        ranking = horizon.get("coast_ranking") or []
        for entry in ranking:
            rows.append(
                {
                    "date": horizon["date"],
                    "horizon_days": int(horizon["forecast_day"]),
                    "coast": entry["coast"],
                    "score": entry["score"],
                    "rank": entry["rank"],
                }
            )
    return pd.DataFrame(rows, columns=COAST_RANKING_COLUMNS)


def explain_rating(
    probabilities: dict[str, float],
    weights: dict[str, float],
    bonuses: dict[str, float],
    applied: dict[str, float],
    weather: dict[str, object],
) -> dict[str, list[dict[str, object]]]:
    """Positive and negative drivers; negatives are the missing positives.

    ``points`` is the score contributed (positive) or forgone (negative).
    """
    positive: list[dict[str, object]] = []
    negative: list[dict[str, object]] = []
    wind = weather.get("wind_speed_kt")
    direction = weather.get("wind_direction", "unknown")
    pressure = weather.get("minimum_pressure_hpa")
    change = weather.get("wind_change_ms")

    def add(flag: bool, key: str, label: str, good: str, bad: str) -> None:
        points = float(bonuses[key])
        if flag:
            positive.append(
                {"name": key, "label": label, "detail": good, "points": points}
            )
        else:
            negative.append(
                {"name": key, "label": label, "detail": bad, "points": -points}
            )

    wind_text = (
        f"{direction} {wind:.0f} kt" if wind is not None else "wind unavailable"
    )
    add(
        bool(applied.get("strong_westerly_wind")),
        "strong_westerly_wind",
        "Strong W-WNW airflow",
        f"{wind_text}",
        f"{wind_text}; needs W-WNW at 20 kt or more",
    )
    pressure_text = (
        f"{pressure:.0f} hPa" if pressure is not None else "pressure unavailable"
    )
    add(
        bool(applied.get("deep_atlantic_low")),
        "deep_atlantic_low",
        "Deep Atlantic low",
        pressure_text,
        f"{pressure_text}; no deep low (1000 hPa or lower)",
    )
    increasing = bool(applied.get("increasing_wind"))
    add(
        increasing,
        "increasing_wind",
        "Increasing wind",
        "wind stronger than previous day",
        "wind not increasing"
        if change is not None
        else "no previous-day wind to compare",
    )
    add(
        bool(applied.get("peak_seawatching_season")),
        "peak_seawatching_season",
        "October-November season",
        "peak seawatching season",
        "outside the October-November peak",
    )
    for species, label in SPECIES_LABELS.items():
        probability = float(probabilities[species])
        points = probability * weights[species] * 100.0
        name = f"{label.lower().replace('-', '_')}_signal"
        if probability >= ELEVATED_SIGNAL:
            positive.append(
                {
                    "name": name,
                    "label": f"Elevated {label} signal",
                    "detail": f"{probability:.0%} event probability",
                    "points": points,
                }
            )
        else:
            negative.append(
                {
                    "name": name,
                    "label": f"Weak {label} signal",
                    "detail": f"{probability:.0%} event probability "
                    f"(elevated at {ELEVATED_SIGNAL:.0%})",
                    "points": -(ELEVATED_SIGNAL - probability)
                    * weights[species]
                    * 100.0,
                }
            )
    return {"positive_drivers": positive, "negative_drivers": negative}


def build_recommendations(
    rating_document: dict[str, object], rarity_document: dict[str, object]
) -> list[dict[str, object]]:
    """One recommendation per horizon, pairing rating and rarity by date."""
    rarity_by_date = {
        horizon["date"]: float(horizon["rarity_index"])
        for horizon in rarity_document["horizons"]
    }
    results = []
    for horizon in rating_document["horizons"]:
        date = str(horizon["date"])
        if date not in rarity_by_date:
            raise ValueError(f"Rarity Index is missing {date}.")
        rating = float(horizon["score"])
        rarity = rarity_by_date[date]
        ranking = horizon.get("coast_ranking") or []
        decision = recommend(rating, rarity)
        results.append(
            {
                "date": date,
                "label": horizon["label"],
                "decision": decision,
                "icon": BANNER_ICONS[decision],
                "seawatch_day_rating": rating,
                "rarity_index": rarity,
                "best_coast": ranking[0]["coast"] if ranking else "Unavailable",
                "best_site": ranking[0]["top_site"] if ranking else "Unavailable",
            }
        )
    return results


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_coast_ranking(
    horizons: list[dict[str, object]], path: Path = COAST_RANKING_OUTPUT
) -> pd.DataFrame:
    frame = coast_ranking_frame(horizons)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame
