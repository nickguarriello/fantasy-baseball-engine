"""
Fantasy Baseball H2H Category Decision Engine
Configuration File - CUSTOMIZE THIS FOR YOUR LEAGUE

League: Public ESPN Fantasy Baseball
League ID: 1985887220
Team ID: 1
Season: 2026
Format: H2H Categories (10 categories)
"""

# ============================================================================
# LEAGUE CONFIGURATION
# ============================================================================
# Update these to match your ESPN league

LEAGUE_CONFIG = {
    'league_id': 1985887220,      # Your ESPN league ID
    'team_id': 1,                  # Your team within the league
    'sport': 'mlb',                # Sport (always 'mlb' for baseball)
    'format': 'h2h_categories',    # Format (always 'h2h_categories')
    'season': 2026,                # Current baseball season
}

# ============================================================================
# H2H CATEGORIES - THE 10 STATS YOUR LEAGUE SCORES
# ============================================================================
# These are the ONLY stats that matter for your league
# Do not modify unless your league changed categories

H2H_CATEGORIES = {
    'hitters': [
        {'name': 'R', 'display': 'Runs', 'stat_key': 'runs', 'higher_is_better': True},
        {'name': 'HR', 'display': 'Home Runs', 'stat_key': 'home_runs', 'higher_is_better': True},
        {'name': 'RBI', 'display': 'RBIs', 'stat_key': 'rbis', 'higher_is_better': True},
        {'name': 'SB', 'display': 'Stolen Bases', 'stat_key': 'stolen_bases', 'higher_is_better': True},
        {'name': 'OBP', 'display': 'On-Base Percentage', 'stat_key': 'obp', 'higher_is_better': True},
    ],
    'pitchers': [
        {'name': 'K', 'display': 'Strikeouts', 'stat_key': 'strikeouts', 'higher_is_better': True},
        {'name': 'QS', 'display': 'Quality Starts', 'stat_key': 'quality_starts', 'higher_is_better': True},
        {'name': 'ERA', 'display': 'ERA', 'stat_key': 'era', 'higher_is_better': False},  # Lower is better
        {'name': 'WHIP', 'display': 'WHIP', 'stat_key': 'whip', 'higher_is_better': False},  # Lower is better
        {'name': 'SVHD', 'display': 'Saves + Holds', 'stat_key': 'sv_hd', 'higher_is_better': True},
    ]
}

# ============================================================================
# API CONFIGURATION
# ============================================================================
# These are the official ESPN Fantasy and MLB Stats API endpoints
# No modification needed unless APIs change

API_CONFIG = {
    'espn_base_url': 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb',
    'mlb_stats_url': 'https://statsapi.mlb.com/api/v1',
    'request_timeout': 30,         # Seconds to wait for API response
    'max_retries': 3,              # Number of times to retry failed API call
    'retry_delay': 2,              # Seconds between retries
}

# ============================================================================
# PHASE 2: WAIVER WIRE RULES (Customize these if desired)
# ============================================================================
# Controls how the engine prioritizes free agents for waiver claims

WAIVER_RULES = {
    'hot_form_threshold': 1.5,     # Z-score > this = "hot" and boost priority
    'ownership_cutoff': 20,        # Only consider players < 20% owned
    'min_games_played': 5,         # Ignore players with < 5 games played
    'weak_category_boost': 1.5,    # Multiply score by this if helps your weakness
}

# ============================================================================
# PHASE 3: LINEUP OPTIMIZATION RULES (Customize these if desired)
# ============================================================================
# Controls how the engine recommends start/bench decisions

LINEUP_RULES = {
    'strong_start_threshold': 0.8,  # Z-score > this = "definitely start"
    'weak_bench_threshold': -0.3,   # Z-score < this = "consider benching"
    'auto_bench_injured': True,     # Auto-bench players flagged as injured
}

# ============================================================================
# PHASE 4: TRADE EVALUATION RULES (Customize these if desired)
# ============================================================================
# Controls how the engine evaluates trade offers

TRADE_RULES = {
    'value_threshold': 1.05,        # Need 5% better value to recommend accept
    'require_category_coverage': True,  # Don't trade away critical categories
    'rest_of_season_weight': 0.3,   # How much to weight remaining schedule
}

# ============================================================================
# DATA MANAGEMENT
# ============================================================================
# Where to store data, how often to refresh, etc.

DATA_CONFIG = {
    'db_path': 'data/fantasy_baseball.db',  # SQLite database location
    'output_dir': 'outputs',                # Where to save CSV exports
    'cache_dir': 'data/cache',              # Where to cache API responses (optional)
    'refresh_frequency': '2-3 times per week',  # How often you'll run the engine
}

# ============================================================================
# LOGGING & DEBUG
# ============================================================================
# Controls how much output the engine shows

DEBUG_CONFIG = {
    'verbose': True,               # Show detailed progress messages
    'show_api_responses': False,   # Show raw API data (useful for debugging)
    'log_file': None,              # Set to 'engine.log' to save logs to file
}

# ============================================================================
# VALIDATION
# ============================================================================

if __name__ == '__main__':
    # Quick validation that config loaded correctly
    print("✓ Configuration loaded successfully")
    print(f"  League: {LEAGUE_CONFIG['league_id']} | Team: {LEAGUE_CONFIG['team_id']}")
    print(f"  Hitter categories: {len(H2H_CATEGORIES['hitters'])}")
    print(f"  Pitcher categories: {len(H2H_CATEGORIES['pitchers'])}")