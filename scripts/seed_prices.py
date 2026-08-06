"""
seed_prices.py · 把价格库目录里的 8 份 .md 入库到 prices.db
v1.2 - 加严格 schema 检查:
  - parse_simple_table 同表所有行 col_count 必须一致,不一致 raise
  - 修复 v1.1 解析漂移(外墙 33 vs 38: 同档 price_col 跳变导致)
  - 补 docstring 说明外墙分两次解析的语义(材料单价 vs 施工造价)

调用约定:
  - parse_simple_table 同表必须 col_count 稳定 → price_col 在全表有效
  - 外墙材料-价格区间.md 是唯一同档内含"材料单价 + 施工造价"双价列的文件
    故用两次 parse_simple_table(price_col=1, price_col=2) 拆出两个 price_type
  - 其他文件都是单一价列,只 parse 一次
"""
import re
import sqlite3
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
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
                      has_unit_col=True, skip_first_data_row=True,
                      has_notes_col=True):
    """
    状态机解析 | col | col | 表
    name_col / spec_col / unit_col / price_col 都在 0-indexed 数据列
    skip_first_data_row: 跳过首行(通常表头) - 但实际表头是表头本身,首数据行是表头

    v1.2 严格 schema 检查:
      - 同表(同一组表头分隔 |---|---| 后到下一个非表行)所有数据行 col_count 必须一致
      - 不一致 raise ValueError,阻止"33 vs 38 漂移"型静默丢行
      - 序号列(1./1.1 等)若在首列,会被自动剥离,剥离后剩余列数才参与 schema check
    """
    rows = []
    current_section = ''
    in_table = False
    col_count = 0
    table_first_row_count = None   # v1.2: 记录表首数据行 col_count(剥序号后),用于 schema check
    table_index = 0                # v1.2: 调试用,标识是第几个表
    lines = text.split('\n')
    for line in lines:
        raw = line.rstrip()
        s = raw.strip()
        # 章节标题 (## 或 ### 但不是表格行)
        if (s.startswith('### ') or s.startswith('## ')) and not s.startswith('|'):
            current_section = s.lstrip('# ').strip()
            in_table = False
            table_first_row_count = None  # v1.2: 新章节,重置 schema 基线
            continue
        if not s.startswith('|'):
            in_table = False
            table_first_row_count = None  # v1.2: 出表,重置
            continue
        # 拆列
        cols = [c.strip() for c in s.split('|') if c.strip() != '']
        # 跳过空表行
        if not cols: continue
        # 表头分隔 (|---|---|)
        if all(re.match(r'^[\-:\s]+$', c) for c in cols):
            in_table = True
            col_count = len(cols)
            table_first_row_count = None  # v1.2: 新表,清基线
            table_index += 1
            continue
        # 表头本身(首行) - 标记进入表,不解析
        # 简单办法:第一次见到 |xxx| 模式时,如果是表头(包含"材料"/"规格"/"类型"等),跳过
        if not in_table:
            # 还没进表,这一行可能是表头
            if any(kw in cols[0] for kw in ('材料', '规格', '类型', '类别', '费用类别', '等级', '做法', '品牌', '主营')):
                in_table = True
                col_count = len(cols)
                table_first_row_count = None
                table_index += 1
                continue
            # 否则是数据行(没有表头分隔) - 也允许
            in_table = True
            col_count = len(cols)
            table_first_row_count = None
            table_index += 1
        # 数据行
        # 处理序号列
        if re.match(r'^\d+(\.\d+)?$', cols[0]) and len(cols) > 2:
            cols = cols[1:]
        if len(cols) < 2: continue
        # v1.2 严格 schema check: 同表所有数据行(剥序号后)col_count 必须一致
        if table_first_row_count is None:
            table_first_row_count = len(cols)
        elif len(cols) != table_first_row_count:
            raise ValueError(
                f'parse_simple_table 严格 schema 检查失败: '
                f'{source_doc} 第 {table_index} 个表({current_section}) '
                f'首行 {table_first_row_count} 列,后续行 {len(cols)} 列 → '
                f'price_col={price_col} 在不一致行上会指向错误列,静默丢行风险。'
                f'行原文: {raw!r}'
            )
        # 提取字段
        material_name = cols[name_col] if name_col < len(cols) else ''
        spec = cols[spec_col] if spec_col is not None and spec_col < len(cols) else material_name
        if has_unit_col and unit_col < len(cols):
            unit = parse_unit(cols[unit_col]) or '元/m²'
            price_text = cols[price_col] if price_col < len(cols) else ''
        else:
            # 从表头里识别 unit (e.g. "综合造价(元/m²)")
            unit = '元/m²'
            price_text = cols[price_col] if price_col < len(cols) else ''
        notes = cols[-1] if has_notes_col and len(cols) > max(price_col, unit_col) + 1 else ''
        pmin, pmax = parse_price_range(price_text)
        if pmin is None and pmax is None: continue
        fluctuation = '大幅波动' if '⚡' in (spec + material_name + notes) else '稳'
        rows.append({
            'material_name': material_name,
            'spec': spec,
            'unit': unit,
            'pmin': pmin, 'pmax': pmax,
            'fluctuation': fluctuation,
            'section': current_section,
            'notes': notes,
        })
    return rows


