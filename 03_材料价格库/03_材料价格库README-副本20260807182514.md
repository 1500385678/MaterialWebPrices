---
aliases:
  - 材料价格库
tags:
  - spacelib
  - 材料价格库
created: 2026-06-27
updated: 2026-06-27
---

# SpaceLib · 材料价格库

> 上一层:[[SpaceLib/SpaceLibControl]]
> 定位:**跨材料类型价格区间 + 供应商速查**

## 跨 Defense 数据源

**实际数据存放位置(v2):`Defense/06-Material/Mobile/PricesLib/`** _(现役路径)_

SpaceLib 不存原始数据,只做**索引和决策路径**。

### 子资源列表

| 子资源 | 位置 | 用途 |
|--------|------|------|
| 价格库/材料价格总库-原始数据 | `Defense/价格库/材料价格总库-原始数据` | 子资源 1 |
| 价格库/材料供应商速查 | `Defense/价格库/材料供应商速查` | 子资源 2 |
| 价格库/造价构成比例 | `Defense/价格库/造价构成比例` | 子资源 3 |
| 价格库/结构体系-造价对比 | `Defense/价格库/结构体系-造价对比` | 子资源 4 |
| 价格库/外墙材料-价格区间 | `Defense/价格库/外墙材料-价格区间` | 子资源 5 |
| 价格库/室内材料-价格区间 | `Defense/价格库/室内材料-价格区间` | 子资源 6 |
| 价格库/屋面系统-价格区间 | `Defense/价格库/屋面系统-价格区间` | 子资源 7 |
| 价格库/屋面系统-供应商速查 | `Defense/价格库/屋面系统-供应商速查` | 子资源 8 |
| 价格库/幕墙系统-价格区间 | `Defense/价格库/幕墙系统-价格区间` | 子资源 9 |
| 价格库/门窗系统-价格区间 | `Defense/价格库/门窗系统-价格区间` | 子资源 10 |
| 价格库/门窗供应商速查 | `Defense/价格库/门窗供应商速查` | 子资源 11 |
| archi-material/references/facade-materials-catalog | `Defense/archi-material/references/facade-materials-catalog` | 子资源 12 |
| archi-material/references/interior-materials-catalog | `Defense/archi-material/references/interior-materials-catalog` | 子资源 13 |
| archi-material/references/material-suppliers-guide | `Defense/archi-material/references/material-suppliers-guide` | 子资源 14 |


## 检索建议

**用 SpaceLib 找什么:**
- 跨子目录的对比查询(防火规范 + 防火构造 + 防火材料 一站式)
- 决策路径推荐(做 X 部位选 Y 规范)
- 索引汇总(把分散的资料串成一条线)

**用 Defense 找什么:**
- 单个目录的详细内容
- 原始数据和完整资料

## 维护规则

1. **SpaceLib 是索引,不是存储** —— 不在 SpaceLib 下新建原始数据,跳到 Defense
2. **每次 Defense 重大变更后,同步 SpaceLib 索引** —— 每周回顾一次
3. **跨学科主题优先用 SpaceLib** —— 单学科用 Defense 单独目录

---

> 变更记录
> - 2026-06-27 · 创建 SpaceLib/材料价格库 · 03_Architect
