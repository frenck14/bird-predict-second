"""Download shared weather and generate the flagship forecasts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

if __package__:
    from .forecast_location import (
        LOCATION_FORECAST_FILE,
        build_location_forecast,
    )
    from .forecast_atlantic_locations import (
        ATLANTIC_LOCATION_FORECAST_FILE,
        LOCATION_MAP_FILE as ATLANTIC_LOCATION_MAP,
        SIMPLE_LOCATION_FORECAST_FILE as ATLANTIC_LOCATION_CSV,
        build_atlantic_location_forecast,
        hotspot_metadata,
    )
    from .forecast_atlantic_species_locations import build_species_layers
    from .forecast_eastern_species_locations import build_eastern_species_layers
    from .birding_opportunity_index import (
        build_from_outputs as build_boi,
        load_goose as load_boi_goose,
        save_birding_opportunity_index,
    )
    from .eastern_target_species import (
        build_eastern_target_species,
        save_eastern_target_species,
    )
    from .forecast_eastern_locations import (
        EASTERN_LOCATION_FORECAST_FILE,
        LOCATION_MAP_FILE as EASTERN_LOCATION_MAP,
        SIMPLE_LOCATION_FORECAST_FILE as EASTERN_LOCATION_CSV,
        build_eastern_location_forecast,
    )
    from .forecast_seabird_locations import (
        LOCATION_MAP_FILE as SEABIRD_LOCATION_MAP,
        SIMPLE_LOCATION_FORECAST_FILE as SEABIRD_LOCATION_CSV,
        SEABIRD_LOCATION_FORECAST_FILE,
        build_seabird_location_forecast,
        best_dutch_site,
    )
    from .forecast_seabird_species import (
        SPECIES_MODEL_PATHS as SEABIRD_SPECIES_MODEL_PATHS,
        generate_species_products as generate_seabird_species_products,
        species_output_paths as seabird_species_output_paths,
    )
    from .build_seabird_dataset import load_all_occurrences as load_seabird_occurrences
    from .target_species import TARGET_SPECIES_OUTPUT, build_target_species, save_target_species
    from .goose_module import goose_models_available, run_goose_module
    from .train_seabird_model import WEATHER_FILE as SEABIRD_WEATHER_FILE
    from .historical_percentiles import (
        HISTORICAL_PERCENTILES_OUTPUT,
        apply_percentile_context,
        historical_distributions,
        save_historical_percentiles,
    )
    from .seabird_guidance import (
        COAST_RANKING_OUTPUT,
        build_recommendations,
        save_coast_ranking,
    )
    from .seawatch_day_rating import (
        HOTSPOTS_OUTPUT as SEAWATCH_HOTSPOTS_OUTPUT,
        RATING_WEIGHTS as SEAWATCH_RATING_WEIGHTS,
        RATING_JSON_OUTPUT as SEAWATCH_RATING_JSON_OUTPUT,
        RATING_OUTPUT as SEAWATCH_RATING_OUTPUT,
        build_rating_products as build_seawatch_rating,
        save_rating_products as save_seawatch_rating,
    )
    from .seabird_decision_support import (
        DECISION_SUPPORT_FILE as SEABIRD_DECISION_FILE,
        FORECAST_HISTORY_FILE as SEABIRD_HISTORY_FILE,
        build_decision_support,
        load_history,
        save_decision_support,
        update_history,
    )
    from .rarity_index import (
        RARITY_INDEX_JSON_OUTPUT,
        RARITY_INDEX_OUTPUT,
        build_from_saved_forecasts as build_rarity_index,
        save_rarity_outputs,
    )
    from .predict_eastern_vagrancy import (
        DEFAULT_MODEL as DEFAULT_EASTERN_MODEL,
        DEFAULT_OUTPUT as DEFAULT_EASTERN_OUTPUT,
        DEFAULT_PLOT as DEFAULT_EASTERN_PLOT,
        make_predictions as make_eastern_predictions,
        save_plot as save_eastern_plot,
    )
    from .predict_seabird import (
        DEFAULT_MODEL as DEFAULT_SEABIRD_MODEL,
        DEFAULT_OUTPUT as DEFAULT_SEABIRD_OUTPUT,
        DEFAULT_PLOT as DEFAULT_SEABIRD_PLOT,
        make_predictions as make_seabird_predictions,
        save_plot as save_seabird_plot,
    )
    from .download_open_meteo_forecast import (
        DEFAULT_FORECAST_FILE,
        download_open_meteo_forecast,
    )
    from .predict_yellow_browed import (
        DEFAULT_MODEL,
        DEFAULT_OUTPUT,
        DEFAULT_PLOT,
        DEFAULT_REPORT,
        build_daily_report,
        load_weather_forecast,
        make_predictions,
        save_plot,
    )
    from .predict_atlantic_vagrancy import (
        DEFAULT_MODEL as DEFAULT_ATLANTIC_MODEL,
        DEFAULT_OUTPUT as DEFAULT_ATLANTIC_OUTPUT,
        DEFAULT_PLOT as DEFAULT_ATLANTIC_PLOT,
        make_predictions as make_atlantic_predictions,
        save_plot as save_atlantic_plot,
    )
else:
    from forecast_location import (
        LOCATION_FORECAST_FILE,
        build_location_forecast,
    )
    from forecast_atlantic_locations import (
        ATLANTIC_LOCATION_FORECAST_FILE,
        LOCATION_MAP_FILE as ATLANTIC_LOCATION_MAP,
        SIMPLE_LOCATION_FORECAST_FILE as ATLANTIC_LOCATION_CSV,
        build_atlantic_location_forecast,
        hotspot_metadata,
    )
    from forecast_atlantic_species_locations import build_species_layers
    from forecast_eastern_species_locations import build_eastern_species_layers
    from birding_opportunity_index import (
        build_from_outputs as build_boi,
        load_goose as load_boi_goose,
        save_birding_opportunity_index,
    )
    from eastern_target_species import (
        build_eastern_target_species,
        save_eastern_target_species,
    )
    from forecast_eastern_locations import (
        EASTERN_LOCATION_FORECAST_FILE,
        LOCATION_MAP_FILE as EASTERN_LOCATION_MAP,
        SIMPLE_LOCATION_FORECAST_FILE as EASTERN_LOCATION_CSV,
        build_eastern_location_forecast,
    )
    from forecast_seabird_locations import (
        LOCATION_MAP_FILE as SEABIRD_LOCATION_MAP,
        SIMPLE_LOCATION_FORECAST_FILE as SEABIRD_LOCATION_CSV,
        SEABIRD_LOCATION_FORECAST_FILE,
        build_seabird_location_forecast,
        best_dutch_site,
    )
    from forecast_seabird_species import (
        SPECIES_MODEL_PATHS as SEABIRD_SPECIES_MODEL_PATHS,
        generate_species_products as generate_seabird_species_products,
        species_output_paths as seabird_species_output_paths,
    )
    from build_seabird_dataset import load_all_occurrences as load_seabird_occurrences
    from target_species import TARGET_SPECIES_OUTPUT, build_target_species, save_target_species
    from goose_module import goose_models_available, run_goose_module
    from train_seabird_model import WEATHER_FILE as SEABIRD_WEATHER_FILE
    from historical_percentiles import (
        HISTORICAL_PERCENTILES_OUTPUT,
        apply_percentile_context,
        historical_distributions,
        save_historical_percentiles,
    )
    from seabird_guidance import (
        COAST_RANKING_OUTPUT,
        build_recommendations,
        save_coast_ranking,
    )
    from seawatch_day_rating import (
        HOTSPOTS_OUTPUT as SEAWATCH_HOTSPOTS_OUTPUT,
        RATING_WEIGHTS as SEAWATCH_RATING_WEIGHTS,
        RATING_JSON_OUTPUT as SEAWATCH_RATING_JSON_OUTPUT,
        RATING_OUTPUT as SEAWATCH_RATING_OUTPUT,
        build_rating_products as build_seawatch_rating,
        save_rating_products as save_seawatch_rating,
    )
    from seabird_decision_support import (
        DECISION_SUPPORT_FILE as SEABIRD_DECISION_FILE,
        FORECAST_HISTORY_FILE as SEABIRD_HISTORY_FILE,
        build_decision_support,
        load_history,
        save_decision_support,
        update_history,
    )
    from rarity_index import (
        RARITY_INDEX_JSON_OUTPUT,
        RARITY_INDEX_OUTPUT,
        build_from_saved_forecasts as build_rarity_index,
        save_rarity_outputs,
    )
    from predict_eastern_vagrancy import (
        DEFAULT_MODEL as DEFAULT_EASTERN_MODEL,
        DEFAULT_OUTPUT as DEFAULT_EASTERN_OUTPUT,
        DEFAULT_PLOT as DEFAULT_EASTERN_PLOT,
        make_predictions as make_eastern_predictions,
        save_plot as save_eastern_plot,
    )
    from predict_seabird import (
        DEFAULT_MODEL as DEFAULT_SEABIRD_MODEL,
        DEFAULT_OUTPUT as DEFAULT_SEABIRD_OUTPUT,
        DEFAULT_PLOT as DEFAULT_SEABIRD_PLOT,
        make_predictions as make_seabird_predictions,
        save_plot as save_seabird_plot,
    )
    from download_open_meteo_forecast import (
        DEFAULT_FORECAST_FILE,
        download_open_meteo_forecast,
    )
    from predict_yellow_browed import (
        DEFAULT_MODEL,
        DEFAULT_OUTPUT,
        DEFAULT_PLOT,
        DEFAULT_REPORT,
        build_daily_report,
        load_weather_forecast,
        make_predictions,
        save_plot,
    )
    from predict_atlantic_vagrancy import (
        DEFAULT_MODEL as DEFAULT_ATLANTIC_MODEL,
        DEFAULT_OUTPUT as DEFAULT_ATLANTIC_OUTPUT,
        DEFAULT_PLOT as DEFAULT_ATLANTIC_PLOT,
        make_predictions as make_atlantic_predictions,
        save_plot as save_atlantic_plot,
    )


ROOT = Path(__file__).resolve().parents[1]
RUN_METADATA = ROOT / "outputs/yellow_browed_run.json"


def _record_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _run_goose(weather: pd.DataFrame, predictor_dates: pd.DatetimeIndex) -> dict[str, object]:
    """Winter Goose Module; skipped (not fatal) until its models are trained."""
    if not goose_models_available():
        return {
            "status": "skipped",
            "reason": "Goose models not trained. Run `python src/build_goose_dataset.py` "
            "and `python src/train_goose_models.py`.",
        }
    products = run_goose_module(weather, predictor_dates)
    rating = products["frames"]["rating"]
    first = rating.iloc[0]
    return {
        "status": "ok",
        "json": "outputs/goose_module.json",
        "generated_at": products["document"]["generated_at"],
        "tomorrow_score": int(first["score"]),
        "tomorrow_rating": str(first["rating"]),
        "tomorrow_decision": str(first["decision"]),
        "tomorrow_best_region": str(first["best_region"]),
        "horizons": [
            {"date": row.date, "score": int(row.score), "rating": row.rating, "decision": row.decision}
            for row in rating.itertuples()
        ],
    }


def run_daily_forecast() -> dict[str, object]:
    if not DEFAULT_MODEL.is_file():
        raise FileNotFoundError(
            f"Production model not found: {DEFAULT_MODEL}. "
            "Train or deploy the Yellow-browed Warbler model first."
        )
    if not DEFAULT_ATLANTIC_MODEL.is_file():
        raise FileNotFoundError(
            f"Production model not found: {DEFAULT_ATLANTIC_MODEL}. "
            "Build the Atlantic Vagrancy dataset and run "
            "`python src/train_atlantic_vagrancy_model.py` first."
        )
    if not DEFAULT_EASTERN_MODEL.is_file():
        raise FileNotFoundError(
            f"Production model not found: {DEFAULT_EASTERN_MODEL}. "
            "Build the Eastern Vagrancy dataset and run "
            "`python src/train_eastern_vagrancy_model.py` first."
        )
    if not DEFAULT_SEABIRD_MODEL.is_file():
        raise FileNotFoundError(
            f"Production model not found: {DEFAULT_SEABIRD_MODEL}. "
            "Build the Seabird dataset and run "
            "`python src/train_seabird_model.py` first."
        )
    missing_species_models = [
        str(path) for path in SEABIRD_SPECIES_MODEL_PATHS.values() if not path.is_file()
    ]
    if missing_species_models:
        raise FileNotFoundError(
            "Seabird species models are missing: "
            + ", ".join(missing_species_models)
            + ". Build the Seabird dataset and run "
            "`python src/train_seabird_species_models.py` first."
        )

    downloaded = download_open_meteo_forecast(DEFAULT_FORECAST_FILE)
    artifact = joblib.load(DEFAULT_MODEL)
    if artifact.get("species") != "Yellow-browed Warbler":
        raise ValueError(
            "Configured production model artifact is not for "
            "Yellow-browed Warbler."
        )
    atlantic_artifact = joblib.load(DEFAULT_ATLANTIC_MODEL)
    if atlantic_artifact.get("species") != "Atlantic Vagrancy Index":
        raise ValueError(
            "Configured production model artifact is not for the "
            "Atlantic Vagrancy Index."
        )
    eastern_artifact = joblib.load(DEFAULT_EASTERN_MODEL)
    if eastern_artifact.get("species") != "Eastern Vagrancy Index":
        raise ValueError(
            "Configured production model artifact is not for the "
            "Eastern Vagrancy Index."
        )
    seabird_artifact = joblib.load(DEFAULT_SEABIRD_MODEL)
    if seabird_artifact.get("species") != "Seabird Index":
        raise ValueError(
            "Configured production model artifact is not for the "
            "Seabird Index."
        )

    weather, predictor_dates = load_weather_forecast(downloaded.path)
    seabird_occurrences = load_seabird_occurrences()
    predictions = make_predictions(weather, predictor_dates, artifact)
    atlantic_predictions = make_atlantic_predictions(
        weather, predictor_dates, atlantic_artifact
    )
    eastern_predictions = make_eastern_predictions(
        weather, predictor_dates, eastern_artifact
    )
    seabird_predictions = make_seabird_predictions(
        weather, predictor_dates, seabird_artifact
    )
    DEFAULT_EASTERN_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    eastern_predictions.to_csv(
        DEFAULT_EASTERN_OUTPUT, index=False, date_format="%Y-%m-%d"
    )
    DEFAULT_SEABIRD_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    seabird_predictions.to_csv(
        DEFAULT_SEABIRD_OUTPUT, index=False, date_format="%Y-%m-%d"
    )
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(
        DEFAULT_OUTPUT, index=False, date_format="%Y-%m-%d"
    )
    DEFAULT_ATLANTIC_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    atlantic_predictions.to_csv(
        DEFAULT_ATLANTIC_OUTPUT,
        index=False,
        date_format="%Y-%m-%d",
    )
    location_predictions = build_location_forecast(predictions, artifact)
    atlantic_locations = build_atlantic_location_forecast(
        atlantic_predictions,
        simple_output_path=ATLANTIC_LOCATION_CSV,
        map_path=ATLANTIC_LOCATION_MAP,
    )
    eastern_locations = build_eastern_location_forecast(
        eastern_predictions,
        simple_output_path=EASTERN_LOCATION_CSV,
        map_path=EASTERN_LOCATION_MAP,
    )
    seabird_locations = build_seabird_location_forecast(
        seabird_predictions,
        simple_output_path=SEABIRD_LOCATION_CSV,
        map_path=SEABIRD_LOCATION_MAP,
        weather=weather,
        occurrences=seabird_occurrences,
    )
    seabird_species_forecasts = generate_seabird_species_products(
        weather,
        predictor_dates,
        seabird_occurrences,
    )
    rarity_index, rarity_document = build_rarity_index()
    seawatch_species = set(SEAWATCH_RATING_WEIGHTS) - {"General Seabird Index"}
    seabird_species_location_details = {
        species: pd.read_csv(
            seabird_species_output_paths(species)["detail"], parse_dates=["date"]
        )
        for species in seawatch_species
    }
    seawatch_rating, seawatch_hotspots, seawatch_rating_document = (
        build_seawatch_rating(
            seabird_predictions,
            {
                species: seabird_species_forecasts[species]
                for species in seawatch_species
            },
            seabird_locations,
            seabird_species_location_details,
            weather,
        )
    )
    seawatch_history, rarity_history = historical_distributions(
        pd.read_csv(SEABIRD_WEATHER_FILE, parse_dates=["date"])
    )
    historical_percentiles = apply_percentile_context(
        seawatch_rating_document, rarity_document, seawatch_history, rarity_history
    )
    save_historical_percentiles(historical_percentiles, HISTORICAL_PERCENTILES_OUTPUT)
    save_rarity_outputs(rarity_index, rarity_document)
    save_seawatch_rating(
        seawatch_rating,
        seawatch_hotspots,
        seawatch_rating_document,
        rating_path=SEAWATCH_RATING_OUTPUT,
        hotspots_path=SEAWATCH_HOTSPOTS_OUTPUT,
        json_path=SEAWATCH_RATING_JSON_OUTPUT,
    )
    save_coast_ranking(seawatch_rating_document["horizons"])
    target_species = build_target_species(rarity_document)
    save_target_species(target_species, TARGET_SPECIES_OUTPUT)
    seabird_recommendations = build_recommendations(
        seawatch_rating_document, rarity_document
    )
    save_decision_support(
        build_decision_support(
            seabird_predictions,
            seabird_locations,
            weather,
            load_history(SEABIRD_HISTORY_FILE),
        ),
        SEABIRD_DECISION_FILE,
    )
    update_history(seabird_predictions, SEABIRD_HISTORY_FILE)
    goose_metadata = _run_goose(weather, predictor_dates)
    species_layers = build_species_layers(atlantic_predictions)
    eastern_species_layers = build_eastern_species_layers(eastern_predictions)
    save_eastern_target_species(
        build_eastern_target_species(eastern_predictions, eastern_artifact)
    )
    boi_goose, boi_goose_history = (
        load_boi_goose() if goose_metadata.get("status") == "ok" else (None, None)
    )
    boi_frame, boi_document = build_boi(
        boi_goose, boi_goose_history, seawatch_history
    )
    save_birding_opportunity_index(boi_frame, boi_document)
    save_plot(predictions, DEFAULT_PLOT)
    save_atlantic_plot(atlantic_predictions, DEFAULT_ATLANTIC_PLOT)
    save_eastern_plot(eastern_predictions, DEFAULT_EASTERN_PLOT)
    save_seabird_plot(seabird_predictions, DEFAULT_SEABIRD_PLOT)
    report = build_daily_report(
        predictions,
        artifact,
        DEFAULT_PLOT,
        weather_source=downloaded.source_description,
    )
    DEFAULT_REPORT.write_text(report, encoding="utf-8")
    seabird_hotspots = hotspot_metadata(seabird_locations)

    metadata: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "species": artifact["species"],
        "model_name": artifact["model_name"],
        "weather_source": downloaded.source_description,
        "input_forecast_file": _record_path(downloaded.path),
        "forecast_csv": _record_path(DEFAULT_OUTPUT),
        "location_forecast_csv": _record_path(LOCATION_FORECAST_FILE),
        "forecast_plot": _record_path(DEFAULT_PLOT),
        "daily_report": _record_path(DEFAULT_REPORT),
        "forecast_start": str(predictions["date"].min().date()),
        "forecast_end": str(predictions["date"].max().date()),
        "mean_probability": float(predictions["probability"].mean()),
        "location_cells": int(
            location_predictions["cell_id"].nunique()
        ),
        "atlantic_vagrancy": {
            "product": atlantic_artifact["species"],
            "model_name": atlantic_artifact["model_name"],
            "model_species": [
                row["species"]
                for row in atlantic_artifact.get("target_species", [])
            ],
            "forecast_csv": _record_path(DEFAULT_ATLANTIC_OUTPUT),
            "forecast_plot": _record_path(DEFAULT_ATLANTIC_PLOT),
            "forecast_start": str(atlantic_predictions["date"].min().date()),
            "forecast_end": str(atlantic_predictions["date"].max().date()),
            "mean_probability": float(atlantic_predictions["probability"].mean()),
            "location_forecast_csv": _record_path(
                ATLANTIC_LOCATION_FORECAST_FILE
            ),
            "location_cells": int(atlantic_locations["cell_id"].nunique()),
            "location_forecast_simple_csv": _record_path(ATLANTIC_LOCATION_CSV),
            "location_forecast_map": _record_path(ATLANTIC_LOCATION_MAP),
            "species_layers": species_layers.to_dict(orient="records"),
        },
        "seabird_index": {
            "product": seabird_artifact["species"],
            "model_name": seabird_artifact["model_name"],
            "model_species": [
                row["species"] for row in seabird_artifact.get("target_species", [])
            ],
            "forecast_csv": _record_path(DEFAULT_SEABIRD_OUTPUT),
            "forecast_plot": _record_path(DEFAULT_SEABIRD_PLOT),
            "forecast_start": str(seabird_predictions["date"].min().date()),
            "forecast_end": str(seabird_predictions["date"].max().date()),
            "mean_probability": float(seabird_predictions["probability"].mean()),
            "strongest_location": seabird_hotspots["strongest_location"],
            "strongest_probability": seabird_hotspots["strongest_probability"],
            "top10_locations": seabird_hotspots["top10_locations"],
            "generated_at": seabird_hotspots["generated_at"],
            "location_forecast_csv": _record_path(SEABIRD_LOCATION_CSV),
            "location_forecast_detail_csv": _record_path(
                SEABIRD_LOCATION_FORECAST_FILE
            ),
            "location_forecast_simple_csv": _record_path(SEABIRD_LOCATION_CSV),
            "location_cells": int(seabird_locations["cell_id"].nunique()),
            "location_forecast_map": _record_path(SEABIRD_LOCATION_MAP),
            "decision_support_json": _record_path(SEABIRD_DECISION_FILE),
        },
        "seabird_species": {
            species: {
                "forecast_csv": _record_path(
                    seabird_species_output_paths(species)["forecast"]
                ),
                "location_forecast_csv": _record_path(
                    seabird_species_output_paths(species)["location"]
                ),
                "hotspots_csv": _record_path(
                    seabird_species_output_paths(species)["hotspots"]
                ),
                "map": _record_path(seabird_species_output_paths(species)["map"]),
                "forecast_start": str(
                    seabird_species_forecasts[species]["date"].min().date()
                ),
                "forecast_end": str(
                    seabird_species_forecasts[species]["date"].max().date()
                ),
                "mean_probability": float(
                    seabird_species_forecasts[species]["probability"].mean()
                ),
            }
            for species in seabird_species_forecasts
        },
        "rarity_index": {
            "csv": _record_path(RARITY_INDEX_OUTPUT),
            "json": _record_path(RARITY_INDEX_JSON_OUTPUT),
            "generated_at": rarity_document["generated_at"],
            "tomorrow_score": float(rarity_index.iloc[0]["rarity_index"]),
            "tomorrow_leading_species": str(
                rarity_index.iloc[0]["leading_rarity_species"]
            ),
            "horizons": [
                {
                    "date": horizon["date"],
                    "rarity_index": horizon["rarity_index"],
                    "leading_rarity_species": horizon["leading_rarity_species"],
                }
                for horizon in rarity_document["horizons"]
            ],
        },
        "seawatch_day_rating": {
            "rating_csv": _record_path(SEAWATCH_RATING_OUTPUT),
            "hotspots_csv": _record_path(SEAWATCH_HOTSPOTS_OUTPUT),
            "rating_json": _record_path(SEAWATCH_RATING_JSON_OUTPUT),
            "generated_at": seawatch_rating_document["generated_at"],
            "tomorrow_score": int(seawatch_rating.iloc[0]["score"]),
            "tomorrow_rating": str(seawatch_rating.iloc[0]["rating"]),
            "tomorrow_best_coast": str(seawatch_rating.iloc[0]["best_coast"]),
            "coast_ranking_csv": _record_path(COAST_RANKING_OUTPUT),
            "historical_percentiles_csv": _record_path(HISTORICAL_PERCENTILES_OUTPUT),
            "historical_percentiles": [
                {
                    "date": horizon["date"],
                    "seawatch_percentile": horizon["historical_percentile"],
                    "seawatch_label": horizon["historical_label"],
                    "rarity_percentile": rarity["historical_percentile"],
                    "rarity_label": rarity["historical_label"],
                }
                for horizon, rarity in zip(
                    seawatch_rating_document["horizons"], rarity_document["horizons"]
                )
            ],
            "target_species_csv": _record_path(TARGET_SPECIES_OUTPUT),
            "tomorrow_target_species": str(
                target_species.loc[target_species["horizon_days"].eq(1)].iloc[0]["species"]
            ),
            "recommendation": seabird_recommendations[0]["decision"],
            "recommendations": [
                {
                    "date": item["date"],
                    "decision": item["decision"],
                    "best_coast": item["best_coast"],
                    "best_site": item["best_site"],
                }
                for item in seabird_recommendations
            ],
            "horizons": [
                {
                    "date": horizon["date"],
                    "score": horizon["score"],
                    "rating": horizon["rating"],
                    "best_coast": horizon["best_coast"]["coast"],
                }
                for horizon in seawatch_rating_document["horizons"]
            ],
        },
    }
    metadata["eastern_vagrancy"] = {
        "product": eastern_artifact["species"],
        "model_name": eastern_artifact["model_name"],
        "model_species": [
            row["species"] for row in eastern_artifact.get("target_species", [])
        ],
        "forecast_csv": _record_path(DEFAULT_EASTERN_OUTPUT),
        "forecast_plot": _record_path(DEFAULT_EASTERN_PLOT),
        "forecast_start": str(eastern_predictions["date"].min().date()),
        "forecast_end": str(eastern_predictions["date"].max().date()),
        "mean_probability": float(eastern_predictions["probability"].mean()),
        "location_forecast_csv": _record_path(EASTERN_LOCATION_FORECAST_FILE),
        "location_cells": int(eastern_locations["cell_id"].nunique()),
        "location_forecast_simple_csv": _record_path(EASTERN_LOCATION_CSV),
        "location_forecast_map": _record_path(EASTERN_LOCATION_MAP),
    }
    metadata["eastern_hotspots"] = hotspot_metadata(eastern_locations)
    metadata["eastern_hotspots"]["species_layers"] = eastern_species_layers.to_dict(
        orient="records"
    )
    metadata["atlantic_hotspots"] = hotspot_metadata(atlantic_locations)
    metadata["seabird_hotspots"] = {
        **seabird_hotspots,
        "best_dutch_site": best_dutch_site(seabird_locations, weather),
    }
    metadata["goose_module"] = goose_metadata
    metadata["birding_opportunity_index"] = {
        "csv": "outputs/birding_opportunity_index.csv",
        "json": "outputs/birding_opportunity_index.json",
        "tomorrow_score": float(boi_frame.iloc[0]["boi_score"]),
        "tomorrow_category": str(boi_frame.iloc[0]["rating_category"]),
    }
    RUN_METADATA.write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> None:
    metadata = run_daily_forecast()
    print(
        f"Generated {metadata['species']} forecast "
        f"{metadata['forecast_start']} to {metadata['forecast_end']}."
    )
    print(f"Weather source: {metadata['weather_source']}")
    print(f"Report: {metadata['daily_report']}")
    eastern = metadata["eastern_vagrancy"]
    print(
        f"Generated Eastern Vagrancy Index forecast "
        f"{eastern['forecast_start']} to {eastern['forecast_end']}."
    )
    atlantic = metadata["atlantic_vagrancy"]
    print(
        f"Generated Atlantic Vagrancy Index forecast "
        f"{atlantic['forecast_start']} to {atlantic['forecast_end']}."
    )
    seabird = metadata["seabird_index"]
    print(
        f"Generated Seabird Index forecast "
        f"{seabird['forecast_start']} to {seabird['forecast_end']}."
    )


if __name__ == "__main__":
    main()