# ============================================================
# 段式解析(经济属性段)
# ============================================================
def parse_section_economic(text, source_doc, category='', default_unit='元/m²'):
    """
    找 ### xxx 段,每个段下找 ### 🔸 经济属性 子段,提取 **材料单价** / **施工造价** / **综合造价**
    """
    rows = []
    # 用 regex 找所有 ##/###/#### 标题 + 内容的配对
    # 兼容 3 种文档风格:
    #   - 幕墙:.md  ## h2 大类 → ### 🔸 段 (3 个 #)
    #   - 室内:.md  ## h2 → ### h3 章节 → #### 🔸 段 (4 个 #)
    pattern = re.compile(r'^(#{2,4})\s+([^\n]+)\n(.*?)(?=^#{2,4}\s+|\Z)', re.MULTILINE | re.DOTALL)
    h2 = ''     # 大类(如 "1. 石材")
    h3 = ''     # 小节(如 "1.1 实木地板",或 "🔸 立面属性")
    for m in pattern.finditer(text):
        hashes = len(m.group(1))
        title = m.group(2).strip()
        content = m.group(3)
        if hashes == 2:
            h2 = title
            h3 = ''
            continue
        if hashes == 3:
            h3 = title
            # 幕墙风格:### 🔸 经济属性 直接是段
            if '经济属性' in title:
                full_name = h2
                _extract_econ(rows, content, full_name, default_unit)
            continue
        if hashes == 4 and '经济属性' in title:
            # 室内风格:#### 🔸 经济属性 段
            # 材料名 = h2 + h3
            full_name = f'{h2} / {h3}' if h3 else h2
            full_name = full_name.replace('🔸 ', '').strip()
            _extract_econ(rows, content, full_name, default_unit)
    return rows


def _extract_econ(rows, content, full_name, default_unit):
    """从经济属性 content 里抽 3 类价格"""
    mat_match = re.search(r'\*\*材料单价\*\*[：:](.+?)(?=\n|$)', content)
    lab_match = re.search(r'\*\*施工造价\*\*[：:](.+?)(?=\n|$)', content)
    comp_match = re.search(r'\*\*综合造价\*\*[：:](.+?)(?=\n|$)', content)
    if mat_match:
        pmin, pmax = parse_price_range(mat_match.group(1))
        if pmin is not None:
            rows.append({
                'material_name': full_name, 'spec': full_name,
                'unit': default_unit, 'pmin': pmin, 'pmax': pmax,
                'price_type': '材料单价', 'section': full_name,
            })
    if lab_match:
        pmin, pmax = parse_price_range(lab_match.group(1))
        if pmin is not None:
            rows.append({
                'material_name': full_name, 'spec': full_name,
                'unit': default_unit, 'pmin': pmin, 'pmax': pmax,
                'price_type': '施工造价', 'section': full_name,
            })
    if comp_match:
        pmin, pmax = parse_price_range(comp_match.group(1))
        if pmin is not None:
            rows.append({
                'material_name': full_name, 'spec': full_name,
                'unit': default_unit, 'pmin': pmin, 'pmax': pmax,
                'price_type': '综合造价', 'section': full_name,
            })


