# Live Data Integration Guide for Next Dutch Firsts

## Overview

The Next Dutch Firsts system has been transformed from a static CSV-based ranking into a **live, continuously updating prediction system**. This guide explains the architecture, how to use it, and how to extend it with new data sources.

## Architecture

### Core Components

1. **`next_dutch_firsts_live_data.py`** — Main data ingestion framework
   - `SourceAdapter` — Base class for all data sources
   - `SourceRegistry` — Central registry of sources
   - `LiveDataManager` — Orchestrates updates across all sources
   - Concrete adapters: `DutchAvifaunaAdapter`, `SpeciesMasterAdapter`, `WesternEuropeAdapter`

2. **`next_dutch_firsts_source_adapters.py`** — Extended source adapters (templates)
   - `ObservationOrgAdapter` — European bird observations
   - `eBirdAdapter` — Global observations
   - `BirdGuidesAdapter` — Atlantic rarity news
   - `ScandinavianRarityAdapter` — Eastern drift signals
   - `BirdCastWeatherAdapter` — Atmospheric indices

3. **`next_dutch_firsts_scoring.py`** — Live scoring integration
   - `LiveDataScorer` — Scores species using live data with priority fallback
   - Source attribution tracking
   - Configurable scoring logic

4. **`next_dutch_firsts_dashboard.py`** — Dashboard enhancements
   - `DataStatusDashboard` — Renders source health status
   - Streamlit integration
   - HTML/text rendering options

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ EXTERNAL DATA SOURCES                                        │
├─────────────────────────────────────────────────────────────┤
│  Priority 1: Dutch Rarity                                    │
│  • Dutch Avifauna (CSV)                                      │
│  • CDNA rarity reports (API stub)                            │
│                                                              │
│  Priority 2: European Occurrence                             │
│  • Observation.org (API stub)                                │
│  • eBird (API stub)                                          │
│  • Western Europe occurrences (CSV)                          │
│                                                              │
│  Priority 3: Atlantic Pathway                                │
│  • BirdGuides rarity news (scrape stub)                      │
│  • Irish Rare Bird Alert (API stub)                          │
│                                                              │
│  Priority 4: Eastern Pathway                                 │
│  • Finland rarity records (API stub)                         │
│  • Sweden (Artportalen) (API stub)                           │
│  • Norway rarity records (API stub)                          │
│  • Germany rarity records (API stub)                         │
│                                                              │
│  Weather Integration                                         │
│  • BirdCast atmospheric indices (API stub)                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
                  [SourceAdapter]
                    (fetch, validate,
                     transform, load)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ LIVE DATA STORE                                              │
├─────────────────────────────────────────────────────────────┤
│  inputs/next_dutch_firsts/live/                             │
│  ├── dutch_rarity_records.parquet                           │
│  ├── european_occurrences.parquet                           │
│  ├── current_season_activity.parquet                        │
│  ├── source_metadata.csv                                    │
│  └── score_attribution.parquet                              │
└─────────────────────────────────────────────────────────────┘
                           ↓
         [LiveDataScorer] (Live > Historical > Manual)
                           ↓
         [Prediction Score with Source Attribution]
                           ↓
         [DataStatusDashboard]
         (Streamlit / HTML / Text)
```

## Quick Start

### 1. Initialize the System

```python
from src.next_dutch_firsts_live_data import create_live_data_manager

# Create manager with all default sources
manager = create_live_data_manager()

# Update all sources (safe; skips unavailable sources)
results = manager.update_all_sources()
# ✅ Dutch Avifauna (CDNA): 25 records
# ✅ Species Master (Live): 35 records
# ⚠ Observation.org: not yet implemented
# ✅ Western Europe Occurrences: 0 records

# View status
manager.print_status()
```

### 2. Score a Species Using Live Data

```python
from src.next_dutch_firsts_scoring import LiveDataScorer

scorer = LiveDataScorer()

# Score a single species
score, metadata = scorer.score_species("Western Tanager")
print(f"Score: {score:.3f}")
print(f"Dutch source: {metadata['dutch_source']} ({metadata['dutch_quality']})")
print(f"Recent records: {metadata['recent_records']}")

