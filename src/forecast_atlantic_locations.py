"""Forecast Atlantic Vagrancy hotspots on a 10 km grid across the North Sea region.

Per-cell probability = Atlantic Index probability x coastal suitability
x regional vagrancy suitability, clipped to [0, 1]. The suitability terms are
transparent expert heuristics driven by the site registry below; they are not
trained or validated against observations.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from pyproj import Transformer

if __package__:
    from .build_atlantic_vagrancy_dataset import (
        TARGET_COUNTRIES,
        load_all_occurrences,
    )
    from .forecast_location import (
        DAY_OF_YEAR_WINDOW,
        _calendar_day_number,
        _day_distance,
        _prepare_national_history,
    )
    from .predict_atlantic_vagrancy import DEFAULT_OUTPUT, risk_level
else:
    from build_atlantic_vagrancy_dataset import (
        TARGET_COUNTRIES,
        load_all_occurrences,
    )
    from forecast_location import (
        DAY_OF_YEAR_WINDOW,
        _calendar_day_number,
        _day_distance,
        _prepare_national_history,
    )
    from predict_atlantic_vagrancy import DEFAULT_OUTPUT, risk_level


LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
ATLANTIC_LOCATION_FORECAST_FILE = (
    ROOT / "outputs/atlantic_vagrancy_location_forecast.csv"
)
SIMPLE_LOCATION_FORECAST_FILE = ROOT / "outputs/atlantic_location_forecast.csv"
LOCATION_MAP_FILE = ROOT / "outputs/atlantic_location_forecast.png"
HORIZONS = {1: "Tomorrow", 3: "+3 days", 7: "+7 days", 14: "+14 days"}
TOP_N = 10
HOTSPOT_COLORS = LinearSegmentedColormap.from_list(
    "hotspot", ["#2b6cb0", "#7fb8e6", "#f7e04a", "#f08a24", "#d62728"]
)
ATLANTIC_DAILY_COUNTS_FILE = (
    ROOT / "outputs/atlantic_vagrancy_daily_counts.csv"
)
GRID_SIZE_METERS = 10_000
GRID_CRS = "EPSG:3035"
HISTORY_START_YEAR = 2010
COAST_FLOOR = 0.25
REGIONAL_FLOOR = 0.4
ATLANTIC_EXPOSURE_SCALE_KM = 500.0
WEST_FACING_BONUS = 0.05
KIND_WEIGHTS = {"island": 0.95, "headland": 0.85, "trap": 0.9}

WGS84_TO_GRID = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True)
GRID_TO_WGS84 = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True)


@dataclass(frozen=True)
class Site:
    name: str
    country: str
    latitude: float
    longitude: float
    kind: str
    radius_km: float
    west_facing: bool = False
    boost_group: str | None = None


# Multiplicative regional boost for classic Atlantic vagrant landfalls.
BONUS_BOOSTS = {
    "Scilly Isles": 1.6,
    "Fair Isle": 1.6,
    "Shetland": 1.5,
    "Outer Hebrides": 1.4,
    "Norfolk coast": 1.3,
    "East Yorkshire coast": 1.3,
    "Zeeland coast": 1.25,
    "Belgian coast": 1.25,
    "Skagen": 1.3,
}

# Extend this registry to add sites. Coordinates are approximate centres.
SITES = [
    Site("Scilly Isles", "GB", 49.92, -6.30, "island", 20, True, "Scilly Isles"),
    Site("Fair Isle", "GB", 59.53, -1.63, "island", 12, True, "Fair Isle"),
    Site("Shetland Mainland", "GB", 60.20, -1.30, "island", 45, True, "Shetland"),
    Site("Sumburgh Head", "GB", 59.85, -1.28, "headland", 20, False, "Shetland"),
    Site("Unst", "GB", 60.75, -0.90, "island", 25, False, "Shetland"),
    Site("Out Skerries", "GB", 60.42, -0.75, "island", 12, False, "Shetland"),
    Site("Lewis", "GB", 58.20, -6.60, "island", 45, True, "Outer Hebrides"),
    Site("Uists", "GB", 57.35, -7.30, "island", 45, True, "Outer Hebrides"),
    Site("Barra", "GB", 56.98, -7.45, "island", 25, True, "Outer Hebrides"),
    Site("St Kilda", "GB", 57.81, -8.58, "island", 15, True),
    Site("North Ronaldsay", "GB", 59.38, -2.43, "island", 15, False),
    Site("Orkney Mainland", "GB", 59.00, -3.20, "island", 35, False),
    Site("Isle of May", "GB", 56.19, -2.56, "island", 12, False),
    Site("Bardsey", "GB", 52.75, -4.80, "island", 15, True),
    Site("Skokholm and Skomer", "GB", 51.70, -5.28, "island", 15, True),
    Site("Portland Bill", "GB", 50.52, -2.46, "headland", 20, False),
    Site("Flamborough Head", "GB", 54.12, -0.08, "headland", 20, False, "East Yorkshire coast"),
    Site("Spurn", "GB", 53.58, 0.12, "trap", 20, False, "East Yorkshire coast"),
    Site("North Norfolk coast", "GB", 52.96, 1.05, "trap", 30, False, "Norfolk coast"),
    Site("Landguard", "GB", 51.94, 1.32, "trap", 15, False),
    Site("Dungeness", "GB", 50.91, 0.97, "trap", 20, False),
    Site("Cape Clear", "IE", 51.44, -9.50, "island", 20, True),
    Site("Mizen Head", "IE", 51.45, -9.82, "headland", 20, True),
    Site("Loop Head", "IE", 52.56, -9.93, "headland", 20, True),
    Site("Inishbofin", "IE", 53.61, -10.22, "island", 15, True),
    Site("Tory Island", "IE", 55.27, -8.25, "island", 15, True),
    Site("Saltee Islands", "IE", 52.12, -6.60, "island", 15, False),
    Site("Hook Head", "IE", 52.12, -6.93, "headland", 15, False),
    Site("Texel", "NL", 53.07, 4.78, "island", 20, False),
    Site("Vlieland and Terschelling", "NL", 53.32, 5.15, "island", 25, False),
    Site("Schiermonnikoog", "NL", 53.48, 6.20, "island", 15, False),
    Site("Maasvlakte", "NL", 51.95, 4.00, "trap", 15, False),
    Site("Zeebrugge", "BE", 51.33, 3.20, "trap", 15, False, "Belgian coast"),
    Site("De Panne", "BE", 51.10, 2.59, "trap", 15, False, "Belgian coast"),
    Site("Westkapelle", "NL", 51.53, 3.45, "trap", 25, False, "Zeeland coast"),
    Site("Blavand", "DK", 55.56, 8.10, "trap", 20, False),
    Site("Romo and Fano", "DK", 55.30, 8.45, "island", 20, False),
    Site("Hanstholm", "DK", 57.12, 8.60, "headland", 20, True),
    Site("Skagen", "DK", 57.74, 10.60, "trap", 20, False, "Skagen"),
]

# Points on the Atlantic-facing edge used to measure exposure.
ATLANTIC_ANCHORS = [
    (51.44, -9.50),
    (53.61, -10.22),
    (55.27, -8.25),
    (57.81, -8.58),
    (49.92, -6.30),
    (59.53, -1.63),
]


COMPASS = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]


def location_label(
    site_name: str,
    easting: int,
    northing: int,
    latitude: float,
    longitude: float,
    country: str,
    sites: list[Site] | None = None,
) -> str:
    """Name a cell after its nearest site, with a compass suffix if not the site's cell."""
    if not site_name:
        return f"{latitude:.2f}N {longitude:.2f}E ({country})"
    sites = SITES if sites is None else sites
    site_by_name = {site.name: site for site in sites}
    site = site_by_name[site_name]
    site_easting, site_northing = _grid_coordinates(
        np.array([site.latitude]), np.array([site.longitude])
    )
    if easting == site_easting[0] and northing == site_northing[0]:
        return site_name
    dx = (longitude - site.longitude) * math.cos(math.radians(site.latitude))
    dy = latitude - site.latitude
    angle = math.degrees(math.atan2(dy, dx)) % 360
    return f"{site_name} ({COMPASS[int((angle + 22.5) // 45) % 8]})"


