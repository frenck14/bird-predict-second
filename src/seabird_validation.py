"""Point-in-time validation for historical Seabird forecasts."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

if __package__:
    from .build_seabird_dataset import SEABIRD_SPECIES
    from .forecast_seabird_locations import (
        build_seabird_location_forecast,
        _build_seabird_features,
    )
    from .forecast_seabird_species import (
        SPECIES_NAMES,
        build_species_location_forecast,
    )
    from .predict_seabird import risk_level
    from .forecast_species_comparison import make_estimator, weather_feature_columns
    from .seawatch_day_rating import RATING_WEIGHTS, build_rating_products
    from .seabird_backtest import load_cached_occurrences, load_historical_weather
    from .train_atlantic_vagrancy_model import influx_cutoff
    from .predict_yellow_browed import add_target_calendar
else:
    from build_seabird_dataset import SEABIRD_SPECIES
    from forecast_seabird_locations import (
        _build_seabird_features,
        build_seabird_location_forecast,
    )
    from forecast_seabird_species import (
        SPECIES_NAMES,
        build_species_location_forecast,
    )
    from predict_seabird import risk_level
    from forecast_species_comparison import make_estimator, weather_feature_columns
    from seawatch_day_rating import RATING_WEIGHTS, build_rating_products
    from seabird_backtest import load_cached_occurrences, load_historical_weather
    from train_atlantic_vagrancy_model import influx_cutoff
    from predict_yellow_browed import add_target_calendar


FORECAST_TARGETS = ("General Seabird Index", *SPECIES_NAMES)
STRICT_VALIDATION_HOLDOUT_WINDOWS = (1, 3, 7, 14)
RATING_SPECIES = tuple(
    species for species in RATING_WEIGHTS if species != "General Seabird Index"
)


class DataLeakageError(ValueError):
    """Raised when a validation input includes records beyond its cutoff."""


class StrictValidationUnavailable(ValueError):
    """Raised when cutoff-available data cannot support a strict validation."""


def filter_to_cutoff_date(
    records: pd.DataFrame,
    data_cutoff_date: date,
    *,
    date_column: str = "date",
) -> pd.DataFrame:
    if date_column not in records:
        raise ValueError(f"Validation records are missing {date_column!r}.")
    result = records.copy()
    dates = pd.to_datetime(result[date_column], errors="raise")
    if dates.isna().any():
        raise ValueError(f"Validation records contain invalid {date_column} values.")
    cutoff = pd.Timestamp(data_cutoff_date)
    result[date_column] = dates
    return result.loc[dates.dt.normalize().le(cutoff)].copy().reset_index(drop=True)


def check_data_leakage(
    sources: dict[str, pd.DataFrame],
    artifacts: dict[str, dict[str, object]],
    data_cutoff_date: date,
) -> None:
    cutoff = pd.Timestamp(data_cutoff_date)
    for source_name, frame in sources.items():
        if frame.empty:
            continue
        date_columns = [
            column for column in ("record_date", "date") if column in frame
        ]
        if not date_columns:
            raise ValueError(
                f"Cannot verify the {source_name} cutoff: no date column is present."
            )
        for date_column in date_columns:
            dates = pd.to_datetime(frame[date_column], errors="raise")
            future = dates.dt.normalize().gt(cutoff)
            if future.any():
                first = dates.loc[future].min().date()
                raise DataLeakageError(
                    f"Strict historical validation stopped: {source_name} "
                    f"{date_column} contains records dated {first}, after "
                    f"data_cutoff_date {data_cutoff_date:%Y-%m-%d}."
                )

    for artifact_name, artifact in artifacts.items():
        for field in ("trained_through_weather_date", "training_end_date", "generated_at"):
            value = artifact.get(field)
            if value is None:
                continue
            timestamp = pd.Timestamp(value)
            if timestamp.date() > data_cutoff_date:
                raise DataLeakageError(
                    f"Strict historical validation stopped: {artifact_name} "
                    f"{field} is {timestamp.date()}, after data_cutoff_date "
                    f"{data_cutoff_date:%Y-%m-%d}."
                )


def load_historical_inputs(
    data_cutoff_date: date,
) -> dict[str, pd.DataFrame | date]:
    weather = filter_to_cutoff_date(load_historical_weather(), data_cutoff_date)
    occurrences = filter_to_cutoff_date(
        load_cached_occurrences(), data_cutoff_date
    )
    check_data_leakage(
        {
            "weather records": weather,
            "occurrence records": occurrences,
            "hotspot history records": occurrences,
        },
        {},
        data_cutoff_date,
    )
    return {
        "analysis_date": data_cutoff_date,
        "data_cutoff_date": data_cutoff_date,
        "weather": weather,
        "occurrences": occurrences,
    }


def _daily_counts(
    occurrences: pd.DataFrame, species: str | None = None
) -> pd.DataFrame:
    selected = occurrences
    if species is not None:
        selected = selected.loc[selected["species"].eq(species)]
    if selected.empty:
        return pd.DataFrame(columns=["date", "count"])
    return (
        selected.groupby(pd.to_datetime(selected["date"]).dt.normalize())
        .size()
        .rename("count")
        .rename_axis("date")
        .reset_index()
    )


def _fit_cutoff_model(
    weather: pd.DataFrame,
    occurrences: pd.DataFrame,
    cutoff: date,
    species: str | None,
    horizon_days: int,
    *,
    engineered_weather: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Fit one lead using only matching pre-cutoff weather and target rows."""
    check_data_leakage(
        {"weather records": weather, "occurrence records": occurrences},
        {},
        cutoff,
    )
    features = (
        engineered_weather.copy()
        if engineered_weather is not None
        else _build_seabird_features(weather)
    )
    counts = _daily_counts(occurrences, species)
    data = features.merge(counts, on="date", how="left", validate="one_to_one")
    data["count"] = data["count"].fillna(0).astype(int)
    weather_columns = weather_feature_columns(data)
    target_dates = pd.DatetimeIndex(data["date"])
    calendar_features = list(
        add_target_calendar(pd.DatetimeIndex([pd.Timestamp(cutoff)])).columns
    )
    feature_columns = [*calendar_features, *weather_columns]
    supervised = pd.concat(
        [
            data["date"].rename("target_date"),
            data["date"].shift(horizon_days).rename("origin_date"),
            data["count"].rename("target"),
            data[weather_columns].shift(horizon_days),
            add_target_calendar(target_dates),
        ],
        axis=1,
    )
    supervised = filter_to_cutoff_date(
        supervised, cutoff, date_column="target_date"
    )
    supervised = supervised.loc[supervised["origin_date"].notna()].reset_index(
        drop=True
    )
    if supervised.empty:
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            f"No {horizon_days}-day training examples are available through "
            f"{cutoff:%Y-%m-%d}."
        )
    threshold = influx_cutoff(supervised["target"], 90)
    labels = supervised["target"].ge(threshold).astype(int)
    positives = int(labels.sum())
    negatives = len(labels) - positives
    if not positives or not negatives:
        label = "General Seabird Index" if species is None else species
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            f"{label} has only one training class by {cutoff:%Y-%m-%d} "
            f"for the {horizon_days}-day horizon."
        )
    model = make_estimator(
        "Random Forest",
        positives,
        negatives,
        random_forest_class_weight=None,
    )
    model.fit(supervised[feature_columns], labels)
    return {
        "model": model,
        "feature_columns": feature_columns,
        "weather_feature_columns": weather_columns,
        "species": "Seabird Index" if species is None else species,
        "influx_threshold_count": threshold,
        "influx_percentile": 90,
        "training_rows": len(supervised),
        "training_positive_days": positives,
        "training_start_date": str(supervised["target_date"].min().date()),
        "training_end_date": str(supervised["target_date"].max().date()),
        "trained_through_weather_date": str(
            supervised["origin_date"].max().date()
        ),
        "horizon_days": horizon_days,
        "generated_at": datetime.combine(
            cutoff, time.min, tzinfo=timezone.utc
        ).isoformat(),
    }


