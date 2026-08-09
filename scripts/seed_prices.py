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

# v1.6 P0 (R30): 路径一致性 assert — BASE 必须落在 Defense/06-Material/Mobile/PricesLib/,
# 若种子脚本被错误地放在 SpaceLib/03_建筑材料/... 等历史位置,启动即崩,防止"读老路径 + 写新库"双线分离
assert BASE.name == 'PricesLib' and '06-Material' in str(BASE), (
    f'seed_prices.py BASE 路径错位: {BASE}。期望 Defense/06-Material/Mobile/PricesLib/,'
    f'实际 BASE.name={BASE.name!r}。修复方法:把 seed_prices.py 放到 PricesLib/scripts/ 下,'
    f'或更新 __file__ 相对路径。'
)

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
    cur = conn.cursor()
    # v1.6 P0 (R29): DROP + CREATE 而非 IF NOT EXISTS,确保 schema 变更(CHECK 约束 / 索引)
    # 立即生效。代价是重跑要全表重建,但 prices.db 是种子库(< 500 行),可接受
    for tbl in ('material_spec_prices', 'suppliers', 'supplier_quotes', 'cost_breakdowns',
                'regions'):
        cur.execute(f'DROP TABLE IF EXISTS {tbl}')
    conn.commit()
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
                      has_notes_col=True,
                      section_blacklist=('快速查表', '常见问题', '关联知识', '核心要点')):
    """
    状态机解析 | col | col | 表
    name_col / spec_col / unit_col / price_col 都在 0-indexed 数据列
    skip_first_data_row: 跳过首行(通常表头) - 但实际表头是表头本身,首数据行是表头
    section_blacklist: 当前 ##/### 章节名命中任一黑名单词时,所有表行不入库
                       (R28 P1 修复:外墙 33 vs 38 漂移 — ## 快速查表 段 5 行预算档被当价格入库,
                        ## 常见问题/## 关联知识 段也可能含表格行但非价格)

    v1.2 严格 schema 检查:
      - 同表(同一组表头分隔 |---|---| 后到下一个非表行)所有数据行 col_count 必须一致
      - 不一致 raise ValueError,阻止"33 vs 38 漂移"型静默丢行
      - 序号列(1./1.1 等)若在首列,会被自动剥离,剥离后剩余列数才参与 schema check

    v1.3 解析漂移案例(外墙 33 vs 38):
      - 历史问题:v1.0 解析外墙时,数据行 col_count 不一致(如 4 列 vs 3 列),price_col=1
        在 4 列行上指向"材料单价",在 3 列行上却指向"施工造价" → 同一文件内价列语义漂移
      - 修复:v1.2 的 schema check 强制 col_count 一致,v1.3 加更细的 price_col 列语义校验
        - price_col 必须 < table_first_row_count(否则报"price_col 越界")
        - 在 main() 里,外墙文件被解析两次(price_col=1=材料单价, price_col=2=施工造价),
          两次解析都必须通过 schema check 才能入库
      - v1.5 加 section_blacklist:## 快速查表/## 常见问题/## 关联知识/## 核心要点 段
        的表格行直接跳过不入库,从源头杜绝"段外行进价"漂移
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
        # v1.5: 黑名单章节内的所有行直接跳过(不更新 in_table/table_first_row_count,
        #       保持基线;但避免数据行污染 schema check)
        if any(bad in current_section for bad in section_blacklist):
            if not s.startswith('|'):
                in_table = False
                table_first_row_count = None
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
            # v1.3 新增:price_col 越界检查
            if price_col >= table_first_row_count:
                raise ValueError(
                    f'parse_simple_table 严格 schema 检查失败: '
                    f'{source_doc} 第 {table_index} 个表({current_section}) '
                    f'price_col={price_col} >= 表首行 col_count={table_first_row_count},'
                    f'价格列越界,会静默丢价。'
                )
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

    v1.3 修复(R27 P0):
      - h3 直接 fallback: 遍历到 hashes==3 (### 1.x 材料) 时,即使 h4 没"经济属性"标题,
        也对 h3_content(剥 h4 后剩余部分)跑 _extract_econ,覆盖"h3 直接跟 bullet 价格"的情况
      - 横表 fallback: 1.4 环氧地坪 / PVC地板 / 橡胶地板 段把价格放在 markdown 表格行里
        (| 材料单价 | 30~80 | 50~200 | 150~400 |),bullet regex 抓不到,新增 _extract_econ_table 处理
      - h3_content 跑前先把 h4 子段剥掉,避免与下面 h4 循环重复入库
    """
    rows = []
    # 独立 pattern: h2/h3/h4 各自独立,避免互相吞 content
    h2_pat = re.compile(r'^##\s+([^\n]+)\n(.*?)(?=^##\s+|\Z)', re.MULTILINE | re.DOTALL)
    h3_pat = re.compile(r'^###\s+([^\n]+)\n(.*?)(?=^###\s+|\Z)', re.MULTILINE | re.DOTALL)
    h4_pat = re.compile(r'^####\s+([^\n]+)\n(.*?)(?=^#{2,4}\s+|\Z)', re.MULTILINE | re.DOTALL)

    def find_h2_before(h3_start):
        last = ''
        # 顺序遍历,找 start <= h3_start 的最后一个 h2
        for m in h2_pat.finditer(text):
            if m.start() > h3_start:
                break
            last = m.group(1).strip()
        return last

    for m3 in h3_pat.finditer(text):
        h3_title = m3.group(1).strip()
        h3_content = m3.group(2)
        h2_title = find_h2_before(m3.start())

        # 段名: ### 🔸 经济属性 用 h2 名;其他用 h2/h3 拼接(去掉 🔸 装饰)
        full_name = (h2_title if '经济属性' in h3_title
                     else f'{h2_title} / {h3_title}'.replace('🔸 ', '').strip())

        # 1. h3 直接 fallback(R27 改法 1):
        #    把 h4 子段内容先剥掉,避免与下面 h4 循环重复入库;
        #    对剩下 h3_content(若有 bullet 形式价格)跑一次 _extract_econ
        h3_content_no_h4 = h4_pat.sub('', h3_content)
        _extract_econ(rows, h3_content_no_h4, full_name, default_unit)

        # 2. h4 子段循环(覆盖 2.1/2.2/2.3/2.4/3.1-3.4 这 8 段:价格列在 #### 🔸 性能参数 下)
        for m4 in h4_pat.finditer(h3_content):
            h4_content = m4.group(2)
            _extract_econ(rows, h4_content, full_name, default_unit)

        # 3. 横表 fallback(R27 改法延伸):
        #    1.4 段价格在 markdown 表格行里,扫 h3_content 一次即可(包含 h4 内的表)
        _extract_econ_table(rows, h3_content, full_name, default_unit)
    return rows


