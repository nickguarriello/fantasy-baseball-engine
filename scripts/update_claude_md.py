"""
Auto-updates the [Last Run Stats] section in CLAUDE.md with live DB counts.
Called by the git pre-commit hook so context stays current across sessions.
"""

import sqlite3
import sys
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
DB_PATH = ROOT / "data" / "fantasy_baseball.db"

SECTION_HEADER = "## Last Run Stats (auto-updated by pre-commit hook)"


def get_db_stats():
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        stats = {}
        for table in ("players", "player_z_scores", "all_rosters", "league_teams"):
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            except Exception:
                stats[table] = "N/A"

        # Latest run info
        try:
            cursor.execute("SELECT MAX(date_calculated) FROM player_z_scores")
            last_run = cursor.fetchone()[0]
            stats["last_run"] = last_run or "unknown"
        except Exception:
            stats["last_run"] = "unknown"

        conn.close()
        return stats
    except Exception as e:
        print(f"[update_claude_md] DB read failed: {e}")
        return None


def update_claude_md(stats):
    if not CLAUDE_MD.exists():
        print("[update_claude_md] CLAUDE.md not found — skipping")
        return

    content = CLAUDE_MD.read_text(encoding="utf-8")

    new_section = f"""{SECTION_HEADER}

- **Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Last data run:** {stats.get('last_run', 'unknown')}
- **Players in DB:** {stats.get('players', 'N/A')}
- **Z-score records:** {stats.get('player_z_scores', 'N/A')}
- **Roster entries:** {stats.get('all_rosters', 'N/A')}
- **League teams:** {stats.get('league_teams', 'N/A')}
"""

    if SECTION_HEADER in content:
        # Replace existing section (up to next ## heading or end of file)
        start = content.index(SECTION_HEADER)
        # Find next section after this one
        rest = content[start + len(SECTION_HEADER):]
        next_section = rest.find("\n## ", 1)
        if next_section == -1:
            content = content[:start] + new_section
        else:
            content = content[:start] + new_section + "\n" + rest[next_section + 1:]
    else:
        # Append new section
        content = content.rstrip() + "\n\n" + new_section

    CLAUDE_MD.write_text(content, encoding="utf-8")
    print(f"[update_claude_md] CLAUDE.md updated with DB stats")


if __name__ == "__main__":
    stats = get_db_stats()
    if stats:
        update_claude_md(stats)
    else:
        print("[update_claude_md] No DB found — CLAUDE.md not updated")
        sys.exit(0)  # Not a fatal error for commits