def _predict_from_cutoff(
    weather: pd.DataFrame,
    cutoff: date,
    target_date: date,
    artifact: dict[str, object],
    *,
    engineered_weather: pd.DataFrame | None = None,
) -> float:
    """Predict from the frozen weather snapshot available on the cutoff date."""
    cutoff_timestamp = pd.Timestamp(cutoff)
    weather_dates = pd.to_datetime(weather["date"], errors="raise").dt.normalize()
    if weather_dates.gt(cutoff_timestamp).any():
        raise DataLeakageError(
            "Strict historical validation stopped: weather inputs contain "
            "records after analysis_date."
        )
    engineered = (
        engineered_weather
        if engineered_weather is not None
        else _build_seabird_features(weather)
    )
    selected = engineered.loc[
        pd.to_datetime(engineered["date"]).dt.normalize().eq(cutoff_timestamp)
    ]
    if selected.empty:
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            "The same-day weather features cannot be reconstructed."
        )
    feature_columns = artifact["feature_columns"]
    weather_columns = artifact["weather_feature_columns"]
    if not isinstance(feature_columns, list) or not isinstance(weather_columns, list):
        raise TypeError("Cutoff model artifact has an invalid feature schema.")
    missing_features = set(weather_columns).difference(selected.columns)
    if missing_features:
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            f"Same-day weather features are missing: {sorted(missing_features)}."
        )
    calendar = add_target_calendar(pd.DatetimeIndex([pd.Timestamp(target_date)]))
    inputs = pd.concat(
        [
            calendar.reset_index(drop=True),
            selected.loc[:, weather_columns].reset_index(drop=True),
        ],
        axis=1,
    )
    missing_model_features = set(feature_columns).difference(inputs.columns)
    if missing_model_features:
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            f"Model inputs cannot be reconstructed: {sorted(missing_model_features)}."
        )
    model = artifact["model"]
    probability = float(model.predict_proba(inputs[feature_columns])[0, 1])
    if not np.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Cutoff model produced an invalid forecast probability.")
    return probability