# Score entire candidate list
import pandas as pd
species_list = pd.read_csv("inputs/next_dutch_firsts/species_master.csv")
scores_df = scorer.apply_live_scoring_to_candidates(species_list)
scores_df.to_csv("outputs/next_dutch_firsts/live_scores.csv", index=False)
```

### 3. Display Status Dashboard

```python
from src.next_dutch_firsts_dashboard import DataStatusDashboard

dashboard = DataStatusDashboard()

# For console/terminal
print(dashboard.render_text_status())

# For web (HTML)
html = dashboard.render_html_status()

# For Streamlit app
dashboard.render_streamlit_status()  # Requires streamlit installed
```

## Data Quality System

Every observation has three quality indicators:

### Quality Tiers

```python
class DataQuality(str, Enum):
    VERIFIED = "verified"        # CDNA-accepted, published records
    PROVISIONAL = "provisional"  # eBird unreviewed, unofficial reports
    UNVERIFIED = "unverified"    # User submissions, manual entries
```

### Confidence Scores (0-1)

- **0.9+** — CDNA-accepted Dutch records, institutional databases
- **0.7-0.8** — eBird provisional, Observation.org user reports
- **0.5-0.7** — News reports, social media mentions
- **<0.5** — Anecdotal observations

### Example: Filtering by Quality

```python
import pandas as pd

# Load Dutch records
df = pd.read_parquet("inputs/next_dutch_firsts/live/dutch_rarity_records.parquet")

# Get only verified records
verified = df[df["quality"] == "verified"]

# Get recent provisional records (last 90 days)
import datetime
cutoff = datetime.datetime.now() - datetime.timedelta(days=90)
recent_provisional = df[
    (df["quality"] == "provisional") &
    (pd.to_datetime(df["observation_date"]) >= cutoff)
]
```

## Source Priority & Fallback Logic

The scoring system implements **three-tier priority**:

```
Priority 1 (Highest): LIVE DATA
├── Dutch Avifauna (CDNA) — verified, ~50% coverage
├── European Occurrences (live) — provisional, expanding coverage
├── BirdGuides — Atlantic pathway signals

Priority 2 (Middle): HISTORICAL DATA
├── Species Master CSV — manual values, established baseline
├── Western Europe Occurrences — historical CSV

Priority 3 (Lowest): MANUAL/DEFAULT VALUES
└── Fallback to 0 if no data available
```

### Example: Source Selection Logic

```python
def get_dutch_record_count(species_name: str) -> tuple[int, str]:
    # Try live data first
    if species_name in dutch_records_live:
        return dutch_records_live[species_name], "Dutch Avifauna (Live)"
    
    # Fall back to historical
    elif species_name in species_master_manual:
        return species_master_manual[species_name], "Species Master (Manual)"
    
    # No data available
    else:
        return 0, "unknown"
```

## Adding New Data Sources

### Example 1: Add Azores Rarity Records

Create a new adapter:

```python
from src.next_dutch_firsts_live_data import SourceAdapter, SourceType, Observation, DataQuality
from datetime import datetime
import pandas as pd

class AzoresRarityAdapter(SourceAdapter):
    """Azores bird records (Western Atlantic pathway)."""
    
    def __init__(self):
        super().__init__("Azores Bird Records", SourceType.ATLANTIC_PATHWAY)
        self.metadata.priority = 3
    
    def fetch(self):
        """Fetch from Azores database or CSV."""
        return pd.read_csv("data/azores_bird_records.csv")
    
    def validate(self, raw_data):
        """Check required columns."""
        return isinstance(raw_data, pd.DataFrame) and "species" in raw_data.columns
    
    def transform(self, raw_data):
        """Convert to Observation objects."""
        observations = []
        for _, row in raw_data.iterrows():
            obs = Observation(
                species_name=row["species"],
                scientific_name=row.get("scientific_name", ""),
                location=row.get("location", "Azores"),
                country="Portugal (Azores)",
                observation_date=datetime.fromisoformat(row["date"]),
                source="Azores Bird Records",
                quality=DataQuality.VERIFIED,
                confidence_score=0.85,
            )
            observations.append(obs)
        return observations
```

Register it:

```python
from src.next_dutch_firsts_live_data import create_live_data_manager
from your_adapter_module import AzoresRarityAdapter

