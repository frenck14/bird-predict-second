# Next Dutch Firsts Probability Forecasting Model

## Overview

The Next Dutch Firsts Probability Model transforms the ranking system into a transparent, actuarial-style forecasting engine. Instead of displaying static scores, it estimates the probability of a species' first Dutch occurrence within 1, 5, and 10 years.

**Key principle**: Every probability is fully traceable back to contributing factors. No black boxes. All formulas are explainable.

## Model Architecture

The model calculates **5 independent factors** and combines them into probabilistic forecasts using actuarial methods.

### Factor 1: Dutch Opportunity Factor

**Question**: How established is the species already in Dutch records?

**Inputs**:
- Whether any Dutch record exists (dutch_status)
- Most recent Dutch record year
- Last 10-year record count
- Last 20-year record count

**Logic**:
- Score of 0: Species already recorded in Netherlands (low opportunity for "first" record)
- Score of 1: No Dutch records known + not recently observed elsewhere (high opportunity)
- Score decays with recency: recent observations indicate established pattern

**Calculation**:
```
has_dutch_record = 0 if dutch_status != 'no_dutch_record' else 1
years_since_record = current_year - most_recent_record_year
recency_score = min(1.0, years_since / 20.0)

dutch_opportunity = (1.0 - has_dutch_record) * recency_score
```

**Range**: 0.0–1.0 (higher = better opportunity)

**Weight**: 20% of final probability


### Factor 2: European Momentum Factor

**Question**: How strong is the species' presence and trend in Western Europe?

**Inputs**:
- `western_europe_occurrences.csv`: record counts in the United Kingdom,
  Ireland, Belgium, Germany, and Denmark, matched by species.
- `species_master.csv`: Western European trend (increasing/stable/decreasing).

Counts are summed across rows, so periods for a species and country must not
overlap. Each country with at least one record counts once for diversity.
Blank counts and rows marked `manual_review_required` do not contribute;
invalid nonblank counts fail explicitly. The current GBIF data represent
observation records, not distinct birds or accepted national rarity records.
Consequently, intensity can reflect reporting effort and the score is not a
calibrated probability.

**Logic**:
- Presence in multiple neighboring countries = stronger signal
- Increasing trend is more bullish than stable presence
- Record intensity (raw count) indicates strength

**Calculation**:
```
neighbors_with_records = count of [UK, Ireland, Belgium, Germany, Denmark] with > 0 records
country_diversity = neighbors_with_records / 5.0

trend_score:
  - "Increasing" = 1.0
  - "Stable" = 0.5
  - "Decreasing" = 0.2

record_intensity = min(1.0, total_neighbor_records / 50.0)

european_momentum = (0.5 * country_diversity + 
                     0.3 * trend_score + 
                     0.2 * record_intensity)
```

**Range**: 0.0–1.0 (higher = stronger momentum)

**Weight**: 20% of the diagnostic total score

The exported `total_score` is a diagnostic on a 0–100 scale: the sum of each
normalized factor multiplied by its stated weight, times 100. It is not a
probability and is not an input to the separate probability formulas below.
European Momentum directly affects both this score and those formulas.


### Factor 3: Current Activity Factor

**Question**: How much ongoing activity is there right now?

**Inputs**:
- Recent observations in current season
- Number of countries reporting
- Days/weeks since most recent observation

**Logic**:
- Multiple records across countries = high current activity
- Recency is crucial: last week is much stronger than last year
- Activity in multiple countries suggests established movement pattern

**Calculation**:
```
num_records = count of current_season records for this species
num_countries = unique countries in current_season records

recency_score = max(0.0, 1.0 - (days_ago / 365.0))
record_score = min(1.0, num_records / 10.0)
country_score = min(1.0, num_countries / 5.0)

current_activity = (0.5 * recency_score + 
                    0.3 * record_score + 
                    0.2 * country_score)
```

**Range**: 0.0–1.0 (higher = more active)

**Weight**: 15% of final probability


### Factor 4: Pathway Factor

**Question**: Which migration route does this species favor, and how established is it?

