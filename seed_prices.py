"""
seed_prices.py · 把价格库目录里的 8 份 .md 入库到 prices.db
v1.2 - 终版:
  - 简单表:状态机解析(支持 5/6 列混合)
  - 段式:兼容 h2/h3/h4 三种标题层级(幕墙.md ### 段 vs 室内.md #### 段)
  - 供应商:5 列通用 + 自动识别"进口(国家)"格式
"""
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / 'prices.db'
SCHEMA = BASE / 'init_schema.sql'

DOCS = {
    '材料价格总库-原始数据.md': ('材料价格总库-原始数据.md', '结构/装饰/设备'),
    '外墙材料-价格区间.md':    ('外墙材料-价格区间.md', '幕墙/外墙'),
    '室内材料-价格区间.md':    ('室内材料-价格区间.md', '室内'),
    '屋面系统-价格区间.md':    ('屋面系统-价格区间.md', '屋面'),
    '幕墙系统-价格区间.md':    ('幕墙系统-价格区间.md', '幕墙'),
    '门窗系统-价格区间.md':    ('门窗系统-价格区间.md', '门窗'),
    '造价构成比例.md':         ('造价构成比例.md', '造价构成'),
    '材料供应商速查.md':       ('材料供应商速查.md', '供应商'),
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(open(SCHEMA, encoding='utf-8').read())
    conn.commit()
    return conn


def parse_price_range(s):
    if not s: return (None, None)
    s = str(s).replace(',', '').replace(' ', '')
    m = re.search(r'(\d+(?:\.\d+)?)\s*[~\-]\s*(\d+(?:\.\d+)?)', s)
    if m: return (float(m.group(1)), float(m.group(2)))
    m = re.search(r'(\d+(?:\.\d+)?)', s)
    if m:
        v = float(m.group(1))
        return (v, v)
    return (None, None)


def parse_unit(s):
    if not s: return ''
    s = str(s).replace(' ', '')
    m = re.search(r'元/(\S+)', s)
    if m: return '元/' + m.group(1)
    return s


# ============================================================
# 简单表解析(状态机)
# ============================================================
def parse_simple_table(text, source_doc, category='',
                      name_col=0, spec_col=0, unit_col=1, price_col=2,
                      has_unit_col=True, has_notes_col=True):
    rows = []
    current_section = ''
    in_table = False
    lines = text.split('\n')
    for line in lines:
        raw = line.rstrip()
        s = raw.strip()
        if (s.startswith('### ') or s.startswith('## ')) and not s.startswith('|'):
            current_section = s.lstrip('# ').strip()
            in_table = False
            continue
        if not s.startswith('|'):
            in_table = False
            continue
        cols = [c.strip() for c in s.split('|') if c.strip() != '']
        if not cols: continue
        if all(re.match(r'^[\-:\s]+$', c) for c in cols):
            in_table = True
            continue
        if not in_table:
            if any(kw in cols[0] for kw in ('材料', '规格', '类型', '类别', '费用类别', '等级', '做法', '品牌', '主营')):
                in_table = True
                continue
            in_table = True
        if re.match(r'^\d+(\.\d+)?$', cols[0]) and len(cols) > 2:
            cols = cols[1:]
        if len(cols) < 2: continue
        material_name = cols[name_col] if name_col < len(cols) else ''
        spec = cols[spec_col] if spec_col is not None and spec_col < len(cols) else material_name
        if has_unit_col and unit_col < len(cols):
            unit = parse_unit(cols[unit_col]) or '元/m²'
            price_text = cols[price_col] if price_col < len(cols) else ''
        else:
            unit = '元/m²'
            price_text = cols[price_col] if price_col < len(cols) else ''
        notes = cols[-1] if has_notes_col and len(cols) > max(price_col, unit_col) + 1 else ''
        pmin, pmax = parse_price_range(price_text)
        if pmin is None and pmax is None: continue
        fluctuation = '大幅波动' if '⚡' in (spec + material_name + notes) else '稳'
        rows.append({
            'material_name': material_name,
            'spec': spec, 'unit': unit,
            'pmin': pmin, 'pmax': pmax,
            'fluctuation': fluctuation,
            'section': current_section, 'notes': notes,
        })
    return rows


# ============================================================
# 段式解析
# ============================================================
def _extract_econ(rows, content, full_name, default_unit):
    mat_match = re.search(r'\*\*材料单价\*\*[：:](.+?)(?=\n|$)', content)
    lab_match = re.search(r'\*\*施工造价\*\*[：:](.+?)(?=\n|$)', content)
    comp_match = re.search(r'\*\*综合造价\*\*[：:](.+?)(?=\n|$)', content)
    if mat_match:
        pmin, pmax = parse_price_range(mat_match.group(1))
        if pmin is not None:
            rows.append({'material_name': full_name, 'spec': full_name,
                         'unit': default_unit, 'pmin': pmin, 'pmax': pmax,
                         'price_type': '材料单价', 'section': full_name})
    if lab_match:
        pmin, pmax = parse_price_range(lab_match.group(1))
        if pmin is not None:
            rows.append({'material_name': full_name, 'spec': full_name,
                         'unit': default_unit, 'pmin': pmin, 'pmax': pmax,
                         'price_type': '施工造价', 'section': full_name})
    if comp_match:
        pmin, pmax = parse_price_range(comp_match.group(1))
        if pmin is not None:
            rows.append({'material_name': full_name, 'spec': full_name,
                         'unit': default_unit, 'pmin': pmin, 'pmax': pmax,
                         'price_type': '综合造价', 'section': full_name})


def parse_section_economic(text, source_doc, category='', default_unit='元/m²'):
    rows = []
    pattern = re.compile(r'^(#{2,4})\s+([^\n]+)\n(.*?)(?=^#{2,4}\s+|\Z)', re.MULTILINE | re.DOTALL)
    h2 = ''; h3 = ''
    for m in pattern.finditer(text):
        hashes = len(m.group(1))
        title = m.group(2).strip()
        content = m.group(3)
        if hashes == 2:
            h2 = title; h3 = ''
            continue
        if hashes == 3:
            h3 = title
            if '经济属性' in title:
                full_name = h2
                _extract_econ(rows, content, full_name, default_unit)
            continue
        if hashes == 4 and '经济属性' in title:
            full_name = f'{h2} / {h3}' if h3 else h2
            full_name = full_name.replace('🔸 ', '').strip()
            _extract_econ(rows, content, full_name, default_unit)
    return rows


# ============================================================
# 供应商表
# ============================================================
def parse_supplier_table(text, current_category):
    rows = []
    section_name = ''
    in_table = False
    for line in text.split('\n'):
        s = line.rstrip()
        if (s.startswith('### ') or s.startswith('## ')) and not s.startswith('|'):
            section_name = s.lstrip('# ').strip()
            in_table = False
            continue
        if not s.startswith('|'):
            in_table = False
            continue
        raw = s.split('|')
        cols = [c.strip() for c in raw]
        if cols and cols[0] == '': cols = cols[1:]
        if cols and cols[-1] == '': cols = cols[:-1]
        if not cols: continue
        if all(re.match(r'^[\-:\s]+$', c) for c in cols if c):
            in_table = True
            continue
        if not in_table: continue
        if re.match(r'^\d+$', cols[0]): continue
        if section_name in ('采购建议', '采购周期参考', '通用采购渠道'): continue
        if len(cols) == 5:
            is_import = '进口' in section_name
            country = cols[1] if is_import else 'CN'
            china_ch = cols[2] if is_import else None
            tier = cols[3] if is_import else cols[2]
            strength = cols[4] if is_import else cols[3]
            note = '' if is_import else (cols[4] if len(cols) > 4 else '')
            if country == '国产': country = 'CN'
            elif country.startswith('进口'):
                m = re.search(r'（(.+?)）', country)
                if m: country = m.group(1)
            rows.append({
                'name': cols[0], 'name_en': None, 'country': country,
                'brand_tier': tier, 'category': current_category,
                'strength': strength, 'china_channel': china_ch,
                'section': section_name, 'notes': note,
            })
        elif len(cols) == 6:
            country = cols[1] or 'CN'
            if country == '国产': country = 'CN'
            elif country.startswith('进口'):
                m = re.search(r'（(.+?)）', country)
                if m: country = m.group(1)
            rows.append({
                'name': cols[0], 'name_en': None, 'country': country,
                'brand_tier': cols[3] if len(cols) > 3 else '',
                'category': current_category,
                'strength': cols[4] if len(cols) > 4 else '',
                'china_channel': cols[2] if len(cols) > 2 else None,
                'section': section_name,
            })
    return rows


# ============================================================
# 造价构成
# ============================================================
def parse_cost_breakdown(text):
    rows = []
    current_building = ''
    current_finish = ''
    in_table = False
    for line in text.split('\n'):
        s = line.rstrip()
        if s.startswith('### ') and not s.startswith('|'):
            t = s.lstrip('# ').strip()
            m = re.match(r'(.+?)(?:（|\()(.+?)(?:）|\))', t)
            if m:
                current_building = m.group(1).strip()
                current_finish = m.group(2).strip()
            else:
                current_building = t; current_finish = None
            in_table = False
            continue
        if not s.startswith('|'):
            in_table = False; continue
        cols = [c.strip() for c in s.split('|') if c.strip() != '']
        if not cols: continue
        if all(re.match(r'^[\-:\s]+$', c) for c in cols):
            in_table = True; continue
        if not in_table: continue
        if re.match(r'^费用类别$|^类别$', cols[0]): continue
        if re.match(r'^\d+$', cols[0]): continue
        if len(cols) < 2: continue
        category_name = cols[0]
        pct_min, pct_max = parse_price_range(cols[1]) if len(cols) > 1 else (None, None)
        pct_typical = None
        if len(cols) > 2:
            tm = re.search(r'(\d+(?:\.\d+)?)', cols[2])
            if tm: pct_typical = float(tm.group(1))
        contents = cols[3] if len(cols) > 3 else ''
        rows.append({
            'building_type': current_building, 'finish_level': current_finish,
            'category': category_name, 'pct_min': pct_min, 'pct_max': pct_max,
            'pct_typical': pct_typical, 'contents': contents,
        })
    return rows


# ============================================================
# 分类 code
# ============================================================
CATEGORY_CODES = {
    '结构/装饰/设备': 'STR', '幕墙/外墙': 'CURT', '室内': 'INT',
    '屋面': 'ROOF', '幕墙': 'CURT', '门窗': 'DOOR',
}


def allocate_code(category, existing_codes):
    prefix = CATEGORY_CODES.get(category, 'X')
    n = 1
    while True:
        code = f'{prefix}_{n:03d}'
        if code not in existing_codes:
            existing_codes.add(code)
            return code
        n += 1


# ============================================================
# insert
# ============================================================
def insert_material_spec_prices(conn, rows, source_doc, category, default_price_type='施工造价'):
    cur = conn.cursor()
    existing = {r[0] for r in cur.execute('SELECT material_code FROM material_spec_prices').fetchall()}
    inserted = 0
    for r in rows:
        code = allocate_code(category, existing)
        pmin, pmax = r['pmin'], r['pmax']
        price_type = r.get('price_type', default_price_type)
        avg = (pmin + pmax) / 2 if pmin is not None and pmax is not None else None
        cur.execute('''
            INSERT INTO material_spec_prices
            (material_code, material_name, category, spec, unit,
             unit_price_min, unit_price_max, unit_price_avg, price_type,
             fluctuation, source_doc, source_section, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [code, r['material_name'], category, r.get('spec', r['material_name']),
              r.get('unit', '元/m²'), pmin, pmax, avg, price_type,
              r.get('fluctuation', '稳'), source_doc, r.get('section', ''),
              r.get('notes', '')])
        inserted += 1
    conn.commit()
    return inserted


def insert_suppliers(conn, rows, source_doc):
    cur = conn.cursor()
    existing = {r[0] for r in cur.execute('SELECT name FROM suppliers').fetchall()}
    inserted = 0
    for r in rows:
        if r['name'] in existing: continue
        cur.execute('''
            INSERT INTO suppliers
            (name, name_en, country, brand_tier, category, strength,
             china_channel, source_doc, notes, verified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        ''', [r['name'], r.get('name_en'), r.get('country', 'CN'),
              r.get('brand_tier'), r.get('category'), r.get('strength'),
              r.get('china_channel'), source_doc,
              r.get('notes') or r.get('section', '')])
        inserted += 1
    conn.commit()
    return inserted


def insert_cost_breakdowns(conn, rows, source_doc):
    cur = conn.cursor()
    inserted = 0
    for r in rows:
        cur.execute('''
            INSERT INTO cost_breakdowns
            (building_type, finish_level, category, pct_min, pct_max, pct_typical, contents, source_doc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [r['building_type'], r.get('finish_level'), r['category'],
              r.get('pct_min'), r.get('pct_max'), r.get('pct_typical'),
              r.get('contents'), source_doc])
        inserted += 1
    conn.commit()
    return inserted


# ============================================================
# main
# ============================================================
def main():
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

    print(f'[seed] DB: {DB_PATH}')
    conn = init_db()
    cur = conn.cursor()
    for tbl in ('material_spec_prices', 'suppliers', 'supplier_quotes', 'cost_breakdowns'):
        try: cur.execute(f'DELETE FROM {tbl}')
        except Exception: pass
    conn.commit()
    print('[seed] schema ready + 旧数据已清')

    summary = {}

    text = (BASE / '材料价格总库-原始数据.md').read_text(encoding='utf-8')
    rows = parse_simple_table(text, DOCS['材料价格总库-原始数据.md'][0],
                              name_col=0, spec_col=0, unit_col=1, price_col=2, has_unit_col=True)
    n = insert_material_spec_prices(conn, rows, DOCS['材料价格总库-原始数据.md'][0], '结构/装饰/设备', '材料单价')
    summary['材料价格总库-原始数据'] = n
    print(f'[seed] 原始数据: {n} 行')

    text = (BASE / '外墙材料-价格区间.md').read_text(encoding='utf-8')
    rows_mat = parse_simple_table(text, DOCS['外墙材料-价格区间.md'][0],
                                  name_col=0, spec_col=0, unit_col=1, price_col=1, has_unit_col=True)
    for r in rows_mat:
        r['unit'] = '元/m²'; r['price_type'] = '材料单价'
    n1 = insert_material_spec_prices(conn, rows_mat, DOCS['外墙材料-价格区间.md'][0], '幕墙/外墙', '材料单价')
    rows_lab = parse_simple_table(text, DOCS['外墙材料-价格区间.md'][0],
                                  name_col=0, spec_col=0, unit_col=1, price_col=2, has_unit_col=True)
    for r in rows_lab:
        r['unit'] = '元/m²'; r['price_type'] = '施工造价'
    n2 = insert_material_spec_prices(conn, rows_lab, DOCS['外墙材料-价格区间.md'][0], '幕墙/外墙', '施工造价')
    summary['外墙材料-价格区间'] = n1 + n2
    print(f'[seed] 外墙: {n1} + {n2} = {n1+n2} 行')

    text = (BASE / '室内材料-价格区间.md').read_text(encoding='utf-8')
    rows = parse_section_economic(text, DOCS['室内材料-价格区间.md'][0], category='室内', default_unit='元/m²')
    n = insert_material_spec_prices(conn, rows, DOCS['室内材料-价格区间.md'][0], '室内')
    summary['室内材料-价格区间'] = n
    print(f'[seed] 室内(段式): {n} 行')

    text = (BASE / '屋面系统-价格区间.md').read_text(encoding='utf-8')
    rows = parse_simple_table(text, DOCS['屋面系统-价格区间.md'][0],
                              name_col=0, spec_col=0, unit_col=1, price_col=1, has_unit_col=False)
    n = insert_material_spec_prices(conn, rows, DOCS['屋面系统-价格区间.md'][0], '屋面', '综合造价')
    summary['屋面系统-价格区间'] = n
    print(f'[seed] 屋面: {n} 行')

    text = (BASE / '幕墙系统-价格区间.md').read_text(encoding='utf-8')
    rows = parse_section_economic(text, DOCS['幕墙系统-价格区间.md'][0], category='幕墙', default_unit='元/m²')
    n = insert_material_spec_prices(conn, rows, DOCS['幕墙系统-价格区间.md'][0], '幕墙')
    summary['幕墙系统-价格区间'] = n
    print(f'[seed] 幕墙(段式): {n} 行')

    text = (BASE / '门窗系统-价格区间.md').read_text(encoding='utf-8')
    rows = parse_simple_table(text, DOCS['门窗系统-价格区间.md'][0],
                              name_col=0, spec_col=0, unit_col=1, price_col=1, has_unit_col=False)
    for r in rows:
        r['unit'] = '元/樘' if '樘' in r.get('spec', '') or r.get('unit') == '元/樘' else '元/m²'
    n = insert_material_spec_prices(conn, rows, DOCS['门窗系统-价格区间.md'][0], '门窗', '综合造价')
    summary['门窗系统-价格区间'] = n
    print(f'[seed] 门窗: {n} 行')

    text = (BASE / '造价构成比例.md').read_text(encoding='utf-8')
    rows = parse_cost_breakdown(text)
    n = insert_cost_breakdowns(conn, rows, DOCS['造价构成比例.md'][0])
    summary['造价构成比例'] = n
    print(f'[seed] 造价构成: {n} 行')

    text = (BASE / '材料供应商速查.md').read_text(encoding='utf-8')
    cat_map = {
        '1. 石材供应商': '石材', '2. 金属板供应商': '金属板', '3. 陶板供应商': '陶板',
        '4. 玻璃幕墙供应商': '玻璃幕墙', '5. GRC / UHPC 供应商': 'GRC/UHPC',
        '6. 木饰面供应商': '木饰面', '7. 涂料供应商': '涂料',
        '8. 瓷砖/岩板供应商': '瓷砖/岩板', '9. 木地板供应商': '木地板',
        '10. 吊顶材料供应商': '吊顶',
    }
    all_rows = []
    current_cat = ''
    for chunk in re.split(r'\n(##\s+[^\n]+)', text):
        if re.match(r'^##\s+', chunk):
            t = re.sub(r'^##\s+', '', chunk).strip()
            current_cat = cat_map.get(t, t)
        else:
            for r in parse_supplier_table(chunk, current_cat):
                all_rows.append(r)
    n = insert_suppliers(conn, all_rows, DOCS['材料供应商速查.md'][0])
    summary['材料供应商速查'] = n
    print(f'[seed] 供应商: {n} 行')

    conn.close()
    print()
    print('=== 总结 ===')
    total = 0
    for k, v in summary.items():
        print(f'  {k}: {v} 行')
        total += v
    print(f'  总计: {total} 行')


if __name__ == '__main__':
    main()
