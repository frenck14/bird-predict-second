"""Scoring integration for Next Dutch Firsts with live data.

Modifies the prediction model to use live data when available,
with fallback to historical datasets and manual values.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
LIVE_DATA_DIR = ROOT / "inputs/next_dutch_firsts/live"


@dataclass
class DataSource:
    """Metadata about which source provided a value."""
    name: str  # e.g., "Dutch Avifauna", "eBird", "Manual"
    priority: int  # 1=high (live), 2=medium (historical), 3=low (manual)
    quality: str  # "verified", "provisional", "unverified"
    timestamp: datetime


@dataclass
class ScoringInput:
    """Input to scoring model with source attribution."""
    species_name: str
    scientific_name: str
    
    # European occurrence data
    corvo_records: int = 0
    ireland_records: int = 0
    uk_records: int = 0
    france_records: int = 0
    spain_records: int = 0
    portugal_records: int = 0
    
    # Temporal data
    corvo_latest_year: int | None = None
    ireland_latest_year: int | None = None
    uk_latest_year: int | None = None
    
    # Dutch data
    dutch_record_count: int = 0
    dutch_latest_year: int | None = None
    
    # Recent activity
    recent_records: int = 0  # Records in last 3 years
    last_10yr_records: int = 0  # Records in last 10 years
    
    # Atmospheric conditions
    atlantic_index: float = 0.0  # BirdCast index
    eastern_drift_index: float = 0.0  # BirdCast index
    
    # Source attribution
    dutch_source: DataSource | None = None
    atlantic_source: DataSource | None = None
    momentum_source: DataSource | None = None


class LiveDataScorer:
    """Scores species using live data with fallback logic."""
    
    def __init__(self):
        self.dutch_rarity_file = LIVE_DATA_DIR / "dutch_rarity_records.parquet"
        self.european_occurrences_file = LIVE_DATA_DIR / "european_occurrences.parquet"
        self.season_activity_file = LIVE_DATA_DIR / "current_season_activity.parquet"
        self.species_master_file = ROOT / "inputs/next_dutch_firsts/species_master.csv"
        
        self.dutch_records: pd.DataFrame | None = None
        self.european_records: pd.DataFrame | None = None
        self.season_records: pd.DataFrame | None = None
        self.species_master: pd.DataFrame | None = None
    
    def load_data(self) -> None:
        """Load all available data sources."""
        logger.info("Loading live data for scoring...")
        
        # Load parquet files if they exist
        if self.dutch_rarity_file.exists():
            self.dutch_records = pd.read_parquet(self.dutch_rarity_file)
            logger.info(f"  Loaded {len(self.dutch_records)} Dutch records")
        
        if self.european_occurrences_file.exists():
            self.european_records = pd.read_parquet(self.european_occurrences_file)
            logger.info(f"  Loaded {len(self.european_records)} European records")
        
        if self.season_activity_file.exists():
            self.season_records = pd.read_parquet(self.season_activity_file)
            logger.info(f"  Loaded {len(self.season_records)} season activity records")
        
        # Load species master for manual values and historical data
        if self.species_master_file.exists():
            self.species_master = pd.read_csv(self.species_master_file)
            logger.info(f"  Loaded {len(self.species_master)} species from master")
    
    def get_dutch_data(self, species_name: str) -> tuple[int, int | None, DataSource | None]:
        """Retrieve Dutch record data for a species.
        
        Priority: Live data > Manual values
        
        Args:
            species_name: Common name of species.
        
        Returns:
            Tuple of (record_count, latest_year, source).
        """
        record_count = 0
        latest_year = None
        source = None
        
        # Try live data first
        if self.dutch_records is not None:
            live = self.dutch_records[self.dutch_records["species_name"] == species_name]
            if not live.empty:
                row = live.iloc[0]
                record_count = int(row["confidence_score"] * 100)  # Placeholder
                obs_date = pd.to_datetime(row["observation_date"])
                latest_year = obs_date.year
                source = DataSource(
                    name="Dutch Avifauna (CDNA)",
                    priority=1,
                    quality="verified",
                    timestamp=datetime.now(),
                )
                return record_count, latest_year, source
        
        # Fallback to manual values
        if self.species_master is not None:
            master = self.species_master[self.species_master["species"] == species_name]
            if not master.empty:
                row = master.iloc[0]
                if pd.notna(row.get("dutch_records")):
                    record_count = int(row["dutch_records"])
                    if pd.notna(row.get("last_dutch_record")):
                        latest_year = int(row["last_dutch_record"])
                    source = DataSource(
                        name="Manual (Species Master)",
                        priority=3,
                        quality="unverified",
                        timestamp=datetime.now(),
                    )
                    return record_count, latest_year, source
        
        return 0, None, None
    
    def get_recent_activity(self, species_name: str, days: int = 365) -> tuple[int, DataSource | None]:
        """Get recent records for a species (last N days).
        
        Args:
            species_name: Common name of species.
            days: Lookback window (default 365 = 1 year).
        
        Returns:
            Tuple of (record_count, source).
        """
        record_count = 0
        source = None
        
        if self.european_records is None or self.european_records.empty:
            return 0, None
        
        # Handle case where parquet file is empty or missing species_name column
        if "species_name" not in self.european_records.columns:
            return 0, None
        
        cutoff_date = datetime.now() - timedelta(days=days)
        recent = self.european_records[
            (self.european_records["species_name"] == species_name) &
            (pd.to_datetime(self.european_records["observation_date"]) >= cutoff_date)
        ]
        
        if not recent.empty:
            record_count = len(recent)
            quality = recent["quality"].mode()
            quality_str = quality[0] if not quality.empty else "provisional"
            
            source = DataSource(
                name="European Occurrences (Live)",
                priority=2,
                quality=quality_str,
                timestamp=datetime.now(),
            )
        
        return record_count, source
    
    def get_momentum_score(self, species_name: str) -> tuple[float, DataSource | None]:
        """Calculate momentum score (recent activity trend).
        
        High recent activity in Atlantic pathway = high momentum.
        
        Args:
            species_name: Common name of species.
        
        Returns:
            Tuple of (momentum_0_to_1, source).
        """
        momentum = 0.0
        source = None
        
        # Recent activity (last 3 years)
        recent_3yr, recent_source = self.get_recent_activity(species_name, days=365 * 3)
        if recent_3yr > 5:
            momentum = min(1.0, recent_3yr / 20.0)
            source = recent_source
        
        return momentum, source
    
    def create_scoring_input(self, species_name: str) -> ScoringInput:
        """Create a ScoringInput from all available data sources.
        
        Implements priority: Live > Historical > Manual
        
        Args:
            species_name: Common name of species.
        
        Returns:
            ScoringInput with source attribution.
        """
        self.load_data()
        
        # Get Dutch data (live or manual)
        dutch_count, dutch_year, dutch_source = self.get_dutch_data(species_name)
        
        # Get recent activity
        recent_count, recent_source = self.get_recent_activity(species_name, days=365)
        last_10yr_count, _ = self.get_recent_activity(species_name, days=365 * 10)
        
        # Get momentum
        momentum, momentum_source = self.get_momentum_score(species_name)
        
        # Get historical European data from species_master
        european_data = {}
        if self.species_master is not None:
            master = self.species_master[self.species_master["species"] == species_name]
            if not master.empty:
                row = master.iloc[0]
                european_data = {
                    "corvo_records": int(row.get("corvo_records", 0)) if pd.notna(row.get("corvo_records")) else 0,
                    "ireland_records": int(row.get("ireland_records", 0)) if pd.notna(row.get("ireland_records")) else 0,
                    "uk_records": int(row.get("uk_records", 0)) if pd.notna(row.get("uk_records")) else 0,
                    "france_records": int(row.get("france_records", 0)) if pd.notna(row.get("france_records")) else 0,
                    "spain_records": int(row.get("spain_records", 0)) if pd.notna(row.get("spain_records")) else 0,
                    "portugal_records": int(row.get("portugal_records", 0)) if pd.notna(row.get("portugal_records")) else 0,
                }
        
        # Get scientific name
        scientific_name = ""
        if self.species_master is not None:
            master = self.species_master[self.species_master["species"] == species_name]
            if not master.empty:
                scientific_name = str(master.iloc[0].get("scientific_name", ""))
        
        return ScoringInput(
            species_name=species_name,
            scientific_name=scientific_name,
            corvo_records=european_data.get("corvo_records", 0),
            ireland_records=european_data.get("ireland_records", 0),
            uk_records=european_data.get("uk_records", 0),
            france_records=european_data.get("france_records", 0),
            spain_records=european_data.get("spain_records", 0),
            portugal_records=european_data.get("portugal_records", 0),
            dutch_record_count=int(dutch_count),
            dutch_latest_year=dutch_year,
            recent_records=recent_count,
            last_10yr_records=int(last_10yr_count),
            dutch_source=dutch_source,
            atlantic_source=recent_source,
            momentum_source=momentum_source,
        )
    
    def score_species(self, species_name: str, base_scorer: Any = None) -> tuple[float, dict[str, Any]]:
        """Score a species using live data with source attribution.
        
        Args:
            species_name: Common name of species.
            base_scorer: Optional function to apply base scoring (default: placeholder).
        
        Returns:
            Tuple of (score_0_to_1, metadata_dict).
        """
        scoring_input = self.create_scoring_input(species_name)
        
        # Use provided scorer or apply default logic
        if base_scorer:
            score = base_scorer(scoring_input)
        else:
            score = self._default_score(scoring_input)
        
        # Build metadata showing which sources contributed
        metadata = {
            "species": species_name,
            "score": score,
            "dutch_source": scoring_input.dutch_source.name if scoring_input.dutch_source else "unknown",
            "dutch_quality": scoring_input.dutch_source.quality if scoring_input.dutch_source else None,
            "atlantic_source": scoring_input.atlantic_source.name if scoring_input.atlantic_source else "none",
            "recent_records": scoring_input.recent_records,
            "dutch_records": scoring_input.dutch_record_count,
            "last_10yr_records": scoring_input.last_10yr_records,
        }
        
        return score, metadata
    
    def _default_score(self, scoring_input: ScoringInput) -> float:
        """Default scoring logic (simplified placeholder).
        
        Combines:
        - Dutch rarity (higher rarity = higher score)
        - Recent European activity (more recent = higher score)
        - Momentum (upward trend = higher score)
        
        Args:
            scoring_input: ScoringInput object.
        
        Returns:
            Score from 0.0 to 1.0.
        """
        score = 0.0
        
        # Dutch rarity component (0-0.3)
        # Fewer Dutch records = higher score
        if scoring_input.dutch_record_count == 0:
            rarity_score = 0.3
        elif scoring_input.dutch_record_count < 5:
            rarity_score = 0.24
        elif scoring_input.dutch_record_count < 10:
            rarity_score = 0.18
        else:
            rarity_score = 0.06
        
        score += rarity_score
        
        # Recent activity component (0-0.4)
        # Recent European records suggest establishment potential
        activity_score = min(0.4, scoring_input.recent_records / 20.0)
        score += activity_score
        
        # Atlantic pipeline component (0-0.2)
        # High corvo/Ireland/UK records suggest good transatlantic pathway
        atlantic_total = (
            scoring_input.corvo_records +
            scoring_input.ireland_records * 0.5 +
            scoring_input.uk_records * 0.25
        )
        atlantic_score = min(0.2, atlantic_total / 50.0)
        score += atlantic_score
        
        # Momentum component (0-0.1)
        # Upward trend in recent years
        momentum_threshold = (scoring_input.last_10yr_records or 0) - (scoring_input.dutch_record_count or 0)
        if momentum_threshold > 0:
            momentum_score = 0.1
        else:
            momentum_score = 0.0
        
        score += momentum_score
        
        return min(1.0, score)


def apply_live_scoring_to_candidates(
    species_list: list[str] | pd.DataFrame,
    base_scorer: Any = None,
) -> pd.DataFrame:
    """Score a list of species using live data.
    
    Args:
        species_list: List of species names or DataFrame with species column.
        base_scorer: Optional custom scorer function.
    
    Returns:
        DataFrame with scores and source attribution.
    """
    if isinstance(species_list, pd.DataFrame):
        species_names = species_list["species"].tolist()
    else:
        species_names = species_list
    
    scorer = LiveDataScorer()
    results = []
    
    for species_name in species_names:
        try:
            score, metadata = scorer.score_species(species_name, base_scorer)
            results.append(metadata)
        except Exception as e:
            logger.warning(f"Error scoring {species_name}: {e}")
            results.append({
                "species": species_name,
                "score": 0.0,
                "error": str(e),
            })
    
    return pd.DataFrame(results)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Example usage
    scorer = LiveDataScorer()
    
    # Score a single species
    score, metadata = scorer.score_species("Western Tanager")
    print(f"\n{metadata['species']}: {score:.3f}")
    print(f"  Dutch source: {metadata['dutch_source']} ({metadata['dutch_quality']})")
    print(f"  Atlantic source: {metadata['atlantic_source']}")
    print(f"  Recent records: {metadata['recent_records']}")
