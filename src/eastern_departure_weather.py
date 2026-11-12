"""Feasibility audit: can source-region departure weather inform eastern vagrant arrivals in NL?

Exploratory, read-only with respect to the production models. Source-region weather is not part of
the local KNMI archive (Dutch stations only), so it is downloaded once from the Open-Meteo ERA5
archive and cached.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/eastern_departure_weather"
CACHE = ROOT / "data/cache/eastern_departure_weather_daily.csv"
CSV_PATH = OUT / "departure_feature_audit.csv"
MD_PATH = OUT / "departure_feature_summary.md"
API = "https://archive-api.open-meteo.com/v1/archive"
START, END = "2010-09-01", "2025-12-31"
# Fixed boxes: (south, north, west, east). Weather is averaged over a 2x2 grid of box-quarter centres.
REGIONS = {
    "Finland": (60.0, 68.0, 21.0, 31.5),
    "Baltics": (53.9, 59.7, 20.9, 28.2),
    "NW Russia": (57.0, 67.0, 31.6, 45.0),
}
NETHERLANDS = (52.2, 5.3)
DAILY = ["temperature_2m_mean", "pressure_msl_mean", "precipitation_sum", "wind_speed_10m_mean",
         "wind_direction_10m_dominant"]
SEASON = ("09-15", "11-20")
LAGS = (1, 2, 3)
COLD_FRONT_DROP_C = -4.0
MIN_EVENT_DAYS = 30
GUILD = "Eastern guild (all species)"
FEATURES = [
    "mean_temperature", "temperature_anomaly", "pressure", "pressure_change_24h", "precipitation",
    "precipitation_anomaly", "mean_wind_speed", "mean_wind_direction", "tailwind", "crosswind",
    "days_since_cold_front",
]


def grid_points(box: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    south, north, west, east = box
    lats = [south + (north - south) * f for f in (0.25, 0.75)]
    lons = [west + (east - west) * f for f in (0.25, 0.75)]
    return [(lat, lon) for lat in lats for lon in lons]


def bearing(origin: tuple[float, float], target: tuple[float, float]) -> float:
    """Initial great-circle bearing in degrees from origin to target."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*origin, *target))
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def region_centre(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[1]) / 2, (box[2] + box[3]) / 2)


def _request(points: list[tuple[float, float]], start: str, end: str) -> list[dict]:
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
        "start_date": start, "end_date": end, "daily": ",".join(DAILY),
        "wind_speed_unit": "ms", "timezone": "UTC",
    }
    for attempt in range(6):
        try:
            response = requests.get(API, params=params, timeout=30)
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
            continue
        if response.status_code == 200:
            payload = response.json()
            return payload if isinstance(payload, list) else [payload]
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"Open-Meteo request failed for {start}..{end}")


