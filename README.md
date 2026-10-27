# galaxy-core

> A 股数据底座:从银河证券 **AmazingData** 采集行情,持久化至 **PostgreSQL/TimescaleDB**,
> 经 **provider**(OpenBB 标准)与 **api**(Finanalyzer 前端)两个消费面对外服务。

## 🏗️ 三顶层架构

```
            ┌─────────────── galaxy-core ───────────────┐
            │                                           │
AmazingData ──→ data/ ──→ PostgreSQL「galaxy」库 ←── provider/
 (SDK 采集)     (写链)      (TimescaleDB 存储)      (读链枢纽:OpenBB 标准)
                                                    │
                              ┌─────────────────────┼──────────────┐
                              ↓                     ↓              ↓
                          api/(HTTP :8001)    OpenBB SDK/AI     galaxy-tui
                       (Finanalyzer 前端后端)  (研究/Agent)     (终端,另仓)
```

**一个角色一层**:

| 顶层 | 角色 | 包名 | 说明 |
|---|---|---|---|
| `data/` | 写链:采集+存储 | `galaxy_core` | scheduler 定时链 + 盘中实时订阅 + CLI;DDD 分层(domain/services/adapters/database) |
| `provider/` | 读链枢纽:唯一数据转换层 | `openbb-provider-amazingdata` | galaxy 库 → OpenBB 标准 schema;**目标 = 单出口**(复权/字段/口径只此一份),api 与仓外消费者(galaxy-tui/OpenBB/AI)终态都经此取数 |
| `api/` | 消费者①:HTTP 服务 | `openbb-app` | fork [finanalyzer/api](https://github.com/finanalyzer/api)(MIT,上游跟踪、只做适配不重写);FastAPI `:8001`,15 个 cn widgets + TradingView UDF,服务 [galaxy-web](../galaxy-web)(Finanalyzer 前端 fork) |

> 数据出口策略:**双出口为过渡常态**(api 暂 SQL 直读库),单出口为目标路线——
> provider 覆盖面做全后,api 数据源层逐步切 OpenBB Platform,全程保持 finanalyzer/api 上游跟踪。

## 📁 目录结构

```
galaxy-core/
├── data/                    # 采集+存储域(包 galaxy_core,src-layout)
│   └── src/galaxy_core/
│       ├── domain/          # 纯业务逻辑(值对象/端口/完整性)
│       ├── services/        # 应用服务层
│       ├── di/              # 依赖注入
│       ├── amazing_data/    # SDK client + provider adapters
│       ├── application/     # CLI + scheduler(含 realtime 订阅子进程)
│       ├── database/        # 连接/模型/存储适配/TimescaleDB
│       └── shared_kernel/   # 配置/工具/异常
├── provider/                # OpenBB provider(包 openbb-provider-amazingdata)
├── api/                     # finanalyzer/api fork(包 openbb-app,独立 py3.13 venv)
├── tests/                   # 测试(data 域为主;api/provider 自带 tests)
├── config/                  # settings.toml(+ dev)
├── alembic/                 # 迁移
├── scripts/                 # 运维脚本(realtime_sub.py / backfill 等)
├── wheels/                  # 银河私有 SDK(不入库,需自备)
└── docs/
```

## 🌌 galaxy-quant workspace 全景

| 仓 | 角色 |
|---|---|
| **galaxy-core**(本仓) | 数据底座:data + provider + api |
| galaxy-web | 前端:fork finanalyzer/app(OpenBB Workspace) |
| galaxy-tui | 终端:fork gloomberb,galaxy provider 插件(直连本库) |
| galaxy-backtest | 回测(独立) |

## ⚙️ 快速开始

### 前置要求

- Python 3.14(data/provider)、3.13(api 自带 venv)、[uv](https://docs.astral.sh/uv/)
- PostgreSQL 15+ 与 TimescaleDB 2.x
- AmazingData SDK wheel(向银河证券申请,放入 `wheels/`)

### data 域(采集)

```bash
uv venv && source .venv/bin/activate
uv pip install wheels/*.whl          # AmazingData + tgw 私有 SDK(不入库,需向银河申请)
uv sync                              # 本包(editable)+ 依赖
cp .env.example .env
```

凭证管理:业务凭证(`GALAXY_*`/`DB_*`)以 [Infisical](https://infisical.com) 为准,
`get_env()` 按 `Infisical → .env → 默认值` 优先级读取。`.env` 只需填 MI 启动三项
(`INFISICAL_CLIENT_ID/SECRET/PROJECT_ID`),业务凭证留空自动拉取;无 Infisical
的公开部署环境才直填。**`.env` 不入 Git。**

```bash
galaxy-core init-db                  # 建表 + hypertable(危险:--recreate 会清库)
galaxy-core kline SH_A --interval day --start 20240101 --end 20241231
python -m galaxy_core.application.scheduler   # 自动同步(systemd 部署见 docs/galaxy-core.service)
```

### api 域(Finanalyzer 前端后端)

```bash
cd api && uv sync
cp openbb-app.env.example .env       # 填 APP_API_KEY + GALAXY_PG_*
uv run uvicorn openbb_app.main:app --port 8001
curl -H "Authorization: Bearer $APP_API_KEY" 'localhost:8001/api/v1/cn/quote?ticker=600325'
```

### provider 域(OpenBB)

```bash
uv pip install -e ".[openbb]"        # 根 extra,装 openbb-provider-amazingdata
python -c "from openbb import obb; print(obb.equity.price.historical('600000.SH', provider='amazingdata').to_df().tail())"
```

## 🔁 同步节奏(生产)

- **00:10** 全量链(非 K 线 → 日线/长周期 → 分钟定稿覆盖 → 残留追扫 → retention)
- **14:00-15:10** realtime_sub 订阅窗口(ETF,min1/min5;universe/周期/窗口全在 `config/settings.toml` 可配)
- **11:50** 会话刷新 timer(TGW 会话最长 24h)
- 触发时刻均按北京时间解释;详见 AGENTS.md

## 📜 许可证

MIT © 2026 Laniakea Kamasylvia
