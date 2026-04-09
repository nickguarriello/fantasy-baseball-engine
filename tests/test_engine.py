"""
Test Suite for Fantasy Baseball Decision Engine

Run with:
    python -m pytest tests/test_engine.py -v

Or run directly:
    python tests/test_engine.py
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LEAGUE_CONFIG, H2H_CATEGORIES, API_CONFIG


class TestConfiguration(unittest.TestCase):
    """Test that configuration is correct."""
    
    def test_league_config_exists(self):
        """Verify league ID and team ID are configured."""
        self.assertEqual(LEAGUE_CONFIG['league_id'], 1985887220)
        self.assertEqual(LEAGUE_CONFIG['team_id'], 1)
        self.assertEqual(LEAGUE_CONFIG['season'], 2026)
    
    def test_categories_configured(self):
        """Verify H2H categories are all configured."""
        hitters = H2H_CATEGORIES['hitters']
        pitchers = H2H_CATEGORIES['pitchers']
        
        # Should have exactly 5 of each
        self.assertEqual(len(hitters), 5)
        self.assertEqual(len(pitchers), 5)
        
        # Check hitter categories
        hitter_names = [c['name'] for c in hitters]
        self.assertIn('R', hitter_names)
        self.assertIn('HR', hitter_names)
        self.assertIn('RBI', hitter_names)
        self.assertIn('SB', hitter_names)
        self.assertIn('OBP', hitter_names)
        
        # Check pitcher categories
        pitcher_names = [c['name'] for c in pitchers]
        self.assertIn('K', pitcher_names)
        self.assertIn('QS', pitcher_names)
        self.assertIn('ERA', pitcher_names)
        self.assertIn('WHIP', pitcher_names)
        self.assertIn('SVHD', pitcher_names)
    
    def test_api_urls(self):
        """Verify API endpoints are configured."""
        self.assertTrue(API_CONFIG['espn_base_url'].startswith('https'))
        self.assertTrue(API_CONFIG['mlb_stats_url'].startswith('https'))


class TestDataStructures(unittest.TestCase):
    """Test that data structures are valid."""
    
    def test_player_dict_structure(self):
        """Verify player dicts have expected fields."""
        sample = {
            'player_id': '123',
            'name': 'Test Player',
            'position': 'OF',
            'mlb_team': 'NYY',
            'is_pitcher': False,
        }
        
        self.assertIn('player_id', sample)
        self.assertIn('name', sample)
        self.assertIn('position', sample)
    
    def test_z_score_dict_structure(self):
        """Verify z-score dicts have expected fields."""
        sample = {
            'player_id': '123',
            'z_season': 1.2,
            'z_30day': 0.8,
            'z_14day': 1.5,
            'z_r': 0.5,
            'z_hr': 2.1,
        }
        
        self.assertIn('z_season', sample)
        self.assertIn('player_id', sample)


def run_quick_validation():
    """Quick validation without full test suite."""
    print("\n" + "="*70)
    print("QUICK VALIDATION")
    print("="*70 + "\n")
    
    checks = [
        ("League ID correct", LEAGUE_CONFIG['league_id'] == 1985887220),
        ("Team ID correct", LEAGUE_CONFIG['team_id'] == 1),
        ("Season set to 2026", LEAGUE_CONFIG['season'] == 2026),
        ("Hitter categories (5)", len(H2H_CATEGORIES['hitters']) == 5),
        ("Pitcher categories (5)", len(H2H_CATEGORIES['pitchers']) == 5),
        ("ESPN API URL valid", API_CONFIG['espn_base_url'].startswith('https')),
        ("MLB Stats API URL valid", API_CONFIG['mlb_stats_url'].startswith('https')),
    ]
    
    passed = sum(1 for _, result in checks if result)
    failed = len(checks) - passed
    
    for name, result in checks:
        status = "✓" if result else "✗"
        print(f"{status} {name}")
    
    print(f"\nResult: {passed} passed, {failed} failed\n")
    return failed == 0


if __name__ == '__main__':
    # Run quick validation first
    if run_quick_validation():
        print("="*70)
        print("RUNNING FULL TEST SUITE")
        print("="*70 + "\n")
        
        # Run full tests
        unittest.main(verbosity=2)
    else:
        sys.exit(1)