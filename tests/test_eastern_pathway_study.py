import numpy as np
import pandas as pd

from src import eastern_pathway_study as eps


def _features(n: int = 40) -> pd.DataFrame:
    index = pd.date_range("2020-09-01", periods=n)
    rng = np.random.default_rng(0)
    cols = {(r, f): rng.normal(size=n) for r in [*eps.DEPARTURE_REGIONS, eps.DUTCH] for f in eps.BASE_FEATURES}
    return pd.DataFrame(cols, index=index)


def test_wind_components_tailwind_and_crosswind() -> None:
    speed = pd.Series([10.0])
    tail, cross = eps.wind_components(speed, pd.Series([90.0]), track=270.0)  # easterly wind toward the west
    assert np.isclose(tail[0], 10.0) and np.isclose(cross[0], 0.0, atol=1e-9)
    tail, cross = eps.wind_components(speed, pd.Series([180.0]), track=270.0)
    assert np.isclose(tail[0], 0.0, atol=1e-9) and np.isclose(cross[0], 10.0)


def test_design_uses_only_past_weather_and_model_sets() -> None:
    f = _features()
    a, b, c, d = (eps.design(f, m, (2,)) for m in "ABCD")
    assert all(col.startswith(tuple(eps.DEPARTURE_REGIONS)) for col in a) and a.shape[1] == 15
    assert all(col.startswith(eps.DUTCH) for col in b) and b.shape[1] == 5
    assert c.shape[1] == 20 and d.shape[1] == 15 + 12
    col = "Finland:tailwind@2"
    assert a[col].iloc[5] == f[("Finland", "tailwind")].iloc[3]
    assert np.isnan(a[col].iloc[1])


def test_seasonal_terms_are_bounded() -> None:
    t = eps.seasonal_terms(pd.date_range("2020-09-15", periods=10))
    assert t.abs().max().max() <= 1
