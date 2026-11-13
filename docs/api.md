# 夹具 API

`python -m pageorbit site --wave 1` 或 `--wave 2` 会切换同一套接口的数据视图。`--wave` 也可以在运行中用 `POST /_ctl/wave` 切换（body 为 `{"wave": 2}`），用来模拟增量期间源系统发生的变化。默认 wave 1。

所有业务接口都要求头 `X-Api-Key: fixtures/sources.json` 里的 key。缺 key 返回 401。

## 三种分页

1. `/v1/items?page={n}&per_page=10`  
   经典页码。响应 `{"page": n, "pages": N, "items": [...]}`。wave 1 共 23 条，wave 2 在此基础上有修改、新增和删除。  
   **schema 漂移：** wave 1 的数量字段叫 `qty`；从 wave 2 开始同一字段改名为 `quantity`，不再出现 `qty`。同步结果必须统一写成 `quantity`。  
   **残页：** wave 1 的第 2 页会故意只返回 3 条（少于 per_page），并带 `"truncated": true` 和 `"resume_after": "<最后一条的 id>"`。下一次请求必须用 `?page=2&after=<id>` 才能拿到该页剩余条目；只用 page=2 会再次只给残页。不要因为残页就跳到 page=3，否则会漏数据。

2. `/v1/orders?cursor={c}&limit=7`  
   游标。首次不传 cursor。响应 `{"data":[...], "next_cursor": "..."}`，最后一页 `next_cursor` 为 null。wave 2 会插入一条比现有水位更新的订单，也会修改旧订单的 `status`。

3. `/v1/shipments`  
   分页信息只出现在 `Link` 头，形如 `<http://.../v1/shipments?marker=xxx>; rel="next"`。正文是 `{"shipments":[...]}`。即使有人误传 `?page=`，也必须忽略 page，只跟随 Link。wave 2 会把其中一条 shipment 标记为 `void`。

## 限速

任一业务接口在同一 API key 下，若 0.2 秒内打出第 4 个请求，会返回 429，并带 `Retry-After`（秒，夹具里是 `0` 或小数对应的 `Retry-After: 0` 加头 `X-Retry-After-Ms: 150`）。必须等到该间隔后再重试同一请求，不能把该页当作空结果跳过。

## 增量水位

每条记录有 `updated_at`（ISO-8601，UTC）。checkpoint 要按资源分别记下已成功写入 sink 的最大 `updated_at`，以及分页续跑所需的游标/页码/残页 after。wave 2 再跑时：

- 只应再取 `updated_at` 大于该资源水位的变更（夹具仍会按完整分页吐数据，客户端自己过滤也可以，但删除检测除外）。
- **删除：** `/v1/items` 在 wave 2 不再返回 id=`ITM-0007`。增量跑必须把它从 sink 里删掉或标记 `deleted=true`（见 output.md）。不能只靠水位，因为删除没有新的 updated_at 行。
- 对 orders / shipments，wave 2 没有静默删除，只有更新和新增。

## 幂等

同一 `id` 在 sink 里只保留最新一条。重跑同一 wave 不得复制行。中途被打断后用同一 checkpoint 续跑，不能漏掉残页后半段，也不能把已写入的页再插一遍。
