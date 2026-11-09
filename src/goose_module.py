"""Winter Goose Module: activity, rare-goose potential, targets, rating and hotspots.

Mirrors the Seawatch Day Rating / Rarity Index / Target Species / Historical
Percentile architecture for wintering geese:

* Goose Activity Index  - probability of an above-normal goose day (0-100).
* Rare Goose Potential  - sum(p x weight), scaled historical P5-P95 -> 0-100.
* Target Geese          - p x weight per rare species, ranked.
* Goose Day Rating      - 70% activity + 30% rare potential.
* Hotspots / regions    - site and region scores for the Dutch goose areas.
* GO / MAYBE / STAY HOME recommendation.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

if __package__:
    from .build_goose_dataset import GOOSE_SITES, REGIONS, SITE_COUNTS_OUTPUT, WINTER_MONTHS
    from .forecast_atlantic_locations import HORIZONS
    from .goose_features import seasonality
    from .historical_percentiles import historical_percentile, percentile_label
    from .rarity_index import scale_rarity_scores
    from .train_goose_models import (
        ACTIVITY_MODEL, COMPARISON_OUTPUT, EVALUATION_OUTPUT, HISTORICAL_SCORES_OUTPUT, IMPORTANCE_OUTPUT,
        MODEL_NAMES, feature_frame, model_path, predict_with_artifact,
    )
else:
    from build_goose_dataset import GOOSE_SITES, REGIONS, SITE_COUNTS_OUTPUT, WINTER_MONTHS
    from forecast_atlantic_locations import HORIZONS
    from goose_features import seasonality
    from historical_percentiles import historical_percentile, percentile_label
    from rarity_index import scale_rarity_scores
    from train_goose_models import (
        ACTIVITY_MODEL, COMPARISON_OUTPUT, EVALUATION_OUTPUT, HISTORICAL_SCORES_OUTPUT, IMPORTANCE_OUTPUT,
        MODEL_NAMES, feature_frame, model_path, predict_with_artifact,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
ACTIVITY_OUTPUT = OUTPUTS / "goose_activity_index.csv"
RARE_OUTPUT = OUTPUTS / "rare_goose_potential.csv"
RATING_OUTPUT = OUTPUTS / "goose_day_rating.csv"
HOTSPOTS_OUTPUT = OUTPUTS / "goose_hotspots.csv"
REGION_OUTPUT = OUTPUTS / "goose_region_ranking.csv"
TARGET_OUTPUT = OUTPUTS / "target_geese.csv"
MODULE_JSON_OUTPUT = OUTPUTS / "goose_module.json"
EUROPEAN_INFLUX_OUTPUT = OUTPUTS / "european_goose_influx.csv"
EUROPEAN_INDEX_OUTPUT = OUTPUTS / "rare_goose_europe_index.csv"

RARE_GOOSE_WEIGHTS = {
    "Lesser White-fronted Goose": 4.0,
    "Red-breasted Goose": 5.0,
    "Snow Goose": 5.0,
    "Ross's Goose": 8.0,
    "Black Brant": 3.0,
}
RATING_WEIGHTS = {"activity": 0.70, "rare": 0.30}
ACTIVITY_BANDS = ((85, "Major Goose Day"), (70, "Strong"), (50, "Good"), (25, "Moderate"), (0, "Quiet"))
RARE_BANDS = ((85, "Exceptional"), (70, "Very High"), (50, "High"), (25, "Moderate"), (0, "Low"))
RATING_BANDS = ((85, "Major Goose Day"), (70, "Excellent"), (50, "Good"), (25, "Fair"), (0, "Poor"))
GO_RATING = 70.0
GO_RARE = 80.0
MAYBE_RATING = 40.0
DECISION_EMOJI = {"GO": "🟢", "MAYBE": "🟡", "STAY HOME": "🔴"}
HORIZONS_BY_OFFSET = {days - 1: (days, label) for days, label in HORIZONS.items()}
TOP_HOTSPOTS = 10
TOP_FEATURES = 10

# Expert priors (not fitted): hard frost and cold outbreaks push geese out of
# frozen inland water and fields towards the milder south-western coast.
COLD_FROST_DAYS = 3
COLD_REGION_MODIFIERS = {
    "Zeeland": 1.15, "Texel": 1.05, "Lauwersmeer": 0.95,
    "IJsselmeergebied": 0.90, "Flevoland": 0.90,
}
SITE_FACTOR_FLOOR = 0.6
SITE_FACTOR_SPAN = 0.6
TOP_SITES_PER_REGION = 3


def band(score: float, bands: tuple[tuple[int, str], ...]) -> str:
    for lower, label in bands:
        if score >= lower:
            return label
    return bands[-1][1]


def recommendation(rating: float, rare_index: float) -> dict[str, str]:
    """GO if rating >= 70 or rare potential >= 80; MAYBE if rating >= 40."""
    reasons = []
    if rating >= GO_RATING:
        reasons.append(f"Goose Day Rating {rating:.0f} >= {GO_RATING:.0f}")
    if rare_index >= GO_RARE:
        reasons.append(f"Rare Goose Potential {rare_index:.0f} >= {GO_RARE:.0f}")
    if reasons:
        decision = "GO"
    elif rating >= MAYBE_RATING:
        decision, reasons = "MAYBE", [f"Goose Day Rating {rating:.0f} is {MAYBE_RATING:.0f}-69"]
    else:
        decision, reasons = "STAY HOME", [f"Goose Day Rating {rating:.0f} < {MAYBE_RATING:.0f}"]
    return {"decision": decision, "emoji": DECISION_EMOJI[decision], "reason": "; ".join(reasons)}


def rank_text(percentile: float) -> str:
    return f"Higher than {percentile:.0f}% of historical winter days"


def percentile_context(score: float, history: pd.Series) -> dict[str, object]:
    percentile = historical_percentile(score, history)
    return {
        "historical_percentile": round(percentile, 1),
        "historical_label": percentile_label(percentile),
        "historical_rank_text": rank_text(percentile),
    }


def european_index_history(history: pd.DataFrame) -> pd.Series:
    """Equal-weight mean of the five species' out-of-fold percentile scores."""
    component_scores = []
    for species in RARE_GOOSE_WEIGHTS:
        reference = np.sort(pd.to_numeric(history[species], errors="raise").dropna().to_numpy())
        values = pd.to_numeric(history[species], errors="raise").to_numpy()
        component_scores.append(
            pd.Series(
                np.searchsorted(reference, values, side="left") / len(reference) * 100.0,
                index=history.index,
            )
        )
    return pd.concat(component_scores, axis=1).mean(axis=1)


