# sink 约定

`--sink` 是一个目录：

- `items.jsonl`、`orders.jsonl`、`shipments.jsonl`：每个 id 一行当前镜像。
- 统一字段：`id`、`updated_at`，其余业务字段按资源保留。
- items 必须有 `sku`、`quantity`（整数）、`deleted`（布尔，默认 false）。不要同时保留 `qty`。
- orders：`code`、`status`、`total_cents`。
- shipments：`order_id`、`state`、`tracking`。

`verify --wave 2` 对照 `fixtures/expected/wave2.json` 比较三张表的 id 集合、指定字段和 ITM-0007 的删除态。行顺序无关。