def fetch_weather(cache: Path = CACHE, refresh: bool = False) -> pd.DataFrame:
    """Daily weather per grid point (long format), cached after the first download."""
    if cache.is_file() and not refresh:
        return pd.read_csv(cache, parse_dates=["date"])
    frames = []
    for region, box in REGIONS.items():
        points = grid_points(box)
        for year in range(int(START[:4]), int(END[:4]) + 1):
            start = max(START, f"{year}-01-01")
            end = min(END, f"{year}-12-31")
            for index, payload in enumerate(_request(points, start, end)):
                daily = pd.DataFrame(payload["daily"]).rename(columns={"time": "date"})
                frames.append(daily.assign(region=region, point=index))
            time.sleep(0.5)
    weather = pd.concat(frames, ignore_index=True)
    weather["date"] = pd.to_datetime(weather["date"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(cache, index=False)
    return weather


def region_daily(weather: pd.DataFrame, region: str) -> pd.DataFrame:
    """Region daily summary: grid-point means; wind direction from the mean wind vector."""
    part = weather.loc[weather["region"].eq(region)].copy()
    radians = np.radians(part["wind_direction_10m_dominant"])
    part["u"] = -part["wind_speed_10m_mean"] * np.sin(radians)
    part["v"] = -part["wind_speed_10m_mean"] * np.cos(radians)
    grouped = part.groupby("date").agg(
        temperature=("temperature_2m_mean", "mean"), pressure=("pressure_msl_mean", "mean"),
        precipitation=("precipitation_sum", "mean"), speed=("wind_speed_10m_mean", "mean"),
        u=("u", "mean"), v=("v", "mean"),
    ).sort_index()
    grouped["direction_from"] = (np.degrees(np.arctan2(-grouped["u"], -grouped["v"])) + 360) % 360
    return grouped.drop(columns=["u", "v"])


def climatology_anomaly(series: pd.Series, window: int = 15) -> pd.Series:
    """Anomaly versus a circularly smoothed day-of-year mean (audit use only, not a forecast input)."""
    doy = series.index.dayofyear.where(series.index.dayofyear <= 365, 365)
    mean = series.groupby(doy).mean().reindex(range(1, 366))
    wrapped = pd.concat([mean.iloc[-window:], mean, mean.iloc[:window]])
    smooth = wrapped.rolling(2 * window + 1, center=True, min_periods=1).mean().iloc[window:-window]
    return series - pd.Series(doy, index=series.index).map(smooth)


def days_since_event(flag: pd.Series, cap: int = 30) -> pd.Series:
    out, count = [], cap
    for value in flag.fillna(False).to_numpy():
        count = 0 if value else min(count + 1, cap)
        out.append(count)
    return pd.Series(out, index=flag.index, dtype=float)


def region_features(daily: pd.DataFrame, box: tuple[float, float, float, float]) -> pd.DataFrame:
    toward = (daily["direction_from"] + 180) % 360
    track = bearing(region_centre(box), NETHERLANDS)
    angle = np.radians(toward - track)
    temp_change = daily["temperature"].diff()
    pressure_change = daily["pressure"].diff()
    front = temp_change.le(COLD_FRONT_DROP_C)
    return pd.DataFrame(
        {
            "mean_temperature": daily["temperature"],
            "temperature_anomaly": climatology_anomaly(daily["temperature"]),
            "pressure": daily["pressure"],
            "pressure_change_24h": pressure_change,
            "precipitation": daily["precipitation"],
            "precipitation_anomaly": climatology_anomaly(daily["precipitation"]),
            "mean_wind_speed": daily["speed"],
            "mean_wind_direction": toward,
            "tailwind": daily["speed"] * np.cos(angle),
            "crosswind": (daily["speed"] * np.sin(angle)).abs(),
            "days_since_cold_front": days_since_event(front),
        }
    )


def all_features(weather: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for region, box in REGIONS.items():
        feats = region_features(region_daily(weather, region), box)
        feats.columns = pd.MultiIndex.from_product([[region], feats.columns])
        frames.append(feats)
    return pd.concat(frames, axis=1)


def load_event_labels(occurrences: pd.DataFrame) -> pd.DataFrame:
    """Daily Dutch record counts per species and for the whole eastern guild."""
    nl = occurrences.loc[occurrences["countryCode"].eq("NL")].copy()
    nl["date"] = pd.to_datetime(nl["date"]).dt.normalize()
    index = pd.date_range("2011-01-01", END)
    counts = nl.groupby(["species", "date"]).size().unstack(0).reindex(index, fill_value=0).fillna(0)
    counts[GUILD] = counts.sum(axis=1)
    return counts


def in_season(index: pd.DatetimeIndex) -> np.ndarray:
    key = index.strftime("%m-%d")
    return (key >= SEASON[0]) & (key <= SEASON[1])


def event_flags(counts: pd.Series) -> pd.Series:
    """Season-day top decile of daily Dutch records, at least 1 (pipeline's influx definition)."""
    season = counts.loc[in_season(counts.index)]
    return season.ge(max(float(np.percentile(season, 90)), 1.0))


def audit(features: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for target in counts.columns:
        events = event_flags(counts[target])
        for (region, name), series in features.items():
            values = np.sin(np.radians(series)) if name == "mean_wind_direction" else series
            adjusted = climatology_anomaly(values)
            for lag in LAGS:
                frame = pd.DataFrame(
                    {
                        "x": adjusted.shift(lag).reindex(events.index),
                        "raw": values.shift(lag).reindex(events.index),
                        "y": events.astype(float),
                    }
                ).dropna()
                rows.append(_score(target, region, name, lag, frame, int(events.sum())))
    table = pd.DataFrame(rows)
    table["q_value"] = benjamini_hochberg(table["p_value"].fillna(1.0).to_numpy())
    table["potential_rank"] = table.groupby("species")["abs_mean_rho"].rank(ascending=False, method="first")
    return table.sort_values(["species", "potential_rank"]).reset_index(drop=True)


def yearly_rho(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = []
    for _, year in frame.groupby(frame.index.year):
        if year["y"].nunique() == 2 and year[column].nunique() > 1:
            values.append(stats.spearmanr(year[column], year["y"])[0])
    return np.array(values, float)


def _score(species: str, region: str, feature: str, lag: int, frame: pd.DataFrame, events: int) -> dict:
    """Primary statistics use the seasonally adjusted feature; raw_* keep the unadjusted correlation."""
    row = {"species": species, "region": region, "feature": feature, "lag_days": lag,
           "event_days": events, "n_days": len(frame), "pooled_spearman": np.nan, "auc": np.nan,
           "mean_yearly_rho": np.nan, "abs_mean_rho": np.nan, "sign_consistency": np.nan,
           "raw_mean_yearly_rho": np.nan, "years": 0, "p_value": np.nan, "uncertain": events < MIN_EVENT_DAYS}
    if frame["y"].nunique() < 2 or frame["x"].nunique() < 2:
        return row
    row["pooled_spearman"] = float(stats.spearmanr(frame["x"], frame["y"])[0])
    positives = frame.loc[frame["y"].eq(1), "x"]
    negatives = frame.loc[frame["y"].eq(0), "x"]
    row["auc"] = float(stats.mannwhitneyu(positives, negatives).statistic / (len(positives) * len(negatives)))
    raw = yearly_rho(frame, "raw")
    if len(raw) >= 5:
        row["raw_mean_yearly_rho"] = float(raw.mean())
    yearly = yearly_rho(frame, "x")
    row["years"] = len(yearly)
    if len(yearly) >= 5:
        row["mean_yearly_rho"] = float(yearly.mean())
        row["abs_mean_rho"] = abs(row["mean_yearly_rho"])
        row["sign_consistency"] = float((np.sign(yearly) == np.sign(yearly.mean())).mean())
        row["p_value"] = float(stats.ttest_1samp(yearly, 0).pvalue) if yearly.std() > 0 else np.nan
    return row


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    order = np.argsort(p)
    ranked = p[order] * len(p) / (np.arange(len(p)) + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1.0)
    out = np.empty_like(adjusted)
    out[order] = adjusted
    return out


def best_per_feature(table: pd.DataFrame, species: str) -> pd.DataFrame:
    part = table.loc[table["species"].eq(species) & table["abs_mean_rho"].notna()]
    best = part.loc[part.groupby(["region", "feature"])["abs_mean_rho"].idxmax()]
    return best.sort_values("abs_mean_rho", ascending=False)


def feature_ranking(table: pd.DataFrame, species: list[str]) -> pd.DataFrame:
    """Pooled ranking across reliable species: mean |yearly rho| of each feature's best region/lag."""
    rows = []
    for name in species:
        best = best_per_feature(table, name)
        rows.append(best.assign(species=name))
    combined = pd.concat(rows)
    return (
        combined.groupby("feature")
        .agg(mean_abs_rho=("abs_mean_rho", "mean"), best_abs_rho=("abs_mean_rho", "max"),
             significant=("q_value", lambda q: int((q < 0.05).sum())), species=("species", "nunique"))
        .sort_values("mean_abs_rho", ascending=False)
    )


def write_report(table: pd.DataFrame, counts: pd.DataFrame, path: Path = MD_PATH) -> None:
    flags = {name: int(event_flags(counts[name]).sum()) for name in counts.columns}
    reliable = [n for n, e in flags.items() if e >= MIN_EVENT_DAYS and n != GUILD]
    lines = [
        "# Departure-weather feasibility: eastern vagrants arriving in the Netherlands", "",
        "Exploratory audit only: no model was changed or retrained. Question: which source-region "
        "weather variables look most informative for eastern vagrant arrivals?", "",
        "## Method", "",
        "- **Weather source:** the local archive holds Dutch KNMI stations only, so source-region weather "
        "was downloaded once from the Open-Meteo ERA5 archive and cached at "
        "`data/cache/eastern_departure_weather_daily.csv` (2010-09-01 to 2025-12-31).",
        "- **Regions (fixed boxes, south-north, west-east):** "
        + "; ".join(f"{r} {b[0]}-{b[1]}N, {b[2]}-{b[3]}E" for r, b in REGIONS.items())
        + ". Each region is a mean over a 2x2 grid of box-quarter centres. Wind direction comes from the mean wind vector.",
        "- **Features:** temperature, anomaly, pressure, 24h pressure change, precipitation, anomaly, wind speed, "
        "wind direction (the direction the wind blows toward), tailwind toward the Netherlands "
        "(wind component along the region-to-NL bearing), crosswind (absolute perpendicular component), and days "
        f"since the last major cold front (a 24h drop in mean temperature of {abs(COLD_FRONT_DROP_C):.0f} C or more, capped at 30). "
        "Anomalies use a day-of-year climatology over the whole archive, which is acceptable for an audit but "
        "would need a cutoff-safe climatology in a production feature.",
        "- **Events:** Dutch records per day from the cached GBIF eastern-guild files, 2011-2025, "
        f"restricted to the autumn passage ({SEASON[0]} to {SEASON[1]}). An event day is in the top decile of "
        "that species' season-day counts, minimum 1 record, matching the pipeline's influx rule. The guild row sums all eastern-registry species with Dutch records.",
        f"- **Lags:** weather {', '.join(map(str, LAGS))} days before the Dutch record date (departure precedes arrival).",
        "- **Seasonal adjustment:** every feature is converted to its anomaly from the day-of-year climatology before "
        "correlating. Raw values (for example mean temperature) fall through autumn just as arrivals of late species rise, "
        "which would otherwise be a calendar effect, not a weather effect. The CSV keeps the raw correlation in `raw_mean_yearly_rho`.",
        "- **Statistic:** Spearman correlation between a feature and the event flag is computed within each autumn "
        "and averaged across years. This avoids the shared seasonal trend and the strong day-to-day autocorrelation "
        "that would make a pooled p-value overconfident. P-values are t-tests across yearly correlations, "
        "Benjamini-Hochberg adjusted over all tests. Effect sizes are small, so |mean yearly rho| ranks potential, not significance alone.", "",
        "## Event days", "", "| Species | Event days (autumn 2011-2025) | Status |", "|---|---:|---|",
    ]
    for name, events in flags.items():
        status = "OK" if events >= MIN_EVENT_DAYS else "uncertain (fewer than 30 event days)"
        lines.append(f"| {name} | {events} | {status} |")
    ranking = feature_ranking(table, reliable + [GUILD])
    lines += ["", "## Feature ranking", "",
              "Mean over the reliable species and the guild of each feature's best region and lag.", "",
              "| Rank | Feature | Mean abs rho | Best abs rho | Significant tests (q<0.05) |", "|---:|---|---:|---:|---:|"]
    for i, (feature, r) in enumerate(ranking.iterrows(), 1):
        lines.append(f"| {i} | {feature} | {r['mean_abs_rho']:.3f} | {r['best_abs_rho']:.3f} | {int(r['significant'])} |")
    for name in [GUILD, *reliable]:
        lines += ["", f"## {name}: top region/feature/lag", "",
                  "| Region | Feature | Lag | Mean yearly rho | Sign consistency | AUC | q |", "|---|---|---:|---:|---:|---:|---:|"]
        for _, r in best_per_feature(table, name).head(5).iterrows():
            lines.append(f"| {r['region']} | {r['feature']} | {int(r['lag_days'])} | {r['mean_yearly_rho']:+.3f} | "
                         f"{r['sign_consistency']:.0%} | {r['auc']:.3f} | {r['q_value']:.3f} |")
    lines += ["", "## Species with too little data", ""]
    for name, events in flags.items():
        if events < MIN_EVENT_DAYS:
            lines.append(f"- {name}: {events} event days; results are in the CSV but flagged uncertain and excluded from the ranking.")
    lines += ["", "## Answer", ""] + answer(table, ranking, reliable)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def answer(table: pd.DataFrame, ranking: pd.DataFrame, reliable: list[str]) -> list[str]:
    top = ranking.head(3)
    significant = int(table.loc[~table["uncertain"] | table["species"].eq(GUILD), "q_value"].lt(0.05).sum())
    guild = best_per_feature(table, GUILD).head(3)
    lines = [
        "Most informative variables by mean |yearly rho|: "
        + ", ".join(f"{f} ({r['mean_abs_rho']:.3f})" for f, r in top.iterrows()) + ".",
        "Strongest guild signals: "
        + "; ".join(f"{r['region']} {r['feature']} lag {int(r['lag_days'])} (rho {r['mean_yearly_rho']:+.3f})" for _, r in guild.iterrows()) + ".",
        f"{significant} of the tests on reliable species and the guild pass q<0.05 after multiple-comparison control.",
    ]
    strongest = float(ranking["best_abs_rho"].max())
    lines.append(
        f"Each ranking value is the best of 9 region/lag combinations, so even pure noise gives roughly 0.04-0.06 with about 15 autumns; "
        f"only values clearly above that are worth attention. The largest effect is |rho| of about {strongest:.2f}, so no single "
        "variable explains much. The evidence is weak: source-region weather has at most modest, species-specific signal "
        "(cold-air and front timing, crosswind), and none for the guild as a whole. A fair next step is a strict-cutoff rolling "
        "test of a few lagged features, compared with the current model, before any claim of improvement."
    )
    return lines


def main() -> None:
    from .build_eastern_vagrancy_dataset import load_all_occurrences

    weather = fetch_weather()
    features = all_features(weather)
    counts = load_event_labels(load_all_occurrences(compact=True))
    table = audit(features, counts)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(CSV_PATH, index=False)
    write_report(table, counts)
    print(table.groupby("species")["event_days"].first())


if __name__ == "__main__":
    main()
