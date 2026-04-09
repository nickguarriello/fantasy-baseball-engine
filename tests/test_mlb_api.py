import requests

season = 2026

# Try different MLB Stats API endpoints
endpoints = [
    f'https://statsapi.mlb.com/api/v1/players',
    f'https://statsapi.mlb.com/api/v1/stats',
    f'https://statsapi.mlb.com/api/v1/sports/1/players',
    f'https://statsapi.mlb.com/api/v1/sports/1/seasons/{season}',
]

for url in endpoints:
    try:
        print(f"Trying: {url}")
        r = requests.get(url, timeout=10)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            print("  ✓ WORKS")
            data = r.json()
            print(f"  Keys: {list(data.keys())[:3]}")
            break
    except Exception as e:
        print(f"  Error: {e}")
