"""
Next Dutch Firsts Probability Forecasting System

Transparent, actuarial-style probability model for predicting Dutch occurrence.
Converts multi-factor analysis into probabilistic forecasts.

No machine learning. All calculations are explainable and auditable.
Every probability is traceable back to contributing factors.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum


class ConfidenceLevel(Enum):
    """Confidence in probability estimate."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass
class FactorAnalysis:
    """Results of a probability factor calculation."""
    factor_name: str
    raw_score: float
    normalized_score: float  # 0.0 to 1.0
    contribution: float      # contribution to final probability
    details: Dict = field(default_factory=dict)

    def __repr__(self):
        return f"{self.factor_name}: {self.normalized_score:.2f} (contrib: {self.contribution:.2%})"


@dataclass
class ProbabilityOutput:
    """Complete probability forecast for one species."""
    species: str
    scientific_name: str
    pathway: str
    probability_1yr: float
    probability_5yr: float
    probability_10yr: float
    confidence: ConfidenceLevel
    confidence_score: float  # 0.0-1.0
    key_drivers: List[str]
    factor_breakdown: Dict[str, FactorAnalysis] = field(default_factory=dict)

    @property
    def total_score(self) -> float:
        """Weighted factor score on a 0-100 scale, not a probability."""
        return 100.0 * sum(
            factor.normalized_score * factor.contribution
            for factor in self.factor_breakdown.values()
        )

    def to_dict(self, formatted: bool = False):
        """Convert to dict for CSV export.
        
        Args:
            formatted: If True, return formatted strings. If False, return numeric values.
        """
        if formatted:
            return {
                'species': self.species,
                'scientific_name': self.scientific_name,
                'pathway': self.pathway,
                'total_score': f"{self.total_score:.2f}",
                'probability_1yr': f"{self.probability_1yr:.1%}",
                'probability_5yr': f"{self.probability_5yr:.1%}",
                'probability_10yr': f"{self.probability_10yr:.1%}",
                'confidence': self.confidence.value,
                'confidence_score': f"{self.confidence_score:.2f}",
                'key_drivers': ' | '.join(self.key_drivers),
            }
        else:
            return {
                'species': self.species,
                'scientific_name': self.scientific_name,
                'pathway': self.pathway,
                'total_score': self.total_score,
                'probability_1yr': self.probability_1yr,
                'probability_5yr': self.probability_5yr,
                'probability_10yr': self.probability_10yr,
                'confidence': self.confidence.value,
                'confidence_score': self.confidence_score,
                'key_drivers': ' | '.join(self.key_drivers),
            }