def _extract_econ(rows, content, full_name, default_unit):
    """从经济属性 content 里抽 3 类价格(每档一行;P0 修复:findall 抓完所有 N 行;P1:多档 / 拆行)

    v1.6 P1 修复 (R31):
    - 幕墙 8 大类每类有 2-4 档变体(国产/进口/规格/厚度),原 parser 只抓第一个价格区间,后面
      全部被吞(如 石材 "150~600 国产" / "300~2000 进口" 只入第 1 档)。
    - 改法:每行(每类价格段)按 / 或 ; 拆成 N 段,每段生成一行入库。
      - 段内若有 括号变体 (e.g. "（国产花岗岩）"),拼到 material_name 后缀(避免重名)
      - 段内若无 括号 (e.g. "铝单板 180~350 元/m²"),用 #1/#2/#3/#4 区分
    """
    # P0 修复 1: regex 容忍冒号后空白([：:]+\s*)
    # P0 修复 2: re.findall 抓完所有 N 行
    # P1 修复 3: 单行内 / 或 ; 拆多档,每档一行
    for price_type, base_pat in [
        ('材料单价', r'\*\*材料单价\*\*[：:]+\s*([^\n]+)'),
        ('施工造价', r'\*\*施工造价\*\*[：:]+\s*([^\n]+)'),
        ('综合造价', r'\*\*综合造价\*\*[：:]+\s*([^\n]+)'),
    ]:
        matches = re.findall(base_pat, content)
        for idx, raw in enumerate(matches):
            # P1: 按 / 或 ; 拆多档(国标全角半角都支持)
            # 关键:必须先保护两类非 split-boundary 的 / :
            #   1) 单位中的 /(如 元/m²) - 元/<非数字>
            #   2) 变体括号内的 /(如 (进口花岗岩/大理石)) - （含/的变体）
            # 然后用普通 split,最后还原
            # 用 lambda 避免 re.sub 解析 \x00 报"bad escape"
            raw_protected = raw.strip()
            # 1) 保护单位:元/<unit> → 元<placeholder><unit> (unit 不含数字/分号/空格)
            raw_protected = re.sub(r'元/([^\s\d;]+)', lambda m: '元\x00' + m.group(1), raw_protected)
            # 2) 保护变体括号内的 /:（...<slash>...）→ （...<placeholder>...）
            # 用平衡匹配:从 ( 开始,到匹配的 ) 结束(简化版:非贪婪 + 无嵌套)
            def protect_paren(m):
                inner = m.group(1)
                return '（' + inner.replace('/', '\x00') + '）'
            raw_protected = re.sub(r'（([^（）]*)）', protect_paren, raw_protected)
            tiers = re.split(r'\s*/\s*|\s*;\s*', raw_protected)
            tiers = [t.replace('\x00', '/').strip() for t in tiers]
            for t_idx, tier in enumerate(tiers):
                tier = tier.strip()
                if not tier:
                    continue
                # 提取括号变体: e.g. "150~600 元/m²（国产花岗岩）" → "国产花岗岩"
                var_m = re.search(r'[\(（]\s*([^\)）]+?)\s*[\)）]', tier)
                var = var_m.group(1) if var_m else ''
                # 去括号后的纯价格文本 (e.g. "150~600 元/m²")
                price_text = re.sub(r'[\(（][^\)）]*[\)）]', '', tier).strip()
                pmin, pmax = parse_price_range(price_text)
                if pmin is None:
                    continue
                # 多档时:有变体拼变体,无变体用 #i 区分
                if len(tiers) > 1:
                    if var:
                        label = f'{full_name}（{var}）'
                    else:
                        label = f'{full_name} #{t_idx+1}'
                else:
                    label = full_name
                unit = parse_unit(price_text) or default_unit
                rows.append({
                    'material_name': label, 'spec': label,
                    'unit': unit, 'pmin': pmin, 'pmax': pmax,
                    'price_type': price_type, 'section': full_name,
                })