def build_historical_forecast(
    analysis_date: date,
    data_cutoff_date: date | None = None,
    inputs: dict[str, pd.DataFrame | date] | None = None,
    holdout_days: int = 1,
) -> dict[str, object]:
    """Build cutoff-safe, lead-specific hindcasts for a selected holdout window."""
    if holdout_days not in STRICT_VALIDATION_HOLDOUT_WINDOWS:
        raise ValueError(
            "Holdout window must be one of "
            f"{STRICT_VALIDATION_HOLDOUT_WINDOWS} days."
        )
    data_cutoff_date = data_cutoff_date or analysis_date
    if analysis_date != data_cutoff_date:
        raise ValueError(
            "Strict cutoff validation requires analysis_date == data_cutoff_date."
        )
    inputs = inputs or load_historical_inputs(data_cutoff_date)
    weather = inputs["weather"]
    occurrences = inputs["occurrences"]
    if not isinstance(weather, pd.DataFrame) or not isinstance(occurrences, pd.DataFrame):
        raise TypeError("Historical inputs must include weather and occurrence frames.")
    check_data_leakage(
        {
            "weather records": weather,
            "occurrence records": occurrences,
            "hotspot history records": occurrences,
        },
        {},
        data_cutoff_date,
    )
    if "date" not in weather:
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            "Cutoff weather records have no date field."
        )
    if not {"date", "species"}.issubset(occurrences.columns):
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            "Cutoff occurrence records are missing required fields."
        )
    weather = weather.copy()
    weather["date"] = pd.to_datetime(weather["date"], errors="raise").dt.normalize()
    if weather.empty:
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            "No cutoff weather records are available."
        )
    if weather["date"].isna().any() or weather["date"].duplicated().any():
        raise ValueError("Cutoff weather must contain unique valid daily dates.")
    weather = weather.sort_values("date").reset_index(drop=True)
    engineered_weather = _build_seabird_features(weather)
    occurrences = occurrences.copy()
    occurrences["date"] = pd.to_datetime(
        occurrences["date"], errors="raise"
    ).dt.normalize()
    target_dates = [
        (pd.Timestamp(analysis_date) + pd.Timedelta(days=offset)).date()
        for offset in range(1, holdout_days + 1)
    ]
    if not pd.to_datetime(weather["date"]).dt.normalize().eq(
        pd.Timestamp(analysis_date)
    ).any():
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            "Same-day weather features are not present."
        )
    products: dict[str, pd.DataFrame] = {}
    artifacts: dict[str, dict[str, object]] = {}
    horizon_artifacts: dict[str, dict[int, dict[str, object]]] = {}
    for product in FORECAST_TARGETS:
        species = None if product == "General Seabird Index" else product
        product_rows = []
        product_horizon_artifacts: dict[int, dict[str, object]] = {}
        for horizon_days, target_date in enumerate(target_dates, start=1):
            artifact = _fit_cutoff_model(
                weather,
                occurrences,
                data_cutoff_date,
                species,
                horizon_days,
                engineered_weather=engineered_weather,
            )
            check_data_leakage(
                {},
                {f"{product} (+{horizon_days}d)": artifact},
                data_cutoff_date,
            )
            probability = _predict_from_cutoff(
                weather,
                analysis_date,
                target_date,
                artifact,
                engineered_weather=engineered_weather,
            )
            product_rows.append(
                {
                    "date": pd.Timestamp(target_date),
                    "probability": probability,
                    "risk_level": risk_level(probability),
                    "horizon_days": horizon_days,
                    "event_threshold_count": float(
                        artifact["influx_threshold_count"]
                    ),
                }
            )
            product_horizon_artifacts[horizon_days] = artifact
        products[product] = pd.DataFrame(product_rows)
        artifacts[product] = product_horizon_artifacts[1]
        horizon_artifacts[product] = product_horizon_artifacts

    general_counts = _daily_counts(occurrences)
    with TemporaryDirectory(prefix="seabird-validation-") as directory:
        output_directory = Path(directory)
        general_counts_path = output_directory / "general_counts.csv"
        general_counts.to_csv(general_counts_path, index=False)
        species_counts_path = output_directory / "species_counts.csv"
        species_count_frames = [
            _daily_counts(occurrences, species).assign(species=species)
            for species in SPECIES_NAMES
        ]
        pd.concat(species_count_frames, ignore_index=True).to_csv(
            species_counts_path, index=False
        )
        locations = build_seabird_location_forecast(
            products["General Seabird Index"],
            analysis_date=analysis_date,
            output_path=output_directory / "general_locations.csv",
            daily_counts_path=general_counts_path,
            weather=weather,
            occurrences=occurrences,
        )
        species_locations = {}
        for species in SPECIES_NAMES:
            detail, _ = build_species_location_forecast(
                species,
                occurrences,
                products[species],
                daily_counts_path=species_counts_path,
                output_directory=output_directory,
                analysis_date=analysis_date,
            )
            species_locations[species] = detail
        rating_species_locations = {
            species: species_locations[species] for species in RATING_SPECIES
        }
        rating, hotspots, rating_document = build_rating_products(
            products["General Seabird Index"],
            {
                species: products[species]
                for species in RATING_SPECIES
            },
            locations,
            rating_species_locations,
            weather,
            analysis_date=analysis_date,
        )

    species_table = pd.concat(
        [
            frame.assign(species=species)
            for species, frame in products.items()
            if species != "General Seabird Index"
        ],
        ignore_index=True,
    )
    return {
        "analysis_date": analysis_date,
        "data_cutoff_date": data_cutoff_date,
        "target_date": target_dates[0],
        "target_dates": target_dates,
        "holdout_days": holdout_days,
        "forecasts": products,
        "species": species_table,
        "locations": locations,
        "species_locations": species_locations,
        "rating": rating,
        "hotspots": hotspots,
        "rating_document": rating_document,
        "artifacts": artifacts,
        "horizon_artifacts": horizon_artifacts,
    }