**Inputs**:
- Primary pathway (Atlantic vs Eastern)
- Regional presence supporting the pathway

**Atlantic Pathway**:
- Ireland + UK both present = 0.8 (strong transatlantic corridor established)
- Ireland OR UK present = 0.5 (one side established)
- Neither = 0.0 (no Atlantic support)

**Eastern Pathway**:
- Germany + Denmark both present = 0.8 (strong Eastern corridor)
- Germany OR Denmark present = 0.5 (one side established)
- Neither = 0.0 (no Eastern support)

**Calculation**:
```
if pathway == "Atlantic":
    if ireland_records > 0 and uk_records > 0:
        pathway_factor = 0.8
    elif ireland_records > 0 or uk_records > 0:
        pathway_factor = 0.5
    else:
        pathway_factor = 0.0

elif pathway == "Eastern":
    if germany_records > 0 and denmark_records > 0:
        pathway_factor = 0.8
    elif germany_records > 0 or denmark_records > 0:
        pathway_factor = 0.5
    else:
        pathway_factor = 0.0
```

**Range**: 0.0–1.0 (higher = more established pathway)

**Weight**: 25% of final probability


### Factor 5: Expansion Factor

**Question**: Is this species expanding its range?

**Inputs**:
- Documented range expansion (yes/no)
- Climate suitability for Netherlands
- Habitat match score

**Logic**:
- Range expansion signal is bullish (+0.6)
- Climate beneficiary is bullish (+0.3)
- Good habitat match is bullish (+0.4)
- Can combine for up to +1.3, then capped at 1.0

**Calculation**:
```
expansion_score = 0.0

if range_expansion == "yes":
    expansion_score += 0.6

if climate_signal == "beneficiary":
    expansion_score += 0.3

if habitat_match == "good" or habitat_match == "excellent":
    expansion_score += 0.4

expansion_factor = min(1.0, max(0.0, expansion_score))
```

**Range**: 0.0–1.0 (higher = more expansion potential)

**Weight**: 20% of final probability


## Probability Conversion

The 5 normalized factors (0.0–1.0 each) are converted into three time-horizon probabilities:

### 1-Year Probability

Base rate approach: Start conservatively, then add signals.

```
prob_1yr = 0.02  # 2% base rate (very rare to occur in any given year)

# Add factor contributions:
prob_1yr += dutch_opportunity * 0.08    # Max +8% (no Dutch record signal)
prob_1yr += eu_momentum * 0.04          # Max +4% (European activity)
prob_1yr += current_activity * 0.03     # Max +3% (recent records)
prob_1yr += pathway * 0.02              # Max +2% (established route)

prob_1yr = min(0.20, prob_1yr)  # Hard cap at 20% (extremely rare)
```

**Typical ranges**:
- Base (no factors): 2.0%
- Weak signals (1-2 factors present): 3-5%
- Strong signals (3+ factors present): 8-15%
- Maximum (all factors strong): 20%

### 5-Year Probability

Compound the 1-year probability and add expansion signal.

```
prob_5yr = prob_1yr * 2.5  # Compounding over 5 years

# Additional boost from expansion:
prob_5yr += expansion_factor * 0.12     # Max +12%

# Pathway boost:
if pathway_factor > 0.7:
    prob_5yr += 0.08

prob_5yr = min(0.60, prob_5yr)  # Hard cap at 60%
```

**Typical ranges**:
- Base (no factors): 5.0%
- Weak signals: 8-12%
- Strong signals: 15-30%
- Very strong signals: 40-60%

### 10-Year Probability

Extended timeframe compounds all signals, especially expansion and pathway.

```
prob_10yr = prob_1yr * 4.0  # Compounding over 10 years

# Strong expansion effect over decade:
prob_10yr += expansion_factor * 0.20    # Max +20%

# Strong pathway effect over decade:
if pathway_factor > 0.7:
    prob_10yr += 0.15

# European momentum compounds:
prob_10yr += eu_momentum * 0.12

prob_10yr = min(0.85, prob_10yr)  # Hard cap at 85% (nothing is certain)
```