# ============================================================
# 供应商表
# ============================================================
def parse_supplier_table(text, current_category):
    """状态机:## 是大类,### 是子类,| col | col | 是表"""
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
        # 拆列:不过滤空(保留末尾空,让列数真实)
        raw = s.split('|')
        # strip 每格,但保留空位
        cols = [c.strip() for c in raw]
        # 移除首尾空(因为 `|...|` split 会多出 2 个空)
        if cols and cols[0] == '': cols = cols[1:]
        if cols and cols[-1] == '': cols = cols[:-1]
        if not cols: continue
        if all(re.match(r'^[\-:\s]+$', c) for c in cols if c):
            in_table = True
            continue
        if not in_table: continue
        if re.match(r'^\d+$', cols[0]): continue
        if section_name in ('采购建议', '采购周期参考', '通用采购渠道'): continue
        # 通用 5 列解析(不区分国产/进口,统一按 name/产品or国家/价格定位/特点/项目)
        # section_name 兼容:
        #   '国产品牌' / '进口品牌' / '进口品牌(中国可购)' / '铝单板' / '锌板/铜板' / ...
        # 进口品牌的 country 从 cols[1] 读(原产国);其他默认 CN
        if len(cols) == 5:
            # 三种 5 列布局,列含义不同,需按段名/行内容分流:
            # 1) 段名含"进口"(### 进口品牌 / 进口品牌(中国可购)):
            #    cols: 品牌|原产国|中国代理/渠道|价格定位|特点
            # 2) 行内容含"进口",但段名不含(### 锌板/铜板 / 穿孔铝板/装饰板):
            #    cols: 品牌|类型(进口(法国))|价格定位|特点|适用项目
            # 3) 完全国产(### 国产品牌 / 铝单板):
            #    cols: 品牌|主营产品/类型|价格定位|特点|适用项目
            is_import_section = '进口' in section_name
            is_import_row = '进口' in cols[1]
            if is_import_section:
                is_import = True
                country = cols[1]  # 原产国(已是国家名,如"意大利"/"法国")
                china_ch = cols[2]  # 中国代理/渠道
                tier = cols[3]      # 价格定位
                strength = cols[4]  # 特点
                note = ''
            elif is_import_row:
                # 处理 '进口(法国)' / '进口(法国/比利时)' 等,兼容半角/全角括号
                c1 = re.sub(r'进口[\(（](.*?)[\)）]', r'\1', cols[1])
                country = c1.split('/')[0].strip() or 'XX'
                china_ch = None  # 无独立"中国代理"列
                tier = cols[2]      # 价格定位
                strength = cols[3]  # 特点
                note = ''
            else:
                is_import = False
                country = 'CN'
                china_ch = None
                tier = cols[2]      # 价格定位
                strength = cols[3]  # 特点
                note = cols[4] if len(cols) > 4 else ''
            rows.append({
                'name': cols[0], 'name_en': None, 'country': country,
                'brand_tier': tier, 'category': current_category,
                'strength': strength, 'china_channel': china_ch,
                'section': section_name,
                '_note': note,  # 暂存到 notes
            })
        elif len(cols) == 6:
            # 兜底:6 列
            rows.append({
                'name': cols[0], 'name_en': None, 'country': cols[1] or 'CN',
                'brand_tier': cols[3] if len(cols) > 3 else '',
                'category': current_category,
                'strength': cols[4] if len(cols) > 4 else '',
                'china_channel': cols[2] if len(cols) > 2 else None,
                'section': section_name,
            })
        elif len(cols) == 4:
            # 兜底:4 列
            rows.append({
                'name': cols[0], 'name_en': None, 'country': 'CN',
                'brand_tier': cols[1] if len(cols) > 1 else '',
                'category': current_category,
                'strength': cols[2] if len(cols) > 2 else '',
                'china_channel': None, 'section': section_name,
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
                current_building = t
                current_finish = None
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
            'building_type': current_building,
            'finish_level': current_finish,
            'category': category_name,
            'pct_min': pct_min, 'pct_max': pct_max,
            'pct_typical': pct_typical, 'contents': contents,
        })
    return rows


