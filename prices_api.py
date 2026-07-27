"""
prices_api.py · 价格库查询 API
支持:
  按材料名/code/规格 查价格
  按材料名 + 价格类型 查
  按地区/品牌档 查
  按 building_type 查造价构成
  按 supplier 查供应
"""
import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / 'prices.db'


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# 查询 1: 按材料名查价格
# ============================================================
def search_by_material(name=None, code=None, category=None, brand_tier=None, region='CN-AVG', limit=30):
    conn = get_conn()
    sql = 'SELECT * FROM material_spec_prices WHERE 1=1'
    params = []
    if name:
        sql += ' AND (material_name LIKE ? OR spec LIKE ?)'
        params.extend([f'%{name}%', f'%{name}%'])
    if code:
        sql += ' AND material_code = ?'
        params.append(code)
    if category:
        sql += ' AND category = ?'
        params.append(category)
    if brand_tier:
        sql += ' AND brand_tier = ?'
        params.append(brand_tier)
    if region:
        sql += ' AND region_code = ?'
        params.append(region)
    sql += ' ORDER BY category, material_name LIMIT ?'
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# 查询 2: 按材料名聚合最新价格(取每种材料的第一条)
# ============================================================
def latest_prices(material_name=None, category=None, limit=20):
    """每种材料取第一条(同种材料多个 price_type 时按优先级:材料单价 < 施工造价)"""
    conn = get_conn()
    sql = '''
        SELECT * FROM material_spec_prices
        WHERE id IN (
            SELECT MIN(id) FROM material_spec_prices
            WHERE region_code = 'CN-AVG' AND fluctuation = '稳'
            GROUP BY material_name
        )
    '''
    params = []
    if material_name:
        sql += ' AND (material_name LIKE ? OR spec LIKE ?)'
        params.extend([f'%{material_name}%', f'%{material_name}%'])
    if category:
        sql += ' AND category = ?'
        params.append(category)
    sql += ' ORDER BY material_name LIMIT ?'
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# 查询 3: 按建筑类型查造价构成
# ============================================================
def cost_breakdown(building_type=None, finish_level=None):
    conn = get_conn()
    sql = 'SELECT * FROM cost_breakdowns WHERE 1=1'
    params = []
    if building_type:
        sql += ' AND building_type LIKE ?'
        params.append(f'%{building_type}%')
    if finish_level:
        sql += ' AND (finish_level LIKE ? OR finish_level IS NULL)'
        params.append(f'%{finish_level}%')
    sql += ' ORDER BY building_type, category'
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# 查询 4: 按 category 查供应商
# ============================================================
def search_suppliers(category=None, country='CN', brand_tier=None, limit=30):
    conn = get_conn()
    sql = 'SELECT * FROM suppliers WHERE 1=1'
    params = []
    if category:
        sql += ' AND category = ?'
        params.append(category)
    if country:
        sql += ' AND country = ?'
        params.append(country)
    if brand_tier:
        sql += ' AND brand_tier = ?'
        params.append(brand_tier)
    sql += ' ORDER BY category, brand_tier, name LIMIT ?'
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# 统计
# ============================================================
def stats():
    conn = get_conn()
    s = {}
    for tbl in ('material_spec_prices', 'suppliers', 'cost_breakdowns', 'regions'):
        s[tbl] = conn.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
    s['categories'] = conn.execute('SELECT COUNT(DISTINCT category) FROM material_spec_prices').fetchone()[0]
    s['brands'] = conn.execute('SELECT COUNT(DISTINCT material_name) FROM material_spec_prices').fetchone()[0]
    s['source_docs'] = conn.execute('SELECT COUNT(DISTINCT source_doc) FROM material_spec_prices').fetchone()[0]
    conn.close()
    return s


if __name__ == '__main__':
    import json
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stats'
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == 'stats':
        print(json.dumps(stats(), ensure_ascii=False, indent=2))
    elif cmd == 'material':
        rows = search_by_material(name=arg)
        print(f'共 {len(rows)} 条')
        for r in rows[:5]:
            print(f"  [{r['material_code']}] {r['material_name']} | {r['unit_price_min']}~{r['unit_price_max']} {r['unit']} ({r['price_type']})")
    elif cmd == 'latest':
        rows = latest_prices(material_name=arg)
        print(f'共 {len(rows)} 条最新价')
        for r in rows[:10]:
            print(f"  [{r['category']}] {r['material_name']} | {r['unit_price_min']}~{r['unit_price_max']} {r['unit']}")
    elif cmd == 'breakdown':
        rows = cost_breakdown(building_type=arg)
        print(f'共 {len(rows)} 条')
        for r in rows:
            print(f"  {r['building_type']:15s} | {r['category']:8s} | {r['pct_min']}~{r['pct_max']}% (典型 {r['pct_typical']}%)")
    elif cmd == 'suppliers':
        rows = search_suppliers(category=arg)
        print(f'共 {len(rows)} 条')
        for r in rows[:10]:
            print(f"  [{r['country']}] {r['name']:20s} | {r['brand_tier']:6s} | {r['strength'] or ''}")
