"""
Database Module - SQLite Management

Handles:
- Database initialization and schema creation
- Player data storage
- Stats storage (time-series)
- Z-score storage and retrieval
- Query operations for decision-making
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import sys
import os

# Add parent directory to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_CONFIG

# Database path from config
DB_PATH = DATA_CONFIG['db_path']


def init_database() -> str:
    """
    Initialize SQLite database with all required tables.
    
    Creates database file and schema if it doesn't exist.
    If database exists, verifies schema is complete.
    
    Returns:
        str: Path to the database file
        
    Raises:
        sqlite3.Error: If database creation fails
    """
    # Ensure data directory exists
    data_dir = Path(DB_PATH).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Connect to database (creates file if doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # ====================================================================
        # Table 1: PLAYERS (Master player data)
        # ====================================================================
        # Stores basic info about each MLB player
        # One row per player, updated occasionally
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                player_id TEXT PRIMARY KEY,           -- ESPN player ID (unique)
                mlb_id INTEGER,                       -- MLB.com player ID
                name TEXT NOT NULL,                   -- Player name
                position TEXT,                        -- Position (C, SS, OF, P, etc.)
                mlb_team TEXT,                        -- MLB team (NYY, BOS, etc.)
                is_pitcher BOOLEAN DEFAULT 0,         -- 1 if pitcher, 0 if hitter
                ownership_pct REAL,                   -- % of leagues that own this player
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ====================================================================
        # Table 2: PLAYER_STATS (Time-series stats)
        # ====================================================================
        # Stores stats every time you refresh
        # Multiple rows per player (one per refresh date)
        # Enables trend analysis: did stats go up or down over time?
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                date_fetched DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                -- BATTING STATS (for hitters)
                games_played INTEGER,
                at_bats INTEGER,
                hits INTEGER,
                home_runs INTEGER,
                rbis INTEGER,
                runs INTEGER,
                stolen_bases INTEGER,
                walks INTEGER,
                strikeouts INTEGER,
                avg REAL,                             -- Batting average
                obp REAL,                             -- On-base percentage
                
                -- PITCHING STATS (for pitchers)
                innings_pitched REAL,
                earned_runs INTEGER,
                era REAL,                             -- Earned run average
                whip REAL,                            -- Walks + Hits / IP
                strikeouts_pitch INTEGER,
                wins INTEGER,
                losses INTEGER,
                saves INTEGER,
                holds INTEGER,
                quality_starts INTEGER,
                
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        ''')
        
        # ====================================================================
        # Table 3: PLAYER_Z_SCORES (Calculated rankings)
        # ====================================================================
        # Stores z-scores (standardized stats showing how good each player is)
        # Z-score = (player's stat - average) / standard deviation
        # +2.0 = elite (top 2%), 0.0 = average, -2.0 = poor (bottom 2%)
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_z_scores (
                z_score_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                date_calculated DATETIME DEFAULT CURRENT_TIMESTAMP,
                position TEXT,
                
                -- Z-SCORES FOR HITTERS (5 categories)
                z_r REAL,                             -- Runs z-score
                z_hr REAL,                            -- Home runs z-score
                z_rbi REAL,                           -- RBIs z-score
                z_sb REAL,                            -- Stolen bases z-score
                z_obp REAL,                           -- On-base % z-score
                
                -- Z-SCORES FOR PITCHERS (5 categories)
                z_k REAL,                             -- Strikeouts z-score
                z_qs REAL,                            -- Quality starts z-score
                z_era REAL,                           -- ERA z-score
                z_whip REAL,                          -- WHIP z-score
                z_svhd REAL,                          -- Saves+Holds z-score
                
                -- COMPOSITE SCORES
                z_season REAL,                        -- Overall season z-score
                z_30day REAL,                         -- Last 30 days z-score
                z_14day REAL,                         -- Last 14 days z-score
                
                -- TREND DATA
                trend_direction TEXT,                 -- 'UP', 'DOWN', or 'FLAT'
                momentum REAL,                        -- Rate of change
                
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        ''')
        
        # ====================================================================
        # Table 4: MY_ROSTER (Your team's players)
        # ====================================================================
        # Snapshot of your roster at each refresh
        # Helps identify which categories your team is weak/strong in
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS my_roster (
                roster_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                date_snapshot DATETIME DEFAULT CURRENT_TIMESTAMP,
                position TEXT,                        -- Position slot (C, SS, OF, P, etc.)
                acquired_date DATE,
                notes TEXT,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        ''')
        
        # ====================================================================
        # Table 5: WAIVER_EVALUATIONS (Phase 2 - Waiver priority scores)
        # ====================================================================
        # Stores waiver priority rankings from Phase 2
        # Helps track which free agents you considered and when
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS waiver_evaluations (
                eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                date_evaluated DATETIME DEFAULT CURRENT_TIMESTAMP,
                priority_score REAL,                  -- 0.0 to 10.0
                helps_weakness TEXT,                  -- Which categories it helps
                reasoning TEXT,                       -- Why it was scored that way
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        ''')
        
        # ====================================================================
        # Table 6: MATCHUP_HISTORY (Phase 5 - Learning data)
        # ====================================================================
        # Records outcomes of matchups to learn what strategies worked
        # Enables Phase 5: Historical Learning
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matchup_history (
                matchup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER,
                date_played DATETIME,
                opponent_name TEXT,
                your_score INTEGER,
                opponent_score INTEGER,
                result TEXT,                          -- 'WIN', 'LOSS', or 'TIE'
                lineups_used TEXT,                    -- JSON of lineup data
                trades_made TEXT,                     -- JSON of trades in this period
                notes TEXT
            )
        ''')
        
        conn.commit()
        print(f"✓ Database initialized at: {DB_PATH}")
        return DB_PATH
        
    except sqlite3.Error as e:
        print(f"✗ Database error: {e}")
        raise
    finally:
        conn.close()


def store_player_stats(players_data: List[Dict], stats_data: Dict) -> int:
    """
    Store player master data and stats in database.
    
    Args:
        players_data: List of player dicts from ESPN API
        stats_data: Dict of player stats from MLB Stats API
    
    Returns:
        int: Number of player records stored
        
    Notes:
        - Inserts new players and updates existing ones
        - Stores time-series stats (one row per refresh)
        - Called once per refresh (daily/2-3x weekly)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    records_stored = 0
    
    try:
        for player in players_data:
            player_id = player.get('id')
            if not player_id:
                continue
            
            # Insert or update player master record
            cursor.execute('''
                INSERT OR REPLACE INTO players 
                (player_id, mlb_id, name, position, mlb_team, is_pitcher, ownership_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_id,
                player.get('mlb_id'),
                player.get('name', 'Unknown'),
                player.get('position'),
                player.get('mlb_team'),
                1 if player.get('is_pitcher') else 0,
                player.get('ownership_pct', 0)
            ))
            
            # Insert stats as time-series record
            if player_id in stats_data:
                stats = stats_data[player_id]
                
                cursor.execute('''
                    INSERT INTO player_stats 
                    (player_id, games_played, at_bats, hits, home_runs, rbis, 
                     runs, stolen_bases, walks, strikeouts, avg, obp,
                     innings_pitched, earned_runs, era, whip, strikeouts_pitch,
                     wins, losses, saves, holds, quality_starts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    player_id,
                    stats.get('games_played'),
                    stats.get('at_bats'),
                    stats.get('hits'),
                    stats.get('home_runs'),
                    stats.get('rbis'),
                    stats.get('runs'),
                    stats.get('stolen_bases'),
                    stats.get('walks'),
                    stats.get('strikeouts'),
                    stats.get('avg'),
                    stats.get('obp'),
                    stats.get('innings_pitched'),
                    stats.get('earned_runs'),
                    stats.get('era'),
                    stats.get('whip'),
                    stats.get('strikeouts_pitch'),
                    stats.get('wins'),
                    stats.get('losses'),
                    stats.get('saves'),
                    stats.get('holds'),
                    stats.get('quality_starts')
                ))
                
                records_stored += 1
        
        conn.commit()
        return records_stored
        
    except sqlite3.Error as e:
        print(f"✗ Error storing player stats: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def get_all_players() -> List[Dict]:
    """
    Retrieve all players from database with their latest stats and z-scores.
    
    Returns:
        List[Dict]: All players with their stats and rankings
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dicts
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT p.*, z.z_season, z.z_30day, z.z_14day
            FROM players p
            LEFT JOIN player_z_scores z ON p.player_id = z.player_id
            ORDER BY z.z_season DESC
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
        
    except sqlite3.Error as e:
        print(f"✗ Error retrieving players: {e}")
        return []
    finally:
        conn.close()


def get_z_scores(position: str = None) -> List[Dict]:
    """
    Retrieve z-scores, optionally filtered by position.
    
    Args:
        position: Optional position filter (e.g., 'OF', 'SS', 'P')
    
    Returns:
        List[Dict]: Players with their z-scores
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        if position:
            cursor.execute('''
                SELECT * FROM player_z_scores 
                WHERE position = ?
                ORDER BY z_season DESC
            ''', (position,))
        else:
            cursor.execute('''
                SELECT * FROM player_z_scores 
                ORDER BY z_season DESC
            ''')
        
        return [dict(row) for row in cursor.fetchall()]
        
    except sqlite3.Error as e:
        print(f"✗ Error retrieving z-scores: {e}")
        return []
    finally:
        conn.close()


def store_z_scores(z_score_data: List[Dict]) -> int:
    """
    Store calculated z-scores in database.
    
    Args:
        z_score_data: List of z-score dicts from processors module
    
    Returns:
        int: Number of z-score records stored
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    records_stored = 0
    
    try:
        for z_data in z_score_data:
            cursor.execute('''
                INSERT INTO player_z_scores
                (player_id, position, z_r, z_hr, z_rbi, z_sb, z_obp,
                 z_k, z_qs, z_era, z_whip, z_svhd,
                 z_season, z_30day, z_14day, trend_direction, momentum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                z_data.get('player_id'),
                z_data.get('position'),
                z_data.get('z_r'),
                z_data.get('z_hr'),
                z_data.get('z_rbi'),
                z_data.get('z_sb'),
                z_data.get('z_obp'),
                z_data.get('z_k'),
                z_data.get('z_qs'),
                z_data.get('z_era'),
                z_data.get('z_whip'),
                z_data.get('z_svhd'),
                z_data.get('z_season'),
                z_data.get('z_30day'),
                z_data.get('z_14day'),
                z_data.get('trend_direction'),
                z_data.get('momentum')
            ))
            records_stored += 1
        
        conn.commit()
        return records_stored
        
    except sqlite3.Error as e:
        print(f"✗ Error storing z-scores: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def get_my_roster() -> List[Dict]:
    """
    Retrieve your current roster.
    
    Returns:
        List[Dict]: Your team's players
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT DISTINCT p.*, mr.position
            FROM players p
            JOIN my_roster mr ON p.player_id = mr.player_id
            WHERE mr.date_snapshot = (
                SELECT MAX(date_snapshot) FROM my_roster
            )
            ORDER BY mr.position
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
        
    except sqlite3.Error as e:
        print(f"✗ Error retrieving your roster: {e}")
        return []
    finally:
        conn.close()