def calculate_validation_metrics(
    forecast: pd.DataFrame,
    observations: pd.DataFrame,
    thresholds: dict[str, float],
    *,
    probability_threshold: float = 0.20,
) -> pd.DataFrame:
    required_forecast = {"product", "probability"}
    required_observations = {"product", "count"}
    if not required_forecast.issubset(forecast.columns):
        raise ValueError("Forecast metrics input must contain product and probability.")
    if not required_observations.issubset(observations.columns):
        raise ValueError("Validation observations must contain product and count.")
    join_columns = ["product"]
    if "date" in forecast.columns or "date" in observations.columns:
        if "date" not in forecast.columns or "date" not in observations.columns:
            raise ValueError("Forecasts and observations must both include date.")
        join_columns.append("date")
    joined = forecast.merge(
        observations,
        on=join_columns,
        how="left",
        validate="one_to_one",
        suffixes=("", "_observation"),
    )
    if joined["count"].isna().any():
        missing = joined.loc[
            joined["count"].isna(), join_columns
        ].to_dict(orient="records")
        raise ValueError(f"Validation observations are missing forecast rows: {missing}")
    rows = []
    for row in joined.itertuples(index=False):
        if row.product not in thresholds:
            if "event_threshold_count" not in joined.columns:
                raise ValueError(
                    f"No training cutoff is available for {row.product}."
                )
        probability = float(row.probability)
        if not np.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError(f"Invalid forecast probability for {row.product}.")
        threshold = (
            float(row.event_threshold_count)
            if "event_threshold_count" in joined.columns
            else thresholds[row.product]
        )
        actual = int(float(row.count) >= threshold)
        predicted = int(probability >= probability_threshold)
        true_positive = int(predicted == 1 and actual == 1)
        false_positive = int(predicted == 1 and actual == 0)
        true_negative = int(predicted == 0 and actual == 0)
        false_negative = int(predicted == 0 and actual == 1)
        rows.append(
            {
                "product": row.product,
                **({"date": row.date} if "date" in joined.columns else {}),
                "probability": probability,
                "observed_count": int(row.count),
                "event_threshold_count": threshold,
                "actual_event": actual,
                "predicted_event": predicted,
                "brier_score": (probability - actual) ** 2,
                "log_loss": -np.log(
                    np.clip(
                        probability if actual else 1 - probability,
                        1e-15,
                        1,
                    )
                ),
                "correct": int(predicted == actual),
                "true_positive": true_positive,
                "false_positive": false_positive,
                "true_negative": true_negative,
                "false_negative": false_negative,
                "precision": (
                    true_positive / (true_positive + false_positive)
                    if true_positive + false_positive
                    else 0.0
                ),
                "recall": (
                    true_positive / (true_positive + false_negative)
                    if true_positive + false_negative
                    else 0.0
                ),
            }
        )
    return pd.DataFrame(rows)


