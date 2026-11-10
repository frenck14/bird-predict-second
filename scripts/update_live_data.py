#!/usr/bin/env python3
"""Update Next Dutch Firsts live data from all configured sources.

This script can be run manually or scheduled (cron, GitHub Actions, etc.).
It updates all registered data sources and generates a status report.

Usage:
    python scripts/update_live_data.py [--skip-unavailable] [--cache] [--score]
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from next_dutch_firsts_live_data import create_live_data_manager
from next_dutch_firsts_dashboard import DataStatusDashboard
from next_dutch_firsts_scoring import apply_live_scoring_to_candidates
import pandas as pd


def setup_logging(level=logging.INFO):
    """Configure logging output."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/live_data_update.log", mode="a"),
        ],
    )


def update_all_sources(skip_unavailable=True):
    """Update all registered data sources."""
    manager = create_live_data_manager()
    results = manager.update_all_sources(skip_unavailable=skip_unavailable)
    return manager, results


def cache_status(manager):
    """Cache current status for quick dashboard retrieval."""
    dashboard = DataStatusDashboard()
    dashboard.cache_status()
    print("\n✅ Status cached for dashboard")


def score_candidates(manager):
    """Generate live scores for all candidate species."""
    print("\n📊 Generating live scores...")
    
    species_master_file = Path(__file__).parent.parent / "inputs/next_dutch_firsts/species_master.csv"
    
    if not species_master_file.exists():
        print(f"⚠ Species master not found: {species_master_file}")
        return
    
    species_list = pd.read_csv(species_master_file)
    scores_df = apply_live_scoring_to_candidates(species_list)
    
    output_file = Path(__file__).parent.parent / "outputs/next_dutch_firsts/live_scores.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    scores_df.to_csv(output_file, index=False)
    
    print(f"✅ Scored {len(scores_df)} species")
    print(f"   Output: {output_file}")
    
    # Show top 10 candidates
    if "score" in scores_df.columns:
        top_10 = scores_df.nlargest(10, "score")[["species", "score", "dutch_quality"]]
        print("\n🏆 Top 10 Candidates:")
        for _, row in top_10.iterrows():
            print(f"   {row['species']:30s} {row['score']:.3f} ({row['dutch_quality']})")


def print_summary(results):
    """Print update summary."""
    print("\n" + "=" * 70)
    print("📊 UPDATE SUMMARY")
    print("=" * 70)
    
    total_records = sum(results.values())
    successful_sources = sum(1 for v in results.values() if v > 0)
    total_sources = len(results)
    
    print(f"Total records loaded: {total_records}")
    print(f"Sources successful: {successful_sources}/{total_sources}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    for source_name, record_count in sorted(results.items()):
        emoji = "✅" if record_count > 0 else "⚠"
        print(f"{emoji} {source_name}: {record_count} records")
    
    print("=" * 70)


def print_status_report(manager):
    """Print detailed status report."""
    manager.print_status()


def main():
    parser = argparse.ArgumentParser(
        description="Update Next Dutch Firsts live data from all sources"
    )
    parser.add_argument(
        "--skip-unavailable",
        action="store_true",
        default=True,
        help="Skip unavailable sources instead of raising errors (default: True)",
    )
    parser.add_argument(
        "--no-skip-unavailable",
        action="store_false",
        dest="skip_unavailable",
        help="Raise errors on unavailable sources",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Cache status for quick dashboard retrieval",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="Generate live scores for candidate species",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging output",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    
    print("\n" + "=" * 70)
    print("🔄 NEXT DUTCH FIRSTS - LIVE DATA UPDATE")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    try:
        # Update all sources
        manager, results = update_all_sources(skip_unavailable=args.skip_unavailable)
        
        # Print summary
        print_summary(results)
        
        # Print detailed status
        print_status_report(manager)
        
        # Cache status if requested
        if args.cache:
            cache_status(manager)
        
        # Generate scores if requested
        if args.score:
            score_candidates(manager)
        
        print("\n" + "=" * 70)
        print("✅ UPDATE COMPLETE")
        print("=" * 70)
        print(f"Finished: {datetime.now().isoformat()}")
        print()
        
        return 0
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logging.exception("Unhandled exception during update")
        return 1


if __name__ == "__main__":
    sys.exit(main())
