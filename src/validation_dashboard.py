"""Read-only dashboard page for the rolling seabird event validation outputs."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_CSV = ROOT / "outputs/seabird_validation/rolling_event_validation.csv"
VALIDATION_SUMMARY = ROOT / "outputs/seabird_validation/event_validation_summary.md"
STRONG_F1 = 0.60
MODERATE_F1 = 0.40
RARE_EVENT_DAYS = 50
REQUIRED_COLUMNS = {
    "species", "year", "start_date", "end_date", "evaluated_days", "event_days",
    "event_prevalence", "precision", "recall", "f1", "brier_score",
    "baseline_brier_score",
}


def classify_f1(f1: float) -> str:
    if f1 >= STRONG_F1:
        return "Strong"
    if f1 >= MODERATE_F1:
        return "Moderate"
    return "Weak"


def load_overall(path: Path = VALIDATION_CSV) -> pd.DataFrame | None:
    """Pooled whole-period rows sorted by F1, or None if the output is missing."""
    if not path.is_file():
        return None
    frame = pd.read_csv(path, dtype={"year": str})
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    overall = frame.loc[frame["year"].eq("all")].copy()
    if overall.empty:
        raise ValueError(f"{path.name} has no pooled 'all' rows.")
    overall["performance"] = overall["f1"].map(classify_f1)
    return overall.sort_values("f1", ascending=False, kind="stable").reset_index(drop=True)


def interpret(row: pd.Series) -> str:
    """Short, data-derived explanation for one species."""
    level = row["performance"]
    lead = {
        "Strong": "This model shows strong ability to identify influx events",
        "Moderate": "This model shows moderate ability to identify influx events",
        "Weak": "This model shows weak ability to identify influx events",
    }[level]
    text = [
        f"{lead}: it finds {row['recall']:.0%} of event days and "
        f"{row['precision']:.0%} of its event alerts are real events."
    ]
    if row["event_days"] < RARE_EVENT_DAYS:
        text.append(
            f"Only {int(row['event_days'])} event days were available "
            f"({row['event_prevalence']:.1%} of days), so these scores are very "
            "uncertain."
        )
    if row["brier_score"] < row["baseline_brier_score"]:
        text.append("Its probabilities beat a constant training-prevalence baseline (lower Brier).")
    else:
        text.append(
            "Its probabilities did not beat a constant training-prevalence "
            "baseline (Brier), so they add little beyond the base rate."
        )
    if row["precision"] > row["recall"] + 0.1:
        text.append("It is conservative: it misses events more than it raises false alarms.")
    elif row["recall"] > row["precision"] + 0.1:
        text.append("It is generous: it catches most events but with many false alarms.")
    return " ".join(text)


def _bar(data: pd.DataFrame, value: str, title: str, fmt: str = ".2f") -> alt.Chart:
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            y=alt.Y("species:N", sort="-x", title=None),
            x=alt.X(f"{value}:Q", title=title),
            tooltip=["species", alt.Tooltip(f"{value}:Q", format=fmt)],
        )
        .properties(height=200)
    )


def show_validation_dashboard(
    csv_path: Path = VALIDATION_CSV, summary_path: Path = VALIDATION_SUMMARY
) -> None:
    st.title("📈 Seabird Model Validation")
    overall = load_overall(csv_path)
    if overall is None:
        st.info(
            "No validation results found. Generate them offline with "
            "`python -m src.rolling_seabird_event_validation`; this page only "
            "reads existing outputs."
        )
        return
    start, end = overall["start_date"].min(), overall["end_date"].max()
    st.markdown(
        "These models predict **influx events** (unusually high daily record "
        "counts for a species), not simple presence.\n\n"
        "- **Strict cutoff validation:** each prediction uses only data available "
        "before the evaluation year.\n"
        "- **Annual expanding-window retraining:** models are refit each January "
        "on all earlier years.\n"
        "- **Daily one-day-ahead hindcasts:** every day is forecast from the "
        "preceding day's observed weather.\n"
        f"- **Evaluation period:** {start} through {end}."
    )
    st.caption(
        "Hindcast with observed-weather inputs, not a replay of archived "
        "operational forecasts. Results are read from saved outputs; nothing is "
        "retrained or rerun here."
    )

    st.header("Overall performance")
    table = overall.rename(
        columns={
            "species": "Species", "event_days": "Event Days",
            "event_prevalence": "Event Prevalence", "precision": "Precision",
            "recall": "Recall", "f1": "F1", "brier_score": "Brier Score",
        }
    )[["Species", "Event Days", "Event Prevalence", "Precision", "Recall", "F1", "Brier Score"]]
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "Event Prevalence": st.column_config.NumberColumn(format="percent"),
            "Precision": st.column_config.NumberColumn(format="%.3f"),
            "Recall": st.column_config.NumberColumn(format="%.3f"),
            "F1": st.column_config.NumberColumn(format="%.3f"),
            "Brier Score": st.column_config.NumberColumn(format="%.4f"),
        },
    )
    st.caption("Precision, recall and F1 use the 0.20 probability cutoff. Sorted by F1.")

    st.header("Performance interpretation")
    st.caption("Strong: F1 ≥ 0.60 · Moderate: 0.40 ≤ F1 < 0.60 · Weak: F1 < 0.40")
    icons = {"Strong": "🟢", "Moderate": "🟡", "Weak": "🔴"}
    for row in overall.itertuples(index=False):
        series = pd.Series(row._asdict())
        st.markdown(
            f"{icons[row.performance]} **{row.species}** · F1 {row.f1:.3f} · "
            f"**{row.performance}**  \n{interpret(series)}"
        )

    st.header("Visualisations")
    st.markdown("**F1 score**")
    st.altair_chart(_bar(overall, "f1", "F1"), width="stretch")
    st.markdown("**Precision and recall**")
    long = overall.melt(
        id_vars="species", value_vars=["precision", "recall"],
        var_name="metric", value_name="value",
    )
    st.altair_chart(
        alt.Chart(long)
        .mark_bar()
        .encode(
            y=alt.Y("species:N", sort=list(overall["species"]), title=None),
            yOffset="metric:N",
            x=alt.X("value:Q", title="Score"),
            color=alt.Color("metric:N", title=None),
            tooltip=["species", "metric", alt.Tooltip("value:Q", format=".3f")],
        )
        .properties(height=260),
        width="stretch",
    )
    st.markdown("**Event prevalence**")
    st.altair_chart(
        _bar(overall, "event_prevalence", "Share of days that were events", ".1%")
        .encode(x=alt.X("event_prevalence:Q", title="Share of days that were events", axis=alt.Axis(format="%"))),
        width="stretch",
    )

    st.header("Species detail")
    for row in overall.itertuples(index=False):
        with st.expander(f"{row.species} · F1 = {row.f1:.3f} ({row.performance})"):
            cols = st.columns(5)
            cols[0].metric("Event days", f"{int(row.event_days):,}")
            cols[1].metric("Precision", f"{row.precision:.3f}")
            cols[2].metric("Recall", f"{row.recall:.3f}")
            cols[3].metric("F1", f"{row.f1:.3f}")
            cols[4].metric("Brier Score", f"{row.brier_score:.4f}")
            st.caption(f"Validation period: {row.start_date} through {row.end_date}")
            st.write(interpret(pd.Series(row._asdict())))

    if summary_path.is_file():
        with st.expander("Full validation method and caveats"):
            st.markdown(summary_path.read_text(encoding="utf-8"))