class ProbabilityModel:
    """
    Transparent actuarial probability model.
    
    Factors:
    1. Dutch Opportunity Factor - History and pattern in Netherlands
    2. European Momentum Factor - Trend across Western Europe
    3. Current Activity Factor - Recent observations and intensity
    4. Pathway Factor - Route and regional presence (Atlantic vs Eastern)
    5. Expansion Factor - Climate/range suitability
    """

    def __init__(self):
        self.current_year = datetime.now().year
        
    def load_data(self, base_path: str) -> Tuple[pd.DataFrame, ...]:
        """Load all data sources."""
        base = Path(base_path)
        
        species_master = pd.read_csv(base / 'species_master.csv')
        dutch_records = pd.read_csv(base / 'dutch_avifauna_records.csv')
        western_europe = pd.read_csv(base / 'western_europe_occurrences.csv')
        current_season = pd.read_csv(base / 'current_season_records.csv')
        species_traits = pd.read_csv(base / 'species_traits.csv')
        
        return species_master, dutch_records, western_europe, current_season, species_traits

    def calculate_dutch_opportunity_factor(
        self,
        species: str,
        dutch_records_df: pd.DataFrame,
        species_master_df: pd.DataFrame
    ) -> FactorAnalysis:
        """
        Dutch Opportunity Factor: How established is the species in Dutch birding records?
        
        Inputs:
        - dutch_records: historical record count
        - last_10yr_records: recent activity in Netherlands
        - last_20yr_records: medium-term pattern
        - most_recent_record_year: recency
        
        Logic:
        - Recent Dutch records greatly reduce probability of "first" occurrence
        - Lack of Dutch records increases opportunity
        - Recent European activity near Netherlands is positive signal
        
        Range: 0.0-1.0 (higher = better opportunity)
        """
        details = {}
        
        # Get Dutch record data
        dutch_row = dutch_records_df[dutch_records_df['species'] == species]
        species_row = species_master_df[species_master_df['species'] == species]
        
        # Score: 0 if Dutch record already exists, 1 if no records
        has_dutch_record = 0
        if not species_row.empty:
            dutch_status = species_row.iloc[0].get('dutch_status', 'no_dutch_record')
            if dutch_status != 'no_dutch_record':
                has_dutch_record = 1  # Already recorded, low opportunity
        
        details['has_dutch_record'] = has_dutch_record
        
        # Get recency score
        recency_score = 0.0
        if not species_row.empty:
            most_recent = species_row.iloc[0].get('most_recent_record_year')
            if pd.notna(most_recent):
                years_since = self.current_year - int(most_recent)
                # More recent = lower score (already established)
                # 0 years = 0.0, 5+ years = 0.3
                recency_score = min(1.0, years_since / 20.0)
            
            last_10yr = species_row.iloc[0].get('last_10yr_records', 0)
            if pd.notna(last_10yr) and last_10yr > 0:
                # Has recent records - lower score
                recency_score = min(0.2, last_10yr / 10.0)
        
        details['recency_score'] = recency_score
        details['years_since_record'] = years_since if 'years_since' in locals() else None
        
        # Combined: if already Dutch record, close to 0. If no record and no recent activity, near 1.0
        raw_score = (1.0 - has_dutch_record) * recency_score
        normalized = min(1.0, max(0.0, raw_score))
        
        return FactorAnalysis(
            factor_name='Dutch Opportunity',
            raw_score=raw_score,
            normalized_score=normalized,
            contribution=0.20,  # 20% weight
            details=details
        )

    def calculate_european_momentum_factor(
        self,
        species: str,
        western_europe_df: pd.DataFrame,
        species_master_df: pd.DataFrame
    ) -> FactorAnalysis:
        """
        European Momentum Factor: How strong is the species' presence in surrounding countries?
        
        Inputs:
        - Western European occurrence counts for the five neighboring countries
        - Western European trend from the species master
        
        Logic:
        - Established presence in nearby countries increases probability of Dutch occurrence
        - Increasing trend is more bullish than stable presence
        - Presence in multiple countries = higher momentum
        
        Range: 0.0-1.0 (higher = stronger momentum)
        """
        species_row = species_master_df[species_master_df['species'] == species]
        countries = ['United Kingdom', 'Ireland', 'Belgium', 'Germany', 'Denmark']
        occurrences = western_europe_df[
            (western_europe_df['species'] == species)
            & western_europe_df['country'].isin(countries)
        ].copy()
        if 'source' in occurrences.columns:
            occurrences = occurrences[occurrences['source'] != 'manual_review_required']
        values = occurrences['record_count']
        present = values.notna() & values.astype(str).str.strip().ne('')
        counts = pd.to_numeric(values[present], errors='raise')
        if ((counts < 0) | ~np.isfinite(counts) | (counts % 1 != 0)).any():
            raise ValueError(f"Invalid European occurrence count for {species}")
        occurrences = occurrences.loc[present].copy()
        occurrences['record_count'] = counts
        neighbor_records = int(counts.sum())
        neighbors_with_records = occurrences.loc[
            occurrences['record_count'] > 0, 'country'
        ].nunique()
        country_diversity = neighbors_with_records / 5.0
        details = {
            'neighbor_records': neighbor_records,
            'total_neighbor_records': neighbor_records,
            'neighbors_with_records': neighbors_with_records,
            'country_diversity': country_diversity,
        }
        
        # Trend signal
        trend_value = species_row.iloc[0].get('western_europe_trend', '') if not species_row.empty else ''
        trend = str(trend_value).lower() if pd.notna(trend_value) else ''
        trend_score = 0.0
        if 'increas' in trend or 'expanding' in trend or 'strong' in trend.lower():
            trend_score = 1.0
            details['trend'] = 'Increasing'
        elif 'stable' in trend or 'regular' in trend:
            trend_score = 0.5
            details['trend'] = 'Stable'
        elif 'decreas' in trend or 'rare' in trend:
            trend_score = 0.2
            details['trend'] = 'Decreasing'
        else:
            details['trend'] = 'Unknown'
        
        # Record intensity (capped at 1.0)
        record_intensity = min(1.0, neighbor_records / 50.0)
        
        # Combined: presence + trend + intensity
        raw_score = (0.5 * country_diversity + 0.3 * trend_score + 0.2 * record_intensity)
        normalized = min(1.0, max(0.0, raw_score))
        
        return FactorAnalysis(
            factor_name='European Momentum',
            raw_score=raw_score,
            normalized_score=normalized,
            contribution=0.20,
            details=details
        )

    def calculate_current_activity_factor(
        self,
        species: str,
        current_season_df: pd.DataFrame
    ) -> FactorAnalysis:
        """
        Current Activity Factor: How much ongoing activity is there right now?
        
        Inputs:
        - Recent observations in current season
        - Number of countries reporting
        - Recency of observations (days/weeks ago)
        
        Logic:
        - Multiple recent records across countries = high activity
        - Single record = lower but non-zero activity
        - Older records = less signal
        
        Range: 0.0-1.0 (higher = more active)
        """
        details = {}
        
        if current_season_df.empty:
            return FactorAnalysis(
                factor_name='Current Activity',
                raw_score=0.0,
                normalized_score=0.0,
                contribution=0.15,
                details={'records_found': 0}
            )
        
        # Find species in current season records
        species_records = current_season_df[current_season_df['species'] == species]
        
        if species_records.empty:
            details['records_found'] = 0
            return FactorAnalysis(
                factor_name='Current Activity',
                raw_score=0.0,
                normalized_score=0.0,
                contribution=0.15,
                details=details
            )
        
        # Count records and countries
        num_records = len(species_records)
        num_countries = species_records['country'].nunique()
        
        details['num_records'] = num_records
        details['num_countries'] = num_countries
        
        # Recency scoring
        try:
            species_records['date'] = pd.to_datetime(species_records['date'], errors='coerce')
            most_recent = species_records['date'].max()
            if pd.notna(most_recent):
                days_ago = (datetime.now() - most_recent).days
                # 0 days = 1.0, 30 days = 0.5, 365+ days = 0.0
                recency_score = max(0.0, 1.0 - (days_ago / 365.0))
                details['days_since_record'] = days_ago
            else:
                recency_score = 0.3
        except:
            recency_score = 0.3
        
        # Combined: record count + country diversity + recency
        record_score = min(1.0, num_records / 10.0)
        country_score = min(1.0, num_countries / 5.0)
        
        raw_score = 0.5 * recency_score + 0.3 * record_score + 0.2 * country_score
        normalized = min(1.0, max(0.0, raw_score))
        
        return FactorAnalysis(
            factor_name='Current Activity',
            raw_score=raw_score,
            normalized_score=normalized,
            contribution=0.15,
            details=details
        )

    def calculate_pathway_factor(
        self,
        species: str,
        species_master_df: pd.DataFrame
    ) -> FactorAnalysis:
        """
        Pathway Factor: Which migration route does this species favor?
        
        Inputs:
        - pathway (Atlantic vs Eastern)
        - Regional presence supporting the pathway
        
        Logic:
        Atlantic pathway:
        - Ireland presence + UK presence = strong Atlantic support
        - Presence in Iceland/Azores = excellent signal
        
        Eastern pathway:
        - Germany + Denmark + Scandinavia presence = strong Eastern support
        - Recent Scandinavian records = excellent signal
        
        Range: 0.0-1.0 (higher = more established pathway)
        """
        details = {}
        
        species_row = species_master_df[species_master_df['species'] == species]
        if species_row.empty:
            return FactorAnalysis(
                factor_name='Pathway',
                raw_score=0.0,
                normalized_score=0.0,
                contribution=0.25,
                details=details
            )
        
        row = species_row.iloc[0]
        pathway = row.get('pathway', 'Unknown')
        details['pathway'] = pathway
        
        if pathway == 'Atlantic':
            # Check Atlantic pathway support
            ireland_records = row.get('ireland_records', 0)
            uk_records = row.get('uk_records', 0)
            
            try:
                ireland_count = int(ireland_records) if pd.notna(ireland_records) and ireland_records != '' else 0
                uk_count = int(uk_records) if pd.notna(uk_records) and uk_records != '' else 0
            except (ValueError, TypeError):
                ireland_count = 0
                uk_count = 0
            
            details['ireland_records'] = ireland_count
            details['uk_records'] = uk_count
            
            # Strong Atlantic support if both UK and Ireland have records
            atlantic_support = 0.0
            if ireland_count > 0 and uk_count > 0:
                atlantic_support = 0.8  # Established on both sides
            elif ireland_count > 0 or uk_count > 0:
                atlantic_support = 0.5  # Present on one side
            
            raw_score = atlantic_support
            
        elif pathway == 'Eastern':
            # Check Eastern pathway support
            germany_records = row.get('germany_records', 0)
            denmark_records = row.get('denmark_records', 0)
            
            try:
                germany_count = int(germany_records) if pd.notna(germany_records) and germany_records != '' else 0
                denmark_count = int(denmark_records) if pd.notna(denmark_records) and denmark_records != '' else 0
            except (ValueError, TypeError):
                germany_count = 0
                denmark_count = 0
            
            details['germany_records'] = germany_count
            details['denmark_records'] = denmark_count
            
            # Strong Eastern support if both Germany and Denmark have records
            eastern_support = 0.0
            if germany_count > 0 and denmark_count > 0:
                eastern_support = 0.8  # Established on both sides
            elif germany_count > 0 or denmark_count > 0:
                eastern_support = 0.5  # Present on one side
            
            raw_score = eastern_support
        else:
            raw_score = 0.3  # Unknown pathway, mild support
        
        normalized = min(1.0, max(0.0, raw_score))
        
        return FactorAnalysis(
            factor_name='Pathway',
            raw_score=raw_score,
            normalized_score=normalized,
            contribution=0.25,
            details=details
        )

    def calculate_expansion_factor(
        self,
        species: str,
        species_traits_df: pd.DataFrame,
        species_master_df: pd.DataFrame
    ) -> FactorAnalysis:
        """
        Expansion Factor: Is this species expanding its range?
        
        Inputs:
        - Range expansion signal
        - Climate suitability for Netherlands
        - Habitat match
        
        Logic:
        - Documented range expansion = strong signal
        - Climate change beneficiary = good signal
        - Good habitat match in Netherlands = multiplier
        
        Range: 0.0-1.0 (higher = more expansion potential)
        """
        details = {}
        
        # Check traits
        traits_row = species_traits_df[species_traits_df['species'] == species]
        expansion_score = 0.0
        
        if not traits_row.empty:
            row = traits_row.iloc[0]
            
            # Range expansion signal
            range_expand = row.get('range_expansion', '').lower() if pd.notna(row.get('range_expansion')) else ''
            if 'yes' in range_expand or 'expand' in range_expand:
                expansion_score += 0.6
                details['range_expansion'] = 'Yes'
            elif 'no' in range_expand or 'stable' in range_expand:
                details['range_expansion'] = 'No'
            
            # Climate signal
            climate = row.get('climate_change_signal', '').lower() if pd.notna(row.get('climate_change_signal')) else ''
            if 'beneficiary' in climate or 'positive' in climate:
                expansion_score += 0.3
                details['climate_signal'] = 'Beneficiary'
            elif 'negative' in climate or 'threatened' in climate:
                expansion_score -= 0.2
                details['climate_signal'] = 'Threatened'
            
            # Habitat match
            habitat = row.get('habitat_match_netherlands', '').lower() if pd.notna(row.get('habitat_match_netherlands')) else ''
            if 'good' in habitat or 'excellent' in habitat or 'high' in habitat:
                expansion_score += 0.4
                details['habitat_match'] = 'Good'
            elif 'poor' in habitat or 'low' in habitat:
                details['habitat_match'] = 'Poor'
        
        normalized = min(1.0, max(0.0, expansion_score))
        
        return FactorAnalysis(
            factor_name='Expansion',
            raw_score=expansion_score,
            normalized_score=normalized,
            contribution=0.20,
            details=details
        )

    def calculate_confidence_score(self, factors: Dict[str, FactorAnalysis]) -> Tuple[ConfidenceLevel, float]:
        """
        Determine confidence in probability estimate.
        
        High confidence: Multiple factors present, good data coverage
        Medium confidence: Some factors missing, reasonable data
        Low confidence: Sparse data, limited factors
        """
        data_coverage = 0
        
        if factors['Dutch Opportunity'].details:
            data_coverage += 1
        if factors['European Momentum'].details.get('neighbors_with_records', 0) > 0:
            data_coverage += 1
        if factors['Current Activity'].details.get('records_found', 0) > 0:
            data_coverage += 1
        if factors['Pathway'].details:
            data_coverage += 1
        if factors['Expansion'].details:
            data_coverage += 1
        
        if data_coverage >= 4:
            confidence = ConfidenceLevel.HIGH
            score = 0.9
        elif data_coverage >= 3:
            confidence = ConfidenceLevel.MEDIUM
            score = 0.6
        else:
            confidence = ConfidenceLevel.LOW
            score = 0.3
        
        return confidence, score

    def identify_key_drivers(self, factors: Dict[str, FactorAnalysis]) -> List[str]:
        """Identify top 3-4 contributing factors."""
        # Sort by normalized score
        sorted_factors = sorted(
            factors.items(),
            key=lambda x: x[1].normalized_score,
            reverse=True
        )
        
        drivers = []
        for name, factor in sorted_factors[:3]:
            if factor.normalized_score > 0.3:
                if name == 'Dutch Opportunity':
                    if factor.normalized_score > 0.7:
                        drivers.append('No Dutch records yet')
                    elif factor.normalized_score < 0.3:
                        drivers.append('Already established in Netherlands')
                    
                elif name == 'European Momentum':
                    if factor.details.get('trend') == 'Increasing':
                        drivers.append(f"Increasing in Europe ({factor.details.get('neighbors_with_records', 0)} countries)")
                    else:
                        drivers.append(f"Present in Europe ({factor.details.get('neighbors_with_records', 0)} countries)")
                    
                elif name == 'Current Activity':
                    if factor.details.get('num_records', 0) > 0:
                        drivers.append(f"Recent activity: {factor.details.get('num_records')} records, {factor.details.get('num_countries')} countries")
                    
                elif name == 'Pathway':
                    pathway = factor.details.get('pathway', 'Unknown')
                    drivers.append(f"Strong {pathway} pathway")
                    
                elif name == 'Expansion':
                    if factor.details.get('range_expansion') == 'Yes':
                        drivers.append('Documented range expansion')
                    if factor.details.get('climate_signal') == 'Beneficiary':
                        drivers.append('Climate change beneficiary')
        
        return drivers if drivers else ['Limited available data']

    def convert_factors_to_probabilities(
        self,
        factors: Dict[str, FactorAnalysis],
        pathway: str
    ) -> Tuple[float, float, float]:
        """
        Convert normalized factors into 1yr, 5yr, 10yr probabilities.
        
        Logic:
        - Base rate: ~2-5% for any candidate in 1 year (very rare)
        - 5-year: compounds to ~8-20% for active candidates
        - 10-year: can reach 40-60% for strong candidates
        
        Scaling:
        1-year probability:
          - Base 2%
          - Dutch Opportunity: +0-8% if no Dutch record
          - European Momentum: +1-4% if strong
          - Current Activity: +1-3% if active
          - Pathway: +0-2% if established
          - Max cap: 20%
        
        5-year probability:
          - 2.5x the 1-year (non-linear accumulation)
          - Additional push if expansion signal strong
          - Typically 8-25%
        
        10-year probability:
          - 4-5x the 1-year (longer timeframe)
          - If pathway strong and expansion present, can reach 50%+
          - Typically 20-65%
        """
        
        dutch_opp = factors['Dutch Opportunity'].normalized_score
        eu_momentum = factors['European Momentum'].normalized_score
        current_activity = factors['Current Activity'].normalized_score
        pathway = factors['Pathway'].normalized_score
        expansion = factors['Expansion'].normalized_score
        
        # 1-YEAR PROBABILITY
        # Start with base rate
        prob_1yr = 0.02
        
        # Dutch opportunity: major driver (no Dutch record = good opportunity)
        prob_1yr += dutch_opp * 0.08
        
        # European momentum: moderate driver
        prob_1yr += eu_momentum * 0.04
        
        # Current activity: small boost
        prob_1yr += current_activity * 0.03
        
        # Pathway presence: small boost
        prob_1yr += pathway * 0.02
        
        # Cap at 20% (extreme events rare)
        prob_1yr = min(0.20, prob_1yr)
        
        # 5-YEAR PROBABILITY
        # 2.5x the 1-year as baseline (compounding)
        prob_5yr = prob_1yr * 2.5
        
        # Additional boost from expansion potential
        prob_5yr += expansion * 0.12
        
        # If pathway is very strong, boost 5-year
        if pathway > 0.7:
            prob_5yr += 0.08
        
        # Cap at 60%
        prob_5yr = min(0.60, prob_5yr)
        
        # 10-YEAR PROBABILITY
        # 4x the 1-year as baseline (long timeframe)
        prob_10yr = prob_1yr * 4.0
        
        # Strong expansion signal compounds over decade
        prob_10yr += expansion * 0.20
        
        # Pathway over 10 years is powerful
        if pathway > 0.7:
            prob_10yr += 0.15
        
        # European momentum compounds
        prob_10yr += eu_momentum * 0.12
        
        # Cap at 85% (nothing is certain)
        prob_10yr = min(0.85, prob_10yr)
        
        return max(0.0, prob_1yr), max(0.0, prob_5yr), max(0.0, prob_10yr)

    def calculate_probability(
        self,
        species: str,
        scientific_name: str,
        pathway: str,
        species_master_df: pd.DataFrame,
        dutch_records_df: pd.DataFrame,
        western_europe_df: pd.DataFrame,
        current_season_df: pd.DataFrame,
        species_traits_df: pd.DataFrame
    ) -> ProbabilityOutput:
        """Calculate complete probability forecast for one species."""
        
        # Calculate all factors
        factors = {
            'Dutch Opportunity': self.calculate_dutch_opportunity_factor(
                species, dutch_records_df, species_master_df
            ),
            'European Momentum': self.calculate_european_momentum_factor(
                species, western_europe_df, species_master_df
            ),
            'Current Activity': self.calculate_current_activity_factor(
                species, current_season_df
            ),
            'Pathway': self.calculate_pathway_factor(
                species, species_master_df
            ),
            'Expansion': self.calculate_expansion_factor(
                species, species_traits_df, species_master_df
            )
        }
        
        # Determine confidence
        confidence, confidence_score = self.calculate_confidence_score(factors)
        
        # Identify drivers
        drivers = self.identify_key_drivers(factors)
        
        # Convert to probabilities
        prob_1yr, prob_5yr, prob_10yr = self.convert_factors_to_probabilities(factors, pathway)
        
        return ProbabilityOutput(
            species=species,
            scientific_name=scientific_name,
            pathway=pathway,
            probability_1yr=prob_1yr,
            probability_5yr=prob_5yr,
            probability_10yr=prob_10yr,
            confidence=confidence,
            confidence_score=confidence_score,
            key_drivers=drivers,
            factor_breakdown=factors
        )

    def calculate_all_probabilities(self, base_path: str) -> pd.DataFrame:
        """Calculate probabilities for all species."""
        
        # Load data
        species_master, dutch_records, western_europe, current_season, species_traits = self.load_data(base_path)
        
        results = []
        
        # Process each species
        for idx, row in species_master.iterrows():
            species = row['species']
            scientific_name = row.get('scientific_name', '')
            pathway = row.get('pathway', 'Unknown')
            
            probability = self.calculate_probability(
                species=species,
                scientific_name=scientific_name,
                pathway=pathway,
                species_master_df=species_master,
                dutch_records_df=dutch_records,
                western_europe_df=western_europe,
                current_season_df=current_season,
                species_traits_df=species_traits
            )
            
            results.append(probability)
        
        # Store results for dashboard access
        self.results = results
        
        # Convert to DataFrame (keep numeric values for sorting/analysis)
        output_data = [p.to_dict(formatted=False) for p in results]
        df = pd.DataFrame(output_data)
        
        self.dataframe = df
        
        return df


