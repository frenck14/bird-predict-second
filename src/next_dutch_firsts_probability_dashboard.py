"""
Next Dutch Firsts Probability Dashboard

Display live probability forecasts and source health status.
Shows 1yr/5yr/10yr probabilities instead of static scores.
"""

import pandas as pd
import json
from html import escape
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum

if __package__:
    from .next_dutch_firsts_weather import MAX_FORECAST_AGE
else:
    from next_dutch_firsts_weather import MAX_FORECAST_AGE


class TableType(Enum):
    """Dashboard table types."""
    BY_1YR = "Most likely within 1 year"
    BY_5YR = "Most likely within 5 years"
    BY_10YR = "Most likely within 10 years"
    ATLANTIC = "Strongest Atlantic candidates"
    EASTERN = "Strongest Eastern candidates"


@dataclass
class ProbabilityRecord:
    """One row in the probability table."""
    species: str
    scientific_name: str
    pathway: str
    probability_1yr: float
    probability_5yr: float
    probability_10yr: float
    confidence: str
    key_drivers: str


class ProbabilityDashboard:
    """Generate probability forecasts dashboard."""
    
    def __init__(self, probabilities_path: Optional[str] = None):
        """
        Initialize dashboard.
        
        Args:
            probabilities_path: Path to probabilities.csv. If None, uses default.
        """
        if probabilities_path is None:
            probabilities_path = '/workspaces/bird-predict-second/outputs/next_dutch_firsts/probabilities.csv'
        
        self.probabilities_path = probabilities_path
        self.df = None
        self.load_probabilities()
    
    def load_probabilities(self):
        """Load probabilities CSV."""
        if Path(self.probabilities_path).exists():
            self.df = pd.read_csv(self.probabilities_path)
            # Parse probability strings back to floats
            for col in ['probability_1yr', 'probability_5yr', 'probability_10yr']:
                if col in self.df.columns:
                    text = self.df[col].astype(str).str.strip()
                    values = pd.to_numeric(text.str.removesuffix('%'), errors='raise')
                    self.df[col] = values.where(~text.str.endswith('%'), values / 100.0)
            self.df['confidence_score'] = pd.to_numeric(self.df['confidence_score'], errors='coerce')

    def get_opportunity_table(self) -> pd.DataFrame:
        """Return all species, with stale saved weather explicitly unavailable."""
        if self.df is None or self.df.empty:
            return pd.DataFrame()
        frame = self.df.copy()
        defaults = {
            'baseline_total_score': frame['total_score'] if 'total_score' in frame else None,
            'weather_support': None,
            'near_term_opportunity_score': None,
            'weather_source': None,
            'weather_forecast_date': None,
            'weather_generated_at': None,
            'weather_input_source': None,
            'weather_raw_probability': None,
            'weather_status': 'unavailable',
            'weather_explanation': 'Weather Support is not present in this saved forecast; regenerate it.',
        }
        for column, default in defaults.items():
            if column not in frame:
                frame[column] = default
        for column in ('baseline_total_score', 'weather_support', 'near_term_opportunity_score', 'weather_raw_probability'):
            frame[column] = pd.to_numeric(frame[column], errors='coerce')
        now = pd.Timestamp.now(tz='UTC')
        generated = pd.to_datetime(frame['weather_generated_at'], utc=True, errors='coerce')
        dates = pd.to_datetime(frame['weather_forecast_date'], errors='coerce', utc=True)
        available = frame['weather_status'].eq('available')
        stale = available & (
            generated.isna() | dates.isna() | (generated > now)
            | (now - generated > MAX_FORECAST_AGE)
            | (dates < now.normalize())
        )
        frame.loc[stale, ['weather_support', 'near_term_opportunity_score']] = float('nan')
        frame.loc[stale, 'weather_status'] = 'unavailable'
        frame.loc[stale, 'weather_explanation'] = 'Saved weather forecast is stale or has invalid dates; regenerate it.'
        return frame.sort_values('near_term_opportunity_score', ascending=False, na_position='last', kind='stable')

    @staticmethod
    def _value(value, suffix: str = '') -> str:
        return 'Unavailable' if pd.isna(value) else f'{float(value):.2f}{suffix}'

    def _opportunity_text(self) -> str:
        frame = self.get_opportunity_table()
        lines = [
            "NEAR-TERM OPPORTUNITY (experimental score, not a probability)",
            "Weather is a pooled pathway signal. Long-term probabilities are unchanged.",
        ]
        for _, row in frame.iterrows():
            lines.append(
                f"{row['species']}: Baseline Total Score {self._value(row['baseline_total_score'])}; "
                f"Weather Support {self._value(row['weather_support'])}; "
                f"Near-Term Opportunity Score {self._value(row['near_term_opportunity_score'])}"
            )
            raw = row['weather_raw_probability']
            raw_text = 'Unavailable' if pd.isna(raw) else f'{float(raw):.4f}'
            source = row['weather_source'] if pd.notna(row['weather_source']) else 'Unavailable'
            date = row['weather_forecast_date'] if pd.notna(row['weather_forecast_date']) else 'Unavailable'
            input_source = row['weather_input_source'] if pd.notna(row['weather_input_source']) else 'Unavailable'
            lines.append(f"  Source: {source}; date: {date}; raw probability: {raw_text}; weather input: {input_source}")
            lines.append(f"  {row['weather_status']}: {row['weather_explanation']}")
        return '\n'.join(lines)

    def _opportunity_html(self) -> str:
        frame = self.get_opportunity_table()
        html = (
            '<div class="section"><h2 class="section-title">Near-Term Opportunity</h2>'
            '<p>Experimental score, not a probability. Weather is a pooled pathway signal; '
            'long-term probabilities are unchanged.</p><table><thead><tr>'
            '<th>Species</th><th>Baseline Total Score</th><th>Weather Support</th>'
            '<th>Near-Term Opportunity Score</th><th>Weather provenance and explanation</th>'
            '</tr></thead><tbody>'
        )
        for _, row in frame.iterrows():
            raw = row['weather_raw_probability']
            raw_text = 'Unavailable' if pd.isna(raw) else f'{float(raw):.4f}'
            def text(column):
                return escape(str(row[column])) if pd.notna(row[column]) else 'Unavailable'
            html += (
                f'<tr><td>{text("species")}</td>'
                f'<td>{self._value(row["baseline_total_score"])}</td>'
                f'<td>{self._value(row["weather_support"])}</td>'
                f'<td>{self._value(row["near_term_opportunity_score"])}</td>'
                f'<td>{text("weather_status")}: {text("weather_source")}; date: '
                f'{text("weather_forecast_date")}; raw probability: {raw_text}; '
                f'weather input: {text("weather_input_source")}<br>{text("weather_explanation")}</td></tr>'
            )
        return html + '</tbody></table></div>'
    
    def get_table(self, table_type: TableType, limit: int = 10) -> pd.DataFrame:
        """Get a specific dashboard table."""
        if self.df is None or self.df.empty:
            return pd.DataFrame()
        
        if table_type == TableType.BY_1YR:
            return self.df.nlargest(limit, 'probability_1yr')[
                ['species', 'probability_1yr', 'probability_5yr', 'confidence', 'key_drivers']
            ]
        
        elif table_type == TableType.BY_5YR:
            return self.df.nlargest(limit, 'probability_5yr')[
                ['species', 'probability_5yr', 'probability_10yr', 'confidence', 'key_drivers']
            ]
        
        elif table_type == TableType.BY_10YR:
            return self.df.nlargest(limit, 'probability_10yr')[
                ['species', 'probability_10yr', 'confidence', 'key_drivers']
            ]
        
        elif table_type == TableType.ATLANTIC:
            atlantic = self.df[self.df['pathway'] == 'Atlantic'].nlargest(limit, 'probability_5yr')[
                ['species', 'probability_1yr', 'probability_5yr', 'probability_10yr', 'confidence']
            ]
            return atlantic
        
        elif table_type == TableType.EASTERN:
            eastern = self.df[self.df['pathway'] == 'Eastern'].nlargest(limit, 'probability_5yr')[
                ['species', 'probability_1yr', 'probability_5yr', 'probability_10yr', 'confidence']
            ]
            return eastern
        
        return pd.DataFrame()
    
    def format_probability(self, prob: float) -> str:
        """Format probability as percentage."""
        if pd.isna(prob):
            return "—"
        return f"{prob:.1%}"
    
    def render_text_probability_card(self, row_idx: int) -> str:
        """Render a single species probability card (text format)."""
        if self.df is None or self.df.empty or row_idx >= len(self.df):
            return ""
        
        row = self.df.iloc[row_idx]
        
        card = f"""
┌─────────────────────────────────────────────────────────┐
│ {row['species']:40s} {"RANK #" + str(row_idx+1):>13s} │
├─────────────────────────────────────────────────────────┤
│ {row['scientific_name']:57s} │
│ Pathway: {row['pathway']:8s}  Confidence: {row['confidence']:8s}       │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Probability of Dutch occurrence                        │
│  ─────────────────────────────────────────────────       │
│                                                           │
│  1 year:   {self.format_probability(row['probability_1yr']):>5s}                          │
│  5 years:  {self.format_probability(row['probability_5yr']):>5s}                          │
│  10 years: {self.format_probability(row['probability_10yr']):>5s}                          │
│                                                           │
├─────────────────────────────────────────────────────────┤
│ Key Drivers:                                              │
"""
        drivers = str(row['key_drivers']).split(' | ')
        for driver in drivers[:3]:
            card += f"│ • {driver[:52]:52s} │\n"
        
        card += "└─────────────────────────────────────────────────────────┘"
        return card
    
    def render_text_status(self) -> str:
        """Render complete dashboard in text format."""
        output = []
        output.append("╔═══════════════════════════════════════════════════════════════════════════╗")
        output.append("║           NEXT DUTCH FIRSTS - PROBABILITY FORECAST DASHBOARD             ║")
        output.append("║                    Transparent Actuarial Model                           ║")
        output.append("╚═══════════════════════════════════════════════════════════════════════════╝")
        output.append("")
        output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        output.append(f"Total species analyzed: {len(self.df) if self.df is not None else 0}")
        output.append("")
        output.append(self._opportunity_text())
        output.append("")
        
        # Table 1: Most likely within 1 year
        output.append("═" * 75)
        output.append("MOST LIKELY WITHIN 1 YEAR")
        output.append("═" * 75)
        output.append("")
        
        table_1yr = self.get_table(TableType.BY_1YR, limit=5)
        if not table_1yr.empty:
            output.append(f"{'Rank':<5} {'Species':<30} {'1-Yr':<8} {'5-Yr':<8} {'Conf':<8}")
            output.append("─" * 75)
            for rank, (idx, row) in enumerate(table_1yr.iterrows(), 1):
                output.append(
                    f"{rank:<5} {row['species']:<30} "
                    f"{self.format_probability(row['probability_1yr']):<8} "
                    f"{self.format_probability(row['probability_5yr']):<8} "
                    f"{row['confidence']:<8}"
                )
        output.append("")
        
        # Table 2: Most likely within 5 years
        output.append("═" * 75)
        output.append("MOST LIKELY WITHIN 5 YEARS")
        output.append("═" * 75)
        output.append("")
        
        table_5yr = self.get_table(TableType.BY_5YR, limit=5)
        if not table_5yr.empty:
            output.append(f"{'Rank':<5} {'Species':<30} {'5-Yr':<8} {'10-Yr':<8} {'Conf':<8}")
            output.append("─" * 75)
            for rank, (idx, row) in enumerate(table_5yr.iterrows(), 1):
                output.append(
                    f"{rank:<5} {row['species']:<30} "
                    f"{self.format_probability(row['probability_5yr']):<8} "
                    f"{self.format_probability(row['probability_10yr']):<8} "
                    f"{row['confidence']:<8}"
                )
        output.append("")
        
        # Table 3: Most likely within 10 years
        output.append("═" * 75)
        output.append("MOST LIKELY WITHIN 10 YEARS")
        output.append("═" * 75)
        output.append("")
        
        table_10yr = self.get_table(TableType.BY_10YR, limit=5)
        if not table_10yr.empty:
            output.append(f"{'Rank':<5} {'Species':<30} {'10-Yr':<8} {'Conf':<8}")
            output.append("─" * 75)
            for rank, (idx, row) in enumerate(table_10yr.iterrows(), 1):
                output.append(
                    f"{rank:<5} {row['species']:<30} "
                    f"{self.format_probability(row['probability_10yr']):<8} "
                    f"{row['confidence']:<8}"
                )
        output.append("")
        
        # Table 4: Atlantic pathways
        output.append("═" * 75)
        output.append("STRONGEST ATLANTIC CANDIDATES")
        output.append("═" * 75)
        output.append("")
        
        table_atlantic = self.get_table(TableType.ATLANTIC, limit=5)
        if not table_atlantic.empty:
            output.append(f"{'Rank':<5} {'Species':<30} {'1-Yr':<8} {'5-Yr':<8} {'10-Yr':<8}")
            output.append("─" * 75)
            for rank, (idx, row) in enumerate(table_atlantic.iterrows(), 1):
                output.append(
                    f"{rank:<5} {row['species']:<30} "
                    f"{self.format_probability(row['probability_1yr']):<8} "
                    f"{self.format_probability(row['probability_5yr']):<8} "
                    f"{self.format_probability(row['probability_10yr']):<8}"
                )
        output.append("")
        
        # Table 5: Eastern pathways
        output.append("═" * 75)
        output.append("STRONGEST EASTERN CANDIDATES")
        output.append("═" * 75)
        output.append("")
        
        table_eastern = self.get_table(TableType.EASTERN, limit=5)
        if not table_eastern.empty:
            output.append(f"{'Rank':<5} {'Species':<30} {'1-Yr':<8} {'5-Yr':<8} {'10-Yr':<8}")
            output.append("─" * 75)
            for rank, (idx, row) in enumerate(table_eastern.iterrows(), 1):
                output.append(
                    f"{rank:<5} {row['species']:<30} "
                    f"{self.format_probability(row['probability_1yr']):<8} "
                    f"{self.format_probability(row['probability_5yr']):<8} "
                    f"{self.format_probability(row['probability_10yr']):<8}"
                )
        output.append("")
        
        return "\n".join(line.rstrip() for line in output)
    
    def render_html_dashboard(self, output_path: Optional[str] = None) -> str:
        """Render dashboard as HTML."""
        if output_path is None:
            output_path = '/workspaces/bird-predict-second/outputs/next_dutch_firsts/probability_dashboard.html'
        
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Next Dutch Firsts - Probability Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .timestamp {
            color: #999;
            font-size: 0.9em;
            margin-top: 10px;
        }
        .content {
            padding: 40px 20px;
        }
        .section {
            margin-bottom: 50px;
        }
        .section-title {
            font-size: 1.8em;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th {
            background: #f5f5f5;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #333;
            border-bottom: 2px solid #667eea;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #eee;
        }
        tr:hover { background: #f9f9f9; }
        .prob-high { color: #d32f2f; font-weight: bold; }
        .prob-medium { color: #f57c00; font-weight: bold; }
        .prob-low { color: #1976d2; }
        .confidence-high { background: #c8e6c9; color: #2e7d32; padding: 4px 8px; border-radius: 4px; font-weight: 600; }
        .confidence-medium { background: #ffe0b2; color: #e65100; padding: 4px 8px; border-radius: 4px; font-weight: 600; }
        .confidence-low { background: #bbdefb; color: #1565c0; padding: 4px 8px; border-radius: 4px; font-weight: 600; }
        .drivers {
            font-size: 0.9em;
            color: #666;
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🦅 Next Dutch Firsts</h1>
            <p>Probability Forecast Dashboard</p>
            <p class="timestamp">Transparent Actuarial Model</p>
            <p class="timestamp">Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC') + """</p>
        </div>
        
        <div class="content">
"""
        
        html += self._opportunity_html()

        # Add tables
        tables = [
            (TableType.BY_1YR, "Most Likely Within 1 Year", ['species', 'probability_1yr', 'probability_5yr', 'confidence']),
            (TableType.BY_5YR, "Most Likely Within 5 Years", ['species', 'probability_5yr', 'probability_10yr', 'confidence']),
            (TableType.BY_10YR, "Most Likely Within 10 Years", ['species', 'probability_10yr', 'confidence']),
            (TableType.ATLANTIC, "Strongest Atlantic Candidates", ['species', 'probability_1yr', 'probability_5yr', 'probability_10yr']),
            (TableType.EASTERN, "Strongest Eastern Candidates", ['species', 'probability_1yr', 'probability_5yr', 'probability_10yr']),
        ]
        
        for table_type, title, columns in tables:
            table_df = self.get_table(table_type, limit=8)
            if not table_df.empty:
                html += f'            <div class="section">\n'
                html += f'                <h2 class="section-title">{title}</h2>\n'
                html += f'                <table>\n'
                
                # Headers
                html += '                    <thead><tr>\n'
                for col in columns:
                    col_display = col.replace('probability_', '').replace('_', ' ').title()
                    html += f'                        <th>{col_display}</th>\n'
                html += '                    </tr></thead>\n'
                
                # Rows
                html += '                    <tbody>\n'
                for rank, (idx, row) in enumerate(table_df.iterrows(), 1):
                    html += '                        <tr>\n'
                    for col in columns:
                        if col == 'species':
                            html += f'                            <td><strong>{rank}. {row[col]}</strong></td>\n'
                        elif 'probability' in col:
                            prob = row[col]
                            if prob >= 0.15:
                                css_class = 'prob-high'
                            elif prob >= 0.08:
                                css_class = 'prob-medium'
                            else:
                                css_class = 'prob-low'
                            html += f'                            <td class="{css_class}">{self.format_probability(prob)}</td>\n'
                        elif col == 'confidence':
                            conf_class = f"confidence-{row[col].lower()}"
                            html += f'                            <td class="{conf_class}">{row[col]}</td>\n'
                        else:
                            html += f'                            <td>{row[col]}</td>\n'
                    html += '                        </tr>\n'
                html += '                    </tbody>\n'
                html += '                </table>\n'
                html += '            </div>\n'
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        
        # Save HTML
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(html)
        
        return output_path


def main():
    """Generate dashboard outputs."""
    dashboard = ProbabilityDashboard()
    
    # Text output
    text_output = dashboard.render_text_status()
    print(text_output)
    
    # Save text
    text_path = '/workspaces/bird-predict-second/outputs/next_dutch_firsts/probability_dashboard.txt'
    Path(text_path).parent.mkdir(parents=True, exist_ok=True)
    with open(text_path, 'w') as f:
        f.write(text_output)
    print(f"\n✅ Text dashboard saved to {text_path}")
    
    # HTML output
    html_path = dashboard.render_html_dashboard()
    print(f"✅ HTML dashboard saved to {html_path}")


if __name__ == '__main__':
    main()
