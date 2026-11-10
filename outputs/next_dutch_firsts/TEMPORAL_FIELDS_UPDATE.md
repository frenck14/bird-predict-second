# Temporal Fields Extension - Dutch Records Data Model

**Date:** November 10, 2026  
**Status:** ✅ Complete  
**Purpose:** Add temporal granularity to Dutch occurrence records

---

## Overview

The Next Dutch Firsts data model has been extended with three new temporal fields to provide better insight into the recency and frequency of Dutch bird records. These fields enable:

- Identification of recently-established vagrants vs. historical records
- Filtering by contemporary occurrence (last 10/20 years)
- Assessment of establishment trends over time
- Better modeling of current species rarity status

---

## New Fields Added

### 1. `most_recent_record_year`

**Type:** Integer (year)  
**Definition:** Year of the latest accepted Dutch record for the species  
**Calculated from:** `last_record_year` column  
**Populated:** 25/50 species (50%)

**Interpretation:**
- Shows how recently the species has been recorded in the Netherlands
- Most recent = 2024 indicates current vagrant/presence
- Historical value (e.g., 1998) indicates no recent records
- Empty = no verified Dutch records found

**Examples:**
```
Red-flanked Bluetail: 2024 (recorded last year - actively vagrant)
American Golden Plover: 1998 (28 years ago - not recently seen)
Western Tanager: (empty - no verified Dutch records)
```

### 2. `last_10yr_records`

**Type:** Integer (count) or empty  
**Definition:** Number of accepted Dutch records in the most recent 10-year period (2016-2026)  
**Populated:** 10/50 species (20%)

**Calculation Logic:**
- ✅ Populated as `0` if last record predates 2016
- ✅ Populated as total count if all records fall within 2016-2026
- ⟶ Left empty if records span across the 2016 boundary (insufficient granularity)

**Interpretation:**
- `0` = No recent records (last record before 2016)
- `1-5` = Exceptionally rare recent vagrant
- `6+` = Established vagrant pattern in recent decade
- Empty = Unclear distribution (requires manual verification)

**Examples:**
```
Red-flanked Bluetail: (empty - records span 1989-2024, insufficient granularity)
American Golden Plover: 0 (last record 1998, before 2016 window)
Siberian Accentor: (empty - needs detailed year breakdown)
```

### 3. `last_20yr_records`

**Type:** Integer (count) or empty  
**Definition:** Number of accepted Dutch records in the most recent 20-year period (2006-2026)  
**Populated:** 13/50 species (26%)

**Calculation Logic:**
- ✅ Populated as `0` if last record predates 2006
- ✅ Populated as total count if all records fall within 2006-2026
- ⟶ Left empty if records span across the 2006 boundary (insufficient granularity)

**Interpretation:**
- `0` = No records in past 20 years
- `1-5` = Rare vagrant with limited recent activity
- `6+` = Regular vagrant in past two decades
- Empty = Requires detailed year breakdown

**Examples:**
```
Yellow-breasted Bunting: (empty - records 1996-2022, spans boundary)
Wilson's Phalarope: (empty - records 1981-2014, spans boundary)
```

---

## Data Quality

### Population Summary

| Field | Count | Percentage | Status |
|-------|-------|-----------|--------|
| **most_recent_record_year** | 25 | 50% | ✅ Populated |
| **last_10yr_records** | 10 | 20% | ✅ Populated |
| **last_20yr_records** | 13 | 26% | ✅ Populated |
| **Not yet populated** | 25 | 50% | ⟶ Manual review |

### Why Some Fields Are Empty

**Sufficient Granularity** (Populated):
- Single record species (e.g., American Golden Plover 1998)
- All records within specified window (complete containment)
- Record predates window (clear `0` value)

**Insufficient Granularity** (Empty - Manual Review Needed):
- Records span across the 2016 boundary (unknown distribution)
- Records span across the 2006 boundary (unknown distribution)
- Multiple records across multiple decades without year breakdown
- Example: Baird's Sandpiper (3 records, 1975-2020) - distribution unclear

**No Verified Data**:
- Species without any Dutch records (25 species)
- Source data insufficient for calculation

---

## Species Status by Recency

### Recently Active Vagrants (most_recent_record_year ≥ 2020)

| Species | Most Recent | Total | Period |
|---------|-------------|-------|--------|
| Red-flanked Bluetail | 2024 | 80 | 1989-2024 |
| Siberian Accentor | 2022 | 6 | 1992-2022 |
| Yellow-breasted Bunting | 2022 | 4 | 1996-2022 |
| Bufflehead | 2020 | 2 | 2006-2020 |
| Baird's Sandpiper | 2020 | 3 | 1975-2020 |

**Interpretation:** These species have been recorded in the Netherlands within the last 6 years, indicating they remain active vagrants or part of established vagrant patterns.

### Historical Records (most_recent_record_year < 2010)

| Species | Most Recent | Total | Years Ago |
|---------|-------------|-------|-----------|
| American Golden Plover | 1998 | 1 | 28 years |
| Upland Sandpiper | 1984 | 1 | 42 years |
| Yellow-billed Cuckoo | 1976 | 1 | 50 years |
| Harlequin Duck | 1997 | 1 | 29 years |

**Interpretation:** These species have not been reliably recorded in recent decades. They represent potential future occurrences rather than established vagrant patterns.

### No Verified Recent Data

25 species without any Dutch records or without recent records available in source data.

---

## Usage in Models

### Filter for Contemporary Vagrants

