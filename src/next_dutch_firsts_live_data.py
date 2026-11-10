"""Live data ingestion framework for Next Dutch Firsts.

Continuously updates species occurrence information from external sources.
Separates verified live sources, historical datasets, and user-maintained data.
Uses a source-adapter pattern for extensibility.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
LIVE_DATA_DIR = ROOT / "inputs/next_dutch_firsts/live"
LIVE_DATA_DIR.mkdir(exist_ok=True)


class DataQuality(str, Enum):
    """Data quality tiers."""
    VERIFIED = "verified"
    PROVISIONAL = "provisional"
    UNVERIFIED = "unverified"


class SourceType(str, Enum):
    """Source category."""
    DUTCH_RARITY = "dutch_rarity"
    EUROPEAN_OCCURRENCE = "european_occurrence"
    ATLANTIC_PATHWAY = "atlantic_pathway"
    EASTERN_PATHWAY = "eastern_pathway"
    WEATHER_INDEX = "weather_index"


@dataclass
class SourceMetadata:
    """Registry entry for a data source."""
    name: str
    source_type: SourceType
    priority: int  # 1-4; lower is higher priority
    last_updated: datetime | None = None
    update_status: str = "not_started"  # not_started, in_progress, success, failed, unavailable
    record_count: int = 0
    error_message: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_type": self.source_type.value,
            "priority": self.priority,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "update_status": self.update_status,
            "record_count": self.record_count,
            "error_message": self.error_message,
        }


@dataclass
class Observation:
    """A single bird observation/record."""
    species_name: str
    scientific_name: str
    location: str
    country: str
    observation_date: datetime
    source: str
    quality: DataQuality
    confidence_score: float  # 0-1
    record_url: str | None = None
    notes: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "species_name": self.species_name,
            "scientific_name": self.scientific_name,
            "location": self.location,
            "country": self.country,
            "observation_date": self.observation_date.isoformat(),
            "source": self.source,
            "quality": self.quality.value,
            "confidence_score": self.confidence_score,
            "record_url": self.record_url,
            "notes": self.notes,
        }


class SourceAdapter(ABC):
    """Base adapter for data source integration.
    
    Each source implements fetch→validate→transform→load pipeline.
    """
    
    def __init__(self, name: str, source_type: SourceType):
        self.name = name
        self.source_type = source_type
        self.metadata = SourceMetadata(name=name, source_type=source_type, priority=1)
    
    @abstractmethod
    def fetch(self) -> Any:
        """Fetch raw data from source.
        
        Returns:
            Raw data (dict, list, DataFrame, etc.)
        
        Raises:
            SourceUnavailableError: If source cannot be accessed.
        """
    
    @abstractmethod
    def validate(self, raw_data: Any) -> bool:
        """Validate raw data structure and content.
        
        Args:
            raw_data: Data returned by fetch()
        
        Returns:
            True if valid, False otherwise.
        """
    
    @abstractmethod
    def transform(self, raw_data: Any) -> list[Observation]:
        """Transform raw data into Observation objects.
        
        Args:
            raw_data: Data returned by fetch()
        
        Returns:
            List of Observation objects.
        """
    
    def load(self, observations: list[Observation]) -> None:
        """Load observations into live data store.
        
        This is called automatically after transform(). Override if needed.
        
        Args:
            observations: List of Observation objects to persist.
        """
        logger.info(f"Base load: {len(observations)} observations from {self.name}")
    
    def update(self) -> list[Observation]:
        """Execute full fetch→validate→transform→load pipeline.
        
        Returns:
            List of Observation objects loaded.
        
        Raises:
            SourceUnavailableError: If fetch fails.
        """
        self.metadata.update_status = "in_progress"
        self.metadata.last_updated = datetime.now()
        
        try:
            raw_data = self.fetch()
            if not self.validate(raw_data):
                raise ValueError(f"Validation failed for {self.name}")
            
            observations = self.transform(raw_data)
            self.load(observations)
            
            self.metadata.update_status = "success"
            self.metadata.record_count = len(observations)
            logger.info(f"✅ {self.name}: {len(observations)} records")
            return observations
        
        except Exception as e:
            self.metadata.update_status = "failed"
            self.metadata.error_message = str(e)
            logger.error(f"❌ {self.name}: {e}")
            raise SourceUnavailableError(f"{self.name} update failed: {e}") from e


class SourceUnavailableError(Exception):
    """Raised when a data source cannot be accessed."""
    pass


class SourceRegistry:
    """Central registry of all data sources."""
    
    def __init__(self):
        self.sources: dict[str, SourceAdapter] = {}
        self._metadata_cache: dict[str, SourceMetadata] = {}
    
    def register(self, adapter: SourceAdapter) -> None:
        """Register a source adapter.
        
        Args:
            adapter: SourceAdapter instance.
        """
        self.sources[adapter.name] = adapter
        logger.info(f"Registered source: {adapter.name} ({adapter.source_type.value})")
    
    def get_source(self, name: str) -> SourceAdapter:
        """Retrieve a registered source by name.
        
        Args:
            name: Source name.
        
        Returns:
            SourceAdapter instance.
        
        Raises:
            KeyError: If source not registered.
        """
        return self.sources[name]
    
    def list_sources(self, source_type: SourceType | None = None) -> list[SourceAdapter]:
        """List all registered sources, optionally filtered by type.
        
        Args:
            source_type: Filter by SourceType (optional).
        
        Returns:
            List of SourceAdapter instances.
        """
        adapters = list(self.sources.values())
        if source_type:
            adapters = [a for a in adapters if a.source_type == source_type]
        return sorted(adapters, key=lambda a: a.metadata.priority)
    
    def save_metadata(self, filepath: Path) -> None:
        """Persist source metadata registry to CSV.
        
        Args:
            filepath: Path to save metadata.
        """
        rows = [adapter.metadata.to_dict() for adapter in self.sources.values()]
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False)
        logger.info(f"Saved source metadata to {filepath}")
    
    def load_metadata(self, filepath: Path) -> None:
        """Load source metadata from CSV.
        
        Args:
            filepath: Path to load metadata from.
        """
        if not filepath.exists():
            logger.warning(f"Metadata file not found: {filepath}")
            return
        
        df = pd.read_csv(filepath)
        # Metadata is informational; sources remain defined in code
        logger.info(f"Loaded source metadata from {filepath}")


# ============================================================================
# CONCRETE SOURCE ADAPTERS
# ============================================================================


class DutchAvifaunaAdapter(SourceAdapter):
    """Dutch Avifauna historical records (CDNA-accepted records).
    
    This adapter reads from the pre-populated dutch_avifauna_records.csv
    that was enriched with verified data.
    """
    
    def __init__(self):
        super().__init__("Dutch Avifauna (CDNA)", SourceType.DUTCH_RARITY)
        self.metadata.priority = 1
        self.source_file = ROOT / "inputs/next_dutch_firsts/dutch_avifauna_records.csv"
    
    def fetch(self) -> pd.DataFrame:
        """Load dutch_avifauna_records.csv."""
        if not self.source_file.exists():
            raise FileNotFoundError(f"Source file not found: {self.source_file}")
        return pd.read_csv(self.source_file)
    
    def validate(self, raw_data: Any) -> bool:
        """Verify required columns present."""
        required = {"species", "scientific_name", "record_count", "source"}
        return isinstance(raw_data, pd.DataFrame) and required.issubset(raw_data.columns)
    
    def transform(self, raw_data: pd.DataFrame) -> list[Observation]:
        """Convert records to Observation objects."""
        observations = []
        
        for _, row in raw_data.iterrows():
            # Skip empty records
            if pd.isna(row.get("record_count")):
                continue
            
            # Infer quality from source reliability
            quality = DataQuality.VERIFIED
            if "provisional" in str(row.get("source", "")).lower():
                quality = DataQuality.PROVISIONAL
            
            # Use last_record_year as observation date (or most_recent_record_year)
            year = row.get("most_recent_record_year") or row.get("last_record_year")
            if pd.isna(year):
                continue
            
            obs = Observation(
                species_name=row["species"],
                scientific_name=row.get("scientific_name", ""),
                location="Netherlands (historical)",
                country="Netherlands",
                observation_date=datetime(int(year), 1, 1),  # Use Jan 1 as proxy
                source=str(row.get("source", "Dutch Avifauna")),
                quality=quality,
                confidence_score=0.9,  # CDNA records are highly reliable
                notes=f"{int(row['record_count'])} records total" if not pd.isna(row.get("record_count")) else None,
            )
            observations.append(obs)
        
        return observations
    
    def load(self, observations: list[Observation]) -> None:
        """Persist to dutch_rarity_records.parquet."""
        filepath = LIVE_DATA_DIR / "dutch_rarity_records.parquet"
        
        if filepath.exists():
            existing = pd.read_parquet(filepath)
            new_df = pd.DataFrame([o.to_dict() for o in observations])
            df = pd.concat([existing, new_df], ignore_index=True)
            df = df.drop_duplicates(subset=["species_name", "country"], keep="last")
        else:
            df = pd.DataFrame([o.to_dict() for o in observations])
        
        df.to_parquet(filepath)
        logger.info(f"Loaded {len(df)} Dutch records to {filepath}")


class SpeciesMasterAdapter(SourceAdapter):
    """Current season activity from species_master.csv.
    
    Reads candidate pool and temporal fields to track current activity.
    """
    
    def __init__(self):
        super().__init__("Species Master (Live)", SourceType.EUROPEAN_OCCURRENCE)
        self.metadata.priority = 2
        self.source_file = ROOT / "inputs/next_dutch_firsts/species_master.csv"
    
    def fetch(self) -> pd.DataFrame:
        """Load species_master.csv."""
        if not self.source_file.exists():
            raise FileNotFoundError(f"Source file not found: {self.source_file}")
        return pd.read_csv(self.source_file)
    
    def validate(self, raw_data: Any) -> bool:
        """Verify required columns."""
        required = {"species", "scientific_name", "pathway"}
        return isinstance(raw_data, pd.DataFrame) and required.issubset(raw_data.columns)
    
    def transform(self, raw_data: pd.DataFrame) -> list[Observation]:
        """Extract candidate metadata as observations."""
        observations = []
        
        for _, row in raw_data.iterrows():
            # Skip if no recent records
            recent_year = row.get("most_recent_record_year")
            if pd.isna(recent_year):
                continue
            
            obs = Observation(
                species_name=row["species"],
                scientific_name=row.get("scientific_name", ""),
                location="European pathway",
                country=row.get("pathway", "Atlantic"),
                observation_date=datetime(int(recent_year), 1, 1),
                source="Species Master",
                quality=DataQuality.VERIFIED,
                confidence_score=0.85,
                notes=f"Pathway: {row.get('pathway')}; Status: {row.get('dutch_status', 'unknown')}",
            )
            observations.append(obs)
        
        return observations
    
    def load(self, observations: list[Observation]) -> None:
        """Persist to current_season_activity.parquet."""
        filepath = LIVE_DATA_DIR / "current_season_activity.parquet"
        
        if filepath.exists():
            existing = pd.read_parquet(filepath)
            new_df = pd.DataFrame([o.to_dict() for o in observations])
            df = pd.concat([existing, new_df], ignore_index=True)
            df = df.drop_duplicates(subset=["species_name"], keep="last")
        else:
            df = pd.DataFrame([o.to_dict() for o in observations])
        
        df.to_parquet(filepath)
        logger.info(f"Loaded {len(df)} season activity records to {filepath}")


class WesternEuropeAdapter(SourceAdapter):
    """European occurrence data (from western_europe_occurrences.csv or live feed).
    
    Placeholder for integration with Observation.org, eBird, BirdGuides feeds.
    """
    
    def __init__(self):
        super().__init__("Western Europe Occurrences", SourceType.ATLANTIC_PATHWAY)
        self.metadata.priority = 2
        self.source_file = ROOT / "inputs/next_dutch_firsts/western_europe_occurrences.csv"
    
    def fetch(self) -> pd.DataFrame:
        """Load western_europe_occurrences.csv or fetch from live source."""
        if self.source_file.exists():
            return pd.read_csv(self.source_file)
        else:
            logger.warning(f"Source file not found: {self.source_file}, using empty dataset")
            return pd.DataFrame()
    
    def validate(self, raw_data: Any) -> bool:
        """Basic validation for DataFrame."""
        return isinstance(raw_data, pd.DataFrame)
    
    def transform(self, raw_data: pd.DataFrame) -> list[Observation]:
        """Convert to Observation objects."""
        if raw_data.empty:
            return []
        
        observations = []
        for _, row in raw_data.iterrows():
            if pd.isna(row.get("species")) or pd.isna(row.get("date")):
                continue
            
            obs = Observation(
                species_name=row.get("species", ""),
                scientific_name=row.get("scientific_name", ""),
                location=row.get("location", "Western Europe"),
                country=row.get("country", ""),
                observation_date=pd.to_datetime(row["date"]),
                source="Western Europe",
                quality=DataQuality.PROVISIONAL,
                confidence_score=0.7,
            )
            observations.append(obs)
        
        return observations
    
    def load(self, observations: list[Observation]) -> None:
        """Persist to european_occurrences.parquet."""
        filepath = LIVE_DATA_DIR / "european_occurrences.parquet"
        
        if filepath.exists():
            existing = pd.read_parquet(filepath)
            new_df = pd.DataFrame([o.to_dict() for o in observations])
            df = pd.concat([existing, new_df], ignore_index=True)
            df = df.drop_duplicates(subset=["species_name", "observation_date"], keep="last")
        else:
            df = pd.DataFrame([o.to_dict() for o in observations])
        
        df.to_parquet(filepath)
        logger.info(f"Loaded {len(df)} European records to {filepath}")


# ============================================================================
# LIVE DATA MANAGER
# ============================================================================


class LiveDataManager:
    """Orchestrates updates across all registered sources."""
    
    def __init__(self):
        self.registry = SourceRegistry()
        self._register_default_sources()
    
    def _register_default_sources(self) -> None:
        """Register built-in source adapters."""
        self.registry.register(DutchAvifaunaAdapter())
        self.registry.register(SpeciesMasterAdapter())
        self.registry.register(WesternEuropeAdapter())
    
    def register_source(self, adapter: SourceAdapter) -> None:
        """Register a custom source adapter.
        
        Args:
            adapter: SourceAdapter instance.
        """
        self.registry.register(adapter)
    
    def update_dutch_records(self) -> int:
        """Update Dutch rarity database.
        
        Returns:
            Number of records loaded.
        """
        logger.info("🇳🇱 Updating Dutch rarity records...")
        try:
            source = self.registry.get_source("Dutch Avifauna (CDNA)")
            observations = source.update()
            return len(observations)
        except SourceUnavailableError as e:
            logger.warning(f"⚠ Dutch records unavailable: {e}")
            return 0
    
    def update_european_occurrences(self) -> int:
        """Update European occurrence database.
        
        Returns:
            Number of records loaded.
        """
        logger.info("🇪🇺 Updating European occurrences...")
        try:
            source = self.registry.get_source("Western Europe Occurrences")
            observations = source.update()
            return len(observations)
        except SourceUnavailableError as e:
            logger.warning(f"⚠ European occurrences unavailable: {e}")
            return 0
    
    def update_current_season_activity(self) -> int:
        """Update current season activity tracking.
        
        Returns:
            Number of records loaded.
        """
        logger.info("📊 Updating current season activity...")
        try:
            source = self.registry.get_source("Species Master (Live)")
            observations = source.update()
            return len(observations)
        except SourceUnavailableError as e:
            logger.warning(f"⚠ Season activity unavailable: {e}")
            return 0
    
    def update_weather_support(self) -> bool:
        """Update weather indices (BirdCast integration stub).
        
        Returns:
            True if successful, False otherwise.
        """
        logger.info("🌦 Updating weather indices (BirdCast)...")
        logger.info("⚠ Weather index update: not yet implemented")
        return False
    
    def update_all_sources(self, skip_unavailable: bool = True) -> dict[str, int]:
        """Update all registered sources.
        
        Args:
            skip_unavailable: If True, unavailable sources don't raise errors.
        
        Returns:
            Dict mapping source name to record count.
        """
        logger.info("=" * 60)
        logger.info("🔄 UPDATING ALL SOURCES")
        logger.info("=" * 60)
        
        results = {}
        for source in self.registry.list_sources():
            try:
                observations = source.update()
                results[source.name] = len(observations)
            except SourceUnavailableError as e:
                if skip_unavailable:
                    logger.warning(f"⚠ Skipping unavailable source: {source.name}")
                    results[source.name] = 0
                else:
                    raise
        
        self.registry.save_metadata(LIVE_DATA_DIR / "source_metadata.csv")
        logger.info("=" * 60)
        logger.info(f"✅ Update cycle complete. Total records: {sum(results.values())}")
        logger.info("=" * 60)
        
        return results
    
    def get_status(self) -> dict[str, Any]:
        """Get current status of all sources.
        
        Returns:
            Dict with source status information.
        """
        status = {
            "timestamp": datetime.now().isoformat(),
            "sources": {},
        }
        
        for source in self.registry.list_sources():
            status["sources"][source.name] = {
                "type": source.source_type.value,
                "priority": source.metadata.priority,
                "last_updated": source.metadata.last_updated.isoformat() if source.metadata.last_updated else None,
                "status": source.metadata.update_status,
                "record_count": source.metadata.record_count,
                "error": source.metadata.error_message,
            }
        
        return status
    
    def print_status(self) -> None:
        """Print human-readable status report."""
        status = self.get_status()
        
        print("\n" + "=" * 70)
        print("📊 LIVE DATA SOURCE STATUS")
        print("=" * 70)
        print(f"Last update: {status['timestamp']}\n")
        
        for source_name, info in status["sources"].items():
            status_emoji = "✅" if info["status"] == "success" else "⚠" if info["status"] == "unavailable" else "❌"
            print(f"{status_emoji} {source_name}")
            print(f"   Type: {info['type']}")
            print(f"   Status: {info['status']}")
            print(f"   Records: {info['record_count']}")
            if info["last_updated"]:
                print(f"   Last updated: {info['last_updated']}")
            if info["error"]:
                print(f"   Error: {info['error']}")
            print()
        
        print("=" * 70)


# ============================================================================
# PUBLIC API
# ============================================================================


def create_live_data_manager() -> LiveDataManager:
    """Factory function to create and configure the live data manager.
    
    Returns:
        Configured LiveDataManager instance.
    """
    return LiveDataManager()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Example usage
    manager = create_live_data_manager()
    results = manager.update_all_sources()
    manager.print_status()
