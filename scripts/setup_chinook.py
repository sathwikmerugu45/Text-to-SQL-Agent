"""
CLI script — downloads the Chinook SQLite database file.

No Docker, no psql, no server needed.
SQLite is built into Python — just download the .sqlite file and you're done.

Usage:
    python -m scripts.setup_chinook
"""

import os
import sys
import urllib.request

CHINOOK_SQLITE_URL = (
    "https://github.com/lerocha/chinook-database/raw/master/"
    "ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
)
LOCAL_SQLITE_PATH = "./data/chinook.sqlite"


def main():
    os.makedirs("./data", exist_ok=True)

    if os.path.exists(LOCAL_SQLITE_PATH):
        size_kb = os.path.getsize(LOCAL_SQLITE_PATH) // 1024
        print(f"✅ Chinook DB already exists at '{LOCAL_SQLITE_PATH}' ({size_kb} KB).")
        print("   Delete it and re-run if you want a fresh copy.")
        return

    print("⬇  Downloading Chinook SQLite database (~1 MB)...")
    print(f"   From: {CHINOOK_SQLITE_URL}")

    try:
        def _progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                pct = min(100, downloaded * 100 // total_size)
                print(f"\r   Progress: {pct}%", end="", flush=True)

        urllib.request.urlretrieve(CHINOOK_SQLITE_URL, LOCAL_SQLITE_PATH, _progress)
        print()  # newline after progress
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        print("   Check your internet connection and try again.")
        sys.exit(1)

    size_kb = os.path.getsize(LOCAL_SQLITE_PATH) // 1024
    print(f"✅ Downloaded to '{LOCAL_SQLITE_PATH}' ({size_kb} KB)")

    # Quick sanity check
    import sqlite3
    conn = sqlite3.connect(LOCAL_SQLITE_PATH)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()

    print(f"\n📋 Tables in Chinook DB ({len(tables)} total):")
    for t in tables:
        print(f"   • {t}")

    print("\n🎉 Setup complete! Now run:")
    print("   python -m scripts.index_schema")


if __name__ == "__main__":
    main()