# ============================================================
# 分类 code
# ============================================================
CATEGORY_CODES = {
    '结构/装饰/设备': 'STR',
    '幕墙/外墙': 'CURT',
    '室内': 'INT',
    '屋面': 'ROOF',
    '幕墙': 'CURT',
    '门窗': 'DOOR',
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
             china_channel, source_doc, verified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        ''', [r['name'], r.get('name_en'), r.get('country', 'CN'),
              r.get('brand_tier'), r.get('category'), r.get('strength'),
              r.get('china_channel'), source_doc])
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
    # 清空旧数据(便于重跑)
    conn = init_db()
    cur = conn.cursor()
    for tbl in ('material_spec_prices', 'suppliers', 'supplier_quotes', 'cost_breakdowns'):
        try: cur.execute(f'DELETE FROM {tbl}')
        except Exception: pass
    conn.commit()
    print('[seed] schema ready + 旧数据已清')

    summary = {}

    # 1. 材料价格总库-原始数据.md
    text = (BASE / '材料价格总库-原始数据.md').read_text(encoding='utf-8')
    rows = parse_simple_table(text, DOCS['材料价格总库-原始数据.md'][0],
                              name_col=0, spec_col=0, unit_col=1, price_col=2, has_unit_col=True)
    n = insert_material_spec_prices(conn, rows, DOCS['材料价格总库-原始数据.md'][0], '结构/装饰/设备', '材料单价')
    summary['材料价格总库-原始数据'] = n
    print(f'[seed] 原始数据: {n} 行')

    # 2. 外墙材料-价格区间.md (材料单价 + 施工造价 各一行)
    text = (BASE / '外墙材料-价格区间.md').read_text(encoding='utf-8')
    rows_mat = parse_simple_table(text, DOCS['外墙材料-价格区间.md'][0],
                                  name_col=0, spec_col=0, unit_col=1, price_col=1, has_unit_col=True)
    # cols: 材料/材料单价/施工造价/工艺与备注
    # 修 unit (元/m² from header)
    for r in rows_mat:
        r['unit'] = '元/m²'
        r['price_type'] = '材料单价'
    n1 = insert_material_spec_prices(conn, rows_mat, DOCS['外墙材料-价格区间.md'][0], '幕墙/外墙', '材料单价')
    rows_lab = parse_simple_table(text, DOCS['外墙材料-价格区间.md'][0],
                                  name_col=0, spec_col=0, unit_col=1, price_col=2, has_unit_col=True)
    for r in rows_lab:
        r['unit'] = '元/m²'
        r['price_type'] = '施工造价'
    n2 = insert_material_spec_prices(conn, rows_lab, DOCS['外墙材料-价格区间.md'][0], '幕墙/外墙', '施工造价')
    summary['外墙材料-价格区间'] = n1 + n2
    print(f'[seed] 外墙: {n1} (材料单价) + {n2} (施工造价) = {n1+n2} 行')

    # 3. 室内材料-价格区间.md (段式)
    text = (BASE / '室内材料-价格区间.md').read_text(encoding='utf-8')
    rows = parse_section_economic(text, DOCS['室内材料-价格区间.md'][0], category='室内', default_unit='元/m²')
    n = insert_material_spec_prices(conn, rows, DOCS['室内材料-价格区间.md'][0], '室内')
    summary['室内材料-价格区间'] = n
    print(f'[seed] 室内(段式): {n} 行')

    # 4. 屋面系统-价格区间.md (3 列:做法/综合造价/工艺与备注)
    text = (BASE / '屋面系统-价格区间.md').read_text(encoding='utf-8')
    rows = parse_simple_table(text, DOCS['屋面系统-价格区间.md'][0],
                              name_col=0, spec_col=0, unit_col=1, price_col=1, has_unit_col=False)
    n = insert_material_spec_prices(conn, rows, DOCS['屋面系统-价格区间.md'][0], '屋面', '综合造价')
    summary['屋面系统-价格区间'] = n
    print(f'[seed] 屋面: {n} 行')

    # 5. 幕墙系统-价格区间.md (段式)
    text = (BASE / '幕墙系统-价格区间.md').read_text(encoding='utf-8')
    rows = parse_section_economic(text, DOCS['幕墙系统-价格区间.md'][0], category='幕墙', default_unit='元/m²')
    n = insert_material_spec_prices(conn, rows, DOCS['幕墙系统-价格区间.md'][0], '幕墙')
    summary['幕墙系统-价格区间'] = n
    print(f'[seed] 幕墙(段式): {n} 行')

    # 6. 门窗系统-价格区间.md (3 列:类型/综合造价/性能与备注)
    text = (BASE / '门窗系统-价格区间.md').read_text(encoding='utf-8')
    rows = parse_simple_table(text, DOCS['门窗系统-价格区间.md'][0],
                              name_col=0, spec_col=0, unit_col=1, price_col=1, has_unit_col=False)
    # 调整 unit:表头里识别 元/樘 vs 元/m²
    for r in rows:
        if '元/樘' in r.get('spec', '') or r.get('unit') == '元/樘':
            r['unit'] = '元/樘'
        else:
            r['unit'] = '元/m²'
    n = insert_material_spec_prices(conn, rows, DOCS['门窗系统-价格区间.md'][0], '门窗', '综合造价')
    summary['门窗系统-价格区间'] = n
    print(f'[seed] 门窗: {n} 行')

    # 7. 造价构成比例.md
    text = (BASE / '造价构成比例.md').read_text(encoding='utf-8')
    rows = parse_cost_breakdown(text)
    n = insert_cost_breakdowns(conn, rows, DOCS['造价构成比例.md'][0])
    summary['造价构成比例'] = n
    print(f'[seed] 造价构成: {n} 行')

    # 8. 材料供应商速查.md
    text = (BASE / '材料供应商速查.md').read_text(encoding='utf-8')
    cat_map = {
        '1. 石材供应商': '石材',
        '2. 金属板供应商': '金属板',
        '3. 陶板供应商': '陶板',
        '4. 玻璃幕墙供应商': '玻璃幕墙',
        '5. GRC / UHPC 供应商': 'GRC/UHPC',
        '6. 木饰面供应商': '木饰面',
        '7. 涂料供应商': '涂料',
        '8. 瓷砖/岩板供应商': '瓷砖/岩板',
        '9. 木地板供应商': '木地板',
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