def main():
    """Run probability model and generate output."""
    model = ProbabilityModel()
    
    base_path = '/workspaces/bird-predict-second/inputs/next_dutch_firsts'
    
    print("Calculating probabilities...")
    df = model.calculate_all_probabilities(base_path)
    
    # Save results (with formatted probabilities for readability)
    output_path = '/workspaces/bird-predict-second/outputs/next_dutch_firsts/probabilities.csv'
    df_formatted = df.copy()
    df_formatted['probability_1yr'] = df_formatted['probability_1yr'].apply(lambda x: f"{x:.1%}")
    df_formatted['probability_5yr'] = df_formatted['probability_5yr'].apply(lambda x: f"{x:.1%}")
    df_formatted['probability_10yr'] = df_formatted['probability_10yr'].apply(lambda x: f"{x:.1%}")
    df_formatted['confidence_score'] = df_formatted['confidence_score'].apply(lambda x: f"{x:.2f}")
    df_formatted.to_csv(output_path, index=False)
    print(f"\n✅ Probabilities saved to {output_path}")
    
    # Print summary (using raw numeric df)
    print(f"\nProcessed {len(df)} species")
    print(f"\nTop 5 by 1-year probability:")
    top_1yr = df.nlargest(5, 'probability_1yr')[['species', 'probability_1yr', 'confidence', 'key_drivers']]
    for idx, row in top_1yr.iterrows():
        print(f"  {row['species']:25s} {row['probability_1yr']:6.1%}  ({row['confidence']:8s})  {row['key_drivers'][:60]}")
    
    print(f"\nTop 5 by 5-year probability:")
    top_5yr = df.nlargest(5, 'probability_5yr')[['species', 'probability_5yr', 'confidence', 'key_drivers']]
    for idx, row in top_5yr.iterrows():
        print(f"  {row['species']:25s} {row['probability_5yr']:6.1%}  ({row['confidence']:8s})  {row['key_drivers'][:60]}")
    
    print(f"\nTop 5 by 10-year probability:")
    top_10yr = df.nlargest(5, 'probability_10yr')[['species', 'probability_10yr', 'confidence', 'key_drivers']]
    for idx, row in top_10yr.iterrows():
        print(f"  {row['species']:25s} {row['probability_10yr']:6.1%}  ({row['confidence']:8s})  {row['key_drivers'][:60]}")
    
    return model, df


if __name__ == '__main__':
    main()
