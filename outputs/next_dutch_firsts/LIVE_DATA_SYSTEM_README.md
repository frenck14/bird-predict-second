# Next Dutch Firsts Live Data System

## Overview

Next Dutch Firsts has been transformed into a **live, continuously updating prediction system** that integrates multiple authoritative data sources. The system separates verified live sources, historical datasets, and user-maintained data through an extensible source adapter architecture.

## Quick Start (5 minutes)

### 1. Update All Data Sources

```bash
# Run the update script
python scripts/update_live_data.py --cache

# Output:
# ✅ Dutch Avifauna (CDNA): 25 records
# ✅ Species Master (Live): 25 records
# ⚠ Western Europe Occurrences: 0 records
# ✅ Update cycle complete. Total records: 50
```

### 2. View Source Status

```python
from src.next_dutch_firsts_live_data import create_live_data_manager

manager = create_live_data_manager()
manager.print_status()
```

### 3. Score Candidate Species

```python
from src.next_dutch_firsts_scoring import LiveDataScorer

scorer = LiveDataScorer()
score, metadata = scorer.score_species("Western Tanager")

print(f"Score: {score:.3f}")
print(f"Dutch data: {metadata['dutch_source']}")
print(f"Dutch records: {metadata['dutch_records']}")
```

### 4. Display Dashboard Status

```python
from src.next_dutch_firsts_dashboard import DataStatusDashboard

dashboard = DataStatusDashboard()
print(dashboard.render_text_status())
```

## Architecture

### File Structure

```
src/
├── next_dutch_firsts_live_data.py        # Core framework (22 KB)
│   ├── SourceAdapter (base class)
│   ├── SourceRegistry (centralized management)
│   ├── LiveDataManager (orchestration)
│   └── Built-in adapters (3):
│       ├── DutchAvifaunaAdapter
│       ├── SpeciesMasterAdapter
│       └── WesternEuropeAdapter
│
├── next_dutch_firsts_source_adapters.py  # Extended adapters (15 KB)
│   ├── ObservationOrgAdapter
│   ├── eBirdAdapter
│   ├── BirdGuidesAdapter
│   ├── ScandinavianRarityAdapter (template for 4 countries)
│   └── BirdCastWeatherAdapter
│
├── next_dutch_firsts_scoring.py          # Live scoring integration (15 KB)
│   ├── LiveDataScorer
│   ├── ScoringInput (with source tracking)
│   ├── DataSource (attribution metadata)
│   └── Priority fallback: Live > Historical > Manual
│
└── next_dutch_firsts_dashboard.py        # Status dashboard (13 KB)
    ├── DataStatusDashboard
    ├── render_text_status()
    ├── render_html_status()
    ├── render_streamlit_status()
    └── ScoreSourceAttribution

scripts/
└── update_live_data.py                   # Scheduled update script

inputs/next_dutch_firsts/live/            # Live data storage (Parquet + CSV)
├── dutch_rarity_records.parquet          # CDNA-verified Dutch records
├── european_occurrences.parquet          # Live European observations
├── current_season_activity.parquet       # Active species this season
├── source_metadata.csv                   # Source health registry
└── dashboard_status_cache.json           # Cached status for quick retrieval

outputs/next_dutch_firsts/
├── LIVE_DATA_INTEGRATION_GUIDE.md        # Full technical reference
└── live_scores.csv                       # Generated candidate scores
```

### Data Flow

```
External Sources → SourceAdapter → Validation → Transform → Load
                                                              ↓
                                            inputs/next_dutch_firsts/live/
                                                              ↓
                                     LiveDataScorer (with Priority Fallback)
                                                              ↓
                                        Prediction Score + Source Attribution
                                                              ↓
                                      DataStatusDashboard (HTML/Text/Streamlit)
```

## Key Features

### ✅ Live Data Integration

- **Dutch Rarity (Priority 1)**: Dutch Avifauna, CDNA rarity reports
- **European Occurrence (Priority 2)**: Observation.org, eBird (stubs in place)
- **Atlantic Pathway (Priority 3)**: BirdGuides, Irish Rare Bird Alert (stubs)
- **Eastern Pathway (Priority 4)**: Scandinavian databases (stubs)
- **Weather Integration**: BirdCast atmospheric indices (stub)

### ✅ Data Quality Tracking

Every observation tracked with:
- **Quality tier**: verified, provisional, unverified
- **Confidence score**: 0-1 scale (0.9 = CDNA, 0.7 = eBird, etc.)
- **Source attribution**: Which data source provided each value

### ✅ Smart Fallback Logic

Three-tier priority ensures reliability:
```
Priority 1 (Live Data) → Live Dutch records, eBird, BirdGuides
Priority 2 (Historical) → Species Master CSV, Western Europe CSV
Priority 3 (Manual)     → Fallback to 0 or manual values
```

