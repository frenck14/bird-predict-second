import shutil
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src import validation_insights as vi
from src.validation_dashboard import classify_f1

REAL = Path(__file__).resolve().parents[1] / "outputs/seabird_validation"
COLUMNS = [
    "species", "year", "start_date", "end_date", "evaluated_days", "event_days",
    "event_prevalence", "precision", "recall", "f1", "brier_score", "baseline_brier_score",
]


def _files(tmp_path: Path, validation=True, calibration=True, images=True) -> Path:
    if validation:
        rows = [
            ["Alpha", "all", "2015-01-01", "2026-08-11", 4000, 900, 0.22, 0.5, 0.8, 0.62, 0.1, 0.17],
            ["Beta", "all", "2015-01-01", "2026-08-11", 4000, 20, 0.005, 0.0, 0.0, 0.0, 0.01, 0.005],
        ]
        pd.DataFrame(rows, columns=COLUMNS).to_csv(tmp_path / "rolling_event_validation.csv", index=False)
    if calibration:
        pd.DataFrame(
            {
                "species": ["Alpha", "Beta"],
                "ece": [0.05, 0.07],
                "verdict": ["mildly underconfident", "strongly overconfident"],
                "uncertain": [False, True],
            }
        ).to_csv(tmp_path / "calibration_metrics.csv", index=False)
        (tmp_path / "calibration_summary.md").write_text("# Calibration report", encoding="utf-8")
    if images:
        source = next(REAL.glob("calibration_reliability_*.png"))
        for name in ("alpha", "beta"):
            shutil.copy(source, tmp_path / f"calibration_reliability_{name}.png")
    return tmp_path


def _script(directory: str) -> None:
    from pathlib import Path

    from src import validation_insights as vi

    d = Path(directory)
    vi.show_validation_insights(
        d / "rolling_event_validation.csv", d / "calibration_metrics.csv", d / "calibration_summary.md"
    )


def _run(directory: Path) -> AppTest:
    return AppTest.from_function(_script, args=(str(directory),), default_timeout=30).run()


@pytest.mark.parametrize(
    ("verdict", "status"),
    [
        ("well calibrated", "Well calibrated"),
        ("mildly overconfident", "Overconfident"),
        ("strongly overconfident", "Overconfident"),
        ("mildly underconfident", "Underconfident"),
        ("strongly underconfident", "Underconfident"),
    ],
)
def test_calibration_status_mapping(verdict: str, status: str) -> None:
    assert vi.calibration_status(verdict) == status


def test_full_page_renders_all_sections(tmp_path: Path) -> None:
    at = _run(_files(tmp_path))
    assert not at.exception
    assert at.title[0].value == "🔍 Validation Insights"
    assert [h.value for h in at.header] == [
        "Model ranking", "Calibration", "Species summaries", "Methodology",
    ]
    ranking = at.dataframe[0].value
    assert list(ranking.columns) == [
        "Species", "Event Days", "Precision", "Recall", "F1", "Brier Score", "ECE",
    ]
    assert ranking["Species"].tolist() == ["Alpha", "Beta"]
    assert ranking["ECE"].tolist() == [0.05, 0.07]
    status = at.dataframe[1].value
    assert status["Status"].tolist() == ["Underconfident", "Overconfident"]
    assert len(at.get("image")) == 2
    text = " ".join(m.value for m in at.markdown)
    assert "Strict cutoff validation" in text and "Leakage prevention" in text
    assert "Calibration: strongly overconfident" in " ".join(m.value for m in at.markdown)


def test_missing_everything_shows_notices_not_errors(tmp_path: Path) -> None:
    at = _run(tmp_path)
    assert not at.exception
    notices = " ".join(i.value for i in at.info)
    assert "Rolling validation results are not available" in notices
    assert "Calibration results are not available" in notices
    assert [h.value for h in at.header] == ["Calibration", "Methodology"]


def test_missing_calibration_keeps_performance_sections(tmp_path: Path) -> None:
    at = _run(_files(tmp_path, calibration=False, images=False))
    assert not at.exception
    assert at.dataframe[0].value["ECE"].isna().all()
    assert "Calibration results are not available" in at.info[0].value


def test_missing_validation_and_images_degrade_individually(tmp_path: Path) -> None:
    at = _run(_files(tmp_path, validation=False, images=False))
    assert not at.exception
    assert "Rolling validation results are not available" in at.info[0].value
    assert sum("Reliability diagram" in i.value for i in at.info) == 2


def test_real_outputs_render() -> None:
    at = _run(REAL)
    assert not at.exception
    assert len(at.dataframe[0].value) == 5
    assert len(at.get("image")) == 5
