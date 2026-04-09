import requests
import json

league_id = 1985887220
season = 2026

# Get ESPN data
print("="*70)
print("ESPN LEAGUE DATA")
print("="*70)
url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{season}/segments/0/leagues/{league_id}"
params = {'view': 'modular,mNav,mMatchupScore,mScoreboard,mStatus,mSettings,mTeam,mPendingTransactions'}
r = requests.get(url, params=params)
data = r.json()

print(f"\nTop-level keys: {list(data.keys())}")
print(f"\nTeams count: {len(data.get('teams', []))}")

if data.get('teams'):
    team = data['teams'][0]
    print(f"\nFirst team structure:")
    print(f"  Keys: {list(team.keys())}")
    print(f"  Team ID: {team.get('id')}")
    print(f"  Team name: {team.get('name')}")
    print(f"  Has 'roster' key: {'roster' in team}")
    if 'roster' in team:
        print(f"  Roster keys: {list(team['roster'].keys())}")
        print(f"  Roster entries count: {len(team['roster'].get('entries', []))}")
        if team['roster'].get('entries'):
            entry = team['roster']['entries'][0]
            print(f"  First entry keys: {list(entry.keys())}")

# Get MLB data
print("\n" + "="*70)
print("MLB PLAYER DATA")
print("="*70)
url = f"https://statsapi.mlb.com/api/v1/sports/1/players"
params = {'season': season}
r = requests.get(url, params=params)
data = r.json()

print(f"\nTop-level keys: {list(data.keys())}")
print(f"People count: {len(data.get('people', []))}")

if data.get('people'):
    person = data['people'][0]
    print(f"\nFirst person structure:")
    print(f"  Keys: {list(person.keys())[:10]}")  # First 10 keys
    print(f"  ID: {person.get('id')}")
    print(f"  Name: {person.get('fullName')}")
