# AGENTS.md

> **本文档是项目约定主源(架构/适配/部署约定)。**

## Project Overview

galaxy-web 是 Finanalyzer 后端,fork 自 [finanalyzer/api](https://github.com/finanalyzer/api)(1.5.12)。
纯 AmazingData 数据层(本地 galaxy-core TimescaleDB),经 `/api/v1` 供 Finanalyzer 前端消费。

## 架构红线

- **数据源唯一**:AmazingData(本地 galaxy 库)。akshare/tushare/yfinance 已废除;HK 路由已下线(无 galaxy 表)。
- **K 线直读 PG**:经 `core/amazingdata_source.py`(GALAXY_PG_*);dashboard/持仓走 SQLite(`data/equity.db`)。
- 上游只做适配不重写;上游更新 cherry-pick,冲突以上游为准。
- symbol 格式:全库带后缀(`600000.SH`);normalize 返回(裸码,带后缀,市场)。

## 布局(src-layout)

```
src/openbb_app/
├── main.py            # 入口(:8001, /api/* 挂载)
├── core/              # amazingdata_source/galaxy_db/financials/utils/database/registry/...
├── routes/            # equity_cn(15 widgets)/tradingview/charts/portfolio/dashboard/proxy/agents/code/
└── templates/         # portfolio.json + cn.json
```

- 数据侧计划与进度见 galaxy-core 主仓 AGENTS（公开仓唯一事实源）。

## 已知坑

- galaxy 报表 `symbol` 带后缀(`600325.SH`),`statement_type='1'`=合并口径;annual 按 EXTRACT(MONTH)=12 过滤(非 LIKE)。
- `stock_basic.security_type` 存大类码(`EXTRA_STOCK_A`),kline 存市场码——Profile 映射注意口径。
- 上游原样引入的 agents/code 目录 ruff 有 10+ 存量问题,不动(跟上游走)。
