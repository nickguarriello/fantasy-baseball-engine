"""
Outputs Module - CSV and Console Generation

Handles:
- CSV file generation
- Console output formatting
- Summary statistics
- Player rankings export
"""

import csv
from pathlib import Path
from typing import List, Dict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_CONFIG


def export_csv(filename: str, players: List[Dict], columns: List[str]) -> str:
    """
    Export players to CSV file.
    
    Args:
        filename: CSV filename (e.g., 'all_players_ranked.csv')
        players: List of player dicts
        columns: List of column names to include
    
    Returns:
        str: Full path to created CSV file
    """
    output_dir = Path(DATA_CONFIG['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = output_dir / filename
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            
            for player in players:
                # Only write columns that exist in player dict
                row = {col: player.get(col, '') for col in columns}
                writer.writerow(row)
        
        print(f"    ✓ {filename} ({len(players)} players)")
        return str(filepath)
        
    except Exception as e:
        print(f"    ✗ Error writing {filename}: {e}")
        return ""


def export_all_rankings(all_players: List[Dict]) -> List[str]:
    """
    Export all ranking CSV files.
    
    Creates multiple CSV files from the player data:
    - all_players_ranked.csv: All 1200+ players
    - free_agents_ranked.csv: Non-roster players
    - your_roster.csv: Your team only
    - hitters_ranked.csv: Hitters only
    - pitchers_ranked.csv: Pitchers only
    
    Args:
        all_players: List of all players with z-scores
    
    Returns:
        List of created CSV file paths
    """
    print("\n  Exporting CSV files...")
    
    created_files = []
    
    # Define columns for CSV export
    columns = [
        'name', 'position', 'mlb_team', 'is_pitcher',
        'z_season', 'z_30day', 'z_14day',
        'z_r', 'z_hr', 'z_rbi', 'z_sb', 'z_obp',
        'z_k', 'z_qs', 'z_era', 'z_whip', 'z_svhd'
    ]
    
    # 1. ALL PLAYERS (sorted by season z-score)
    all_sorted = sorted(all_players, key=lambda x: x.get('z_season', 0), reverse=True)
    file1 = export_csv('all_players_ranked.csv', all_sorted, columns)
    created_files.append(file1)
    
    # 2. HITTERS ONLY
    hitters = [p for p in all_sorted if not p.get('is_pitcher')]
    file2 = export_csv('hitters_ranked.csv', hitters, columns)
    created_files.append(file2)
    
    # 3. PITCHERS ONLY
    pitchers = [p for p in all_sorted if p.get('is_pitcher')]
    file3 = export_csv('pitchers_ranked.csv', pitchers, columns)
    created_files.append(file3)
    
    return created_files


def print_summary(all_players: List[Dict], your_roster: List[Dict] = None) -> None:
    """
    Print summary statistics to console.
    
    Args:
        all_players: All players with z-scores
        your_roster: Your team roster (optional)
    """
    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)
    
    hitters = [p for p in all_players if not p.get('is_pitcher')]
    pitchers = [p for p in all_players if p.get('is_pitcher')]
    
    print(f"\nTotal Players Analyzed: {len(all_players)}")
    print(f"  Hitters: {len(hitters)}")
    print(f"  Pitchers: {len(pitchers)}")
    
    if your_roster:
        your_hitters = [p for p in your_roster if not p.get('is_pitcher')]
        your_pitchers = [p for p in your_roster if p.get('is_pitcher')]
        
        print(f"\nYour Roster: {len(your_roster)} players")
        print(f"  Hitters: {len(your_hitters)}")
        print(f"  Pitchers: {len(your_pitchers)}")
        
        # Your team's average z-score
        if your_roster:
            avg_z = sum(p.get('z_season', 0) for p in your_roster) / len(your_roster)
            print(f"  Average Z-Score: {avg_z:.2f}")
    
    # Top players
    print(f"\nTop 5 Players Overall:")
    for i, player in enumerate(sorted(all_players, key=lambda x: x.get('z_season', 0), reverse=True)[:5], 1):
        print(f"  {i}. {player.get('name')} ({player.get('position')}) Z={player.get('z_season'):.2f}")
    
    print("\n" + "="*70 + "\n")


def print_status() -> None:
    """
    Print quick status check from database.
    
    Shows how many records exist without needing to load all data.
    """
    import sqlite3
    from config import DATA_CONFIG
    
    db_path = DATA_CONFIG['db_path']
    
    if not Path(db_path).exists():
        print("Database not yet created.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM players")
        player_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM player_stats")
        stats_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM player_z_scores")
        z_count = cursor.fetchone()[0]
        
        print(f"\nDatabase Status:")
        print(f"  Players in database: {player_count}")
        print(f"  Stats records: {stats_count}")
        print(f"  Z-score records: {z_count}")
        
    except sqlite3.Error as e:
        print(f"Error querying database: {e}")
    finally:
        conn.close()