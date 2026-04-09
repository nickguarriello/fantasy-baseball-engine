import requests
import json

league_id = 1985887220
season = 2026

# Try different ESPN views to get roster data
print("Testing different ESPN views...")
views_to_try = [
    'mTeam,mRoster',
    'mTeam,mRoster,mSettings',
    'mTeam',
    'mRoster',
]

for view in views_to_try:
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{season}/segments/0/leagues/{league_id}"
    params = {'view': view}
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    
    if data.get('teams'):
        team = data['teams'][0]
        has_roster = 'roster' in team
        print(f"View '{view}': has roster = {has_roster}")
        if has_roster:
            entries = len(team.get('roster', {}).get('entries', []))
            print(f"  → Roster entries: {entries}")
            if entries > 0:
                entry = team['roster']['entries'][0]
                print(f"  → First entry keys: {list(entry.keys())}")
