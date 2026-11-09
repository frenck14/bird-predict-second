import re
from io import StringIO
from pathlib import Path

import pandas as pd


OBS_FILE = "data/raw/0019564-260928105237408.csv"
WEATHER_FILE = "data/raw/result (1).txt"
OUTPUT_FILE = "data/processed/bird_predict_dataset.csv"
WEATHER_COLUMNS = [
    "STN",
    "DATE",
    "DDVEC",
    "FG",
    "FHX",
    "TG",
    "TN",
    "TX",
    "RH",
    "PX",
]


def load_knmi_station(filepath, station_id):
    """Load one station's daily KNMI observations from a downloaded text file."""
    filepath = Path(filepath)
    if not filepath.is_file():
        raise FileNotFoundError(f"KNMI file does not exist: {filepath}")

    with filepath.open("r", encoding="utf-8") as file:
        rows = [
            line.strip()
            for line in file
            if re.match(r"^\s*\d{1,3}\s*,\s*\d{8}\s*,", line)
        ]

    if not rows:
        raise ValueError(f"No KNMI data rows found in {filepath}")

    all_weather = pd.read_csv(
        StringIO("\n".join(rows)),
        header=None,
        names=WEATHER_COLUMNS,
        skipinitialspace=True,
    )
    all_weather["STN"] = pd.to_numeric(all_weather["STN"], errors="raise").astype(int)
    weather = all_weather.loc[all_weather["STN"] == int(station_id)].copy()

    if weather.empty:
        available = sorted(all_weather["STN"].dropna().astype(int).unique().tolist())
        raise ValueError(
            f"Station {station_id} has no records in {filepath}; "
            f"stations present: {available}"
        )

    for column in WEATHER_COLUMNS[2:]:
        weather[column] = pd.to_numeric(weather[column], errors="coerce")
        weather[column] = weather[column].mask(weather[column] == -9999)
    for column in ["DDVEC", "FG", "FHX", "PX"]:
        weather[column] = weather[column].mask(weather[column] == -1)
    weather.loc[weather["RH"] == -1, "RH"] = 0

    weather["date"] = pd.to_datetime(
        weather["DATE"].astype("string"),
        format="%Y%m%d",
        errors="raise",
    )
    if weather["date"].duplicated().any():
        duplicated_dates = (
            weather.loc[weather["date"].duplicated(keep=False), "date"]
            .dt.strftime("%Y-%m-%d")
            .unique()
            .tolist()
        )
        raise ValueError(
            f"Station {station_id} has duplicate weather dates: "
            f"{duplicated_dates[:5]}"
        )

    return weather.sort_values("date").reset_index(drop=True)


def build_dataset():
    print("Loading observations...")
    obs = pd.read_csv(OBS_FILE, sep="\t")
    obs["date"] = pd.to_datetime(
        obs["eventDate"].astype("string").str[:10],
        errors="coerce",
    )
    valid_obs = obs.dropna(subset=["date"])
    daily_counts = (
        valid_obs.groupby("date")
        .size()
        .reset_index(name="n_records")
    )
    print(f"Observation days with valid dates: {len(daily_counts)}")
    print(f"Observations with missing or invalid dates: {obs['date'].isna().sum()}")

    print("Loading weather...")
    weather = load_knmi_station(WEATHER_FILE, station_id=235)
    print(f"Weather days: {len(weather)}")

    unmatched_observations = (~valid_obs["date"].isin(weather["date"])).sum()
    print(f"Observations outside KNMI date coverage: {unmatched_observations}")

    dataset = weather.merge(
        daily_counts,
        how="left",
        on="date",
        validate="one_to_one",
    )
    dataset["n_records"] = dataset["n_records"].fillna(0).astype(int)

    positive_counts = dataset.loc[dataset["n_records"] > 0, "n_records"]
    threshold = positive_counts.quantile(0.90)
    dataset["influx"] = (dataset["n_records"] >= threshold).astype(int)

    print(f"Positive days: {len(positive_counts)}")
    print(f"Influx threshold (90th percentile of positive days): {threshold}")
    print(f"Influx days: {int(dataset['influx'].sum())}")

    dataset.to_csv(OUTPUT_FILE, index=False)
    print(f"\nDataset saved: {OUTPUT_FILE}")
    return dataset


if __name__ == "__main__":
    build_dataset()
