"""
Fetchers Module - API Communication

Handles:
- ESPN Fantasy API calls (league data, rosters, players)
- MLB Stats API calls (player statistics)
- Error handling and retries
- Response parsing and validation
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LEAGUE_CONFIG, API_CONFIG, DEBUG_CONFIG


def _make_request(url: str, params: Optional[Dict] = None, max_retries: int = 3) -> Optional[Dict]:
    """
    Make HTTP request with retry logic and error handling.
    
    Handles timeouts, connection errors, HTTP errors, and JSON parsing.
    Returns None on failure (doesn't crash).
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=API_CONFIG['request_timeout'],
                headers={'User-Agent': 'Mozilla/5.0 (Fantasy Baseball Engine)'}
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                print(f"  ⏱ Timeout, retrying ({attempt}/{max_retries})...")
                time.sleep(API_CONFIG['retry_delay'])
            else:
                print(f"  ✗ Timeout after {max_retries} attempts")
                return None
                
        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                print(f"  🌐 Connection error, retrying...")
                time.sleep(API_CONFIG['retry_delay'])
            else:
                print(f"  ✗ Connection failed")
                return None
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"  ⏸ Rate limited...")
                time.sleep(10)
            elif attempt < max_retries:
                print(f"  ⚠ HTTP {e.response.status_code}, retrying...")
                time.sleep(API_CONFIG['retry_delay'])
            else:
                print(f"  ✗ HTTP {e.response.status_code}")
                return None
                
        except ValueError:
            print(f"  ✗ Invalid JSON")
            return None
    
    return None


def fetch_espn_league_data() -> Optional[Dict]:
    """
    Fetch your roster from ESPN Fantasy API.
    
    Returns:
        Dict with 'my_roster' (your players) and 'league_info'
        Or None if fetch fails
    """
    print("  Fetching ESPN league data...")
    
    league_id = LEAGUE_CONFIG['league_id']
    season = LEAGUE_CONFIG['season']
    team_id = LEAGUE_CONFIG['team_id']
    
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{season}/segments/0/leagues/{league_id}"
    params = {'view': 'mRoster'}
    
    response = _make_request(url, params)
    
    if not response:
        return None
    
    try:
        teams = response.get('teams', [])
        if not teams:
            print("  ✗ No teams in response")
            return None
        
        # Find your team
        my_team = None
        for team in teams:
            if team.get('id') == team_id:
                my_team = team
                break
        
        if not my_team:
            print(f"  ✗ Team {team_id} not found")
            return None
        
        # Extract roster
        my_roster = []
        roster = my_team.get('roster', {})
        entries = roster.get('entries', [])
        
        for entry in entries:
            player_pool = entry.get('playerPoolEntry', {})
            player = player_pool.get('player', {})
            
            player_id = player.get('id')
            if not player_id:
                continue
            
            position = player.get('defaultPositionId', 'UNKNOWN')
            is_pitcher = position in ['P', 'SP', 'RP']
            
            my_roster.append({
                'id': player_id,
                'player_id': player_id,
                'name': player.get('fullName', 'Unknown'),
                'position': position,
                'mlb_team': player.get('proTeamId'),
                'is_pitcher': is_pitcher,
            })
        
        league_info = {
            'name': 'League',
            'season': season,
            'league_id': league_id,
            'num_teams': len(teams),
        }
        
        print(f"    ✓ Found {len(my_roster)} players on your roster")
        print(f"    ✓ League has {league_info['num_teams']} teams")
        
        return {
            'my_roster': my_roster,
            'all_players': my_roster,
            'league_info': league_info
        }
        
    except (KeyError, IndexError, TypeError) as e:
        print(f"  ✗ Error parsing ESPN: {e}")
        return None


