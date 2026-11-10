"""Dashboard enhancements for Next Dutch Firsts live data.

Provides a data status section showing source health and update history.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
LIVE_DATA_DIR = ROOT / "inputs/next_dutch_firsts/live"


class DataStatusDashboard:
    """Renders live data source status for dashboard display."""
    
    def __init__(self):
        self.metadata_file = LIVE_DATA_DIR / "source_metadata.csv"
        self.status_cache_file = LIVE_DATA_DIR / "dashboard_status_cache.json"
    
    def load_source_metadata(self) -> pd.DataFrame | None:
        """Load current source metadata.
        
        Returns:
            DataFrame with source status or None if unavailable.
        """
        if not self.metadata_file.exists():
            logger.warning(f"Metadata file not found: {self.metadata_file}")
            return None
        
        try:
            return pd.read_csv(self.metadata_file)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return None
    
    def get_status_summary(self) -> dict[str, Any]:
        """Get current status of all sources.
        
        Returns:
            Dict with overall system status and per-source details.
        """
        metadata = self.load_source_metadata()
        
        if metadata is None or metadata.empty:
            return {
                "status": "initializing",
                "timestamp": datetime.now().isoformat(),
                "sources": {},
                "overall_health": "unknown",
            }
        
        sources = {}
        healthy_count = 0
        total_count = len(metadata)
        
        for _, row in metadata.iterrows():
            source_name = row.get("name", "Unknown")
            status = row.get("update_status", "unknown")
            
            # Determine emoji
            if status == "success":
                emoji = "✅"
                healthy_count += 1
            elif status == "unavailable" or status == "failed":
                emoji = "⚠"
            else:
                emoji = "❌"
            
            sources[source_name] = {
                "emoji": emoji,
                "type": row.get("source_type", "unknown"),
                "status": status,
                "priority": int(row.get("priority", 0)),
                "record_count": int(row.get("record_count", 0)),
                "last_updated": row.get("last_updated"),
                "error": row.get("error_message"),
            }
        
        # Overall health assessment
        health_percent = (healthy_count / total_count * 100) if total_count > 0 else 0
        if health_percent >= 80:
            overall_health = "good"
        elif health_percent >= 60:
            overall_health = "fair"
        else:
            overall_health = "poor"
        
        return {
            "status": "operational",
            "timestamp": datetime.now().isoformat(),
            "overall_health": overall_health,
            "health_percent": health_percent,
            "sources_healthy": healthy_count,
            "sources_total": total_count,
            "sources": sources,
        }
    
    def render_text_status(self) -> str:
        """Render human-readable text status report.
        
        Returns:
            Multi-line string for console/terminal display.
        """
        status = self.get_status_summary()
        
        lines = [
            "",
            "=" * 70,
            "📊 LIVE DATA SOURCE STATUS",
            "=" * 70,
            f"Overall Health: {status['overall_health'].upper()} ({status['health_percent']:.0f}%)",
            f"Timestamp: {status['timestamp']}",
            "",
        ]
        
        for source_name, info in sorted(status["sources"].items()):
            lines.append(f"{info['emoji']} {source_name}")
            lines.append(f"   Type: {info['type']}")
            lines.append(f"   Status: {info['status']}")
            lines.append(f"   Records: {info['record_count']}")
            if info["last_updated"]:
                lines.append(f"   Last updated: {info['last_updated']}")
            if info["error"]:
                lines.append(f"   Error: {info['error']}")
            lines.append("")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def render_html_status(self) -> str:
        """Render HTML status dashboard.
        
        Returns:
            HTML string for web display.
        """
        status = self.get_status_summary()
        
        html = f"""
        <div class="live-data-status">
            <h2>🔄 Live Data Status</h2>
            <div class="status-summary">
                <p><strong>Overall Health:</strong> {status['overall_health'].upper()}</p>
                <p><strong>Sources Online:</strong> {status['sources_healthy']}/{status['sources_total']}</p>
                <p><strong>Last Updated:</strong> {status['timestamp']}</p>
            </div>
            <table class="sources-table">
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Records</th>
                        <th>Last Update</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for source_name, info in sorted(status["sources"].items()):
            emoji = info["emoji"]
            status_text = info["status"]
            records = info["record_count"]
            updated = info["last_updated"] or "Never"
            
            html += f"""
                    <tr>
                        <td>{emoji} {source_name}</td>
                        <td>{info['type']}</td>
                        <td>{status_text}</td>
                        <td>{records}</td>
                        <td>{updated}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
            <style>
                .live-data-status { font-family: monospace; margin: 20px; }
                .status-summary { background: #f5f5f5; padding: 10px; border-radius: 5px; }
                .sources-table {
                    border-collapse: collapse;
                    width: 100%;
                    margin-top: 10px;
                }
                .sources-table th, .sources-table td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                .sources-table th { background-color: #f2f2f2; }
            </style>
        </div>
        """
        
        return html
    
    def render_streamlit_status(self) -> None:
        """Render status dashboard in Streamlit app.
        
        Requires: streamlit imported in calling context.
        """
        try:
            import streamlit as st
        except ImportError:
            logger.warning("Streamlit not available; use render_text_status() instead")
            return
        
        status = self.get_status_summary()
        
        st.subheader("🔄 Live Data Source Status")
        
        # Overall health metric
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Overall Health", status["overall_health"].upper())
        with col2:
            st.metric("Sources Online", f"{status['sources_healthy']}/{status['sources_total']}")
        with col3:
            st.metric("Health Score", f"{status['health_percent']:.0f}%")
        
        st.divider()
        
        # Per-source status
        st.write("### Source Status")
        
        df_rows = []
        for source_name, info in sorted(status["sources"].items()):
            df_rows.append({
                "Status": info["emoji"],
                "Source": source_name,
                "Type": info["type"],
                "Records": info["record_count"],
                "Last Updated": info["last_updated"] or "Never",
            })
        
        if df_rows:
            df_status = pd.DataFrame(df_rows)
            st.dataframe(df_status, use_container_width=True)
        
        # Source details (expandable)
        st.write("### Source Details")
        for source_name, info in sorted(status["sources"].items()):
            with st.expander(f"{info['emoji']} {source_name}"):
                st.write(f"**Type:** {info['type']}")
                st.write(f"**Status:** {info['status']}")
                st.write(f"**Priority:** {info['priority']}")
                st.write(f"**Records:** {info['record_count']}")
                if info["last_updated"]:
                    st.write(f"**Last Updated:** {info['last_updated']}")
                if info["error"]:
                    st.warning(f"**Error:** {info['error']}")
    
    def cache_status(self) -> None:
        """Cache current status to JSON file for quick retrieval.
        
        Useful for dashboard that needs frequent status updates without
        full re-computation.
        """
        status = self.get_status_summary()
        
        try:
            with open(self.status_cache_file, "w") as f:
                json.dump(status, f, indent=2)
            logger.info(f"Cached status to {self.status_cache_file}")
        except Exception as e:
            logger.error(f"Failed to cache status: {e}")
    
    def load_cached_status(self) -> dict[str, Any] | None:
        """Load cached status if available.
        
        Returns:
            Cached status dict or None if not available.
        """
        if not self.status_cache_file.exists():
            return None
        
        try:
            with open(self.status_cache_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load cached status: {e}")
            return None


class ScoreSourceAttribution:
    """Track which sources contributed to each species score."""
    
    def __init__(self):
        self.attribution_file = LIVE_DATA_DIR / "score_attribution.parquet"
    
    def save_attribution(self, species_name: str, score: float, sources: dict[str, Any]) -> None:
        """Record which sources contributed to a score.
        
        Args:
            species_name: Name of species.
            score: Calculated score.
            sources: Dict with source names and quality indicators.
        """
        record = {
            "species": species_name,
            "score": score,
            "timestamp": datetime.now().isoformat(),
            "dutch_source": sources.get("dutch_source", "none"),
            "dutch_quality": sources.get("dutch_quality"),
            "atlantic_source": sources.get("atlantic_source", "none"),
            "atlantic_quality": sources.get("atlantic_quality"),
            "weather_source": sources.get("weather_source", "none"),
        }
        
        if self.attribution_file.exists():
            existing = pd.read_parquet(self.attribution_file)
            df = pd.concat([existing, pd.DataFrame([record])], ignore_index=True)
        else:
            df = pd.DataFrame([record])
        
        df.to_parquet(self.attribution_file)
    
    def get_attribution_for_species(self, species_name: str) -> dict[str, Any] | None:
        """Retrieve source attribution for a species.
        
        Args:
            species_name: Name of species.
        
        Returns:
            Latest attribution record or None.
        """
        if not self.attribution_file.exists():
            return None
        
        df = pd.read_parquet(self.attribution_file)
        species_records = df[df["species"] == species_name]
        
        if species_records.empty:
            return None
        
        # Return most recent record
        return species_records.iloc[-1].to_dict()
    
    def get_source_impact(self) -> pd.DataFrame:
        """Analyze which sources contribute most to scores.
        
        Returns:
            DataFrame with source impact statistics.
        """
        if not self.attribution_file.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(self.attribution_file)
        
        impact = {
            "Dutch Avifauna": len(df[df["dutch_source"] == "Dutch Avifauna (CDNA)"]),
            "European Live": len(df[df["atlantic_source"].str.contains("Live", na=False)]),
            "Manual Values": len(df[df["dutch_source"] == "Manual (Species Master)"]),
            "Weather": len(df[df["weather_source"] != "none"]),
        }
        
        return pd.DataFrame([impact])


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Example usage
    dashboard = DataStatusDashboard()
    print(dashboard.render_text_status())
    dashboard.cache_status()
