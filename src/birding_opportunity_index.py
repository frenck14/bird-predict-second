"""Birding Opportunity Index (BOI): one 0-100 daily score for all forecast systems.

Each module is first converted to a historical percentile (0-100), so the four
modules share one scale:

    Atlantic / Eastern : percentile of the Index probability among all
                         historical model-output days
    Seawatch / Goose   : the percentile of the day rating already published
                         in their JSON documents

    BOI = sum(weight x module percentile)  (weights renormalised over the
          modules that are available, e.g. the Goose module is off-season)

BOI historical percentile = share of historical days with a strictly lower BOI,
built from the same per-module historical percentiles on dates where the
Atlantic, Eastern and Seawatch histories overlap. Goose joins on winter days
where it is available. Weights and categories are fixed heuristics.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import pandas as pd

if __package__:
    from .eastern_target_species import (
        EASTERN_TARGET_SPECIES_CSV,
        historical_national_probabilities,
    )
    from .forecast_atlantic_species_locations import SPECIES_LAYERS, species_output_paths
    from .goose_module import (
        MODULE_JSON_OUTPUT as GOOSE_JSON,
        historical_distributions as goose_historical_distributions,
        load_history as load_goose_history,
    )
    from .historical_percentiles import historical_percentile, historical_seawatch_scores
    from .predict_atlantic_vagrancy import DEFAULT_MODEL as ATLANTIC_MODEL
    from .predict_atlantic_vagrancy import DEFAULT_OUTPUT as ATLANTIC_FORECAST
    from .predict_atlantic_vagrancy import make_predictions as make_atlantic_predictions
    from .predict_eastern_vagrancy import DEFAULT_MODEL as EASTERN_MODEL
    from .predict_eastern_vagrancy import DEFAULT_OUTPUT as EASTERN_FORECAST
    from .seawatch_day_rating import RATING_JSON_OUTPUT as SEAWATCH_JSON
    from .train_atlantic_vagrancy_model import WEATHER_FILE as ATLANTIC_WEATHER_FILE
    from .train_seabird_model import WEATHER_FILE as SEABIRD_WEATHER_FILE
else:
    from eastern_target_species import (
        EASTERN_TARGET_SPECIES_CSV,
        historical_national_probabilities,
    )
    from forecast_atlantic_species_locations import SPECIES_LAYERS, species_output_paths
    from goose_module import (
        MODULE_JSON_OUTPUT as GOOSE_JSON,
        historical_distributions as goose_historical_distributions,
        load_history as load_goose_history,
    )
    from historical_percentiles import historical_percentile, historical_seawatch_scores
    from predict_atlantic_vagrancy import DEFAULT_MODEL as ATLANTIC_MODEL
    from predict_atlantic_vagrancy import DEFAULT_OUTPUT as ATLANTIC_FORECAST
    from predict_atlantic_vagrancy import make_predictions as make_atlantic_predictions
    from predict_eastern_vagrancy import DEFAULT_MODEL as EASTERN_MODEL
    from predict_eastern_vagrancy import DEFAULT_OUTPUT as EASTERN_FORECAST
    from seawatch_day_rating import RATING_JSON_OUTPUT as SEAWATCH_JSON
    from train_atlantic_vagrancy_model import WEATHER_FILE as ATLANTIC_WEATHER_FILE
    from train_seabird_model import WEATHER_FILE as SEABIRD_WEATHER_FILE

LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
BOI_CSV = ROOT / "outputs/birding_opportunity_index.csv"
BOI_JSON = ROOT / "outputs/birding_opportunity_index.json"
ATLANTIC_LOCATION_FILE = ROOT / "outputs/atlantic_vagrancy_location_forecast.csv"
EASTERN_LOCATION_FILE = ROOT / "outputs/eastern_vagrancy_location_forecast.csv"
SEABIRD_TARGET_FILE = ROOT / "outputs/target_species.csv"

HORIZONS = {1: "Tomorrow", 3: "+3 days", 7: "+7 days", 14: "+14 days"}
WEIGHTS = {"Atlantic": 0.35, "Eastern": 0.35, "Seawatch": 0.15, "Goose": 0.15}
# Lower bound (inclusive) -> category; 100 falls in Mega Day.
CATEGORIES = (
    (90, "Mega Day"),
    (80, "Excellent"),
    (60, "Good"),
    (40, "Average"),
    (20, "Quiet"),
    (0, "Dead"),
)
STYLES = {
    "Atlantic": "Island and west-coast vagrant hunting: headlands and migration "
    "traps for Nearctic passerines",
    "Eastern": "East-coast bush-bashing: migration traps, coastal scrub and "
    "headlands for Siberian vagrants",
    "Seawatch": "Seawatching: sit at a Dutch or west-coast headland with a scope",
    "Goose": "Goose-flock scanning: polders and estuaries for rare geese among "
    "the wintering flocks",
}
LOW_STYLE = "Local patch birding or a rest day; no major target is forecast"
COLUMNS = [
    "date", "horizon_days", "label", "boi_score", "historical_percentile",
    "rating_category", "recommended_style", "main_module",
    "atlantic_percentile", "eastern_percentile", "seawatch_percentile",
    "goose_percentile", "best_hotspots", "target_species",
]


def category(score: float) -> str:
    for lower, label in CATEGORIES:
        if score >= lower:
            return label
    return CATEGORIES[-1][1]


def weighted_score(percentiles: dict[str, float | None]) -> tuple[float, dict[str, float]]:
    """Return (BOI, weighted contribution per module) over available modules."""
    available = {k: v for k, v in percentiles.items() if v is not None and pd.notna(v)}
    total = sum(WEIGHTS[k] for k in available)
    if total <= 0:
        raise ValueError("No module is available to build the BOI.")
    contributions = {k: WEIGHTS[k] / total * float(v) for k, v in available.items()}
    return sum(contributions.values()), contributions


def percentile_series(series: pd.Series) -> pd.Series:
    """Share of values strictly lower, 0-100 (matches historical_percentile)."""
    values = series.dropna()
    ranks = (values.rank(method="min") - 1) / len(values) * 100.0
    return ranks.reindex(series.index)


def historical_boi(
    atlantic: pd.Series,
    eastern: pd.Series,
    seawatch: pd.Series,
    goose: pd.Series | None = None,
) -> pd.Series:
    """BOI for every historical date where Atlantic, Eastern and Seawatch exist."""
    frame = pd.DataFrame(
        {
            "Atlantic": percentile_series(atlantic),
            "Eastern": percentile_series(eastern),
            "Seawatch": percentile_series(seawatch),
        }
    ).dropna()
    if goose is not None:
        frame["Goose"] = percentile_series(goose).reindex(frame.index)
    scores = [
        weighted_score({k: row[k] for k in frame.columns})[0]
        for _, row in frame.iterrows()
    ]
    return pd.Series(scores, index=frame.index, name="boi")


def _top_cells(path: Path, day: pd.Timestamp, limit: int = 3) -> list[str]:
    if not path.is_file():
        return []
    frame = pd.read_csv(path, parse_dates=["date"])
    top = frame.loc[frame["date"].eq(day)].sort_values(
        ["forecast_probability", "cell_id"], ascending=[False, True]
    ).head(limit)
    return [
        f"{row.location} ({row.forecast_probability:.0%})" for row in top.itertuples()
    ]


def _atlantic_species(day: pd.Timestamp, limit: int = 3) -> list[str]:
    scored = []
    for species in SPECIES_LAYERS:
        path = species_output_paths(str(species["slug"]))["location"]
        if not path.is_file():
            continue
        frame = pd.read_csv(path, usecols=["date", "forecast_probability"], parse_dates=["date"])
        today = frame.loc[frame["date"].eq(day), "forecast_probability"]
        if not today.empty:
            scored.append((float(today.max()), str(species["species"])))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [f"{name} ({prob:.0%})" for prob, name in scored[:limit]]


def _csv_species(path: Path, horizon: int, day: pd.Timestamp, limit: int = 3) -> list[str]:
    if not path.is_file():
        return []
    frame = pd.read_csv(path)
    rows = frame.loc[
        frame["horizon_days"].eq(horizon) & frame["date"].eq(f"{day:%Y-%m-%d}")
    ].sort_values("rank").head(limit)
    return [f"{r.species} ({r.probability:.0%})" for r in rows.itertuples()]


def module_details(
    module: str,
    horizon: int,
    day: pd.Timestamp,
    seawatch_horizon: dict[str, object] | None,
    goose_horizon: dict[str, object] | None,
) -> tuple[list[str], list[str]]:
    """(best hotspots, most likely target species) for one module."""
    if module == "Atlantic":
        return _top_cells(ATLANTIC_LOCATION_FILE, day), _atlantic_species(day)
    if module == "Eastern":
        return (
            _top_cells(EASTERN_LOCATION_FILE, day),
            _csv_species(EASTERN_TARGET_SPECIES_CSV, horizon, day),
        )
    if module == "Seawatch":
        hotspots = [
            f"{h['location']} ({h['score']:.0f})"
            for h in (seawatch_horizon or {}).get("top10_hotspots", [])[:3]
        ]
        return hotspots, _csv_species(SEABIRD_TARGET_FILE, horizon, day)
    hotspots = [
        f"{h['location']} ({h['score']:.0f})"
        for h in (goose_horizon or {}).get("top10_hotspots", [])[:3]
    ]
    geese = [
        f"{g['species']} ({g['probability']:.0%})"
        for g in (goose_horizon or {}).get("target_geese", [])[:3]
    ]
    return hotspots, geese


def build_birding_opportunity_index(
    atlantic_forecast: pd.DataFrame,
    eastern_forecast: pd.DataFrame,
    seawatch_document: dict[str, object],
    goose_document: dict[str, object] | None,
    atlantic_history: pd.Series,
    eastern_history: pd.Series,
    seawatch_history: pd.Series,
    goose_history: pd.Series | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build the BOI frame and JSON document for tomorrow, +3, +7 and +14 days."""
    history = historical_boi(
        atlantic_history, eastern_history, seawatch_history, goose_history
    )
    atlantic = atlantic_forecast.assign(
        date=pd.to_datetime(atlantic_forecast["date"]).dt.normalize()
    ).set_index("date")["probability"]
    eastern = eastern_forecast.assign(
        date=pd.to_datetime(eastern_forecast["date"]).dt.normalize()
    ).set_index("date")["probability"]
    seawatch_by_day = {int(h["forecast_day"]): h for h in seawatch_document["horizons"]}
    goose_by_day = {
        int(h["forecast_day"]): h for h in (goose_document or {}).get("horizons", [])
    }
    rows = []
    for horizon, label in HORIZONS.items():
        day = atlantic.index.min() + pd.Timedelta(days=horizon - 1)
        if day not in atlantic.index or day not in eastern.index:
            raise ValueError(f"Vagrancy forecasts are missing {label} ({day.date()}).")
        seawatch_horizon = seawatch_by_day[horizon]
        if pd.Timestamp(seawatch_horizon["date"]) != day:
            raise ValueError(f"Seawatch rating date mismatch for {label}.")
        goose_horizon = goose_by_day.get(horizon)
        goose_percentile = None
        if (
            goose_horizon
            and not goose_horizon.get("off_season")
            and pd.Timestamp(goose_horizon["date"]) == day
        ):
            goose_percentile = float(
                goose_horizon["goose_day_rating"]["historical_percentile"]
            )
        percentiles = {
            "Atlantic": historical_percentile(float(atlantic[day]), atlantic_history),
            "Eastern": historical_percentile(float(eastern[day]), eastern_history),
            "Seawatch": float(seawatch_horizon["historical_percentile"]),
            "Goose": goose_percentile,
        }
        score, contributions = weighted_score(percentiles)
        main = max(contributions, key=lambda k: (contributions[k], k))
        rating = category(score)
        style = LOW_STYLE if rating in ("Dead", "Quiet") else STYLES[main]
        hotspots, species = module_details(
            main, horizon, day, seawatch_horizon, goose_horizon
        )
        rows.append(
            {
                "date": f"{day:%Y-%m-%d}",
                "horizon_days": horizon,
                "label": label,
                "boi_score": round(score, 1),
                "historical_percentile": round(
                    historical_percentile(score, history), 1
                ),
                "rating_category": rating,
                "recommended_style": style,
                "main_module": main,
                "atlantic_percentile": round(percentiles["Atlantic"], 1),
                "eastern_percentile": round(percentiles["Eastern"], 1),
                "seawatch_percentile": round(percentiles["Seawatch"], 1),
                "goose_percentile": (
                    None if goose_percentile is None else round(goose_percentile, 1)
                ),
                "best_hotspots": "; ".join(hotspots),
                "target_species": "; ".join(species),
                "_contributions": {k: round(v, 2) for k, v in contributions.items()},
                "_hotspots": hotspots,
                "_species": species,
            }
        )
    frame = pd.DataFrame(rows)
    document = {
        "product": "Birding Opportunity Index",
        "method": (
            "weighted mean of module historical percentiles; weights "
            "renormalised over available modules"
        ),
        "weights": WEIGHTS,
        "categories": {
            "0-20": "Dead", "20-40": "Quiet", "40-60": "Average",
            "60-80": "Good", "80-90": "Excellent", "90-100": "Mega Day",
        },
        "historical_sample_size": int(len(history)),
        "horizons": [
            {
                "horizon_days": r["horizon_days"],
                "label": r["label"],
                "date": r["date"],
                "boi_score": r["boi_score"],
                "historical_percentile": r["historical_percentile"],
                "rating_category": r["rating_category"],
                "recommended_style": r["recommended_style"],
                "main_module": r["main_module"],
                "module_percentiles": {
                    "Atlantic": r["atlantic_percentile"],
                    "Eastern": r["eastern_percentile"],
                    "Seawatch": r["seawatch_percentile"],
                    "Goose": r["goose_percentile"],
                },
                "weighted_contributions": r["_contributions"],
                "best_hotspots": r["_hotspots"],
                "target_species": r["_species"],
            }
            for r in rows
        ],
    }
    return frame[COLUMNS], document