def european_influx_score(
    species_probabilities: dict[str, float], history: pd.DataFrame
) -> dict[str, object]:
    species_activity = []
    for species, probability in species_probabilities.items():
        context = percentile_context(probability, history[species])
        species_activity.append({
            "species": species,
            "probability": probability,
            "activity_score": round(probability * 100.0, 1),
            "european_percentile": context["historical_percentile"],
            "historical_label": context["historical_label"],
        })
    index_score = float(np.mean([
        item["european_percentile"] for item in species_activity
    ]))
    context = percentile_context(index_score, european_index_history(history))
    return {
        "score": round(index_score, 1),
        **context,
        "species_activity": species_activity,
    }


def load_artifacts(directory: Path = OUTPUTS) -> dict[str, dict[str, object]]:
    missing = [str(model_path(name, directory)) for name in MODEL_NAMES if not model_path(name, directory).is_file()]
    if missing:
        raise FileNotFoundError(
            "Goose models are missing: " + ", ".join(missing)
            + ". Run `python src/build_goose_dataset.py` and `python src/train_goose_models.py`."
        )
    return {name: joblib.load(model_path(name, directory)) for name in MODEL_NAMES}


def goose_models_available(directory: Path = OUTPUTS) -> bool:
    return all(model_path(name, directory).is_file() for name in MODEL_NAMES) and HISTORICAL_SCORES_OUTPUT.is_file()


