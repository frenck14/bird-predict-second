"""Combined weather + persistence seabird event model under strict-cutoff rolling validation."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from .forecast_seabird_locations import _build_seabird_features
from .forecast_seabird_species import SPECIES_NAMES
from .forecast_species_comparison import MIN_TRAIN_YEARS, make_estimator, weather_feature_columns
from .predict_yellow_browed import add_target_calendar
from .rolling_seabird_event_validation import ROOT, load_observations
from .seabird_backtest import load_cached_occurrences, load_historical_weather
from .seabird_calibration import SPECIES_ORDER, calibration_metrics
from .seabird_observation_validation import OBSERVATIONS_FILE
from .seabird_validation import _daily_counts, check_data_leakage
from .train_atlantic_vagrancy_model import influx_cutoff
from .train_seabird_species_models import CLASSIFICATION_THRESHOLD
from .weather_vs_persistence import build_forecasts, metrics

OUT = ROOT / "outputs/seabird_validation"
PREDICTIONS_PATH = OUT / "rolling_event_predictions.csv"
COMBINED_PATH = OUT / "rolling_weather_persistence_predictions.csv"
CSV_PATH = OUT / "weather_persistence_comparison.csv"
MD_PATH = OUT / "weather_persistence_summary.md"
PERSISTENCE_COLUMNS = ["event_yesterday", "event_count_3d", "event_count_7d"]
MODELS = {"A": "Weather", "B": "Persistence", "C": "Weather + Persistence"}
MIN_EVENTS_UNCERTAIN = 50


def persistence_features(daily: pd.Series, threshold: float, targets: pd.DatetimeIndex) -> pd.DataFrame:
    """Event history strictly before each target date: yesterday, last 3 and last 7 days."""
    events = (daily >= threshold).astype(float).shift(1)
    features = pd.DataFrame(
        {
            "event_yesterday": events,
            "event_count_3d": events.rolling(3, min_periods=1).sum(),
            "event_count_7d": events.rolling(7, min_periods=1).sum(),
        }
    )
    return features.reindex(targets).fillna(0.0)


def fit_combined(
    weather: pd.DataFrame,
    engineered: pd.DataFrame,
    occurrences: pd.DataFrame,
    daily_events: pd.Series,
    cutoff: pd.Timestamp,
    species: str,
) -> dict[str, object]:
    """Same Random Forest and event definition as the weather model, plus persistence inputs."""
    check_data_leakage({"weather records": weather, "occurrence records": occurrences}, {}, cutoff.date())
    data = engineered.merge(_daily_counts(occurrences, species), on="date", how="left", validate="one_to_one")
    data["count"] = data["count"].fillna(0).astype(int)
    weather_columns = weather_feature_columns(data)
    calendar_columns = list(add_target_calendar(pd.DatetimeIndex([cutoff])).columns)
    supervised = pd.concat(
        [
            data["date"].rename("target_date"),
            data["date"].shift(1).rename("origin_date"),
            data["count"].rename("target"),
            data[weather_columns].shift(1),
            add_target_calendar(pd.DatetimeIndex(data["date"])),
        ],
        axis=1,
    )
    supervised = supervised.loc[
        supervised["target_date"].le(cutoff) & supervised["origin_date"].notna()
    ].reset_index(drop=True)
    threshold = influx_cutoff(supervised["target"], 90)
    labels = supervised["target"].ge(threshold).astype(int)
    history = persistence_features(daily_events, threshold, pd.DatetimeIndex(supervised["target_date"]))
    supervised = pd.concat([supervised, history.reset_index(drop=True)], axis=1)
    feature_columns = [*calendar_columns, *weather_columns, *PERSISTENCE_COLUMNS]
    positives = int(labels.sum())
    model = make_estimator("Random Forest", positives, len(labels) - positives,
                           random_forest_class_weight=None)
    model.fit(supervised[feature_columns], labels)
    return {
        "model": model, "feature_columns": feature_columns, "weather_columns": weather_columns,
        "threshold": float(threshold),
    }


def run_rolling(refresh_progress: bool = True) -> pd.DataFrame:
    """Annual expanding-window fits; one-day-ahead predictions for every evaluation day."""
    weather = load_historical_weather().sort_values("date").reset_index(drop=True)
    weather = weather.assign(date=pd.DatetimeIndex(pd.to_datetime(weather["date"])).normalize())
    occurrences = load_cached_occurrences()
    occurrences = occurrences.assign(date=pd.to_datetime(occurrences["date"]).dt.normalize())
    observations = load_observations(ROOT / OBSERVATIONS_FILE)
    stored = pd.read_csv(PREDICTIONS_PATH, parse_dates=["date"])
    observed = observations.groupby(["species", "date"])["count"].sum()
    engineered = _build_seabird_features(weather)
    dates = pd.DatetimeIndex(weather["date"])
    last_target = stored["date"].max()
    first_year = sorted(dates.year.unique())[MIN_TRAIN_YEARS - 1] + 1
    frames = []
    for year in range(first_year, last_target.year + 1):
        cutoff = pd.Timestamp(year=year, month=1, day=1) - pd.Timedelta(days=1)
        targets = pd.date_range(cutoff + pd.Timedelta(days=1),
                                min(pd.Timestamp(year=year, month=12, day=31), last_target))
        origin_features = engineered.set_index("date").loc[targets - pd.Timedelta(days=1)].reset_index(drop=True)
        calendar = add_target_calendar(targets).reset_index(drop=True)
        for species in SPECIES_NAMES:
            if refresh_progress:
                print(f"Combined {year}: {species}", flush=True)
            daily = observed.xs(species, level="species").reindex(
                pd.date_range("2000-01-01", last_target), fill_value=0
            )
            artifact = fit_combined(
                weather.loc[weather["date"].le(cutoff)],
                engineered.loc[engineered["date"].le(cutoff)],
                occurrences.loc[occurrences["date"].le(cutoff)],
                daily, cutoff, species,
            )
            history = persistence_features(daily, artifact["threshold"], targets).reset_index(drop=True)
            inputs = pd.concat([calendar, origin_features[artifact["weather_columns"]], history], axis=1)
            probability = artifact["model"].predict_proba(inputs[artifact["feature_columns"]])[:, 1]
            frames.append(pd.DataFrame({"date": targets, "species": species, "prob_c": probability,
                                        "combined_threshold": artifact["threshold"]}))
    return pd.concat(frames, ignore_index=True)


def comparison_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    groups = [("Overall", None), *[(season, season) for season in ["Spring", "Summer", "Autumn", "Winter"]]]
    for species in SPECIES_ORDER:
        subset = frame.loc[frame["species"].eq(species)]
        for group, season in groups:
            part = subset if season is None else subset.loc[subset["season"].eq(season)]
            if part.empty:
                continue
            for key, name in MODELS.items():
                row = {"species": species, "group": group, "model": name, **metrics(part, key)}
                if season is None:
                    cal = calibration_metrics(part[f"prob_{key.lower()}"], part["actual_event"])
                    row.update(ece=cal["ece"], mce=cal["mce"])
                rows.append(row)
    table = pd.DataFrame(rows)
    table["uncertain"] = table["species"].map(
        subset_events(frame)
    ).lt(MIN_EVENTS_UNCERTAIN)
    return table


def subset_events(frame: pd.DataFrame) -> dict[str, int]:
    return frame.groupby("species")["actual_event"].sum().astype(int).to_dict()


def build_frame(stored: pd.DataFrame, combined: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    frame = build_forecasts(stored, observations)
    frame = frame.merge(combined[["date", "species", "prob_c", "combined_threshold"]], on=["date", "species"],
                        how="left", validate="one_to_one")
    if frame["prob_c"].isna().any():
        raise ValueError("Combined predictions do not cover every evaluation day.")
    frame["pred_c"] = frame["prob_c"].ge(CLASSIFICATION_THRESHOLD)
    return frame


def verdict(table: pd.DataFrame, species: str) -> str:
    overall = table.loc[table["species"].eq(species) & table["group"].eq("Overall")].set_index("model")
    a, b, c = (overall.loc[m] for m in MODELS.values())
    flag = " (uncertain: fewer than 50 event days)" if bool(overall["uncertain"].iloc[0]) else ""
    best = overall["f1"].idxmax()
    gain = c["f1"] - max(a["f1"], b["f1"])
    brier_gain = min(a["brier"], b["brier"]) - c["brier"]
    if c["f1"] >= max(a["f1"], b["f1"]) and c["brier"] <= min(a["brier"], b["brier"]):
        text = f"Combined is best on F1 and Brier (F1 {gain:+.3f}, Brier {brier_gain:+.3f} vs the better single model)"
    elif c["f1"] >= max(a["f1"], b["f1"]):
        text = f"Combined has the best F1 ({gain:+.3f}) but not the best Brier ({brier_gain:+.3f})"
    elif c["brier"] <= min(a["brier"], b["brier"]):
        text = f"Combined has the best Brier ({brier_gain:+.3f}) but not the best F1 ({gain:+.3f}); {best} leads F1"
    else:
        text = f"Combined does not beat the best single model (F1 {gain:+.3f}, Brier {brier_gain:+.3f}); {best} leads F1"
    return text + flag


def write_summary(table: pd.DataFrame, path=MD_PATH) -> None:
    overall = table.loc[table["group"].eq("Overall")]
    lines = [
        "# Weather + persistence model comparison",
        "",
        "Same strict-cutoff, annual expanding-window, one-day-ahead validation as the rolling event "
        "validation (2015-01-01 to 2026-08-11), same aligned influx-event labels, same 0.20 "
        "probability threshold. Raw probabilities are scored.",
        "",
        "- **Weather:** the stored production-model forecasts (`rolling_event_predictions.csv`).",
        "- **Persistence:** P(event | yesterday's status) from training days only, refit each January.",
        "- **Weather + Persistence:** the same Random Forest and weather/calendar predictors, plus "
        "yesterday-event, 3-day event count and 7-day event count. Persistence inputs cover days "
        "strictly before the target, use the cutoff's event threshold, and training rows end at the cutoff.",
        "",
        "## Overall",
        "",
        "| Species | Events | Model | Precision | Recall | F1 | Brier | AUC | ECE |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in overall.iterrows():
        lines.append(
            f"| {r['species']} | {int(r['event_days'])} | {r['model']} | {r['precision']:.3f} | "
            f"{r['recall']:.3f} | {r['f1']:.3f} | {r['brier']:.3f} | {r['auc']:.3f} | {r['ece']:.3f} |"
        )
    lines += ["", "## Verdict per species", ""]
    lines += [f"- **{s}:** {verdict(table, s)}" for s in SPECIES_ORDER]
    lines += ["", "## F1 by season", "", "| Species | Season | Events | Weather | Persistence | Weather + Persistence |",
              "|---|---|---:|---:|---:|---:|"]
    seasonal = table.loc[~table["group"].eq("Overall")]
    for (species, season), part in seasonal.groupby(["species", "group"], sort=False):
        f1 = part.set_index("model")["f1"]
        lines.append(f"| {species} | {season} | {int(part['event_days'].iloc[0])} | "
                     f"{f1['Weather']:.3f} | {f1['Persistence']:.3f} | {f1['Weather + Persistence']:.3f} |")
    lines += ["", "## Reading", ""] + reading(table)
    lines += ["", "Sooty Shearwater (33 event days) and Great Shearwater (15) are flagged uncertain; "
              "their differences are not reliable.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def reading(table: pd.DataFrame) -> list[str]:
    overall = table.loc[table["group"].eq("Overall")].pivot(index="species", columns="model", values="f1")
    brier = table.loc[table["group"].eq("Overall")].pivot(index="species", columns="model", values="brier")
    main = [s for s in SPECIES_ORDER if s in ("Northern Fulmar", "Manx Shearwater", "European Storm-petrel")]
    wins = [s for s in main if overall.loc[s, "Weather + Persistence"] >= overall.loc[s].max()]
    lines = []
    for s in main:
        lines.append(
            f"- {s}: F1 weather {overall.loc[s, 'Weather']:.3f}, persistence {overall.loc[s, 'Persistence']:.3f}, "
            f"combined {overall.loc[s, 'Weather + Persistence']:.3f}; Brier "
            f"{brier.loc[s, 'Weather']:.3f} / {brier.loc[s, 'Persistence']:.3f} / "
            f"{brier.loc[s, 'Weather + Persistence']:.3f}."
        )
    lines.append(
        f"- The combined model has the best F1 for {len(wins)} of the {len(main)} species with enough events"
        + (f" ({', '.join(wins)})." if wins else ".")
    )
    return lines


def main() -> None:
    if "--refresh" in sys.argv or not COMBINED_PATH.exists():
        run_rolling().to_csv(COMBINED_PATH, index=False)
    combined = pd.read_csv(COMBINED_PATH, parse_dates=["date"])
    stored = pd.read_csv(PREDICTIONS_PATH, parse_dates=["date"])
    observations = load_observations(ROOT / OBSERVATIONS_FILE)
    frame = build_frame(stored, combined, observations)
    if not np.allclose(frame["event_threshold_count"], frame["combined_threshold"]):
        raise ValueError("Combined model event thresholds differ from the stored validation.")
    table = comparison_table(frame)
    table.to_csv(CSV_PATH, index=False)
    write_summary(table)
    print(table.loc[table["group"].eq("Overall")].round(3).to_string())


if __name__ == "__main__":
    main()
