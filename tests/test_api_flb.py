import requests

league_id = 1985887220
season = 2026

url = f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{season}/segments/0/leagues/{league_id}'
params = {
    'view': 'modular,mNav,mMatchupScore,mScoreboard,mStatus,mSettings,mTeam,mPendingTransactions'
}

print(f"Testing: {url}")
print(f"Params: {params}")

try:
    r = requests.get(url, params=params, timeout=10)
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        print("✓ SUCCESS")
        data = r.json()
        print(f"Keys in response: {list(data.keys())}")
    else:
        print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