def save_birding_opportunity_index(
    frame: pd.DataFrame,
    document: dict[str, object],
    csv_path: Path = BOI_CSV,
    json_path: Path = BOI_JSON,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def load_goose(path: Path = GOOSE_JSON) -> tuple[dict | None, pd.Series | None]:
    if not path.is_file():
        return None, None
    try:
        history = goose_historical_distributions(load_goose_history())[2]
    except (FileNotFoundError, ValueError):
        return None, None
    return json.loads(path.read_text(encoding="utf-8")), history


def build_from_outputs(
    goose_document: dict[str, object] | None = None,
    goose_history: pd.Series | None = None,
    seawatch_history: pd.Series | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build the BOI from persisted forecasts; used by run_daily_forecast and main."""
    weather = pd.read_csv(ATLANTIC_WEATHER_FILE, parse_dates=["date"])
    atlantic_artifact = joblib.load(ATLANTIC_MODEL)
    atlantic_history = _history_probabilities(
        weather, atlantic_artifact, make_atlantic_predictions
    )
    eastern_history = historical_national_probabilities(joblib.load(EASTERN_MODEL))
    if seawatch_history is None:
        seawatch_history = historical_seawatch_scores(
            pd.read_csv(SEABIRD_WEATHER_FILE, parse_dates=["date"])
        )
    return build_birding_opportunity_index(
        pd.read_csv(ATLANTIC_FORECAST),
        pd.read_csv(EASTERN_FORECAST),
        json.loads(SEAWATCH_JSON.read_text(encoding="utf-8")),
        goose_document,
        atlantic_history,
        eastern_history,
        seawatch_history,
        goose_history,
    )


def _history_probabilities(weather, artifact, predict) -> pd.Series:
    weather = weather.copy()
    weather["date"] = pd.to_datetime(weather["date"]).dt.normalize()
    weather = weather.sort_values("date").reset_index(drop=True)
    weather = weather.drop(
        columns=["month", "day_of_year", "day_of_year_sin", "day_of_year_cos"],
        errors="ignore",
    )
    predictions = predict(weather, pd.DatetimeIndex(weather["date"])[:-1], artifact)
    return predictions.set_index("date")["probability"].astype(float)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    goose_document, goose_history = load_goose()
    frame, document = build_from_outputs(goose_document, goose_history)
    save_birding_opportunity_index(frame, document)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
