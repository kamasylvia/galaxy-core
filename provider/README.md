# openbb-provider-amazingdata

DB-backed A-share provider for OpenBB Platform.

- 数据源：本地 TimescaleDB `obb_equity_historical` 视图（galaxy-core migration 29），不直连 AmazingData SDK。
- 首个 fetcher：`EquityHistorical`（日线；A 股/ETF/指数全覆盖）。
- 连接配置：credentials `pg_host/pg_port/pg_db/pg_user/pg_password`，缺省读 `GALAXY_PG_*` 环境变量（默认本地 galaxy）。

```bash
pip install -e packages/openbb-provider-amazingdata
python -c "from openbb import obb; print(obb.equity.price.historical(symbol='600000.SH', provider='amazingdata').results[0])"
```
