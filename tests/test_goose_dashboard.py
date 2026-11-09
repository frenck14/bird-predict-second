from __future__ import annotations

import json

import pandas as pd
from streamlit.testing.v1 import AppTest

from src import goose_module as gm
from tests.test_goose_module import _history, _probabilities


def _document(tmp_path):
    probabilities, conditions = _probabilities(0.6, 0.2)
    products = gm.build_goose_products(probabilities, conditions, _history())
    gm.save_goose_products(products, tmp_path)
    return tmp_path / "goose_module.json"


def _script(path: str) -> None:
    from pathlib import Path

    import app

    app.show_goose_forecast(Path(path))


def test_goose_section_renders_all_tabs_and_sections(tmp_path):
    path = _document(tmp_path)
    at = AppTest.from_function(_script, args=(str(path),)).run(timeout=60)
    assert not at.exception
    assert [h.value for h in at.header] == ["🪿 Goose Forecast"]
    assert [tab.label for tab in at.tabs] == ["Tomorrow", "+3 days", "+7 days", "+14 days"]
    titles = [m.value for m in at.markdown if str(m.value).startswith("####")]
    assert titles[:7] == [
        "#### 1. Goose Day Rating", "#### 2. Goose Activity Index", "#### 3. Rare Goose Potential",
        "#### 4. 🎯 Target Geese", "#### 5. Best Goose Regions", "#### 6. Hotspot Map",
        "#### 7. Historical Context",
    ]
    assert "#### European Goose Influx" in titles
    assert any(metric.label == "Rare Goose Europe Index" for metric in at.metric)


def test_goose_section_handles_missing_file(tmp_path):
    at = AppTest.from_function(_script, args=(str(tmp_path / "missing.json"),)).run(timeout=60)
    assert not at.exception
    assert any("No Goose Forecast" in info.value for info in at.info)


def test_recommendation_banner_rendered(tmp_path):
    path = _document(tmp_path)
    at = AppTest.from_function(_script, args=(str(path),)).run(timeout=60)
    messages = [m.value for m in [*at.success, *at.warning, *at.error]]
    assert any(("GO" in v or "MAYBE" in v or "STAY HOME" in v) for v in messages)