def evaluate_forecast(
    result: dict[str, object],
    observations: pd.DataFrame,
    *,
    data_cutoff_date: date,
) -> pd.DataFrame:
    if result.get("analysis_date") != data_cutoff_date:
        raise ValueError("Evaluation cutoff must match the forecast analysis date.")
    holdout_days = int(result.get("holdout_days", 1))
    expected_dates = pd.date_range(
        pd.Timestamp(data_cutoff_date) + pd.Timedelta(days=1),
        periods=holdout_days,
        freq="D",
    )
    target_dates = pd.DatetimeIndex(
        pd.to_datetime(result.get("target_dates", [result["target_date"]]))
    ).normalize()
    if not target_dates.equals(expected_dates):
        raise ValueError(
            "Evaluation targets must be the consecutive dates after the cutoff."
        )
    if pd.Timestamp(result["target_date"]) != expected_dates[0]:
        raise ValueError("Evaluation target must begin the day after the cutoff.")
    if "date" not in observations:
        raise ValueError(
            "Holdout observations must include their observation date."
        )
    observation_dates = pd.to_datetime(observations["date"], errors="raise").dt.normalize()
    if not observation_dates.isin(expected_dates).all():
        message = (
            "Evaluation observations must be limited to the day after the cutoff."
            if holdout_days == 1
            else "Evaluation observations must be limited to the selected holdout window."
        )
        raise ValueError(message)
    forecast_frames = result["forecasts"]
    if not isinstance(forecast_frames, dict):
        raise TypeError("Historical forecast result has an invalid forecasts payload.")
    forecast_rows = []
    for product, frame in forecast_frames.items():
        if not {"date", "probability"}.issubset(frame.columns):
            raise ValueError(
                f"Forecast rows for {product} must contain date and probability."
            )
        forecast_rows.extend(
            {
                "product": product,
                "date": pd.Timestamp(row.date).normalize(),
                "probability": float(row.probability),
                **(
                    {"event_threshold_count": float(row.event_threshold_count)}
                    if "event_threshold_count" in frame.columns
                    else {}
                ),
            }
            for row in frame.itertuples(index=False)
        )
    forecast = pd.DataFrame(forecast_rows)
    forecast_dates = pd.DatetimeIndex(forecast["date"].unique()).sort_values()
    if not forecast_dates.equals(expected_dates):
        raise ValueError("Forecast rows do not match the selected holdout window.")
    thresholds = {
        product: float(artifact["influx_threshold_count"])
        for product, artifact in result["artifacts"].items()
        if "influx_threshold_count" in artifact
    }
    return calculate_validation_metrics(
        forecast,
        observations,
        thresholds,
    )