def _extract_econ_table(rows, content, full_name, default_unit):
    """
    段内横表 fallback(R27 v1.3 修复):
    1.4 环氧地坪 / PVC地板 / 橡胶地板 段把价格放在 markdown 表格行里:
        | 对比项   | 环氧地坪   | PVC地板     | 橡胶地板     |
        | 材料单价 | 30~80 元/m² | 50~200 元/m² | 150~400 元/m² |
        | 施工造价 | 50~150 元/m² | 60~180 元/m² | 200~400 元/m² |
    bullet regex 抓不到,扫横表行:首列含"材料单价/施工造价/综合造价"且 >= 3 列的行,
    后面每列(每个材料)各生成一行入库(material_name = full_name / 列名)。
    """
    price_keys = ('材料单价', '施工造价', '综合造价')
    header_keys = ('对比项', '类别', '材料', '规格', '项目', '项', '类型', '等级', '名称')
    lines = content.split('\n')
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith('|'): continue
        cols = [c.strip() for c in s.split('|') if c.strip() != '']
        if len(cols) < 3: continue
        if cols[0] not in price_keys: continue
        # 找表头(向上搜索,跳过 |---|---| 分隔行,直到首个列数一致的 | xxx | ... | 行;
        # 1.4 横表里表头可能在数据行 5-10 行之上,需要 1-15 行搜索范围)
        col_names = None
        for j in range(i-1, max(0, i-15), -1):
            head = lines[j].strip()
            if not head.startswith('|'): continue
            if all(re.match(r'^[\-:\s]+$', c) for c in head.split('|') if c.strip() != ''):
                continue  # 跳过表头分隔
            hcols = [c.strip() for c in head.split('|') if c.strip() != '']
            if len(hcols) == len(cols) and hcols[0] in header_keys:
                col_names = hcols[1:]
                break
        if not col_names:
            col_names = [f'档{idx+1}' for idx in range(len(cols) - 1)]
        price_type = cols[0]
        for idx, raw in enumerate(cols[1:]):
            col_name = col_names[idx] if idx < len(col_names) else f'档{idx+1}'
            pmin, pmax = parse_price_range(raw)
            if pmin is None: continue
            material_name = f'{full_name} / {col_name}'
            rows.append({
                'material_name': material_name, 'spec': material_name,
                'unit': parse_unit(raw) or default_unit,
                'pmin': pmin, 'pmax': pmax,
                'price_type': price_type, 'section': full_name,
            })


