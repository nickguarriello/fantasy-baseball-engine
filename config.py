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
# ============================================================================
# ESPN PRO TEAM ID MAPPING
# ============================================================================
# Maps ESPN's proTeamId (on each player) to the MLB team abbreviation.
# Used to disambiguate players who share the same name (e.g. two "Max Muncy"s).
# Source: ESPN /seasons/2026?view=proTeamSchedules_wl

ESPN_PRO_TEAM_MAP = {
    0:  'FA',
    1:  'BAL',  2:  'BOS',  3:  'LAA',  4:  'CWS',  5:  'CLE',
    6:  'DET',  7:  'KC',   8:  'MIL',  9:  'MIN',   10: 'NYY',
    11: 'ATH',  12: 'SEA',  13: 'TEX',  14: 'TOR',   15: 'ATL',
    16: 'CHC',  17: 'CIN',  18: 'HOU',  19: 'LAD',   20: 'WSH',
    21: 'NYM',  22: 'PHI',  23: 'PIT',  24: 'STL',   25: 'SD',
    26: 'SF',   27: 'COL',  28: 'MIA',  29: 'ARI',   30: 'TB',
}

# Maps ESPN team abbreviations to MLB Stats API team name substrings.
# Used when joining ESPN roster data to MLB player stats by team.
ESPN_TEAM_TO_MLB_NAME = {
    'BAL': 'Baltimore',   'BOS': 'Boston',      'LAA': 'Angels',
    'CWS': 'White Sox',   'CLE': 'Guardians',   'DET': 'Detroit',
    'KC':  'Kansas City', 'MIL': 'Milwaukee',   'MIN': 'Minnesota',
    'NYY': 'Yankees',     'ATH': 'Athletics',   'SEA': 'Seattle',
    'TEX': 'Texas',       'TOR': 'Toronto',     'ATL': 'Atlanta',
    'CHC': 'Cubs',        'CIN': 'Cincinnati',  'HOU': 'Houston',
    'LAD': 'Dodgers',     'WSH': 'Washington',  'NYM': 'Mets',
    'PHI': 'Philadelphia','PIT': 'Pittsburgh',  'STL': 'St. Louis',
    'SD':  'San Diego',   'SF':  'San Francisco','COL': 'Colorado',
    'MIA': 'Miami',       'ARI': 'Arizona',     'TB':  'Tampa Bay',
}

# ============================================================================
# ESPN POSITION ID MAPPING
# ============================================================================
# Maps ESPN's numeric defaultPositionId to a readable position abbreviation

ESPN_POSITION_MAP = {
    1:  'SP',
    2:  'C',
    3:  '1B',
    4:  '2B',
    5:  '3B',
    6:  'SS',
    7:  'OF',   # LF → OF
    8:  'OF',   # CF → OF
    9:  'OF',   # RF → OF (confirmed: Soto/Carroll/Crews all posId=9)
    10: 'DH',   # confirmed: Trout/Yelich posId=10
    11: 'RP',   # confirmed: Miller/Uribe/Romano/Pagan all posId=11
    12: 'RP',
    13: 'P',    # generic pitcher
}

# Maps ESPN lineupSlotId (current roster slot) to readable name.
# Also used to decode player.eligibleSlots (what slots a player can fill).
ESPN_LINEUP_SLOT_MAP = {
    0:  'C',
    1:  '1B',
    2:  '2B',
    3:  '3B',
    4:  'SS',
    5:  'OF',
    6:  '2B/SS',
    7:  '1B/3B',
    8:  'LF',
    9:  'CF',
    10: 'RF',
    11: 'DH',
    12: 'UTIL',
    13: 'SP',
    14: 'P',
    15: 'BE',
    16: 'BE',   # this league uses 16 for bench (5 bench spots all slotId=16)
    17: 'IL',   # IL slot 1 (confirmed: Mookie Betts)
    18: 'IL',   # IL slot 2 (overflow)
    19: 'IL',   # IL slot 3 (overflow)
}