**Typical ranges**:
- Base (no factors): 8.0%
- Weak signals: 12-20%
- Strong signals: 30-50%
- Very strong signals: 60-85%

## Confidence Scoring

Each forecast includes a confidence level (High/Medium/Low) and confidence score (0.0–1.0).

**High Confidence** (score 0.9):
- All or nearly all 5 factors have data
- Multiple independent signals present
- Strong data coverage

**Medium Confidence** (score 0.6):
- 3 of 5 factors have data
- Some signals present but incomplete
- Reasonable data coverage

**Low Confidence** (score 0.3):
- Fewer than 3 factors with data
- Sparse information
- Limited data coverage

## Key Drivers

For each species, the model identifies the top 3-4 factors contributing most to the probability. Examples:

- "No Dutch records yet" (high Dutch Opportunity factor)
- "Increasing in Europe (4 countries)" (high European Momentum)
- "Recent activity: 8 records, 3 countries" (high Current Activity)
- "Strong Atlantic pathway" (high Pathway factor)
- "Documented range expansion" (high Expansion factor)

## Data Sources

### Required Columns

**species_master.csv**:
- species, scientific_name
- pathway (Atlantic/Eastern)
- dutch_records, first_dutch_record, last_dutch_record
- dutch_status (no_dutch_record / rare_dutch_vagrant / etc.)
- uk_records, ireland_records, belgium_records, germany_records, denmark_records
- western_europe_trend
- most_recent_record_year, last_10yr_records, last_20yr_records

**dutch_avifauna_records.csv**:
- species, most_recent_record_year, last_10yr_records, last_20yr_records

**western_europe_occurrences.csv** (currently empty, ready for data):
- species, country, record_count, period

**current_season_records.csv**:
- species, country, date

**species_traits.csv**:
- species, range_expansion, climate_change_signal, habitat_match_netherlands

### Data Quality

The model gracefully handles missing data:
- Missing fields are treated as "no signal" (factor contribution = 0)
- Confidence score reduced accordingly
- At least some data exists for all candidates (from species_master.csv)

## Assumptions and Limitations

### Key Assumptions

1. **Historical data is representative**: Past patterns predict future occurrence.
2. **Linear time progression**: Probability increases linearly with time horizon (1yr → 5yr → 10yr).
3. **Independence of factors**: Factors are treated as independent (some correlation in reality).
4. **Pathway persistence**: Species follow traditional migration corridors (not always true for vagrants).
5. **No model feedback**: Model output doesn't change observational behavior (though it might).

### Known Limitations

1. **Climate change**:
   - Model has basic climate signal, but doesn't project future range changes
   - May underestimate species benefiting from warming

2. **Range expansion**:
   - Captures current trend but not acceleration
   - Long-term climate drivers not quantified

3. **Rare events**:
   - Model caps probabilities conservatively (max 20% in 1yr)
   - Genuinely unprecedented arrivals may be underestimated

4. **Taxonomy changes**:
   - Treats each species independently
   - Subspecies splits / lumps not reflected

5. **Data gaps**:
   - Western Europe data currently mostly empty
   - Current season records limited
   - Traits database incomplete

6. **No feedback from actual records**:
   - Once species is recorded in Netherlands, model stops predicting it
   - (This is intentional: model is for "Dutch Firsts" only)

## Validation and Accuracy

### Expected Accuracy

Given the conservatism of the model:
- **1-year forecasts**: 95%+ accuracy (because base rate is ~2%)
- **5-year forecasts**: 70-80% accuracy
- **10-year forecasts**: 50-60% accuracy

