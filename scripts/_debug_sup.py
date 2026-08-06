"""debug supplier parse"""
import sys
sys.path.insert(0, r'D:\Mac\Mac\Mac\workteam\05_space\03_architect\Defense\06-Material\Attack\价格库\scripts')
from seed_prices import parse_supplier_table
import re

text = open(r'D:\Mac\Mac\Mac\workteam\05_space\03_architect\Defense\06-Material\Attack\价格库\材料供应商速查.md', encoding='utf-8').read()
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