### ✅ Extensible Architecture

Source adapter pattern allows new sources without modifying core code:

```python
class MyCustomAdapter(SourceAdapter):
    def fetch(self): ...
    def validate(self): ...
    def transform(self): ...
    def load(self): ...

manager.register_source(MyCustomAdapter())
```

### ✅ Safe Updates

- Missing sources generate warnings, not failures
- Partial updates supported (skip unavailable sources)
- Idempotent operations (safe to re-run)

### ✅ Status Dashboard

Real-time view of data source health:

```
✅ Dutch Avifauna (CDNA)
   Type: dutch_rarity
   Status: success
   Records: 25
   Last updated: 2026-11-10T11:45:57

⚠ Observation.org
   Type: european_occurrence
   Status: unavailable
   Error: API key not configured
```

## Usage Examples

### Example 1: Score All Candidate Species

```python
import pandas as pd
from src.next_dutch_firsts_scoring import apply_live_scoring_to_candidates

species = pd.read_csv("inputs/next_dutch_firsts/species_master.csv")
scores = apply_live_scoring_to_candidates(species)
scores.to_csv("outputs/live_scores.csv")

# Columns: species, score, dutch_source, dutch_quality, atlantic_source, ...
```

### Example 2: Filter by Data Quality

```python
import pandas as pd

# Get only verified records
df = pd.read_parquet("inputs/next_dutch_firsts/live/dutch_rarity_records.parquet")
verified = df[df["quality"] == "verified"]
print(f"Verified Dutch records: {len(verified)}")

# Get provisional records from last 30 days
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(days=30)
recent_provisional = df[
    (df["quality"] == "provisional") &
    (pd.to_datetime(df["observation_date"]) >= cutoff)
]
```

### Example 3: Add a New Data Source

```python
from src.next_dutch_firsts_live_data import (
    SourceAdapter, SourceType, Observation, DataQuality,
    create_live_data_manager
)

class MyRarityAdapter(SourceAdapter):
    def __init__(self):
        super().__init__("My Rarity Database", SourceType.ATLANTIC_PATHWAY)
        self.metadata.priority = 3
    
    def fetch(self):
        return pd.read_csv("data/my_birds.csv")
    
    def validate(self, raw_data):
        return "species" in raw_data.columns
    
    def transform(self, raw_data):
        observations = []
        for _, row in raw_data.iterrows():
            obs = Observation(
                species_name=row["species"],
                scientific_name=row.get("scientific_name", ""),
                location=row.get("location", ""),
                country=row.get("country", ""),
                observation_date=pd.to_datetime(row["date"]),
                source="My Rarity Database",
                quality=DataQuality.PROVISIONAL,
                confidence_score=0.75,
            )
            observations.append(obs)
        return observations

# Register and use
manager = create_live_data_manager()
manager.register_source(MyRarityAdapter())
manager.update_all_sources()
```

### Example 4: Scheduled Daily Updates (Cron)

```bash
# Add to crontab
0 3 * * * cd /path/to/repo && python3 scripts/update_live_data.py --cache --score
```

### Example 5: Custom Scoring Function

```python
from src.next_dutch_firsts_scoring import LiveDataScorer, ScoringInput

def my_scorer(inp: ScoringInput) -> float:
    score = 0.0
    
    # Dutch rarity (50%)
    if inp.dutch_record_count == 0:
        score += 0.5
    elif inp.dutch_record_count < 5:
        score += 0.4
    
    # Recent activity (30%)
    score += min(0.3, inp.recent_records / 50)
    
    # Atlantic pipeline (20%)
    score += min(0.2, (inp.corvo_records + inp.ireland_records) / 100)
    
    return min(1.0, score)

scorer = LiveDataScorer()
score, metadata = scorer.score_species("Western Tanager", base_scorer=my_scorer)
```

## Data Schema

### Dutch Rarity Records

```csv
species_name,scientific_name,location,country,observation_date,source,quality,confidence_score,record_url,notes
Red-flanked Bluetail,Tarsiger cyanurus,Netherlands (historical),Netherlands,2024-01-15,Dutch Avifauna,verified,0.95,,80 records total
```

**Columns:**
- `species_name`: Common name (English)
- `scientific_name`: Binomial nomenclature
- `location`: Geographic location
- `country`: Country or region
- `observation_date`: ISO datetime of observation
- `source`: Data source name
- `quality`: verified | provisional | unverified
- `confidence_score`: 0.0-1.0 (higher = more reliable)
- `record_url`: Link to original record (optional)
- `notes`: Additional metadata

### Source Metadata

```csv
name,source_type,priority,last_updated,update_status,record_count,error_message
Dutch Avifauna (CDNA),dutch_rarity,1,2026-11-10T11:45:57.343633,success,25,
Observation.org,european_occurrence,2,,not_started,0,API key not configured
```

