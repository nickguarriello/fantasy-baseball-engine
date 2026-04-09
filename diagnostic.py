import requests

season = 2026

# The API requires 'stats' parameter
url = f"https://statsapi.mlb.com/api/v1/stats"
params = {
    'group': 'hitting',
    'season': season,
    'stats': 'season'  # THIS is required
}

print(f"Testing URL: {url}")
print(f"Params: {params}\n")

try:
    r = requests.get(url, params=params, timeout=30)
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"Response keys: {list(data.keys())}")
        print(f"Stats count: {len(data.get('stats', []))}")
        
        if data.get('stats'):
            first_stat = data['stats'][0]
            print(f"First stat group keys: {list(first_stat.keys())}")
            print(f"Players in first group: {len(first_stat.get('stats', []))}")
            
            if first_stat.get('stats'):
                first_player = first_stat['stats'][0]
                print(f"\nFirst player structure:")
                print(f"  Keys: {list(first_player.keys())}")
                if 'stats' in first_player:
                    print(f"  Stats keys: {list(first_player['stats'].keys())[:10]}")
    else:
        print(f"Error: {r.text[:300]}")
        
except Exception as e:
    print(f"Exception: {e}")
