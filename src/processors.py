"""
Processors Module - Statistical Calculations

Handles:
- Z-score calculations (standardized statistics)
- Trend detection (is player improving or declining?)
- Position grouping (hitters vs pitchers)
- Data validation and normalization
"""

import numpy as np
from typing import Dict, List, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import H2H_CATEGORIES


def _calculate_z_score(value: float, mean: float, std_dev: float, invert: bool = False) -> float:
    """
    Calculate z-score for a single value.
    
    Z-score formula: (value - mean) / standard_deviation
    
    Tells you how many standard deviations a value is from the mean.
    
    Args:
        value: The player's actual stat (e.g., 28 home runs)
        mean: Average stat for that position (e.g., 20 HR average)
        std_dev: Variation in stats (e.g., 5 HR std dev)
        invert: If True, negate the z-score (for stats where lower is better)
    
    Returns:
        float: Z-score
        
    Examples:
        value=28, mean=20, std_dev=5 → (28-20)/5 = +1.6
        (Player is 1.6 standard deviations above average = excellent)
        
        For ERA (lower is better):
        value=3.0, mean=4.0, std_dev=0.5, invert=True
        → -((3.0-4.0)/0.5) = +2.0
        (Lower ERA is better, so we invert the sign)
    
    Notes:
        - Returns 0.0 if std_dev is 0 (no variation = can't calculate)
        - Typical z-scores range from -3.0 to +3.0
    """
    if std_dev == 0 or value is None:
        return 0.0
    
    z = (value - mean) / std_dev
    
    # For stats where lower is better (ERA, WHIP), negate the z-score
    if invert:
        z = -z
    
    return round(z, 2)


