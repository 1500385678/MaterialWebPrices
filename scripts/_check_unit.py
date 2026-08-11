#!/usr/bin/env python3
"""
R282 P0 防御脚本:扫 prices.db 验证 unit 字段,任何非"元/..."行告警。
用法:python3 scripts/_check_unit.py
退出码:0 = 干净,1 = 有污染(便于 cron 串联)
"""
import sys
from pathlib import Path

# 与 seed_prices 复用 BASE 锚点
BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
from seed_prices import BASE as SEED_BASE  # noqa: E402

DB_PATH = SEED_BASE / 'prices.db'

# 合法 unit 白名单(预定义单位,非"元/"前缀的合法值)
LEGACY_UNITS = {'元/组', '元/套', '元/点', '元/台', '元/桶', '元/kW', '元/kg'}

def main():
    import sqlite3
    if not DB_PATH.exists():
        print(f'❌ DB 不存在: {DB_PATH}')
        return 1
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('''
        SELECT id, material_name, unit, source_section
        FROM material_spec_prices
        WHERE unit NOT LIKE "元/%%"
          AND unit NOT IN ({})
        ORDER BY id
    '''.format(','.join('?' * len(LEGACY_UNITS))), tuple(LEGACY_UNITS))
    polluted = cur.fetchall()
    if polluted:
        print(f'❌ 发现 {len(polluted)} 行 unit 污染:')
        for r in polluted:
            print(f'  id={r["id"]} | name={r["material_name"]!r} | unit={r["unit"]!r} | section={r["source_section"]!r}')
        return 1
    # 统计正常 unit 分布
    cur.execute('SELECT unit, COUNT(*) AS cnt FROM material_spec_prices GROUP BY unit ORDER BY cnt DESC')
    print('✅ unit 字段干净。分布:')
    for r in cur.fetchall():
        print(f'  {r["unit"]}: {r["cnt"]}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
