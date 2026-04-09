import requests
import json

season = 2026

url = "https://statsapi.mlb.com/api/v1/stats"
params = {'group': 'hitting', 'season': season, 'stats': 'season'}

r = requests.get(url, params=params, timeout=30)
data = r.json()

if data.get('stats'):
    stat_group = data['stats'][0]
    player_pool = stat_group.get('playerPool', [])
    
    if player_pool:
        first = player_pool[0]
        print("First player keys:")
        for key in first.keys():
            value = first[key]
            print(f"  {key}: {type(value).__name__}")
            if key == 'stats':
                print(f"    Value: {value}")
                if isinstance(value, dict):
                    print(f"    Dict keys: {list(value.keys())[:10]}")
