"""debug supplier parse · v1.3 改:删除 Windows 硬编路径,改用 __file__ 相对路径"""
import sys
from pathlib import Path
# 用 __file__ 相对路径,跨 macOS/Windows/Linux 通用
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
from seed_prices import parse_supplier_table
import re

text = (BASE / '材料供应商速查.md').read_text(encoding='utf-8')
cat_map = {'1. 石材供应商': '石材'}

chunks = re.split(r'\n(##\s+[^\n]+)', text)
current_cat = ''
all_rows = []
for chunk in chunks:
    if re.match(r'^##\s+', chunk):
        t = re.sub(r'^##\s+', '', chunk).strip()
        current_cat = cat_map.get(t, t)
        print(f'== {t} (cat={current_cat}) ==')
    else:
        rows = parse_supplier_table(chunk, current_cat)
        for r in rows:
            print(f'  -> {r["name"]} | country={r["country"]} | tier={r["brand_tier"]} | sec={r["section"]}')
        all_rows.extend(rows)
print(f'TOTAL: {len(all_rows)}')