```python
import pandas as pd

species = pd.read_csv('inputs/next_dutch_firsts/species_master.csv')

# Species with records in last 10 years
contemporary = species[species['last_10yr_records'].notna()]
contemporary = contemporary[contemporary['last_10yr_records'].astype(float) > 0]

print(f"Species actively recorded in last 10 years: {len(contemporary)}")
```

### Filter for Established Patterns

```python
# Species with multiple records in last 20 years (established pattern)
established = species[species['last_20yr_records'].notna()]
established = established[established['last_20yr_records'].astype(float) >= 3]

print(f"Species with established 20-year pattern: {len(established)}")
```

### Identify Long-Absent Species

```python
# Species with verified records but none in last 20 years
absent = species[species['last_20yr_records'] == 0]

print(f"Species not recorded in 20 years: {len(absent)}")
```

---

## Manual Verification Requirements

### Species Needing Year-Level Detail (11 species)

These species have records spanning across the boundary years (2006, 2016) and need detailed year-by-year breakdown:

**Require Research:**
- Baird's Sandpiper (3 records, 1975-2020)
- Black-throated Thrush (3 records, 2003-2021)
- Dusky Thrush (4 records, 1991-2020)
- Falcated Duck (1 record, 2019)
- Lanceolated Warbler (3 records, 1992-2020)
- Long-toed Stint (2 records, 1992-2017)
- Oriental Turtle Dove (3 records, 2010-2022)
- Siberian Rubythroat (2 records, 2009-2021)
- Siberian Thrush (2 records, 2003-2018)
- Stejneger's Stonechat (1 record, 2017)
- Wilson's Phalarope (2 records, 1981-2014)
- Yellow-breasted Bunting (4 records, 1996-2022)

**Sources to Consult:**
- CDNA decision bulletins by year
- Dutch Avifauna historical records database
- Published rarity reports with year annotations
- Vogelbescherming species accounts with timeline

---

## Schema Summary

### `dutch_avifauna_records.csv` (9 columns)

```
species,
scientific_name,
record_count,
first_record_year,
last_record_year,
source,
most_recent_record_year,      [NEW]
last_10yr_records,             [NEW]
last_20yr_records              [NEW]
```

### `species_master.csv` (20 columns)

Includes all original columns plus:
```
most_recent_record_year,      [NEW]
last_10yr_records,             [NEW]
last_20yr_records              [NEW]
```

---

## Backward Compatibility

✅ **All original fields preserved** - No existing data modified  
✅ **Additive only** - New columns appended to end  
✅ **Non-destructive** - Empty values used, no placeholders  
✅ **Existing validations maintained** - `verification_status` unchanged  

---

## Next Steps

### Short-term (Week 1)
- Use populated fields for contemporary vagrant analysis
- Filter by `most_recent_record_year >= 2020` for active species

### Medium-term (Weeks 2-4)
- Research 11 species needing year-level detail
- Consult CDNA bulletins for annual record breakdown
- Update `last_10yr_records` and `last_20yr_records` with precise counts

### Long-term
- Maintain year-by-year record database for future queries
- Update `most_recent_record_year` as new records occur
- Archive historical boundaries for trend analysis

---

## Reference Dates

For future updates, use these reference points:

| Window | Years | Current Cutoff |
|--------|-------|---|
| **Most Recent** | Current year | 2026 |
| **10-year window** | Last 10 years | 2016-2026 |
| **20-year window** | Last 20 years | 2006-2026 |

When updating in future years:
- Update `current_year` in calculation script
- Recalculate all temporal fields
- Document boundary changes

---

## Examples by Species Type

### Recently Active Vagrant
**Red-flanked Bluetail**
```
Total records: 80 (1989-2024)
Most recent: 2024 ✓
Last 10yr (2016-2026): ⟶ (needs granular data)
Last 20yr (2006-2026): ⟶ (needs granular data)
Status: Active contemporary vagrant
```

### Historical Singleton Record
**American Golden Plover**
```
Total records: 1 (1998-1998)
Most recent: 1998 ✓
Last 10yr (2016-2026): 0 ✓
Last 20yr (2006-2026): 0 ✓
Status: Not recorded in 28 years
```

### Records Spanning Boundary (Needs Detail)
**Baird's Sandpiper**
```
Total records: 3 (1975-2020)
Most recent: 2020 ✓
Last 10yr (2016-2026): ⟶ (spans boundary)
Last 20yr (2006-2026): ⟶ (spans boundary)
Status: Requires detailed year breakdown
```

### No Records
**Western Tanager**
```
Total records: (none)
Most recent: (empty)
Last 10yr: (empty)
Last 20yr: (empty)
Status: No verified Dutch records
```

---

## Questions & Support

### What does "spans boundary" mean?
If a species has records from before and after a cutoff year (e.g., 2006 or 2016), we don't know how many fall on each side without year-level data. We leave these fields blank for manual review.

### How do I update these fields?
Use the population script in `src/populate_dutch_records.py`, updating the `current_year` variable. The script will recalculate all fields automatically.

### What if new records are discovered?
Update `last_record_year` and `record_count` in `dutch_avifauna_records.csv`, then re-run the population script to recalculate temporal fields.

### Can I filter by these fields?
Yes - use pandas/SQL to filter by `most_recent_record_year`, `last_10yr_records`, and `last_20yr_records` values for modeling or analysis.

---

**Schema Extended:** November 10, 2026  
**New Fields:** 3  
**Populated:** 25/50 species (most_recent_record_year)  
**Pending Manual Review:** 11 species (year-level detail)  
**Status:** Ready for temporal analysis and modeling