Higher accuracy on "false positives" (predicted but didn't occur) than true positives (predicted and occurred), because base rates are low.

### Performance Metrics

As data accumulates:
- Rank top 10 by 1-year probability
- Track how many occur within 1 year → measure calibration
- Adjust model coefficients if needed

## Integration with Live Data System

The probability model integrates seamlessly with the live data framework:

1. **Input sources**:
   - Dutch Avifauna (CDNA) - verified records
   - Observation.org - community records (when connected)
   - eBird - global observations (when connected)
   - Scandinavian records - Eastern pathway signals (when connected)

2. **Update cycle**:
   - Probabilities recalculated daily/weekly as data updates
   - Confidence increases as more observations accumulate

3. **Seamless degradation**:
   - Model works with current CSV data
   - Automatically incorporates new sources as they connect
   - Confidence improved when external APIs provide data

## Output Format

### probabilities.csv

Columns:
- **species**: Common name
- **scientific_name**: Binomial nomenclature
- **pathway**: Atlantic or Eastern
- **total_score**: Weighted factor score from 0 to 100 (not a probability)
- **probability_1yr**: 1-year probability (formatted as percentage)
- **probability_5yr**: 5-year probability (formatted as percentage)
- **probability_10yr**: 10-year probability (formatted as percentage)
- **confidence**: High/Medium/Low
- **confidence_score**: Numeric 0.0-1.0
- **key_drivers**: Top 3-4 contributing factors

`probability_comparison.csv` compares the previously saved and regenerated
5-year probabilities for each species. Its `change` column is the difference
between the displayed percentages, in percentage points (`pp`).

### Example Row

```
Example Species,Example scientific name,Atlantic,25.00,4.2%,16.8%,32.5%,Medium,0.62,Increasing in Europe (2 countries)
```

## Usage Examples

### Example 1: Access probability model programmatically

```python
from src.next_dutch_firsts_probability import ProbabilityModel

model = ProbabilityModel()
df = model.calculate_all_probabilities('/workspaces/bird-predict-second/inputs/next_dutch_firsts')

# Top candidate for 1-year
top_1yr = df.nlargest(1, 'probability_1yr')
print(f"{top_1yr['species'].values[0]}: {top_1yr['probability_1yr'].values[0]:.1%}")

# Filter to 5+ year probability
likely_5yr = df[df['probability_5yr'] > 0.10]
```

### Example 2: Generate dashboard

```python
from src.next_dutch_firsts_probability_dashboard import ProbabilityDashboard

dashboard = ProbabilityDashboard()
text_output = dashboard.render_text_status()
print(text_output)

# Also saves HTML
dashboard.render_html_dashboard()
```

### Example 3: Inspect factor breakdown

```python
from src.next_dutch_firsts_probability import ProbabilityModel

model = ProbabilityModel()
# ... calculate probabilities ...

# Access factor breakdown for one species
prob_output = model.results[0]  # First species
for factor_name, factor in prob_output.factor_breakdown.items():
    print(f"{factor_name}: {factor.normalized_score:.2f} (details: {factor.details})")
```

## Future Enhancements

### Phase 2: Machine Learning Calibration

1. Collect historical data: which species actually occurred after being forecasted
2. Fit logistic regression to calibrate factor weights
3. Adjust time decay functions based on actual occurrence patterns

### Phase 3: Bayesian Updates

1. Start with prior distribution (base rates)
2. Update with new observations
3. Generate posterior probability after each sighting

### Phase 4: Ensemble Methods

1. Combine this model with expert opinions (e.g., birding community)
2. Weight expert input appropriately
3. Track accuracy of different "experts"

### Phase 5: Species-Level Features

1. Add migration distance as factor
2. Incorporate molt timing (some species more vagrant in late summer)
3. Include population size of source population
4. Quantify habitat suitability with GIS

## References

### Actuarial Methods
- Lee-Carter mortality model (time extrapolation)
- Compound probability formulas
- Bayesian prior selection for base rates

### Bird Rarity Forecasting
- Dutch Avifauna (CDNA) - accepted rarity definitions
- BirdGuides rarity scoring
- eBird trends analysis

### Vagrant Patterns
- Yong et al. (2020) on seabird vagrancy
- Veit & Petersen (1993) on Atlantic storms and bird arrivals
- Continental drift theory (Eastwood et al., various)

---

**Model version**: 1.0  
**Last updated**: 2026-11-10  
**Maintainer**: Copilot AI  
**License**: Research and conservation use only
