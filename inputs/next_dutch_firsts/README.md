# Next Dutch Firsts datasets

These CSV files provide inputs to the Next Dutch Firsts probability model.

- `species_master.csv`: Candidate species, origins, pathways, regional record
  counts, trends, and notes.
- `dutch_avifauna_records.csv`: Dutch record counts, first and last record
  years, and sources by species.
- `western_europe_occurrences.csv`: Species record counts by country and time
  period, with sources.
- `current_season_records.csv`: Recent observations with `species`, `country`,
  `observation_date`, `location`, `observation_count`, and `source`. Blank
  counts represent presence-only observations, not zero individuals.
- `species_traits.csv`: Migration, range, climate, and habitat traits by species.

Run the eBird refresh from the repository root:

```bash
python -m pip install -r requirements.txt
python -m src.next_dutch_firsts_ebird
```

Set `EBIRD_API_KEY` in the root `.env` (see `.env.example`) or the environment.
The key is sent only in the eBird authentication header. The refresh resolves
scientific names against the eBird taxonomy, then requests validated recent
observations for GB, IE, BE, DE and DK for every candidate. Unresolved taxonomy,
request failures, invalid responses and potentially truncated responses abort
the refresh rather than being interpreted as no observations. Explicit
scientific-name aliases are maintained in the adapter.

The eBird recent endpoint covers a maximum of **30 days** and reports recent
location-level sightings, not every checklist or a complete current season.
On successful refresh, existing eBird rows are replaced by the latest snapshot;
rows from other sources are preserved. The Current Activity factor counts
observation rows and countries and uses the latest observation date, not the
number of individual birds. This heuristic reflects reporting effort and
should not be interpreted as a complete census or calibrated probability.

The refresh writes `outputs/next_dutch_firsts/ebird_activity_summary.csv`,
`probabilities.csv`, and `ebird_influence_report.csv`. The influence report
compares the prior saved five-year probabilities (which are rounded in the
existing probabilities CSV) with the newly calculated unrounded values, in
probability units; its change is not a percentage-point-formatted string. The
comparison can also reflect rounding or changes to other model inputs since
the prior probabilities were saved.
The activity summary counts eBird rows, while
`combined_current_activity_score` includes any retained non-eBird records.
The existing probabilities CSV must contain exactly the current candidate set.
All outputs are prepared before replacing the existing files; an interrupted
write can require rerunning the refresh to restore a consistent set.

## Near-term Weather Support

The probability model and eBird refresh also produce an experimental
`near_term_opportunity_score`. The existing `total_score` remains the
five-factor baseline (also exported as `baseline_total_score`); the existing
1-, 5-, and 10-year probabilities and their confidence are unchanged.

Weather Support uses the Atlantic Vagrancy Index for Atlantic pathways, the
Eastern Vagrancy Index for Eastern pathways, and the Seabird Index for
Pelagic or Seabird pathways. It reads the daily forecast CSVs and
`outputs/yellow_browed_run.json`, choosing the earliest forecast date on or
after the current UTC date, and no later than tomorrow. The completed run must
not be in the future or older than 48 hours, and its product paths and date ranges must match the
forecast files. Missing, invalid, expired or stale inputs make the near-term
score unavailable with an explanation; the baseline probabilities are still
available. Unknown pathways instead receive an explicitly labelled neutral 50.

For each known pathway, the raw forecast probability is scaled to 0–100 as
`min(100, 100 * probability / threshold)`, where the existing high-risk
threshold is 0.20 for Atlantic and 0.50 for Eastern and Seabird forecasts.
The experimental near-term score is
`clip(baseline_total_score + 0.25 * (weather_support - 50), 0, 100)`.
Thus weather contributes at most ±12.5 points and neutral weather preserves
the baseline. It is a pooled pathway signal, not a species-specific response,
historical percentile, calibrated probability or purely weather-only measure.
The 0–100 score, raw probability, source, forecast date, weather input source,
generation time, status and explanation are saved alongside the probabilities.
When rendered, the text/HTML probability dashboard shows these fields and
marks a saved forecast unavailable once it expires. Previously rendered
static files do not update themselves and must be regenerated to reflect
expiry. Existing probability CSVs without weather fields remain readable and
explicitly show weather as unavailable.

In the Streamlit Rare Birds → Forecasts → Next Dutch Firsts view, the
probability-engine table is separate from the illustrative demo ranking and
its demo-data filters. It defaults to descending near-term opportunity;
long-term sorting offers a 1-, 5-, or 10-year horizon. The table checks weather
freshness when the page runs and reports unavailable scores rather than
sorting stale forecasts as current. Refreshing the page rechecks freshness.

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
status. Imported observations do not establish acceptance as Dutch records.
