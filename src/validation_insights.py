"""Read-only "Validation Insights" page combining validation and calibration outputs."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from .validation_dashboard import interpret, load_overall

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/seabird_validation"
VALIDATION_CSV = OUT / "rolling_event_validation.csv"
CALIBRATION_CSV = OUT / "calibration_metrics.csv"
CALIBRATION_MD = OUT / "calibration_summary.md"
CALIBRATION_COLUMNS = {"species", "ece", "verdict", "uncertain"}


def load_calibration(path: Path = CALIBRATION_CSV) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    frame = pd.read_csv(path)
    missing = CALIBRATION_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    return frame


def calibration_status(verdict: str) -> str:
    """Collapse the five-level class to the three statuses shown to users."""
    if verdict.startswith("well"):
        return "Well calibrated"
    if verdict.endswith("underconfident"):
        return "Underconfident"
    if verdict.endswith("overconfident"):
        return "Overconfident"
    return verdict.capitalize()


def figure_path(species: str, directory: Path) -> Path:
    slug = species.lower().replace(" ", "_").replace("-", "_")
    return directory / f"calibration_reliability_{slug}.png"


def build_ranking(overall: pd.DataFrame, calibration: pd.DataFrame | None) -> pd.DataFrame:
    ranking = overall[
        ["species", "event_days", "precision", "recall", "f1", "brier_score"]
    ].copy()
    ece = calibration.set_index("species")["ece"] if calibration is not None else {}
    ranking["ece"] = ranking["species"].map(ece) if calibration is not None else float("nan")
    return ranking


def species_summary(row: pd.Series, calibration_row: pd.Series | None) -> str:
    text = interpret(row)
    if calibration_row is None:
        return text
    status = calibration_status(calibration_row["verdict"])
    detail = {
        "Underconfident": "Real event frequency is higher than its stated probabilities.",
        "Overconfident": "Real event frequency is lower than its stated probabilities.",
        "Well calibrated": "Its probabilities match observed frequencies.",
    }.get(status, "")
    uncertain = " Calibration is uncertain (fewer than 50 event days)." if calibration_row["uncertain"] else ""
    return f"{text} Calibration: {calibration_row['verdict']}. {detail}{uncertain}"


def show_validation_insights(
    validation_csv: Path = VALIDATION_CSV,
    calibration_csv: Path = CALIBRATION_CSV,
    calibration_md: Path = CALIBRATION_MD,
) -> None:
    st.title("🔍 Validation Insights")
    st.caption(
        "Read-only view of saved validation and calibration outputs. Nothing is "
        "retrained or rerun here."
    )
    overall = load_overall(validation_csv)
    calibration = load_calibration(calibration_csv)
    if overall is None:
        st.info(
            "Rolling validation results are not available "
            f"(`{validation_csv.name}` not found), so performance sections are "
            "hidden. Generate them offline with "
            "`python -m src.rolling_seabird_event_validation`."
        )
    else:
        _performance(overall, calibration)
    _calibration(overall, calibration, calibration_csv, calibration_md)
    if overall is not None:
        _summaries(overall, calibration)
    _methodology()


def _performance(overall: pd.DataFrame, calibration: pd.DataFrame | None) -> None:
    st.header("Model ranking")
    ranking = build_ranking(overall, calibration).rename(
        columns={
            "species": "Species", "event_days": "Event Days", "precision": "Precision",
            "recall": "Recall", "f1": "F1", "brier_score": "Brier Score", "ece": "ECE",
        }
    )
    st.dataframe(
        ranking,
        hide_index=True,
        width="stretch",
        column_config={
            "Precision": st.column_config.NumberColumn(format="%.3f"),
            "Recall": st.column_config.NumberColumn(format="%.3f"),
            "F1": st.column_config.NumberColumn(format="%.3f"),
            "Brier Score": st.column_config.NumberColumn(format="%.4f"),
            "ECE": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    st.caption("Ranked by F1 at the 0.20 probability cutoff. Lower Brier and ECE are better.")
    if calibration is None:
        st.caption("ECE is unavailable because the calibration metrics file is missing.")

    st.subheader("F1 by species")
    st.altair_chart(
        alt.Chart(overall)
        .mark_bar()
        .encode(
            y=alt.Y("species:N", sort="-x", title=None),
            x=alt.X("f1:Q", title="F1"),
            tooltip=["species", alt.Tooltip("f1:Q", format=".3f")],
        )
        .properties(height=220),
        width="stretch",
    )
    st.subheader("Precision vs recall")
    long = overall.melt(
        id_vars="species", value_vars=["precision", "recall"], var_name="metric", value_name="value"
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
        .properties(height=280),
        width="stretch",
    )


def _calibration(
    overall: pd.DataFrame | None,
    calibration: pd.DataFrame | None,
    calibration_csv: Path,
    calibration_md: Path,
) -> None:
    st.header("Calibration")
    if calibration is None:
        st.info(
            "Calibration results are not available "
            f"(`{calibration_csv.name}` not found). Generate them offline with "
            "`python -m src.seabird_calibration`."
        )
        return
    st.markdown(
        "A calibrated model's 30% forecasts verify about 30% of the time. "
        "**Overconfident** means stated probabilities exceed observed frequency; "
        "**underconfident** means they fall below it."
    )
    status = calibration.assign(Status=calibration["verdict"].map(calibration_status))
    st.dataframe(
        status.assign(
            Detail=status["verdict"], Uncertain=status["uncertain"].map({True: "Yes", False: "No"})
        )[["species", "Status", "Detail", "ece", "Uncertain"]].rename(
            columns={"species": "Species", "Detail": "Class", "ece": "ECE"}
        ),
        hide_index=True,
        width="stretch",
        column_config={"ECE": st.column_config.NumberColumn(format="%.3f")},
    )
    st.subheader("Reliability diagrams")
    st.caption("Points on the dashed diagonal are perfectly calibrated; bars show forecast counts per bin.")
    species = list(overall["species"]) if overall is not None else list(calibration["species"])
    columns = st.columns(2)
    for index, name in enumerate(species):
        with columns[index % 2]:
            path = figure_path(name, calibration_csv.parent)
            if path.is_file():
                st.image(str(path), caption=name)
            else:
                st.info(f"Reliability diagram for {name} is not available.")
    if calibration_md.is_file():
        with st.expander("Full calibration report"):
            st.markdown(calibration_md.read_text(encoding="utf-8"))
    else:
        st.caption(f"`{calibration_md.name}` not found; the full report is unavailable.")


def _summaries(overall: pd.DataFrame, calibration: pd.DataFrame | None) -> None:
    st.header("Species summaries")
    by_species = calibration.set_index("species") if calibration is not None else None
    for row in overall.itertuples(index=False):
        cal = (
            by_species.loc[row.species]
            if by_species is not None and row.species in by_species.index
            else None
        )
        st.markdown(f"**{row.species}** · F1 {row.f1:.3f} ({row.performance})")
        st.write(species_summary(pd.Series(row._asdict()), cal))


def _methodology() -> None:
    st.header("Methodology")
    st.markdown(
        "- **Strict cutoff validation:** every model and event threshold uses only "
        "data dated on or before the cutoff; later records are used only to score.\n"
        "- **Rolling annual validation:** models are refit each January on all "
        "earlier years (expanding window) and then forecast every day of that "
        "year one day ahead.\n"
        "- **Influx-event prediction:** the target is an unusually high daily record "
        "count (at or above the training-only 90th percentile), not simple presence.\n"
        "- **Leakage prevention:** training weather, occurrence records and "
        "thresholds are filtered to the cutoff and checked automatically; each "
        "forecast uses only the previous day's weather.\n"
        "- **Caveat:** a hindcast using observed weather, not a replay of archived "
        "forecasts. Labels are GBIF record counts, so reporting effort matters."
    )
