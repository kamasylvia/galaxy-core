# galaxy-web

> Finanalyzer 后端 — fork [finanalyzer/api](https://github.com/finanalyzer/api)(1.5.12),纯 AmazingData 数据层。

## 定位

- 本服务 = **数据 API**:FastAPI(`:8001`,全 `/api/*`),15 个 cn widgets + TradingView UDF + portfolio/dashboard。
- 数据层 = galaxy-core TimescaleDB(`galaxy` 库,K 线/报表/资金流直读);dashboard/持仓走本地 SQLite。
- 上游跟踪 finanalyzer/api,只做适配不重写。

## 快速开始

```bash
cp openbb-app.env.example .env   # 填 APP_API_KEY + GALAXY_PG_*
uv sync
uv run uvicorn openbb_app.main:app --reload --port 8001
```

冒烟:`curl -H "Authorization: Bearer $APP_API_KEY" localhost:8001/api/v1/cn/quote?ticker=600325`
