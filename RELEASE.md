# Release Notes

## v0.0.1 (2026-07-27) — 初始建库

**数据**
- 5 表 schema 落地:`regions` / `suppliers` / `material_spec_prices` / `supplier_quotes` / `cost_breakdowns`
- 初始入库 430 条数据:278 材料规格价 / 77 供应商 / 75 造价构成 / 14 地区 / 6 类别
- 6 大类别覆盖:结构装饰/幕墙外墙/室内/屋面/幕墙/门窗
- 221 个 distinct material_name,跨 6 份内部参考文档

**查询 API**
- `prices_api.py` 4 个查询函数:`stats` / `latest <keyword>` / `breakdown <type>` / `suppliers <category>`
- 历史快照式数据模型:每条价格带 `valid_from / valid_to / source_doc` 三元组
- 跨库引用:MaterialWeb 端通过 `material_code` 软关联

**脚本**
- `init_schema.sql` 建表语句
- `seed_prices.py` 灌库脚本(可重跑,带清空+重灌)
- `prices_api.py` 查询 API

**已知限制**
- 8 条 `reference` 真实工程参考图未配图(本库只存价格,图归 MaterialWeb)
- `supplier_quotes` 表暂空(等真实报价单数据)
- 价格库与 MaterialWeb 跨库查询未集成(下版本 v0.0.5)