# ============================================================
# 供应商表
# ============================================================
def parse_supplier_table(text, current_category):
    """状态机:## 是大类,### 是子类,| col | col | 是表

    v1.5 P0 修复 (R98):
    - chunk 切分后 ## 标题是 chunk 边界(不在 chunk 内容里),
      chunk 内的表头(## 通用采购渠道 / ## 采购周期参考)丢失 → section_name 永远 ""
    - 修法 A: section_name 用 current_category 兜底初始化;同时
      过滤键加 current_category 双键,即使 chunk 内没 ### 头也能识别
      "采购周期参考" / "通用采购渠道" 段。
    """
    rows = []
    # P0 修复 1: section_name 用 current_category 兜底,处理"## 通用采购渠道"
    # / "## 采购周期参考" 这类 ## 标题作为 chunk 边界的场景
    section_name = current_category or ''
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
        # P0 修复 2: 双键过滤 — section_name 兜底 + current_category 直接命中
        # 涵盖:1) ## 通用采购渠道/## 采购周期参考 作为 chunk 边界(无 ### 头)
        #      2) ### 采购建议 在 chunk 内(原 filter 路径,保留兼容)
        _BLACKLIST = ('采购建议', '采购周期参考', '通用采购渠道')
        if section_name in _BLACKLIST or current_category in _BLACKLIST:
            continue
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
# brand_tier 推断 (P0 R29)
# ============================================================
def infer_brand_tier(material_name, spec='', notes='', section=''):
    """根据 material_name / spec / section / notes 推断品牌档位。

    v1.6 P0 修复 (R29):
    - 历史 295/295 行全为 '中端'(schema DEFAULT 兜底),前端"经济/中端/中高端/高端/旗舰" 5 档
      实际只有 1 档可用,经济/旗舰档查询 404。
    - 推断规则(优先级 高→低):
      1. 旗舰/5x 💰  → 旗舰
      2. (进口+高端) 或 4x 💰  → 高端
      3. 进口 或 中高端 或 3x 💰  → 中高端
      4. 高端字样  → 高端
      5. 中端字样 或 1-2x 💰  → 中端
      6. 经济字样  → 经济
      7. 默认      → 中端
    """
    text = f'{material_name or ""} {spec or ""} {notes or ""} {section or ""}'
    cnt_money = text.count('💰')
    if '旗舰' in text or cnt_money >= 5:
        return '旗舰'
    if '进口' in text and '高端' in text:
        return '高端'
    if cnt_money >= 4:
        return '高端'
    if '进口' in text:
        return '中高端'
    if '中高端' in text or cnt_money >= 3:
        return '中高端'
    if '高端' in text:
        return '高端'
    if '中端' in text:
        return '中端'
    if '经济' in text:
        return '经济'
    if cnt_money >= 1:
        return '中端'
    return '中端'


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
        # v1.6 P0 (R29): brand_tier 不再依赖 schema DEFAULT 兜底,先推断
        brand_tier = infer_brand_tier(
            r.get('material_name', ''),
            r.get('spec', ''),
            r.get('notes', ''),
            r.get('section', ''),
        )
        cur.execute('''
            INSERT INTO material_spec_prices
            (material_code, material_name, category, spec, unit,
             unit_price_min, unit_price_max, unit_price_avg, price_type,
             brand_tier, fluctuation, source_doc, source_section, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [code, r['material_name'], category, r.get('spec', r['material_name']),
              r.get('unit', '元/m²'), pmin, pmax, avg, price_type,
              brand_tier, r.get('fluctuation', '稳'), source_doc, r.get('section', ''),
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
    # v1.5 P1 解析漂移检测(R28):外墙 材料单价 与 施工造价 行数必须一致(33==33),
    # 漂移(33 vs 38)典型是快速查表段 5 行被施工造价分支误抓 → section_blacklist 之后
    # 应自动对齐;若还漂移,raise 阻止入库
    if n1 != n2:
        raise ValueError(
            f'外墙材料-价格区间 解析漂移(R28 P1):材料单价 {n1} 行 vs 施工造价 {n2} 行,'
            f'两者必须一致(典型 33==33)。差异来源:section_blacklist 未生效,'
            f'或价格列漂移到其他段。'
        )
    summary['外墙材料-价格区间'] = n1 + n2
    print(f'[seed] 外墙: {n1} (材料单价) + {n2} (施工造价) = {n1+n2} 行 [drift-check OK]')

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
    # v1.6 P1 (R31): 幕墙 8 大类(石材/金属板/陶板/玻璃/清水混凝土/GRC/UHPC/木饰面/涂料)每类
    # 至少 2 档(材料单价 + 施工造价),多档后预期 >= 24 行(8 × 3)。若仍 = 16 行(每类 2 行),
    # 说明多档 / 拆行未生效,log.warn + raise 阻止入库。
    unique_mains = len({r['material_name'].split('（')[0].split(' #')[0] for r in rows})
    if n < 24 or unique_mains < 8:
        import warnings
        warnings.warn(
            f'幕墙 8 大类 解析异常 (R31 P1):总 {n} 行,唯一大类 {unique_mains} 个。'
            f'预期 >= 24 行 / 8 大类。可能多档 / 拆行未生效或 8 大类标题被误吞。'
        )
        raise ValueError(
            f'幕墙解析漂移 (R31 P1):总 {n} 行 < 24 预期 / 大类 {unique_mains} < 8 预期。'
            f'请检查 _extract_econ 多档 / 拆行 与 h3 标题正则。'
        )
    summary['幕墙系统-价格区间'] = n
    print(f'[seed] 幕墙(段式·多档拆行): {n} 行 (8 大类 × {n//8} 档均值) [tier-check OK]')

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