def fetch_mlb_player_stats(player_sample: Optional[List] = None) -> Dict:
    """
    Fetch MLB player stats from MLB Stats API.
    
    Returns:
        Dict mapping player_id to stats dict
    """
    print("  Fetching MLB player statistics...")
    print("    This may take 1-2 minutes...")
    
    season = LEAGUE_CONFIG['season']
    all_stats = {}
    
    try:
        # Fetch hitters
        print("    Fetching hitters...", end=" ", flush=True)
        hitting_url = "https://statsapi.mlb.com/api/v1/stats"
        hitting_params = {
            'group': 'hitting',
            'season': season,
            'stats': 'season'
        }
        
        hitting_response = _make_request(hitting_url, hitting_params)
        
        if hitting_response and hitting_response.get('stats'):
            stat_group = hitting_response['stats'][0]
            player_pool = stat_group.get('playerPool', [])
            
            for player_data in player_pool:
                player_id = player_data.get('id')
                if not player_id:
                    continue
                
                person = player_data.get('person', {})
                
                # stats might be a string or dict - handle both
                stats_data = player_data.get('stats')
                if isinstance(stats_data, str):
                    stats = json.loads(stats_data) if stats_data else {}
                else:
                    stats = stats_data if stats_data else {}
                
                all_stats[player_id] = {
                    'player_id': player_id,
                    'mlb_id': player_id,
                    'name': person.get('fullName', 'Unknown'),
                    'position': player_data.get('position', {}).get('abbreviation'),
                    'mlb_team': None,
                    'is_pitcher': False,
                    'games_played': stats.get('gamesPlayed', 0),
                    'at_bats': stats.get('atBats', 0),
                    'hits': stats.get('hits', 0),
                    'home_runs': stats.get('homeRuns', 0),
                    'rbis': stats.get('rbi', 0),
                    'runs': stats.get('runs', 0),
                    'stolen_bases': stats.get('stolenBases', 0),
                    'walks': stats.get('baseOnBalls', 0),
                    'strikeouts': stats.get('strikeOuts', 0),
                    'avg': float(stats.get('avg', 0)) if stats.get('avg') else 0.0,
                    'obp': float(stats.get('obp', 0)) if stats.get('obp') else 0.0,
                    'innings_pitched': 0.0,
                    'earned_runs': 0,
                    'era': 0.0,
                    'whip': 0.0,
                    'strikeouts_pitch': 0,
                    'wins': 0,
                    'losses': 0,
                    'saves': 0,
                    'holds': 0,
                    'quality_starts': 0,
                }
            
            print(f"✓ ({len(player_pool)} hitters)")
        else:
            print("✗")
        
        # Fetch pitchers
        print("    Fetching pitchers...", end=" ", flush=True)
        pitching_url = "https://statsapi.mlb.com/api/v1/stats"
        pitching_params = {
            'group': 'pitching',
            'season': season,
            'stats': 'season'
        }
        
        pitching_response = _make_request(pitching_url, pitching_params)
        
        if pitching_response and pitching_response.get('stats'):
            stat_group = pitching_response['stats'][0]
            player_pool = stat_group.get('playerPool', [])
            
            for player_data in player_pool:
                player_id = player_data.get('id')
                if not player_id:
                    continue
                
                person = player_data.get('person', {})
                
                # stats might be a string or dict - handle both
                stats_data = player_data.get('stats')
                if isinstance(stats_data, str):
                    stats = json.loads(stats_data) if stats_data else {}
                else:
                    stats = stats_data if stats_data else {}
                
                if player_id not in all_stats:
                    all_stats[player_id] = {
                        'player_id': player_id,
                        'mlb_id': player_id,
                        'name': person.get('fullName', 'Unknown'),
                        'position': player_data.get('position', {}).get('abbreviation'),
                        'mlb_team': None,
                        'is_pitcher': True,
                        'games_played': 0,
                        'at_bats': 0,
                        'hits': 0,
                        'home_runs': 0,
                        'rbis': 0,
                        'runs': 0,
                        'stolen_bases': 0,
                        'walks': 0,
                        'strikeouts': 0,
                        'avg': 0.0,
                        'obp': 0.0,
                    }
                
                all_stats[player_id].update({
                    'innings_pitched': float(stats.get('inningsPitched', 0)) if stats.get('inningsPitched') else 0.0,
                    'earned_runs': stats.get('earnedRuns', 0),
                    'era': float(stats.get('era', 0)) if stats.get('era') else 0.0,
                    'whip': float(stats.get('whip', 0)) if stats.get('whip') else 0.0,
                    'strikeouts_pitch': stats.get('strikeOuts', 0),
                    'wins': stats.get('wins', 0),
                    'losses': stats.get('losses', 0),
                    'saves': stats.get('saves', 0),
                    'holds': stats.get('holds', 0),
                    'quality_starts': stats.get('qualityStarts', 0),
                    'is_pitcher': True,
                })
            
            print(f"✓ ({len(player_pool)} pitchers)")
        else:
            print("✗")
        
        print(f"    ✓ Retrieved stats for {len(all_stats)} total players")
        return all_stats
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return {}


def test_api_connectivity() -> bool:
    """
    Test that both APIs are reachable.
    
    Returns:
        bool: True if working, False if not
    """
    print("Testing API connectivity...")
    
    # Test ESPN
    print("  ESPN Fantasy API...", end=" ")
    league_id = LEAGUE_CONFIG['league_id']
    season = LEAGUE_CONFIG['season']
    espn_url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{season}/segments/0/leagues/{league_id}"
    espn_params = {'view': 'mRoster'}
    espn_response = _make_request(espn_url, espn_params)
    
    if espn_response:
        print("✓")
    else:
        print("✗")
        return False
    
    # Test MLB
    print("  MLB Stats API...", end=" ")
    mlb_url = "https://statsapi.mlb.com/api/v1/stats"
    mlb_params = {'group': 'hitting', 'season': season, 'stats': 'season'}
    mlb_response = _make_request(mlb_url, mlb_params)
    
    if mlb_response:
        print("✓")
    else:
        print("✗")
        return False
    
    return True
