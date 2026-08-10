-- ============================================================
-- 价格库 Schema v1.1
-- 路径(运行时):由 seed_prices.py 用 BASE / 'prices.db' 拼接,默认本仓库根
-- 跨平台说明:本 SQL 注释无绝对路径;DB 位置 = scripts/seed_prices.py BASE 变量
-- 设计:流水式价格快照(每个材料+规格+地区+品牌档+时间 = 一行)
-- 关联:material_code 引用 MaterialWeb.materials.code(跨库,文档性 FK)
-- ============================================================

-- ----------------------------------------------------------
-- 1. 地区(中国行政区,标准化)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS regions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT    NOT NULL UNIQUE,     -- 'CN-BJ' / 'CN-SH' / 'CN-GD'
    name            TEXT    NOT NULL,             -- '北京' / '上海' / '广东'
    tier            TEXT    DEFAULT NULL,         -- '一线'/'新一线'/'省会'/'地市'/'县级'
    sort_order      INTEGER DEFAULT 0
);

-- ----------------------------------------------------------
-- 2. 供应商(国产 + 进口,统一)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppliers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,             -- '万峰石材' / 'VMZINC'
    name_en         TEXT    DEFAULT NULL,         -- 'Wanfeng Stone'
    country         TEXT    DEFAULT 'CN',         -- 'CN' / 'IT' / 'DE' / 'ES'
    brand_tier      TEXT    DEFAULT NULL,         -- '经济'/'中端'/'中高端'/'高端'/'旗舰'
    category        TEXT    DEFAULT NULL,         -- 主营品类:石材/金属板/陶板/...
    strength        TEXT    DEFAULT NULL,         -- 1-2 句特点
    china_channel   TEXT    DEFAULT NULL,         -- '北京/上海展厅'
    website         TEXT    DEFAULT NULL,
    contact         TEXT    DEFAULT NULL,
    address         TEXT    DEFAULT NULL,
    source_doc      TEXT    DEFAULT NULL,         -- '材料供应商速查.md'
    verified_at     TEXT    DEFAULT NULL,
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_suppliers_category ON suppliers(category);
CREATE INDEX IF NOT EXISTS idx_suppliers_tier     ON suppliers(brand_tier);

-- ----------------------------------------------------------
-- 3. 价格快照(核心表,流水式)
-- 一行 = 某时刻对"某材料某规格某地区某品牌档"的报价区间
-- 维度:material_code + spec + region_code + brand_tier + craft + time
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS material_spec_prices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    material_code   TEXT    NOT NULL,             -- FK MaterialWeb.materials.code
    material_name   TEXT,                         -- 中文名(冗余便于搜索)
    category        TEXT,                         -- '结构材料'/'幕墙'/'屋面'/'室内'/'门窗'/'装饰'/'设备'/'用量'
    spec            TEXT    DEFAULT NULL,         -- 'GRC 平板 15mm' / '国产花岗岩 25mm 火烧面'
    region_code     TEXT    DEFAULT 'CN-AVG',      -- 缺省全国平均(原 .md 区间都是全国均价)
    brand_tier      TEXT    DEFAULT '中端' CHECK (brand_tier IN ('经济','中端','中高端','高端','旗舰')),  -- 5档 (经济<100 / 中端<500 / 中高端<1500 / 高端<3000 / 旗舰>=3000,元/m²均价),v1.7 R212 价格判档为主,文本"旗舰/进口"向上覆盖
    craft           TEXT    DEFAULT NULL,         -- 干挂/湿贴/光面/火烧/异形/...
    unit            TEXT    NOT NULL,              -- '元/m²' / '元/m³' / '元/t' / '元/块'
    unit_price_min  REAL    NOT NULL,             -- 区间下限
    unit_price_max  REAL    NOT NULL,             -- 区间上限
    unit_price_avg  REAL,                         -- (min+max)/2
    price_type      TEXT    DEFAULT '施工造价',    -- '材料单价' / '施工造价' / '综合造价'
    fluctuation     TEXT    DEFAULT '稳',          -- '稳'/'波动'/'大幅波动'(原 .md ⚡)
    valid_from      TEXT    DEFAULT '2024-01-01',  -- 行情生效时间
    valid_to        TEXT    DEFAULT NULL,          -- 失效时间(NULL = 现行)
    source_doc      TEXT    NOT NULL,             -- '外墙材料-价格区间.md'
    source_section  TEXT,                         -- 文档内 '### 1. 天然石材'
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_msp_material   ON material_spec_prices(material_code);
CREATE INDEX IF NOT EXISTS idx_msp_category   ON material_spec_prices(category);
CREATE INDEX IF NOT EXISTS idx_msp_tier       ON material_spec_prices(brand_tier);
CREATE INDEX IF NOT EXISTS idx_msp_valid      ON material_spec_prices(valid_to);