def _grid_coordinates(
    latitudes: np.ndarray, longitudes: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    eastings, northings = WGS84_TO_GRID.transform(longitudes, latitudes)
    return (
        np.floor(np.asarray(eastings) / GRID_SIZE_METERS).astype(int)
        * GRID_SIZE_METERS,
        np.floor(np.asarray(northings) / GRID_SIZE_METERS).astype(int)
        * GRID_SIZE_METERS,
    )


def _distance_km(
    easting: np.ndarray, northing: np.ndarray, points: np.ndarray
) -> np.ndarray:
    """Distance in km from each cell centre to each (easting, northing) point."""
    return (
        np.hypot(
            easting[:, None] - points[None, :, 0],
            northing[:, None] - points[None, :, 1],
        )
        / 1000.0
    )


def _site_points(sites: list[Site]) -> np.ndarray:
    eastings, northings = WGS84_TO_GRID.transform(
        [site.longitude for site in sites], [site.latitude for site in sites]
    )
    return np.column_stack([eastings, northings])


def build_grid(
    occurrences: pd.DataFrame,
    sites: list[Site] | None = None,
) -> pd.DataFrame:
    """Return the 10 km cells with GBIF history or a registry site."""
    sites = SITES if sites is None else sites
    frame = occurrences.loc[
        occurrences["countryCode"].isin(TARGET_COUNTRIES)
    ].copy()
    frame["latitude"] = pd.to_numeric(frame["decimalLatitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["decimalLongitude"], errors="coerce")
    frame = frame.dropna(subset=["latitude", "longitude", "date"])
    frame["date"] = pd.to_datetime(frame["date"])
    easting, northing = _grid_coordinates(
        frame["latitude"].to_numpy(), frame["longitude"].to_numpy()
    )
    frame["grid_easting"], frame["grid_northing"] = easting, northing
    frame["cell_id"] = (
        frame["grid_easting"].astype(str) + "-" + frame["grid_northing"].astype(str)
    )
    historical = (
        frame.groupby("cell_id")
        .agg(
            grid_easting=("grid_easting", "first"),
            grid_northing=("grid_northing", "first"),
            country=("countryCode", lambda codes: codes.mode().iloc[0]),
            historical_records=("date", "size"),
            historical_years=("date", lambda dates: dates.dt.year.nunique()),
        )
        .reset_index()
    )

    site_easting, site_northing = _grid_coordinates(
        np.array([site.latitude for site in sites]),
        np.array([site.longitude for site in sites]),
    )
    site_cells = pd.DataFrame(
        {
            "grid_easting": site_easting,
            "grid_northing": site_northing,
            "country": [site.country for site in sites],
        }
    )
    site_cells["cell_id"] = (
        site_cells["grid_easting"].astype(str)
        + "-"
        + site_cells["grid_northing"].astype(str)
    )
    site_cells = site_cells.loc[
        ~site_cells["cell_id"].isin(historical["cell_id"])
    ].drop_duplicates("cell_id")
    site_cells["historical_records"] = 0
    site_cells["historical_years"] = 0
    grid = pd.concat([historical, site_cells], ignore_index=True)
    return grid.sort_values("cell_id").reset_index(drop=True)


def add_suitability(
    grid: pd.DataFrame,
    *,
    kind_weights: dict[str, float] | None = None,
    west_facing_bonus: float = WEST_FACING_BONUS,
    anchors: list[tuple[float, float]] | None = None,
    exposure_scale_km: float = ATLANTIC_EXPOSURE_SCALE_KM,
    boost_strength: float = 1.0,
    boosts: dict[str, float] | None = None,
    sites: list[Site] | None = None,
) -> pd.DataFrame:
    """Add coastal, regional and bonus suitability components to each cell.

    The keyword arguments let a species profile reshape the defaults, which
    describe the Atlantic guild.
    """
    sites = SITES if sites is None else sites
    kind_weights = KIND_WEIGHTS if kind_weights is None else kind_weights
    anchors = ATLANTIC_ANCHORS if anchors is None else anchors
    result = grid.copy()
    easting = result["grid_easting"].to_numpy() + GRID_SIZE_METERS / 2
    northing = result["grid_northing"].to_numpy() + GRID_SIZE_METERS / 2

    distances = _distance_km(easting, northing, _site_points(sites))
    radii = np.array([site.radius_km for site in sites])
    kind_weight = np.array(
        [
            kind_weights[site.kind] + (west_facing_bonus if site.west_facing else 0)
            for site in sites
        ]
    )
    site_scores = kind_weight[None, :] * np.exp(-((distances / radii) ** 2))
    best_site = site_scores.argmax(axis=1)
    site_score = site_scores.max(axis=1)
    result["coastal_suitability"] = COAST_FLOOR + (1 - COAST_FLOOR) * np.clip(
        site_score, 0, 1
    )
    result["nearest_site"] = [
        sites[index].name if score > 0.05 else "" for index, score in zip(best_site, site_score)
    ]

    anchor_array = np.array(anchors)
    anchor_easting, anchor_northing = WGS84_TO_GRID.transform(
        anchor_array[:, 1], anchor_array[:, 0]
    )
    atlantic_distance = _distance_km(
        easting, northing, np.column_stack([anchor_easting, anchor_northing])
    ).min(axis=1)
    result["atlantic_distance_km"] = atlantic_distance
    exposure = np.exp(-atlantic_distance / exposure_scale_km)

    boost = np.ones(len(result))
    for group, group_boost in (BONUS_BOOSTS if boosts is None else boosts).items():
        indexes = [
            index for index, site in enumerate(sites) if site.boost_group == group
        ]
        group_score = np.exp(-((distances[:, indexes] / radii[indexes]) ** 2)).max(
            axis=1
        )
        boost = np.maximum(
            boost, 1 + (group_boost - 1) * boost_strength * group_score
        )
    result["bonus_boost"] = boost
    result["regional_suitability"] = (
        REGIONAL_FLOOR + (1 - REGIONAL_FLOOR) * exposure
    ) * boost
    return result


def _seasonal_expected_probability(
    daily_counts: pd.DataFrame, target_date: pd.Timestamp
) -> float:
    counts = daily_counts.rename(columns={"count": "record_count"})
    counts["date"] = pd.to_datetime(counts["date"])
    counts = counts.loc[counts["date"].dt.year.ge(HISTORY_START_YEAR)]
    full_index = pd.date_range(
        counts["date"].min(), counts["date"].max(), freq="D"
    )
    history = (
        counts.set_index("date")["record_count"]
        .reindex(full_index, fill_value=0)
        .rename_axis("date")
        .reset_index()
    )
    history = _prepare_national_history(history)
    history = history.loc[history["year"].lt(target_date.year)]
    window = history.loc[
        _day_distance(
            history["calendar_day"].to_numpy(),
            _calendar_day_number(target_date),
        )
        <= DAY_OF_YEAR_WINDOW
    ]
    if window.empty:
        raise ValueError(
            f"No earlier-year seasonal history for {target_date.date()}."
        )
    return float((window["record_count"].ge(1).sum() + 0.5) / (len(window) + 1))


def calculate_atlantic_location_forecast(
    cells: pd.DataFrame,
    daily_counts: pd.DataFrame,
    national_forecast: pd.DataFrame,
    date_weights: dict[pd.Timestamp, float] | None = None,
    risk_function=risk_level,
    sites: list[Site] | None = None,
) -> pd.DataFrame:
    """Combine the national Atlantic probability with cell suitability.

    Cells may carry a species_suitability column; date_weights then scales it
    per date (the species' seasonal occurrence curve).
    """
    forecast = national_forecast.loc[:, ["date", "probability"]].copy()
    forecast["date"] = pd.to_datetime(forecast["date"]).dt.normalize()
    forecast["probability"] = pd.to_numeric(forecast["probability"], errors="coerce")
    if (
        forecast.empty
        or forecast["date"].duplicated().any()
        or forecast["probability"].isna().any()
        or not forecast["probability"].between(0, 1).all()
    ):
        raise ValueError(
            "National forecast must contain unique dates and probabilities "
            "between zero and one."
        )

    sites = SITES if sites is None else sites
    has_species = "species_suitability" in cells.columns
    base_suitability = cells["coastal_suitability"] * cells["regional_suitability"]
    centres_longitude, centres_latitude = GRID_TO_WGS84.transform(
        cells["grid_easting"].to_numpy() + GRID_SIZE_METERS / 2,
        cells["grid_northing"].to_numpy() + GRID_SIZE_METERS / 2,
    )
    locations = [
        location_label(site, int(e), int(n), float(lat), float(lon), country, sites)
        for site, e, n, lat, lon, country in zip(
            cells["nearest_site"],
            cells["grid_easting"],
            cells["grid_northing"],
            centres_latitude,
            centres_longitude,
            cells["country"],
        )
    ]
    frames = []
    for target in forecast.itertuples(index=False):
        national_expected = _seasonal_expected_probability(
            daily_counts, pd.Timestamp(target.date)
        )
        frame = cells.copy()
        suitability = base_suitability
        if has_species:
            weight = (date_weights or {}).get(pd.Timestamp(target.date), 1.0)
            frame["species_suitability"] = cells["species_suitability"] * weight
            suitability = base_suitability * frame["species_suitability"]
        suitability = suitability.to_numpy()
        frame["date"] = pd.Timestamp(target.date)
        frame["center_latitude"] = centres_latitude
        frame["center_longitude"] = centres_longitude
        frame["location"] = locations
        frame["atlantic_national_probability"] = float(target.probability)
        frame["national_expected_probability"] = national_expected
        frame["expected_probability"] = np.clip(
            national_expected * suitability, 0, 1
        )
        frame["forecast_probability"] = np.clip(
            float(target.probability) * suitability, 0, 1
        )
        frame["anomaly_score"] = (
            frame["forecast_probability"] - frame["expected_probability"]
        )
        frame["risk_level"] = frame["forecast_probability"].map(risk_function)
        frame["rank"] = (
            frame["forecast_probability"]
            .rank(method="first", ascending=False)
            .astype(int)
        )
        frames.append(frame)

    result = pd.concat(frames, ignore_index=True)
    columns = [
        "date",
        "cell_id",
        "country",
        "location",
        "grid_easting",
        "grid_northing",
        "center_latitude",
        "center_longitude",
        "nearest_site",
        "historical_records",
        "historical_years",
        *(
            ["occupied_years", "cell_occupancy", "species_suitability"]
            if has_species
            else []
        ),
        "coastal_suitability",
        "regional_suitability",
        "bonus_boost",
        "atlantic_distance_km",
        "atlantic_national_probability",
        "national_expected_probability",
        "expected_probability",
        "forecast_probability",
        "anomaly_score",
        "risk_level",
        "rank",
    ]
    return result.loc[:, columns].sort_values(
        ["date", "rank"], kind="stable"
    ).reset_index(drop=True)


def simple_location_forecast(result: pd.DataFrame) -> pd.DataFrame:
    """Return the compact public schema from the detailed location forecast."""
    simple = result.rename(
        columns={
            "center_latitude": "latitude",
            "center_longitude": "longitude",
            "forecast_probability": "probability",
        }
    )
    return simple.loc[
        :,
        [
            "date",
            "location",
            "country",
            "latitude",
            "longitude",
            "probability",
            "anomaly_score",
            "rank",
        ],
    ]


def horizon_dates(dates: pd.Series) -> dict[int, pd.Timestamp]:
    """Map tomorrow, +3, +7 and +14 days to forecast dates."""
    available = sorted(pd.to_datetime(dates).dt.normalize().unique())
    if not available:
        raise ValueError("Location forecast contains no dates.")
    start = pd.Timestamp(available[0])
    selected = {
        horizon: start + pd.Timedelta(days=horizon - 1) for horizon in HORIZONS
    }
    missing = {h: d.date() for h, d in selected.items() if d not in set(available)}
    if missing:
        raise ValueError(f"Location forecast is missing horizon dates: {missing}.")
    return selected


def top_hotspots(result: pd.DataFrame, top_n: int = TOP_N) -> dict[int, pd.DataFrame]:
    """Return the top-N cells for each forecast horizon, highest probability first."""
    top: dict[int, pd.DataFrame] = {}
    for horizon, day in horizon_dates(result["date"]).items():
        selected = result.loc[result["date"].eq(day)]
        top[horizon] = selected.sort_values("rank").head(top_n)
    return top


def save_location_map(
    result: pd.DataFrame,
    output_path: Path = LOCATION_MAP_FILE,
    title: str = "Atlantic Vagrancy hotspots",
) -> Path:
    """Draw one panel per horizon: red = strongest, yellow = moderate, blue = low."""
    top = top_hotspots(result)
    days = horizon_dates(result["date"])
    ceiling = max(float(result["forecast_probability"].max()), 1e-9)
    figure, axes = plt.subplots(2, 2, figsize=(15, 11), sharex=True, sharey=True)
    scatter = None
    for axis, (horizon, label) in zip(axes.ravel(), HORIZONS.items()):
        day = result.loc[result["date"].eq(days[horizon])].sort_values(
            "forecast_probability"
        )
        scatter = axis.scatter(
            day["center_longitude"],
            day["center_latitude"],
            c=day["forecast_probability"],
            cmap=HOTSPOT_COLORS,
            vmin=0,
            vmax=ceiling,
            marker="s",
            s=70,
            edgecolors="#333333",
            linewidths=0.3,
        )
        for rank, row in enumerate(top[horizon].itertuples(), start=1):
            axis.annotate(
                str(rank),
                (row.center_longitude, row.center_latitude),
                fontsize=7,
                ha="center",
                va="center",
                fontweight="bold",
            )
        listing = "\n".join(
            f"{rank}. {row.location} {row.forecast_probability:.1%}"
            for rank, row in enumerate(top[horizon].itertuples(), start=1)
        )
        axis.text(
            0.99,
            0.99,
            listing,
            transform=axis.transAxes,
            fontsize=6.5,
            va="top",
            ha="right",
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
        )
        axis.set_title(f"{label} ({days[horizon]:%Y-%m-%d})")
        axis.set_aspect(1 / math.cos(math.radians(54)))
        axis.grid(alpha=0.25)
    for axis in axes[1]:
        axis.set_xlabel("Longitude")
    for axis in axes[:, 0]:
        axis.set_ylabel("Latitude")
    figure.suptitle(f"{title} (red = strongest, blue = low)")
    figure.colorbar(
        scatter, ax=axes.ravel().tolist(), label="Cell probability", shrink=0.7
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(figure)
    return output_path


def hotspot_metadata(result: pd.DataFrame) -> dict[str, object]:
    """Summarise the tomorrow hotspots for the run metadata."""
    tomorrow = top_hotspots(result)[1]
    strongest = tomorrow.iloc[0]
    return {
        "strongest_location": str(strongest["location"]),
        "strongest_probability": float(strongest["forecast_probability"]),
        "top10_locations": [
            {
                "rank": int(row.rank),
                "location": str(row.location),
                "country": str(row.country),
                "probability": float(row.forecast_probability),
            }
            for row in tomorrow.itertuples()
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_atlantic_location_forecast(
    national_forecast: pd.DataFrame,
    *,
    output_path: Path = ATLANTIC_LOCATION_FORECAST_FILE,
    daily_counts_path: Path = ATLANTIC_DAILY_COUNTS_FILE,
    simple_output_path: Path | None = None,
    map_path: Path | None = None,
    sites: list[Site] | None = None,
) -> pd.DataFrame:
    """Load GBIF history, calculate hotspots and write the CSV and map outputs."""
    if not daily_counts_path.is_file():
        raise FileNotFoundError(f"Daily counts not found: {daily_counts_path}")
    occurrences = load_all_occurrences()
    cells = add_suitability(build_grid(occurrences, sites=sites), sites=sites)
    LOGGER.info("Atlantic hotspot grid: %d cells", len(cells))
    result = calculate_atlantic_location_forecast(
        cells,
        pd.read_csv(daily_counts_path),
        national_forecast,
        sites=sites,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, date_format="%Y-%m-%d")
    if simple_output_path is not None:
        simple_location_forecast(result).to_csv(
            simple_output_path, index=False, date_format="%Y-%m-%d"
        )
    if map_path is not None:
        save_location_map(result, map_path)
    return result


def cell_polygon(grid_easting: int, grid_northing: int) -> list[list[float]]:
    """Return a 10 km EPSG:3035 square as closed WGS84 [lon, lat] coordinates."""
    east, north = float(grid_easting), float(grid_northing)
    x = [east, east + GRID_SIZE_METERS, east + GRID_SIZE_METERS, east, east]
    y = [north, north, north + GRID_SIZE_METERS, north + GRID_SIZE_METERS, north]
    longitudes, latitudes = GRID_TO_WGS84.transform(x, y)
    return [[float(lon), float(lat)] for lon, lat in zip(longitudes, latitudes)]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = build_atlantic_location_forecast(
        pd.read_csv(DEFAULT_OUTPUT),
        simple_output_path=SIMPLE_LOCATION_FORECAST_FILE,
        map_path=LOCATION_MAP_FILE,
    )
    for horizon, frame in top_hotspots(result).items():
        print(f"\n{HORIZONS[horizon]}")
        print(
            frame[["rank", "location", "country", "forecast_probability"]].to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
