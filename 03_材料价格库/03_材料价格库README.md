---
aliases:
  - 材料价格库
tags:
  - spacelib
  - 材料价格库
created: 2026-06-27
updated: 2026-08-09
---

# Defense · 材料价格库索引

> 上一层:[[../00_DefenseControl]]
> 定位:**跨材料类型价格区间 + 供应商速查**(索引层)

## 跨 Defense 数据源

**实际数据存放位置:`Defense/06-Material/Mobile/PricesLib/`**

本目录只做**索引和决策路径**,不存原始数据;原始 .md 与 prices.db 全部在父级 `../` 目录。

### 子资源列表(实际物理路径)

| 子资源 | 位置 | 用途 |
|--------|------|------|
| 材料价格总库-原始数据 | `Defense/06-Material/Mobile/PricesLib/材料价格总库-原始数据` | 子资源 1 |
| 材料供应商速查 | `Defense/06-Material/Mobile/PricesLib/材料供应商速查` | 子资源 2 |
| 造价构成比例 | `Defense/06-Material/Mobile/PricesLib/造价构成比例` | 子资源 3 |
| 结构体系-造价对比 | `Defense/06-Material/Mobile/PricesLib/结构体系-造价对比` | 子资源 4 |
| 外墙材料-价格区间 | `Defense/06-Material/Mobile/PricesLib/外墙材料-价格区间` | 子资源 5 |
| 室内材料-价格区间 | `Defense/06-Material/Mobile/PricesLib/室内材料-价格区间` | 子资源 6 |
| 屋面系统-价格区间 | `Defense/06-Material/Mobile/PricesLib/屋面系统-价格区间` | 子资源 7 |
| 屋面系统-供应商速查 | `Defense/06-Material/Mobile/PricesLib/屋面系统-供应商速查` | 子资源 8 |
| 幕墙系统-价格区间 | `Defense/06-Material/Mobile/PricesLib/幕墙系统-价格区间` | 子资源 9 |
| 门窗系统-价格区间 | `Defense/06-Material/Mobile/PricesLib/门窗系统-价格区间` | 子资源 10 |
| 门窗供应商速查 | `Defense/06-Material/Mobile/PricesLib/门窗供应商速查` | 子资源 11 |
| init_schema.sql | `Defense/06-Material/Mobile/PricesLib/init_schema.sql` | 子资源 12 |
| prices.db | `Defense/06-Material/Mobile/PricesLib/prices.db` | 子资源 13 |
| seed_prices.py | `Defense/06-Material/Mobile/PricesLib/scripts/seed_prices.py` | 子资源 14 |


## 检索建议

**用本目录找什么:**
- 跨子目录的对比查询(8 大类材料价格 + 供应商一站式)
- 决策路径推荐(做 X 部位选 Y 材料 + Y 供应商)
- 索引汇总(把分散的资料串成一条线)

**用父级 `../` 找什么:**
- 单个目录的详细内容
- 原始数据和完整资料
- prices.db 入库数据(SQL 查询)

## 维护规则

1. **本目录是索引,不是存储** —— 不在本目录下新建原始数据,跳到父级 `../`
2. **每次父级重大变更后,同步本目录索引** —— 每周回顾一次
3. **跨学科主题优先用本目录** —— 单学科用父级 `../` 单独文件

---

> 变更记录
> - 2026-08-11 · 批 3 同步 价格库Control 修复记录;本目录 14 条子资源路径仍准确,无需调整 · materialwebprices Coder (批 3 02:00 夜间迭代)
> - 2026-08-09 · 整段"## 跨 Defense 数据源"重写;14 条子资源位置从 `Defense/03_建筑材料/...` / `Defense/价格库/...` 改为 `Defense/06-Material/Mobile/PricesLib/...`;补 init_schema/prices.db/seed_prices.py 3 条技术资源 · materialwebprices Coder (批 3 夜间迭代)
> - 2026-06-27 · 创建 SpaceLib/材料价格库 · 03_Architect