-- ----------------------------------------------------------
-- 4. 供应商-材料 关联(更具体的报价,带联系人/交期)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS supplier_quotes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id),
    material_code   TEXT    NOT NULL,
    spec            TEXT    DEFAULT NULL,
    unit            TEXT,                          -- '元/m²' / '元/kg'
    unit_price      REAL,                          -- 具体单价(非区间)
    currency        TEXT    DEFAULT 'CNY',
    moq             TEXT    DEFAULT NULL,          -- 最小起订量
    lead_time       TEXT    DEFAULT NULL,          -- 交期
    region_code     TEXT    DEFAULT 'CN-AVG',
    quote_date      TEXT,                          -- 报价日期
    valid_until     TEXT,                          -- 报价有效期
    contact_person  TEXT,
    contact_phone   TEXT,
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_sq_supplier ON supplier_quotes(supplier_id);
CREATE INDEX IF NOT EXISTS idx_sq_material ON supplier_quotes(material_code);

-- ----------------------------------------------------------
-- 5. 造价构成(分部分项)
-- 从 `造价构成比例.md` 数字化
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS cost_breakdowns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    building_type   TEXT    NOT NULL,             -- '高层住宅'/'甲级写字楼'/'商业综合体'/'文化建筑'/'教育'/'五星酒店'/'综合医院'/'工业厂房'
    finish_level    TEXT    DEFAULT NULL,         -- '毛坯'/'精装'/'豪华'
    category        TEXT    NOT NULL,             -- '土建'/'安装'/'装饰'/'室外'/'措施'/'其他费'/'预备费'/'税金'
    pct_min         REAL,
    pct_max         REAL,
    pct_typical     REAL,                         -- 典型值
    contents        TEXT,                         -- 包含内容(从原 .md 搬)
    source_doc      TEXT    DEFAULT '造价构成比例.md',
    source_section  TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_cb_building ON cost_breakdowns(building_type);

-- ----------------------------------------------------------
-- 6. 初始数据:地区
-- ----------------------------------------------------------
INSERT OR IGNORE INTO regions (code, name, tier, sort_order) VALUES
    ('CN-BJ',   '北京',     '一线',   1),
    ('CN-SH',   '上海',     '一线',   2),
    ('CN-GD',   '广东',     '一线',   3),
    ('CN-SZ',   '深圳',     '一线',   4),
    ('CN-CD',   '成都',     '新一线', 5),
    ('CN-HZ',   '杭州',     '新一线', 6),
    ('CN-WH',   '武汉',     '新一线', 7),
    ('CN-NJ',   '南京',     '新一线', 8),
    ('CN-SY',   '沈阳',     '新一线', 9),
    ('CN-XA',   '西安',     '新一线', 10),
    ('CN-CS',   '长沙',     '新一线', 11),
    ('CN-TJ',   '天津',     '新一线', 12),
    ('CN-QD',   '青岛',     '新一线', 13),
    ('CN-AVG',  '全国均价', '平均',   99);
