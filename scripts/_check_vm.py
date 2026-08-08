"""查 VMZINC / 锌板 / 进口(法国) (v1.4 跨平台)"""
import sys
from pathlib import Path

# 复用 seed_prices 的 BASE 锚点
sys.path.insert(0, str(Path(__file__).parent))
from seed_prices import BASE  # noqa: E402

DB_PATH = BASE / "prices.db"


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"DB_PATH not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    print('--- 锌板/铜板 section ---')
    for r in conn.execute("SELECT name, country, brand_tier, notes FROM suppliers WHERE name LIKE '%VMZINC%' OR name LIKE '%Rheinzink%' OR name LIKE '%TECU%'"):
        print(f"  {r['name']:25s} | country={r['country']:15s} | tier={r['brand_tier']} | notes={r['notes']}")
    print()
    print('--- 包含"进口"country 的 ---')
    for r in conn.execute("SELECT name, country, notes FROM suppliers WHERE country LIKE '%进口%' LIMIT 10"):
        print(f"  {r['name']:25s} | country={r['country']} | notes={r['notes']}")
    print()
    print('--- 金属板 category 全部 ---')
    for r in conn.execute("SELECT name, country, brand_tier, notes FROM suppliers WHERE category='金属板' ORDER BY name"):
        print(f"  {r['name']:25s} | {r['country']:15s} | {r['brand_tier']:8s} | {r['notes']}")


if __name__ == "__main__":
    import sqlite3  # noqa: E402
    main()