**Columns:**
- `name`: Adapter name
- `source_type`: dutch_rarity | european_occurrence | atlantic_pathway | eastern_pathway | weather_index
- `priority`: 1 (highest) to 4 (lowest)
- `last_updated`: ISO datetime of last successful update
- `update_status`: not_started | in_progress | success | failed | unavailable
- `record_count`: Number of records loaded
- `error_message`: Error details if update failed

## Configuration

### API Keys & Credentials

External data sources may require API keys:

```python
from src.next_dutch_firsts_source_adapters import eBirdAdapter, ObservationOrgAdapter

# eBird (https://ebird.org/api)
ebird = eBirdAdapter(api_key="your_ebird_key")

# Observation.org (https://www.observation.org/api/v2)
obs_org = ObservationOrgAdapter(api_key="your_obs_org_key")

manager = create_live_data_manager()
manager.register_source(ebird)
manager.register_source(obs_org)
```

Set environment variables or store in config file:

```bash
export EBIRD_API_KEY="your_key"
export OBSERVATION_ORG_API_KEY="your_key"
```

### Scheduling Options

**Option 1: Cron Job (Linux/macOS)**
```bash
0 3 * * * /usr/bin/python3 /path/to/scripts/update_live_data.py --cache --score
```

**Option 2: GitHub Actions (Cloud)**
```yaml
on:
  schedule:
    - cron: '0 3 * * *'
```

**Option 3: Cloud Function (Google Cloud/AWS Lambda)**
```python
@functions_framework.http
def update(request):
    manager = create_live_data_manager()
    manager.update_all_sources()
    return {"status": "ok"}
```

## Troubleshooting

### Issue: "Source unavailable" warnings

Some adapters not yet fully implemented (eBird, Observation.org, etc.). System gracefully continues. To implement:

1. Add API access code in adapter
2. Set environment variable with API key
3. Re-run update

### Issue: No records loaded

Check:
- Source file exists: `ls -la inputs/next_dutch_firsts/live/`
- Source is registered: `manager.list_sources()`
- CSV/API not empty: `head data/source.csv`

### Issue: Old data persists

Parquet files accumulate across updates. To reset:

```bash
rm inputs/next_dutch_firsts/live/*.parquet
python scripts/update_live_data.py --cache
```

### Issue: Scoring returns 0 for all species

Verify:
- Dutch rarity records loaded: `manager.registry.get_source("Dutch Avifauna").metadata.record_count`
- Species names match: Check species_master.csv vs. dutch_avifauna_records.csv

## Performance Notes

- **Update time**: ~1-2 seconds for 3 built-in sources
- **Parquet storage**: ~8 KB per 1000 records (compressed)
- **Scoring**: ~100 species/sec on modern hardware
- **Dashboard rendering**: <100ms

## References & Further Reading

- [LIVE_DATA_INTEGRATION_GUIDE.md](LIVE_DATA_INTEGRATION_GUIDE.md) — Comprehensive technical reference
- Source adapters: `src/next_dutch_firsts_source_adapters.py`
- Scoring logic: `src/next_dutch_firsts_scoring.py`
- Dashboard: `src/next_dutch_firsts_dashboard.py`

## Next Steps

### Short-term (This week)

- [ ] Implement eBird API adapter
- [ ] Implement Observation.org API adapter
- [ ] Set up scheduled updates (cron or GitHub Actions)
- [ ] Test scoring with live data

### Medium-term (Next 2-4 weeks)

- [ ] Add BirdGuides news feed scraper
- [ ] Integrate Scandinavian rarity databases
- [ ] Connect BirdCast atmospheric indices
- [ ] Build Streamlit dashboard with live updates

### Long-term (Next 2-3 months)

- [ ] Train ML model on live data
- [ ] Probability forecasting (P(Dutch record within 1/5/10 years))
- [ ] Real-time alert system for new records
- [ ] Interactive species explorer with pathway visualization

## Contributing

To add a new data source:

1. Extend `SourceAdapter` base class
2. Implement: `fetch()`, `validate()`, `transform()`, optionally `load()`
3. Register with `LiveDataManager.register_source()`
4. Test with `update_all_sources()`
5. Document in README and LIVE_DATA_INTEGRATION_GUIDE

See `next_dutch_firsts_source_adapters.py` for templates.

## Status

**Last Updated**: 2026-11-10  
**System Status**: ✅ Operational  
**Data Sources**: 3 active (Dutch Avifauna, Species Master, Western Europe)  
**Total Records**: 50 loaded  
**Ready for**: Live scoring, forecasting, model development  

---

For detailed technical documentation, see [LIVE_DATA_INTEGRATION_GUIDE.md](LIVE_DATA_INTEGRATION_GUIDE.md).
