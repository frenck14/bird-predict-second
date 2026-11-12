"""Audit of where the weather model adds value beyond yesterday's-event persistence."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .ebird_baseline_benchmark import fit_predict_persistence
from .rolling_seabird_event_validation import ROOT, load_observations
from .seabird_calibration import SPECIES_ORDER
from .seabird_observation_validation import OBSERVATIONS_FILE
from .train_seabird_species_models import CLASSIFICATION_THRESHOLD

OUT = ROOT / "outputs/seabird_validation"
PREDICTIONS_PATH = OUT / "rolling_event_predictions.csv"
CSV_PATH = OUT / "weather_vs_persistence.csv"
MD_PATH = OUT / "weather_vs_persistence.md"
SEASONS = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
           6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"}
MIN_EVENTS_UNCERTAIN = 50
COLUMNS = ["analysis", "species", "group", "model", "n", "event_days", "tp", "fp", "fn", "tn",
           "precision", "recall", "f1", "brier", "auc"]


def build_forecasts(predictions: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    """One row per species and date with weather (A) and persistence (B) probabilities."""
    predictions = predictions.assign(date=pd.to_datetime(predictions["date"]))
    counts = observations.groupby(["species", "date"])["count"].sum()
    end = predictions["date"].max()
    frames = []
    for species in SPECIES_ORDER:
        rows = predictions.loc[predictions["species"].eq(species)].sort_values("date").copy()
        daily = counts.xs(species, level="species").reindex(
            pd.date_range("2010-01-01", end), fill_value=0
        )
        rows["prob_a"] = rows["probability"]
        rows["prob_b"] = np.nan
        rows["yesterday_event"] = False
        rows["event_last_7d"] = False
        for year, year_rows in rows.groupby(rows["date"].dt.year):
            threshold = float(year_rows["event_threshold_count"].iloc[0])
            labels = (daily >= threshold).astype(float)
            train_end = pd.Timestamp(year=year, month=1, day=1) - pd.Timedelta(days=1)
            targets = pd.DatetimeIndex(year_rows["date"])
            rows.loc[year_rows.index, "prob_b"] = fit_predict_persistence(labels, train_end, targets)
            rows.loc[year_rows.index, "yesterday_event"] = (
                labels.shift(1).reindex(targets).fillna(0).astype(bool).to_numpy()
            )
            rows.loc[year_rows.index, "event_last_7d"] = (
                labels.shift(1).rolling(7, min_periods=1).max().reindex(targets).fillna(0)
                .astype(bool).to_numpy()
            )
        frames.append(rows.drop(columns="probability").assign(species=species))
    frame = pd.concat(frames, ignore_index=True)
    frame["actual_event"] = frame["actual_event"].astype(bool)
    frame["pred_a"] = frame["prob_a"].ge(CLASSIFICATION_THRESHOLD)
    frame["pred_b"] = frame["prob_b"].ge(CLASSIFICATION_THRESHOLD)
    frame["season"] = frame["date"].dt.month.map(SEASONS)
    return frame


def metrics(rows: pd.DataFrame, model: str) -> dict[str, float]:
    actual = rows["actual_event"]
    predicted = rows[f"pred_{model.lower()}"]
    probability = rows[f"prob_{model.lower()}"]
    tp = int((actual & predicted).sum())
    fp = int((~actual & predicted).sum())
    fn = int((actual & ~predicted).sum())
    tn = int((~actual & ~predicted).sum())
    auc = (
        float(roc_auc_score(actual, probability))
        if actual.nunique() == 2 and probability.nunique() > 1 else np.nan
    )
    return {
        "n": len(rows), "event_days": int(actual.sum()), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        "brier": float(((probability - actual.astype(float)) ** 2).mean()) if len(rows) else np.nan,
        "auc": auc,
    }


def event_runs(actual: pd.Series) -> pd.Series:
    """Run length of the event streak containing each event day (0 for non-events)."""
    group = (actual != actual.shift()).cumsum()
    lengths = actual.groupby(group).transform("sum")
    return lengths.where(actual, 0).astype(int)


def audit(frame: pd.DataFrame) -> pd.DataFrame:
    records = []

    def add(analysis: str, species: str, group: str, rows: pd.DataFrame) -> None:
        if rows.empty:
            return
        for model, label in (("A", "A weather"), ("B", "B persistence")):
            records.append({"analysis": analysis, "species": species, "group": group,
                            "model": label, **metrics(rows, model)})

    for species in SPECIES_ORDER:
        rows = frame.loc[frame["species"].eq(species)].sort_values("date").reset_index(drop=True)
        add("overall", species, "all days", rows)
        for season in ("Winter", "Spring", "Summer", "Autumn"):
            add("season", species, season, rows.loc[rows["season"].eq(season)])
        add("yesterday_state", species, "after event day (continuation)", rows.loc[rows["yesterday_event"]])
        add("yesterday_state", species, "after non-event day (onset possible)", rows.loc[~rows["yesterday_event"]])
        for season in ("Spring", "Summer", "Autumn", "Winter"):
            add("onset_within_season", species, season,
                rows.loc[~rows["yesterday_event"] & rows["season"].eq(season)])
        add("fresh_onset_window", species, "no event in previous 7 days", rows.loc[~rows["event_last_7d"]])
        rows["run_length"] = event_runs(rows["actual_event"])
        for label, mask in (
            ("isolated event (run of 1)", rows["run_length"].eq(1)),
            ("short run (2-3 days)", rows["run_length"].between(2, 3)),
            ("long run (4+ days)", rows["run_length"].ge(4)),
        ):
            subset = rows.loc[mask]
            if subset.empty:
                continue
            for model, name in (("A", "A weather"), ("B", "B persistence")):
                hits = int(subset[f"pred_{model.lower()}"].sum())
                records.append({
                    "analysis": "event_cluster_recall", "species": species, "group": label,
                    "model": name, "n": len(subset), "event_days": len(subset), "tp": hits,
                    "fn": len(subset) - hits, "recall": hits / len(subset),
                })
    return pd.DataFrame(records).reindex(columns=COLUMNS)


def overlap(frame: pd.DataFrame) -> pd.DataFrame:
    """Event-day detection overlap and false-alarm overlap between the two models."""
    rows = []
    for species in SPECIES_ORDER:
        d = frame.loc[frame["species"].eq(species)]
        events, quiet = d.loc[d["actual_event"]], d.loc[~d["actual_event"]]
        onset = events.loc[~events["yesterday_event"]]
        rows.append({
            "species": species,
            "event_days": len(events),
            "both_found": int((events["pred_a"] & events["pred_b"]).sum()),
            "weather_only_found": int((events["pred_a"] & ~events["pred_b"]).sum()),
            "persistence_only_found": int((~events["pred_a"] & events["pred_b"]).sum()),
            "neither_found": int((~events["pred_a"] & ~events["pred_b"]).sum()),
            "onset_days": len(onset),
            "onsets_found_by_weather": int(onset["pred_a"].sum()),
            "onsets_found_by_persistence": int(onset["pred_b"].sum()),
            "weather_false_alarms": int(quiet["pred_a"].sum()),
            "persistence_false_alarms": int(quiet["pred_b"].sum()),
            "false_alarms_in_both": int((quiet["pred_a"] & quiet["pred_b"]).sum()),
        })
    return pd.DataFrame(rows)


def seasonal_onset_auc(table: pd.DataFrame, species: str) -> float:
    """Event-weighted weather AUC after non-event days, computed within season (removes the seasonal cycle)."""
    rows = table.loc[
        table["analysis"].eq("onset_within_season") & table["species"].eq(species)
        & table["model"].eq("A weather") & table["event_days"].ge(10)
    ].dropna(subset=["auc"])
    return float(np.average(rows["auc"], weights=rows["event_days"])) if len(rows) else np.nan


def verdict(species: str, table: pd.DataFrame, lap: pd.DataFrame) -> str:
    o = table.loc[table["analysis"].eq("overall") & table["species"].eq(species)].set_index("model")
    a, b = o.loc["A weather"], o.loc["B persistence"]
    state = table.loc[
        table["analysis"].eq("yesterday_state") & table["species"].eq(species)
        & table["group"].str.startswith("after non-event") & table["model"].eq("A weather")
    ].iloc[0]
    row = lap.loc[lap["species"].eq(species)].iloc[0]
    if a.event_days < MIN_EVENTS_UNCERTAIN:
        return "Too few event days to judge."
    within = seasonal_onset_auc(table, species)
    independent = within > 0.60
    if a.f1 > b.f1 and a.brier < b.brier:
        lead = "weather beats persistence"
    elif a.f1 <= b.f1 and a.brier >= b.brier:
        lead = "persistence beats weather"
    else:
        lead = "weather and persistence trade wins"
    detail = (
        f"weather AUC {state.auc:.2f} on days after a non-event, {within:.2f} within season "
        + ("(independent skill beyond seasonality)" if independent else "(little skill beyond seasonality)")
    )
    return f"{lead}; {detail}; finds {row.onsets_found_by_weather}/{row.onset_days} onsets."


def write_report(table: pd.DataFrame, lap: pd.DataFrame, path: Path = MD_PATH) -> None:
    def f(v: float, nd: int = 3) -> str:
        return "-" if pd.isna(v) else f"{v:.{nd}f}"

    lines = [
        "# Weather vs persistence audit", "",
        "A = stored rolling weather forecast. B = yesterday-event baseline: probability that an "
        "event follows an event (or a non-event), estimated from training years only, refit "
        "each January. Same labels, dates (2015-01-01 to 2026-08-11) and 0.20 cutoff.", "",
        "## 1. Confusion matrices and scores", "",
        "| Species | Model | TP | FP | FN | TN | Precision | Recall | F1 | Brier |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    overall = table.loc[table["analysis"].eq("overall")]
    for r in overall.itertuples():
        lines.append(f"| {r.species} | {r.model} | {int(r.tp)} | {int(r.fp)} | {int(r.fn)} | {int(r.tn)} | "
                     f"{f(r.precision)} | {f(r.recall)} | {f(r.f1)} | {f(r.brier, 4)} |")
    lines += ["", "## 2. Who finds which events", "",
              "| Species | Events | Both | Weather only | Persistence only | Neither | "
              "Weather false alarms | Persistence false alarms | In both |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in lap.itertuples():
        lines.append(f"| {r.species} | {r.event_days} | {r.both_found} | {r.weather_only_found} | "
                     f"{r.persistence_only_found} | {r.neither_found} | {r.weather_false_alarms} | "
                     f"{r.persistence_false_alarms} | {r.false_alarms_in_both} |")
    lines += ["", "## 3. Seasonal differences (F1 / Brier)", "",
              "| Species | Season | Events | A F1 | B F1 | A Brier | B Brier |", "|---|---|---:|---:|---:|---:|---:|"]
    season = table.loc[table["analysis"].eq("season")]
    for (species, group), pair in season.groupby(["species", "group"], sort=False):
        a, b = pair.set_index("model").loc["A weather"], pair.set_index("model").loc["B persistence"]
        lines.append(f"| {species} | {group} | {a.event_days:.0f} | {f(a.f1)} | {f(b.f1)} | "
                     f"{f(a.brier, 4)} | {f(b.brier, 4)} |")
    lines += ["", "## 4. Multi-day event clustering (recall by event-run length)", "",
              "| Species | Run type | Event days | A recall | B recall |", "|---|---|---:|---:|---:|"]
    cluster = table.loc[table["analysis"].eq("event_cluster_recall")]
    for (species, group), pair in cluster.groupby(["species", "group"], sort=False):
        p = pair.set_index("model")
        lines.append(f"| {species} | {group} | {p.loc['A weather', 'n']:.0f} | "
                     f"{f(p.loc['A weather', 'recall'])} | {f(p.loc['B persistence', 'recall'])} |")
    lines += ["", "## 5. Starts of influxes (events after a non-event day)", "",
              "| Species | Onset days | Found by weather | Found by persistence | Weather AUC after non-event | Weather AUC after event |",
              "|---|---:|---:|---:|---:|---:|"]
    state = table.loc[table["analysis"].eq("yesterday_state") & table["model"].eq("A weather")]
    for r in lap.itertuples():
        s = state.loc[state["species"].eq(r.species)].set_index("group")
        lines.append(f"| {r.species} | {r.onset_days} | {r.onsets_found_by_weather} | "
                     f"{r.onsets_found_by_persistence} | "
                     f"{f(s.loc['after non-event day (onset possible)', 'auc'], 2)} | "
                     f"{f(s.loc['after event day (continuation)', 'auc'], 2)} |")
    lines += ["", "Within-season AUC of the weather model on days after a non-event (seasons with "
              "at least 10 events):", "",
              "| Species | Season | Events | Weather AUC |", "|---|---|---:|---:|"]
    within = table.loc[
        table["analysis"].eq("onset_within_season") & table["model"].eq("A weather")
        & table["event_days"].ge(10)
    ]
    for r in within.itertuples():
        lines.append(f"| {r.species} | {r.group} | {int(r.event_days)} | {f(r.auc, 2)} |")
    lines += ["", "## Verdict by species", ""]
    lines += [f"- **{s}:** {verdict(s, table, lap)}" for s in SPECIES_ORDER]
    lines += ["", "## Reading the results", ""] + reading(table, lap) + [
        "", "## Caveats", "",
        "- Persistence at a 0.20 cutoff flags every day after an event (the training chance of "
        "another event is well above 0.20) and almost never anything else, so it cannot find a "
        "new onset by construction.",
        "- Sooty and Great Shearwater have fewer than 50 event days; treat them as uncertain.",
        "- The weather model also receives calendar inputs, so whole-period AUC after a "
        "non-event partly reflects the seasonal cycle. The within-season AUC removes that.",
        "- AUC is rank-based and ignores the cutoff; it measures whether weather ranks event days "
        "above quiet days within a persistence state.", "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def reading(table: pd.DataFrame, lap: pd.DataFrame) -> list[str]:
    rated = [s for s in SPECIES_ORDER
             if lap.loc[lap["species"].eq(s), "event_days"].iloc[0] >= MIN_EVENTS_UNCERTAIN]
    state = table.loc[table["analysis"].eq("yesterday_state") & table["model"].eq("A weather")]
    onset_auc = {
        s: state.loc[state["species"].eq(s) & state["group"].str.startswith("after non-event"), "auc"].iloc[0]
        for s in rated
    }
    onset = lap.set_index("species")
    summer = {
        s: table.loc[
            table["analysis"].eq("onset_within_season") & table["species"].eq(s)
            & table["group"].eq("Summer") & table["model"].eq("A weather"), "auc"
        ].iloc[0]
        for s in rated
    }
    return [
        "- Summer holds most event days, and there the weather model's within-season AUC after a "
        "non-event is " + ", ".join(f"{s} {summer[s]:.2f}" for s in rated)
        + ". Its extra skill comes from spring and autumn, not the main season.",
        "- Weather-only finds are events that persistence cannot flag, which are overwhelmingly "
        "onsets. Persistence-only finds are continuation days where weather probability stays "
        "below 0.20.",
        "- Within days that follow a non-event, weather ranks event days above quiet days with AUC "
        + ", ".join(f"{s} {onset_auc[s]:.2f}" for s in rated)
        + " overall, and "
        + ", ".join(f"{s} {seasonal_onset_auc(table, s):.2f}" for s in rated)
        + " within season (0.50 = no skill).",
        "- Onsets found by weather: "
        + "; ".join(
            f"{s} {onset.loc[s, 'onsets_found_by_weather']}/{onset.loc[s, 'onset_days']}" for s in rated
        )
        + ".",
    ]


def main() -> None:
    predictions = pd.read_csv(PREDICTIONS_PATH)
    observations = load_observations(ROOT / OBSERVATIONS_FILE)
    frame = build_forecasts(predictions, observations)
    table = audit(frame)
    lap = overlap(frame)
    table.to_csv(CSV_PATH, index=False)
    write_report(table, lap)
    print(lap.to_string())


if __name__ == "__main__":
    main()