def load_validation_observations(
    target_dates: date | list[date],
    occurrences: pd.DataFrame | None = None,
) -> pd.DataFrame:
    records = occurrences if occurrences is not None else load_cached_occurrences()
    if not {"date", "species"}.issubset(records.columns):
        raise ValueError("Occurrence observations must contain date and species.")
    dated = records.copy()
    dated["date"] = pd.to_datetime(dated["date"], errors="raise").dt.normalize()
    selected_dates = (
        [target_dates] if isinstance(target_dates, date) else list(target_dates)
    )
    target_index = pd.DatetimeIndex(pd.to_datetime(selected_dates)).normalize()
    if target_index.empty:
        raise ValueError("Validation holdout dates must not be empty.")
    if dated.empty or dated["date"].max() < target_index.max():
        raise StrictValidationUnavailable(
            "Strict validation unavailable for this date. "
            "Holdout occurrence observations are not available through the "
            f"selected window ending {target_index.max().date()}."
        )
    selected = dated.loc[dated["date"].isin(target_index)]
    guild_names = {str(item["species"]) for item in SEABIRD_SPECIES}
    counts = selected.groupby(["date", "species"]).size().to_dict()
    result = []
    for target_date in target_index:
        result.append(
            {
                "product": "General Seabird Index",
                "count": sum(
                    int(counts.get((target_date, name), 0))
                    for name in guild_names
                ),
                "date": target_date,
            }
        )
        result.extend(
            {
                "product": species,
                "count": int(counts.get((target_date, species), 0)),
                "date": target_date,
            }
            for species in SPECIES_NAMES
        )
    return pd.DataFrame(result)
