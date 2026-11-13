# pageorbit

把三套分页风格不同的本地 HTTP API 增量同步到同一份湖表。服务由本仓库夹具提供，不访问公网。

```
python -m pageorbit site --port 8763
python -m pageorbit sync --base http://127.0.0.1:8763 --source fixtures/sources.json --sink <sink> --checkpoint <ckpt.json>
python -m pageorbit verify --sink <sink> --expect fixtures/expected/wave2.json --wave 2
```