def calculate_z_scores(players_data: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Calculate z-scores for all players across all categories.
    
    Groups players by position, calculates mean/std dev per category,
    then calculates each player's z-score in that category.
    
    Args:
        players_data: List of players with their stats
    
    Returns:
        Tuple of:
        - List of players with z-scores added
        - Dict of position-level statistics (for debugging)
        
    Logic:
        1. Group players by position (C, SS, OF, P, etc.)
        2. For each position and stat category:
           - Calculate mean stat value
           - Calculate standard deviation
        3. For each player in that position:
           - Calculate z-score = (player_stat - mean) / std_dev
        4. Calculate composite "Season Z" = average of all category z-scores
    """
    print("  Calculating z-scores by position...")
    
    z_scored_players = []
    position_stats = {}
    
    # Step 1: Group players by position
    # Each position has different stat ranges (outfielders vs pitchers)
    
    position_groups = {}
    for player in players_data:
        position = player.get('position', 'UNKNOWN')
        if position not in position_groups:
            position_groups[position] = []
        position_groups[position].append(player)
    
    # Step 2: For each position group, calculate z-scores
    
    for position, position_players in position_groups.items():
        # Determine if this is hitters or pitchers
        is_pitcher = position.upper() in ['P', 'SP', 'RP']
        
        if is_pitcher:
            categories = H2H_CATEGORIES['pitchers']
        else:
            categories = H2H_CATEGORIES['hitters']
        
        # Calculate mean and std dev for each category in this position
        position_means = {}
        position_stds = {}
        
        for category in categories:
            stat_key = category['stat_key']
            values = []
            
            # Collect all values for this stat across all players
            for player in position_players:
                value = player.get(stat_key)
                if value is not None and value > 0:  # Only use valid positive values
                    values.append(float(value))
            
            if values:
                position_means[stat_key] = np.mean(values)
                position_stds[stat_key] = np.std(values)
            else:
                position_means[stat_key] = 0
                position_stds[stat_key] = 1
        
        # Step 3: Calculate z-scores for each player in this position
        
        for player in position_players:
            z_data = {
                'player_id': player.get('player_id'),
                'name': player.get('name'),
                'position': position,
                'mlb_team': player.get('mlb_team'),
                'is_pitcher': is_pitcher,
            }
            
            z_scores = []
            
            # Calculate z-score for each category
            for category in categories:
                stat_key = category['stat_key']
                stat_name = category['name']
                player_value = player.get(stat_key)
                
                if player_value is None:
                    z_score = 0.0
                else:
                    z_score = _calculate_z_score(
                        player_value,
                        position_means[stat_key],
                        position_stds[stat_key],
                        invert=not category['higher_is_better']
                    )
                
                # Store z-score with category name (z_r, z_hr, z_era, etc.)
                z_key = f"z_{stat_name.lower()}"
                z_data[z_key] = z_score
                z_scores.append(z_score)
            
            # Step 4: Calculate composite z-score (average of all categories)
            # This gives a single number showing overall performance
            
            if z_scores:
                season_z = round(np.mean(z_scores), 2)
            else:
                season_z = 0.0
            
            z_data['z_season'] = season_z
            z_data['z_30day'] = season_z  # In Phase 1, same as season
            z_data['z_14day'] = season_z  # In Phase 1, same as season
            
            z_scored_players.append(z_data)
        
        # Record position-level stats (useful for debugging)
        position_stats[position] = {
            'count': len(position_players),
            'means': position_means,
            'stds': position_stds,
        }
    
    print(f"    ✓ Calculated z-scores for {len(z_scored_players)} players")
    return z_scored_players, position_stats


def calculate_trends(historical_data: List[Dict]) -> List[Dict]:
    """
    Analyze player trends: are they improving or declining?
    
    Compares stats over time windows to detect momentum.
    
    Args:
        historical_data: List of players with stats from multiple time periods
    
    Returns:
        List of players with trend data added
        
    Notes:
        - In Phase 1, we don't have historical data yet
        - This function is included for Phase 2 preparation
        - Real trends need data from multiple refreshes (2-3 weeks of data)
        - For now, returns 'FLAT' trend until data accumulates
    """
    print("  Analyzing player trends...")
    
    # In Phase 1, we don't have historical data to compare
    # This is a placeholder for when we have multiple days of stats
    
    for player in historical_data:
        # As placeholder, mark all as FLAT
        player['trend_direction'] = 'FLAT'
        player['momentum'] = 0.0
    
    print(f"    ✓ Trend analysis complete (data accumulating)")
    return historical_data


def validate_player_data(player: Dict) -> bool:
    """
    Validate that player data is complete and reasonable.
    
    Checks:
    - Has required fields (name, position)
    - Stats are positive numbers or None
    - No obviously bad data
    
    Args:
        player: Player dict to validate
    
    Returns:
        bool: True if data looks good, False if suspicious
    """
    # Must have name and position
    if not player.get('name') or not player.get('position'):
        return False
    
    # Stats should be numbers (or None)
    # Should not have negative counts (can't have -5 home runs)
    stat_fields = [
        'games_played', 'at_bats', 'hits', 'home_runs', 'rbis',
        'runs', 'stolen_bases', 'walks', 'strikeouts',
        'innings_pitched', 'earned_runs', 'wins', 'losses',
        'saves', 'holds', 'quality_starts'
    ]
    
    for field in stat_fields:
        value = player.get(field)
        if value is not None:
            if not isinstance(value, (int, float)) or value < 0:
                return False
    
    return True


def normalize_stats(stats_dict: Dict) -> Dict:
    """
    Normalize stats dictionary for database storage.
    
    Converts None to 0 where appropriate, ensures types are correct.
    
    Args:
        stats_dict: Raw stats from API
    
    Returns:
        Dict: Cleaned stats ready for storage
    """
    normalized = {}
    
    # Map of field names and their default values
    int_fields = [
        'games_played', 'at_bats', 'hits', 'home_runs', 'rbis',
        'runs', 'stolen_bases', 'walks', 'strikeouts',
        'earned_runs', 'wins', 'losses', 'saves', 'holds', 'quality_starts'
    ]
    
    float_fields = [
        'avg', 'obp', 'slg', 'ops',
        'innings_pitched', 'era', 'whip'
    ]
    
    for field in int_fields:
        value = stats_dict.get(field)
        normalized[field] = int(value) if value is not None else 0
    
    for field in float_fields:
        value = stats_dict.get(field)
        normalized[field] = float(value) if value is not None else 0.0
    
    return normalized