def predict_probabilities(
    weather: pd.DataFrame,
    predictor_dates: pd.DatetimeIndex,
    artifacts: dict[str, dict[str, object]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Next-day probabilities per model, plus the weather conditions per target date."""
    features = feature_frame(weather).set_index("date")
    missing = predictor_dates.difference(features.index)
    if len(missing):
        raise ValueError(f"Weather is missing predictor dates: {list(missing.strftime('%Y-%m-%d'))}")
    target_dates = predictor_dates + pd.Timedelta(days=1)
    inputs = pd.concat(
        [seasonality(target_dates).reset_index(drop=True),
         features.loc[predictor_dates].reset_index(drop=True)],
        axis=1,
    )
    probabilities = pd.DataFrame({"date": target_dates})
    for name, artifact in artifacts.items():
        missing_features = set(artifact["feature_columns"]).difference(inputs.columns)
        if missing_features:
            raise ValueError(f"Weather cannot construct {name} features: {sorted(missing_features)}")
        values = predict_with_artifact(artifact, inputs)
        if not np.isfinite(values).all():
            raise ValueError(f"{name} produced non-finite probabilities.")
        probabilities[name] = values
    conditions = pd.DataFrame(
        {
            "date": target_dates,
            "cold_outbreak": inputs["goose_cold_outbreak"].fillna(0).astype(bool),
            "rapid_temp_drop": inputs["goose_rapid_temp_drop"].fillna(0).astype(bool),
            "consecutive_frost_days": inputs["goose_consecutive_frost_days"].fillna(0),
            "temperature_c": inputs["goose_temp_mean_c"],
        }
    )
    return probabilities, conditions


def rarity_raw(probabilities: pd.DataFrame) -> pd.Series:
    return sum(probabilities[species] * weight for species, weight in RARE_GOOSE_WEIGHTS.items())


def load_history(path: Path = HISTORICAL_SCORES_OUTPUT) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Goose historical scores missing: {path}. Run train_goose_models.py.")
    history = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    needed = [ACTIVITY_MODEL, *RARE_GOOSE_WEIGHTS]
    if not set(needed).issubset(history.columns):
        raise ValueError(f"Historical scores must contain {needed}.")
    return history.dropna(subset=needed)


def historical_distributions(history: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, dict[str, object]]:
    """Historical winter-day activity score, rare raw, and day rating (all unrounded)."""
    activity = (history[ACTIVITY_MODEL] * 100.0).clip(0, 100)
    raw = rarity_raw(history)
    rare_index, scale = scale_rarity_scores(raw, raw)
    rating = RATING_WEIGHTS["activity"] * activity + RATING_WEIGHTS["rare"] * rare_index
    return activity, raw, rating, scale


def site_table(site_counts: pd.DataFrame | None) -> pd.DataFrame:
    """Per-site weights from historical winter GBIF records (sqrt-damped)."""
    sites = pd.DataFrame(GOOSE_SITES, columns=["site", "region", "latitude", "longitude"])
    if site_counts is None or site_counts.empty:
        sites["common_factor"] = sites["rare_factor"] = 1.0
        return sites
    sites = sites.merge(site_counts[["site", "common_records", "rare_records"]], on="site", how="left").fillna(0)
    for group in ("common", "rare"):
        records = sites[f"{group}_records"].astype(float)
        peak = records.max()
        share = np.sqrt(records / peak) if peak > 0 else 0.0
        sites[f"{group}_factor"] = SITE_FACTOR_FLOOR + SITE_FACTOR_SPAN * share
    return sites


def build_hotspots(
    sites: pd.DataFrame, activity: float, rare_index: float, condition: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cold = bool(condition["cold_outbreak"]) or float(condition["consecutive_frost_days"]) >= COLD_FROST_DAYS
    rows = sites.copy()
    modifier = rows["region"].map(COLD_REGION_MODIFIERS).fillna(1.0) if cold else 1.0
    rows["score"] = (
        (RATING_WEIGHTS["activity"] * activity * rows["common_factor"]
         + RATING_WEIGHTS["rare"] * rare_index * rows["rare_factor"]) * modifier
    ).clip(0, 100).round(1)
    rows["rating"] = rows["score"].map(lambda value: band(value, RATING_BANDS))
    rows = rows.sort_values(["score", "site"], ascending=[False, True]).reset_index(drop=True)
    hotspots = rows.head(TOP_HOTSPOTS).copy()
    hotspots.insert(0, "rank", np.arange(1, len(hotspots) + 1))
    hotspots = hotspots.rename(columns={"site": "location"})[
        ["rank", "location", "region", "latitude", "longitude", "score", "rating"]
    ]
    regions = (
        rows.groupby("region")["score"]
        .apply(lambda scores: float(scores.nlargest(TOP_SITES_PER_REGION).mean()))
        .reindex(REGIONS).dropna().round(1).sort_values(ascending=False, kind="stable")
    )
    ranking = pd.DataFrame({"rank": np.arange(1, len(regions) + 1), "region": regions.index, "score": regions.to_numpy()})
    ranking["rating"] = ranking["score"].map(lambda value: band(value, RATING_BANDS))
    top_site = rows.sort_values("score", ascending=False).drop_duplicates("region").set_index("region")["site"]
    ranking["top_site"] = ranking["region"].map(top_site)
    return hotspots, ranking


def evaluation_records(path: Path = EVALUATION_OUTPUT) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    frame = pd.read_csv(path)
    keep = ["model", "status", "roc_auc", "pr_auc", "training_records", "positive_events", "data_sufficiency"]
    frame = frame[[c for c in keep if c in frame.columns]]
    return json.loads(frame.to_json(orient="records"))


def model_comparison_records(path: Path = COMPARISON_OUTPUT) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    return json.loads(pd.read_csv(path).to_json(orient="records"))


def top_features(path: Path = IMPORTANCE_OUTPUT, limit: int = TOP_FEATURES) -> dict[str, list[dict[str, object]]]:
    if not path.is_file():
        return {}
    frame = pd.read_csv(path)
    return {
        str(name): [{"feature": row.feature, "importance": round(float(row.importance), 5)} for row in group.head(limit).itertuples()]
        for name, group in frame.groupby("model")
    }


def build_goose_products(
    probabilities: pd.DataFrame,
    conditions: pd.DataFrame,
    history: pd.DataFrame,
    site_counts: pd.DataFrame | None = None,
    evaluation: list[dict[str, object]] | None = None,
    importance: dict[str, list[dict[str, object]]] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Return every goose table plus the JSON document."""
    probabilities = probabilities.assign(date=pd.to_datetime(probabilities["date"]).dt.normalize())
    conditions = conditions.assign(date=pd.to_datetime(conditions["date"]).dt.normalize())
    activity_history, raw_history, rating_history, scale = historical_distributions(history)
    sites = site_table(site_counts)
    first = probabilities["date"].min()
    date_rows = probabilities.set_index("date")
    european_by_days: dict[int, dict[str, object]] = {}
    for days, label in HORIZONS.items():
        target_date = first + pd.Timedelta(days=days - 1)
        if target_date not in date_rows.index:
            raise ValueError(f"Goose forecast is missing {label} ({target_date.date()}).")
        row = date_rows.loc[target_date]
        european_by_days[days] = european_influx_score(
            {species: float(row[species]) for species in RARE_GOOSE_WEIGHTS},
            history,
        )
    tomorrow_score = float(european_by_days[1]["score"])
    change_7d = float(european_by_days[7]["score"]) - tomorrow_score
    change_14d = float(european_by_days[14]["score"]) - tomorrow_score
    activity_rows, rare_rows, rating_rows, target_rows, hotspot_rows, region_rows = [], [], [], [], [], []
    european_rows, european_species_rows = [], []
    horizons = []
    for offset, (days, label) in HORIZONS_BY_OFFSET.items():
        target = first + pd.Timedelta(days=offset)
        match = probabilities.loc[probabilities["date"].eq(target)]
        if match.empty:
            raise ValueError(f"Goose forecast is missing {label} ({target.date()}).")
        row = match.iloc[0]
        condition = conditions.loc[conditions["date"].eq(target)].iloc[0]
        date_text = str(target.date())
        european_influx = european_by_days[days]
        european_influx["change_7d_points"] = round(change_7d, 1)
        european_influx["change_14d_points"] = round(change_14d, 1)
        european_rows.append({
            "date": date_text, "horizon_days": days, "label": label,
            "rare_goose_europe_index": european_influx["score"],
            "historical_percentile": european_influx["historical_percentile"],
            "historical_label": european_influx["historical_label"],
            "change_7d_points": european_influx["change_7d_points"],
            "change_14d_points": european_influx["change_14d_points"],
        })
        for item in european_influx["species_activity"]:
            european_species_rows.append({
                "date": date_text, "horizon_days": days, "label": label, **item,
            })
        probability = float(row[ACTIVITY_MODEL])
        activity_exact = min(max(probability * 100.0, 0.0), 100.0)
        raw = float(sum(row[s] * w for s, w in RARE_GOOSE_WEIGHTS.items()))
        rare_series, _ = scale_rarity_scores(pd.Series([raw]), raw_history)
        rare_exact = float(rare_series.iloc[0])
        rating_exact = RATING_WEIGHTS["activity"] * activity_exact + RATING_WEIGHTS["rare"] * rare_exact
        activity_score, rare_score, rating_score = (int(round(v)) for v in (activity_exact, rare_exact, rating_exact))
        activity_context = percentile_context(activity_exact, activity_history)
        rare_context = percentile_context(raw, raw_history)
        rating_context = percentile_context(rating_exact, rating_history)
        decision = recommendation(rating_exact, rare_exact)

        species_probabilities = {s: float(row[s]) for s in RARE_GOOSE_WEIGHTS}
        targets = sorted(
            (
                {"species": s, "probability": p, "rarity_weight": RARE_GOOSE_WEIGHTS[s],
                 "target_score": p * RARE_GOOSE_WEIGHTS[s]}
                for s, p in species_probabilities.items()
            ),
            key=lambda item: (-item["target_score"], item["species"]),
        )
        for rank, item in enumerate(targets, start=1):
            item["rank"] = rank
            target_rows.append({"date": date_text, "horizon_days": days, **item})
        hotspots, regions = build_hotspots(sites, activity_exact, rare_exact, condition)
        for _, spot in hotspots.iterrows():
            hotspot_rows.append({"date": date_text, "horizon_days": days, **spot.to_dict()})
        for _, region in regions.iterrows():
            region_rows.append({"date": date_text, "horizon_days": days, **region.to_dict()})

        activity_rows.append({
            "date": date_text, "horizon_days": days, "label": label,
            "probability": probability, "score": activity_score,
            "category": band(activity_exact, ACTIVITY_BANDS),
            "historical_percentile": activity_context["historical_percentile"],
            "historical_label": activity_context["historical_label"],
        })
        rare_rows.append({
            "date": date_text, "horizon_days": days, "label": label,
            "rarity_raw": raw, "score": rare_score, "category": band(rare_exact, RARE_BANDS),
            **{f"{s}_probability": p for s, p in species_probabilities.items()},
            "leading_species": targets[0]["species"],
            "historical_percentile": rare_context["historical_percentile"],
            "historical_label": rare_context["historical_label"],
        })
        rating_rows.append({
            "date": date_text, "horizon_days": days, "label": label,
            "score": rating_score, "rating": band(rating_exact, RATING_BANDS),
            "activity_score": activity_score, "rare_score": rare_score,
            "decision": decision["decision"], "best_region": regions.iloc[0]["region"],
            "historical_percentile": rating_context["historical_percentile"],
            "historical_label": rating_context["historical_label"],
        })
        horizons.append({
            "label": label, "forecast_day": days, "date": date_text,
            "off_season": int(target.month) not in WINTER_MONTHS,
            "goose_day_rating": {"score": rating_score, "rating": band(rating_exact, RATING_BANDS),
                                 "component_points": {"activity": round(RATING_WEIGHTS["activity"] * activity_exact, 2),
                                                      "rare": round(RATING_WEIGHTS["rare"] * rare_exact, 2)},
                                 **rating_context},
            "goose_activity": {"score": activity_score, "category": band(activity_exact, ACTIVITY_BANDS),
                               "probability": probability, **activity_context},
            "rare_goose_potential": {"score": rare_score, "category": band(rare_exact, RARE_BANDS),
                                     "rarity_raw": raw, "species_probabilities": species_probabilities,
                                     **rare_context},
            "european_goose_influx": european_influx,
            "recommendation": decision,
            "target_geese": targets,
            "best_regions": regions.to_dict(orient="records"),
            "top10_hotspots": hotspots.to_dict(orient="records"),
            "conditions": {
                "cold_outbreak": bool(condition["cold_outbreak"]),
                "rapid_temp_drop": bool(condition["rapid_temp_drop"]),
                "consecutive_frost_days": float(condition["consecutive_frost_days"]),
                "temperature_c": None if pd.isna(condition["temperature_c"]) else round(float(condition["temperature_c"]), 1),
            },
        })
    document = {
        "product": "Winter Goose Module",
        "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
        "rare_goose_weights": RARE_GOOSE_WEIGHTS,
        "rating_weights": RATING_WEIGHTS,
        "rare_scaling": {**scale, "method": "historical_raw_p5_p95_clipped_to_0_100"},
        "historical_context": {
            "method": "share of historical winter days (out-of-fold model output) with a lower score",
            "sample_size": int(len(history)),
            "labels": {"<50": "Common Conditions", "50-75": "Above Average", "75-90": "Strong",
                       "90-95": "Exceptional", "95+": "Historic"},
        },
        "model_evaluation": evaluation or [],
        "feature_importance": importance or {},
        "model_comparison": model_comparison_records(),
        "european_influx_method": (
            "Equal-weight mean of each rare species' percentile among its "
            "out-of-fold European activity probabilities; 7/14-day changes "
            "are forecast index differences from Tomorrow."
        ),
        "horizons": horizons,
    }
    frames = {
        "activity": pd.DataFrame(activity_rows),
        "rare": pd.DataFrame(rare_rows),
        "rating": pd.DataFrame(rating_rows),
        "targets": pd.DataFrame(target_rows),
        "hotspots": pd.DataFrame(hotspot_rows),
        "regions": pd.DataFrame(region_rows),
        "european_influx": pd.DataFrame(european_rows),
        "european_species_activity": pd.DataFrame(european_species_rows),
    }
    return {"frames": frames, "document": document}


def save_goose_products(products: dict[str, object], directory: Path = OUTPUTS) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    names = {
        "activity": "goose_activity_index.csv", "rare": "rare_goose_potential.csv",
        "rating": "goose_day_rating.csv", "targets": "target_geese.csv",
        "hotspots": "goose_hotspots.csv", "regions": "goose_region_ranking.csv",
        "european_influx": EUROPEAN_INDEX_OUTPUT.name,
        "european_species_activity": EUROPEAN_INFLUX_OUTPUT.name,
    }
    for key, filename in names.items():
        products["frames"][key].to_csv(directory / filename, index=False)
    (directory / "goose_module.json").write_text(
        json.dumps(products["document"], indent=2, allow_nan=False, default=float) + "\n", encoding="utf-8"
    )


def run_goose_module(
    weather: pd.DataFrame,
    predictor_dates: pd.DatetimeIndex,
    directory: Path = OUTPUTS,
) -> dict[str, object]:
    """Forecast, build and save every goose product from trained artifacts."""
    probabilities, conditions = predict_probabilities(weather, predictor_dates, load_artifacts(directory))
    site_counts = pd.read_csv(SITE_COUNTS_OUTPUT) if SITE_COUNTS_OUTPUT.is_file() else None
    products = build_goose_products(
        probabilities, conditions, load_history(), site_counts,
        evaluation_records(), top_features(),
    )
    save_goose_products(products, directory)
    return products


def main() -> None:
    if __package__:
        from .predict_yellow_browed import load_weather_forecast
    else:
        from predict_yellow_browed import load_weather_forecast
    weather, predictor_dates = load_weather_forecast(ROOT / "inputs/open_meteo_forecast_current.csv")
    products = run_goose_module(weather, predictor_dates)
    print(products["frames"]["rating"].to_string(index=False))


if __name__ == "__main__":
    main()
