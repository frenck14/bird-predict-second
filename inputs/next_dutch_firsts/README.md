# Next Dutch Firsts datasets

These CSV files provide inputs for a future Next Dutch Firsts module.
`species_master.csv` contains an initial candidate list; the other datasets
are header-only. They contain no occurrence data or predictions yet.

- `species_master.csv`: Candidate species, origins, pathways, regional record
  counts, trends, and notes.
- `dutch_avifauna_records.csv`: Dutch record counts, first and last record
  years, and sources by species.
- `western_europe_occurrences.csv`: Species record counts by country and time
  period, with sources.
- `current_season_records.csv`: Individual current-season observations,
  including dates, locations, and sources.
- `species_traits.csv`: Migration, range, climate, and habitat traits by species.

Populate the existing columns with data rows beneath the headers. Keep the
headers and column order unchanged so future loaders can rely on this schema.

The master list is an editorial candidate universe, not a model ranking.
`High interest` in notes flags subjects for future investigation, not a score.
`dutch_first`, `mega_rarity`, and `extreme_rarity` are provisional candidate
labels, not verified record-count categories. Some requested species are
already recorded in the Netherlands; Red-flanked Bluetail is included as a
pathway comparator despite being an almost annual visitor. Occurrence counts
and dates are deliberately blank. Confirm current acceptance, taxonomy,
provenance, and Dutch rarity status before modeling or treating a candidate as
a potential first. The list includes speculative long-distance candidates.

Historical context for initial labels: the
[CSNA Dutch checklist dated 1 February 2025](https://www.dutchavifauna.nl/static/images/page/webprog20250220-139.pdf)
and [Vogelbescherming's Red-flanked Bluetail account](https://www.vogelbescherming.nl/ontdek-vogels/kennis-over-vogels/vogelgids/vogel/blauwstaart).
The checklist reflects decisions through 2024 and cannot establish current
status. No live occurrence records have been imported.