manager = create_live_data_manager()
manager.register_source(AzoresRarityAdapter())
```

### Example 2: Add API-Based Source (eBird)

Template already exists in `next_dutch_firsts_source_adapters.py`:

```python
from src.next_dutch_firsts_source_adapters import eBirdAdapter

manager = create_live_data_manager()

# Register with API key
ebird_adapter = eBirdAdapter(api_key="your_api_key_here")
manager.register_source(ebird_adapter)

# Update
manager.update_european_occurrences()  # eBird will be included
```

## Integration with Scoring Model

### Using Live Data in Model

```python
from src.next_dutch_firsts_scoring import apply_live_scoring_to_candidates

# Score all species using live data
species_list = pd.read_csv("inputs/next_dutch_firsts/species_master.csv")
scores = apply_live_scoring_to_candidates(species_list)

# Results include source attribution
# Columns: species, score, dutch_source, dutch_quality, 
#          atlantic_source, recent_records, dutch_records, last_10yr_records
```

### Custom Scoring Logic

```python
from src.next_dutch_firsts_scoring import LiveDataScorer, ScoringInput

def my_custom_scorer(scoring_input: ScoringInput) -> float:
    """Custom scoring function using live data."""
    score = 0.0
    
    # Weight Dutch rarity heavily
    if scoring_input.dutch_record_count == 0:
        score += 0.4  # Not yet recorded in Dutch
    
    # Add momentum from recent records
    recent_activity = scoring_input.recent_records / 100.0
    score += min(0.3, recent_activity)
    
    # Add Atlantic pipeline contribution
    atlantic_activity = (
        scoring_input.corvo_records * 0.5 +
        scoring_input.ireland_records * 0.2
    ) / 100.0
    score += min(0.3, atlantic_activity)
    
    return min(1.0, score)

scorer = LiveDataScorer()
score, metadata = scorer.score_species(
    "Western Tanager",
    base_scorer=my_custom_scorer
)
```

## Automated Scheduled Updates

### Option 1: Cron Job (Linux/macOS)

```bash
# Add to crontab (crontab -e)
# Run daily at 3 AM
0 3 * * * /usr/bin/python3 /path/to/update_live_data.py

# Create update_live_data.py:
#!/usr/bin/env python3
from src.next_dutch_firsts_live_data import create_live_data_manager
from src.next_dutch_firsts_dashboard import DataStatusDashboard
import logging

logging.basicConfig(level=logging.INFO)
manager = create_live_data_manager()
results = manager.update_all_sources()

# Cache status for dashboard
dashboard = DataStatusDashboard()
dashboard.cache_status()

print(f"✅ Update complete: {sum(results.values())} records")
```

### Option 2: GitHub Actions Workflow

```yaml
# .github/workflows/update-live-data.yml
name: Update Live Data

on:
  schedule:
    - cron: '0 3 * * *'  # Daily at 3 AM UTC
  workflow_dispatch:     # Manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Update live data
        run: python3 scripts/update_live_data.py
      
      - name: Commit results
        run: |
          git config --local user.email "bot@example.com"
          git config --local user.name "Live Data Bot"
          git add inputs/next_dutch_firsts/live/
          git commit -m "🔄 Daily live data update" || echo "No changes"
          git push
```

### Option 3: Cloud Function (Google Cloud / AWS Lambda)

```python
# Google Cloud Function
import functions_framework
from src.next_dutch_firsts_live_data import create_live_data_manager
from src.next_dutch_firsts_dashboard import DataStatusDashboard

@functions_framework.http
def update_live_data(request):
    """HTTP-triggered update function."""
    manager = create_live_data_manager()
    results = manager.update_all_sources()
    
    dashboard = DataStatusDashboard()
    dashboard.cache_status()
    
    return {
        "status": "success",
        "records_updated": sum(results.values()),
        "timestamp": datetime.now().isoformat(),
    }
