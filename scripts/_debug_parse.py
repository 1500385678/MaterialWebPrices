"""Debug 解析: 屋面 + 幕墙 · v1.3 改:删除 Windows 硬编路径,改用 __file__ 相对路径"""
import sys
from pathlib import Path
# 用 __file__ 相对路径,跨 macOS/Windows/Linux 通用
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
from seed_prices import parse_simple_table, parse_section_economic

# 屋面
text = (BASE / '屋面系统-价格区间.md').read_text(encoding='utf-8')
print('--- 屋面 (3 列简单表) ---')
rows = parse_simple_table(text, '屋面系统-价格区间.md', name_col=0, spec_col=0, unit_col=1, price_col=1, has_unit_col=False)
print(f'count: {len(rows)}')
for r in rows[:5]:
    print(r)

# 幕墙
text2 = (BASE / '幕墙系统-价格区间.md').read_text(encoding='utf-8')
print()
print('--- 幕墙 (段式) ---')
rows2 = parse_section_economic(text2, '幕墙系统-价格区间.md')
print(f'count: {len(rows2)}')
for r in rows2[:5]:
    print(r)
print()
# 找 ### 🔸 经济属性
import re
matches = re.findall(r'### 🔸.*?经济属性', text2)
print(f'经济属性 pattern found: {len(matches)}')
print(f'first 3: {matches[:3]}')
# 看经济属性段长啥样
idx = text2.find('经济属性')
if idx > 0:
    print('--- 段样本 ---')
    print(text2[idx:idx+200])
