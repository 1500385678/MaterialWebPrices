# 材料价格库 (MaterialWeb Prices)

建筑材料价格数据库 + 跨库查询 API。配套 MaterialWeb (`1500385678/MaterialWeb`) 的造价模块使用。

## 数据规模

- **278 条** `material_spec_prices` 材料规格价（221 个 distinct material_name）
- **77 条** `suppliers` 供应商
- **75 条** `cost_breakdowns` 造价构成
- **14 条** `regions` 地区
- **6 条** `categories` 类别
- **6 个** `source_doc` 来源文档

## 6 大类别

| 类别 | 典型材料 |
| --- | --- |
| 结构/装饰/设备 | 钢筋、混凝土、砌块、花岗岩 |
| 幕墙/外墙 | 干挂石材、铝板、玻璃幕墙、外墙涂料 |
| 室内 | 地面、墙面、吊顶、卫浴五金 |
| 屋面 | 防水卷材、屋面瓦、排水系统 |
| 幕墙 | 玻璃幕墙、石材幕墙、金属幕墙 |
| 门窗 | 断桥铝、塑钢、实木复合、系统门窗 |

## 跨库引用约定

- **material_code** 自管理（如 `STR_001` / `CURT_002` / `WALL_001`）
- MaterialWeb 端材料表的 `material_code` 字段（v0.0.5 起）反查本库
- 不强制 1:1 覆盖：很多价格库条目无对应 Web 详情
- 缺 `material_code` 的 Web 材料 → 详情页 "价格" tab 显示 "暂无参考价"

## 查询命令

```powershell
cd D:\Mac\Mac\Mac\workteam\05_space\03_architect\Defense\06-Material\Attack\价格库
python -X utf8 prices_api.py stats
python -X utf8 prices_api.py latest 花岗岩
python -X utf8 prices_api.py breakdown 高层住宅
python -X utf8 prices_api.py suppliers 石材
```

## 重灌数据

```powershell
python -X utf8 seed_prices.py
```

## 数据来源

6 份内部参考文档 + 1 份 `报价单_20260530.txt` 报价单。
所有价格条目带 `valid_from / valid_to / source_doc` 三元组，历史可追溯。

## 版本

- v0.0.1 (2026-07-27) — 初始建库,278 + 77 + 75 + 14 + 6 行,5 表查询 API