```

## Data Schema

### Live Data Files

All live data stored in `inputs/next_dutch_firsts/live/`:

#### `dutch_rarity_records.parquet`

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| species_name | string | "Red-flanked Bluetail" | Common name |
| scientific_name | string | "Tarsiger cyanurus" | Binomial nomenclature |
| location | string | "Netherlands (historical)" | Where record occurred |
| country | string | "Netherlands" | Country code or name |
| observation_date | datetime | 2024-01-15 | Date of observation |
| source | string | "Dutch Avifauna" | Data source name |
| quality | string | "verified" | verified/provisional/unverified |
| confidence_score | float | 0.95 | 0-1 scale |
| record_url | string | "https://..." | Link to original record (optional) |
| notes | string | "80 records total" | Additional metadata |

#### `european_occurrences.parquet`

Same schema as `dutch_rarity_records.parquet`, with:
- `country` = 2-letter ISO code (e.g., "GB", "IE", "FR")
- `source` = observation platform (eBird, Observation.org, etc.)
- `confidence_score` varies by review status

#### `current_season_activity.parquet`

Tracks current season observations for active candidates.
Same schema as above.

#### `source_metadata.csv`

| Column | Type | Example |
|--------|------|---------|
| name | string | "Dutch Avifauna (CDNA)" |
| source_type | string | "dutch_rarity" |
| priority | int | 1 |
| last_updated | datetime | 2024-11-10T15:30:00 |
| update_status | string | "success" |
| record_count | int | 25 |
| error_message | string | NULL or error text |

## Monitoring & Troubleshooting

### Check Update Status

```python
from src.next_dutch_firsts_live_data import create_live_data_manager

manager = create_live_data_manager()
status = manager.registry.get_source("Dutch Avifauna (CDNA)").metadata

print(f"Status: {status.update_status}")
print(f"Records: {status.record_count}")
print(f"Last updated: {status.last_updated}")
if status.error_message:
    print(f"Error: {status.error_message}")
```

### View Live Data

```python
import pandas as pd

# Dutch records
df_dutch = pd.read_parquet("inputs/next_dutch_firsts/live/dutch_rarity_records.parquet")
print(f"Dutch records: {len(df_dutch)}")
print(df_dutch.groupby("quality").size())

# European occurrences
df_europe = pd.read_parquet("inputs/next_dutch_firsts/live/european_occurrences.parquet")
print(f"European records: {len(df_europe)}")
print(f"Last 7 days: {len(df_europe[pd.to_datetime(df_europe['observation_date']) >= (datetime.now() - timedelta(days=7))])}")
```

### Common Issues

**Issue: "Source unavailable" warnings**
- Some sources not yet fully implemented (eBird, Observation.org, BirdGuides)
- System gracefully skips unavailable sources
- Use `update_all_sources(skip_unavailable=True)` to proceed

**Issue: No records loaded**
- Source CSV/API may be empty or missing
- Check file exists: `ls -la inputs/next_dutch_firsts/live/`
- Verify source is registered: `manager.list_sources()`

**Issue: Old data in live store**
- Parquet files accumulate records across updates
- Clear manually if needed: `rm inputs/next_dutch_firsts/live/*.parquet`

## Future Enhancements

### Phase 2: Full API Integration

- [ ] Implement Observation.org API (requires API key)
- [ ] Implement eBird API for all regions
- [ ] Connect to BirdGuides RSS feed
- [ ] Add Scandinavian rarity databases
- [ ] Integrate BirdCast weather indices

### Phase 3: Advanced Analytics

- [ ] Trend analysis (species establishment rate)
- [ ] Pathway detection (which route for each species?)
- [ ] Prediction confidence intervals
- [ ] Year-to-year change tracking

### Phase 4: User Interface

- [ ] Streamlit dashboard with live updates
- [ ] Real-time notification alerts
- [ ] Species probability forecasts (1yr, 5yr, 10yr)
- [ ] Interactive pathway visualization

### Phase 5: Model Integration

- [ ] Train machine learning model on live data
- [ ] Probability estimates: P(Dutch record within T years)
- [ ] Feature importance analysis
- [ ] Calibration against historical establishment patterns

## References

- Source adapter pattern: Extensible, decoupled design for data integration
- Parquet format: Columnar storage for efficient analysis and compression
- BirdCast: https://www.birdcast.info/ — Atmospheric indices for bird migration
- CDNA: https://cdna.nl/ — Dutch rarity committee
- Dutch Avifauna: https://nl.avibase.bsc-eoc.org/ — Historical records

## Support & Contributing

For questions, issues, or to add a new data source:

1. Check this guide and existing source adapters
2. Review `next_dutch_firsts_live_data.py` for SourceAdapter interface
3. Create a new adapter following the pattern
4. Register and test with `LiveDataManager`
5. Document any API keys or special setup required
