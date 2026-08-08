"""verify prices.db (v1.4 跨平台)"""
import sys
from pathlib import Path

# 复用 seed_prices 的 BASE 锚点 (scripts/seed_prices.py.parent.parent)
sys.path.insert(0, str(Path(__file__).parent))
from seed_prices import BASE  # noqa: E402

DB_PATH = BASE / "prices.db"


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"DB_PATH not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    tables = [r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print('TABLES:', tables)
    for t in tables:
        n = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'  {t}: {n}')

    print()
    print('--- sample material_spec_prices ---')
    for r in conn.execute('SELECT material_code, material_name, unit_price_min, unit_price_max, unit, price_type, category FROM material_spec_prices LIMIT 8'):
        print(f"  {r['material_code']:10s} | {r['category']:10s} | {r['material_name'][:30]:30s} | {r['unit_price_min']}~{r['unit_price_max']} {r['unit']} ({r['price_type']})")

    print()
    print('--- sample suppliers ---')
    for r in conn.execute('SELECT name, country, brand_tier, category FROM suppliers LIMIT 8'):
        print(f"  [{r['country']}] {r['name']:20s} | {r['brand_tier']:6s} | {r['category']}")

    print()
    print('--- sample cost_breakdowns (高层住宅) ---')
    for r in conn.execute("SELECT building_type, category, pct_min, pct_max, pct_typical FROM cost_breakdowns WHERE building_type LIKE '%高层%' OR building_type LIKE '%酒店%'"):
        print(f"  {r['building_type']:20s} | {r['category']:8s} | {r['pct_min']}~{r['pct_max']}% (typ {r['pct_typical']}%)")


if __name__ == "__main__":
    import sqlite3  # noqa: E402
    main()
