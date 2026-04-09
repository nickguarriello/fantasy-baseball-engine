"""
Fantasy Baseball H2H Category Decision Engine
Phase 1: Foundation (Data Fetch + Z-Score Calculation)

Run this script to execute the complete data pipeline:
1. Fetch ESPN league data
2. Fetch MLB player statistics
3. Calculate z-scores
4. Export CSV rankings

Usage:
    python main.py

Expected runtime: 10-15 minutes first run, 5-10 minutes subsequent runs
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LEAGUE_CONFIG
from src.database import init_database, store_player_stats, store_z_scores
from src.fetchers import fetch_espn_league_data, fetch_mlb_player_stats, test_api_connectivity
from src.processors import calculate_z_scores, calculate_trends, validate_player_data
from src.outputs import export_all_rankings, print_summary, print_status


def main():
    """
    Main orchestrator function.
    
    Runs the complete pipeline:
    1. Initialize database
    2. Fetch data from APIs
    3. Process and calculate z-scores
    4. Store in database
    5. Export CSV files
    6. Print summary
    """
    
    print("\n" + "="*70)
    print("FANTASY BASEBALL H2H DECISION ENGINE")
    print("Phase 1: Foundation (Data Pipeline + Z-Scores)")
    print("="*70)
    print(f"League ID: {LEAGUE_CONFIG['league_id']}")
    print(f"Team ID: {LEAGUE_CONFIG['team_id']}")
    print(f"Run Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    try:
        # ====================================================================
        # STEP 1: Test API connectivity
        # ====================================================================
        print("[1/6] Testing API connectivity...")
        if not test_api_connectivity():
            print("✗ Cannot connect to APIs. Check internet connection.")
            return False
        print()
        
        # ====================================================================
        # STEP 2: Initialize database
        # ====================================================================
        print("[2/6] Initializing database...")
        db_path = init_database()
        print(f"✓ Database ready at: {db_path}\n")
        
        # ====================================================================
        # STEP 3: Fetch ESPN league data
        # ====================================================================
        print("[3/6] Fetching ESPN league data...")
        print("  - Your roster")
        print("  - League info")
        espn_data = fetch_espn_league_data()
        
        if not espn_data:
            print("✗ Failed to fetch ESPN data")
            return False
        
        my_roster = espn_data.get('my_roster', [])
        print(f"✓ Found {len(my_roster)} players on your roster\n")
        
        # ====================================================================
        # STEP 4: Fetch MLB player statistics
        # ====================================================================
        print("[4/6] Fetching MLB player statistics...")
        print("  - Pulling current season stats for 1200+ MLB players")
        print("  - This is the slowest step (2-3 minutes typical)")
        mlb_stats = fetch_mlb_player_stats()
        
        if not mlb_stats:
            print("✗ Failed to fetch MLB stats")
            return False
        
        print(f"✓ Retrieved stats for {len(mlb_stats)} players\n")
        
        # ====================================================================
        # STEP 5: Calculate z-scores
        # ====================================================================
        print("[5/6] Calculating z-scores...")
        print("  - Grouping players by position")
        print("  - Computing standardized rankings")
        print("  - Z-scores: (+2.0 = elite, 0.0 = average, -2.0 = poor)")
        
        # Convert stats dict to list of players
        all_players = list(mlb_stats.values())
        
        # Filter valid players
        valid_players = [p for p in all_players if p.get('name') and p.get('position')]
        
        # Calculate z-scores
        z_scored_players, position_stats = calculate_z_scores(valid_players)
        
        if not z_scored_players:
            print("✗ Failed to calculate z-scores")
            return False
        
        print(f"✓ Calculated z-scores for {len(z_scored_players)} players\n")
        
        # ====================================================================
        # STEP 6: Calculate trends (placeholder for Phase 2)
        # ====================================================================
        print("[6/6] Analyzing trends...")
        trends_players = calculate_trends(z_scored_players)
        print(f"✓ Trend analysis complete\n")
        
        # ====================================================================
        # STORE IN DATABASE
        # ====================================================================
        print("[DB] Storing player stats in database...")
        stats_stored = store_player_stats(valid_players, mlb_stats)
        print(f"✓ Stored {stats_stored} player records")
        
        print("[DB] Storing z-scores in database...")
        z_stored = store_z_scores(z_scored_players)
        print(f"✓ Stored {z_stored} z-score records\n")
        
        # ====================================================================
        # EXPORT CSV FILES
        # ====================================================================
        print("[CSV] Exporting CSV files...")
        csv_files = export_all_rankings(z_scored_players)
        print()
        
        # ====================================================================
        # PRINT SUMMARY
        # ====================================================================
        print_summary(z_scored_players, my_roster)
        
        # ====================================================================
        # SUCCESS
        # ====================================================================
        print("="*70)
        print("✓ PHASE 1 COMPLETE")
        print("="*70)
        print(f"Completion Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nDeliverables:")
        print(f"  📊 Database: {db_path}")
        print(f"  📈 CSV files ({len(csv_files)} files):")
        for csv_file in csv_files:
            if csv_file:
                print(f"     - {Path(csv_file).name}")
        print("\nNext steps:")
        print("  1. Open CSV files in Excel to review rankings")
        print("  2. Run Phase 2: python phase_2_waiver_wire.py (coming soon)")
        print("  3. Use rankings for waiver claims and lineup decisions")
        print("="*70 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)