# Slot names shown in the eligible positions column (real positions only,
# excludes meta-slots like UTIL, 2B/SS flex, BE, IL).
ESPN_PRIMARY_SLOTS = {'C', '1B', '2B', '3B', 'SS', 'OF', 'DH', 'SP', 'RP'}

# lineupSlotId values that mean a player is NOT active in a lineup spot.
ESPN_INACTIVE_SLOT_IDS = {15, 16, 17, 18, 19}  # BE (15,16), IL (17,18,19)

# Position IDs that are pitchers
PITCHER_POSITION_IDS = {1, 11, 12, 13}   # SP, RP, RP-alt, P-generic

# ============================================================================
# OUTFIELD POSITION NORMALIZATION
# ============================================================================
# CF, LF, RF all count as OF for fantasy purposes.
# Any position in this set is treated as "OF" in waiver/matchup analysis.

OF_POSITIONS = {'OF', 'CF', 'LF', 'RF'}

# ============================================================================
# INJURY STATUS
# ============================================================================
# ESPN injury status values that mean a player is unavailable or risky.
# Players with these statuses get flagged and excluded from START recommendations.

INJURED_STATUSES = {
    'INJURY_RESERVE',
    'FIFTEEN_DAY_IL',
    'SIXTY_DAY_IL',
    'SEVEN_DAY_IL',
    'TEN_DAY_IL',
    'OUT',
    'SUSPENSION',
    'BEREAVEMENT',
}

QUESTIONABLE_STATUSES = {
    'DAY_TO_DAY',
    'QUESTIONABLE',
    'DOUBTFUL',
}

# ============================================================================
# ESPN FANTASY BASEBALL STAT ID MAPPING
# ============================================================================
# Maps ESPN's numeric stat IDs to our internal category keys.
# Used to parse in-week accumulated stats from the ESPN matchup API.
# IDs marked (confirmed) validated via live API inspection.
# IDs marked (estimated) are best guesses — may need adjustment.

ESPN_STAT_IDS = {
    # --- Batting (all confirmed via live API scoreByStat result flags) ---
    '20': 'runs',           # R    (confirmed — UAT: values matched R totals)
    '5':  'home_runs',      # HR   (confirmed — UAT: values matched HR totals)
    '21': 'rbis',           # RBI  (confirmed — UAT: values matched RBI totals)
    '23': 'stolen_bases',   # SB   (confirmed — UAT: values matched SB totals)
    '17': 'obp',            # OBP  (confirmed — rate stat, result flag matched)
    # --- Pitching ---
    '48': 'strikeouts',     # K    (confirmed)
    '63': 'quality_starts', # QS   (confirmed)
    '47': 'era',            # ERA  (confirmed — result flag + value 3.62 matched)
    '41': 'whip',           # WHIP (confirmed — result flag + value 1.24 matched)
    '83': 'sv_hd',          # SV+HD (confirmed)
}

# Rate stats from ESPN — stored as floats, not summed
ESPN_RATE_STAT_IDS = {'47', '41', '17'}   # ERA, WHIP, OBP


# ============================================================================
# ESPN AUTH (optional — unlocks Player Rater data and ownership %)
# ============================================================================
# Credentials are loaded from espn_credentials.py (gitignored).
# Without them, the engine falls back to derived free agents and MLB z-scores.

try:
    from espn_credentials import ESPN_S2, ESPN_SWID  # type: ignore
except ImportError:
    ESPN_S2   = None
    ESPN_SWID = None

# ============================================================================
# VALIDATION
# ============================================================================

if __name__ == '__main__':
    # Quick validation that config loaded correctly
    print("✓ Configuration loaded successfully")
    print(f"  League: {LEAGUE_CONFIG['league_id']} | Team: {LEAGUE_CONFIG['team_id']}")
    print(f"  Hitter categories: {len(H2H_CATEGORIES['hitters'])}")
    print(f"  Pitcher categories: {len(H2H_CATEGORIES['pitchers'])}")