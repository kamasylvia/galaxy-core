# galaxy-core

> 📥 从银河证券 **AmazingData** 接口拉取行情数据,持久化至 **PostgreSQL/TimescaleDB**,
> 经 **`services/http`** 对外提供标准数据服务,前端见 galaxy-web/Finanalyzer。
>
> **三层架构**:AmazingData SDK(采集,scheduler)→ PostgreSQL galaxy 库(存储)→
> `services/http`(数据 API,供 Finanalyzer SPA 消费)。
> `services/http` fork 自 [finanalyzer/api](https://github.com/finanalyzer/api)
> (MIT,仅做 AmazingData 数据源适配,不含上游 akshare/tushare 链)。
> `packages/openbb-provider-amazingdata` 为遗留 OpenBB provider(前端已不依赖)。

---

## 📁 目录结构

```
galaxy-core/                     # 项目根目录
├── pyproject.toml                    # 项目元数据 & 依赖声明
├── README.md                         # 项目文档
├── AGENTS.md                         # 约定主源(架构/DI/命名/命令/测试)
├── .gitignore                        # Git 忽略配置
├── .python-version                   # Python 版本 (3.14)
├── .env                              # 环境变量文件
├── .env.example                      # 环境变量模板
├── config/
│   └── settings.toml                 # 应用配置（TOML 格式）
├── docs/
│   └── AmazingData/                  # AmazingData API 文档
├── wheels/                           # 私有 .whl 文件(官方 SDK,不入库)
├── scripts/                          # 运营工具脚本(backfill_industry_daily_v2.py 等)
├── packages/
│   └── openbb-provider-amazingdata/  # 遗留 OpenBB provider 子包(前端已不依赖)
├── services/
│   └── http/                         # Finanalyzer API fork(FastAPI :8001,/api/v1;独立 py3.13 src-layout)
├── src/
│   └── galaxy_core/               # 主包
│       ├── __init__.py               # 包初始化 & 核心导出
│       ├── __main__.py               # 包入口: python -m galaxy_core
│       │
│       ├── domain/                   # 纯业务逻辑层（无外部依赖）
│       │   ├── value_objects.py      # Interval, SecurityType, KlineBar 等值对象
│       │   ├── completeness/         # 完整性检查纯函数
│       │   ├── date_range/           # 日期范围解析和合并
│       │   ├── interval/             # 周期边界计算
│       │   ├── ports/                # Protocol-based 端口接口（6 个端口）
│       │   └── symbol/               # 标的验证和类型推断
│       │
│       ├── services/                 # 应用服务层（通过端口接口注入依赖）
│       │   ├── kline_data_service.py
│       │   ├── calendar_data_service.py
│       │   └── reference_data_service.py
│       │
│       ├── di/                       # 依赖注入容器
│       │   └── container.py          # injector AppModule + create_injector()
│       │
│       ├── amazing_data/             # AmazingData API 相关模块
│       │   └── api/                  # API 封装
│       │       ├── client.py         # AmazingData 客户端连接
│       │       ├── lazy_client.py    # 延迟加载客户端
│       │       └── adapters/         # Provider 适配器（SDK → async）
│       │
│       ├── application/              # 应用层
│       │   ├── cli/                  # 命令行工具
│       │   │   └── commands.py       # CLI 命令实现
│       │   ├── scheduler/            # 自动同步调度器
│       │   └── grpc/                 # gRPC 服务接口
│       │       └── server.py         # ConnectRPC 服务端入口
│       │
│       ├── database/                 # 数据库层
│       │   ├── core/                 # 连接管理
│       │   │   ├── async_connection.py # 异步 SQLAlchemy 会话管理（单例）
│       │   │   ├── connection.py     # DatabaseManager（同步，遗留）
│       │   │   └── timescale.py      # TimescaleDB hypertable 设置
│       │   ├── models/               # SQLAlchemy ORM 模型
│       │   └── services/             # 数据访问层
│       │       ├── kline.py          # K线 CRUD 操作
│       │       ├── missing_data_tracker.py # 缺失数据跟踪与同步
│       │       ├── empty_query_cache.py # 空查询缓存（独立于 empty_query.py）
│       │       ├── completeness_check_log_manager.py # 完整性检查日志
│       │       ├── kline_completeness_checker.py # 缺失数据检测
│       │       ├── trading_calendar.py
│       │       ├── empty_query.py    # 空查询缓存
│       │       └── adapters/         # Store 适配器（DB → async）
│       │
│       └── shared_kernel/            # 共享核心模块
│           ├── enums/                # 兼容性重导出
│           ├── exceptions/           # 异常层次结构
│           └── utils/                # 工具函数
│               ├── config_loader/    # TOML + 环境变量配置
│               └── ...
└── tests/                            # 测试
    ├── unit/                         # 单元测试
    │   ├── kline/                    # K线单元测试
    │   ├── scheduler/                # 调度器单元测试
    │   ├── amazing_data/             # AmazingData 客户端单元测试
    │   ├── core/                     # 核心工具测试
    │   └── shared_kernel/            # 共享核心测试
    └── integration/                  # 集成测试
        └── kline/                    # K线集成测试
```

> 💡 **设计理念**: `src/` 下采用扁平结构，主入口通过 `python -m galaxy_core` 调用 `__main__.py`。

---

## ⚙️ 快速开始

### 前置要求

- Python >= 3.13, < 3.14
- [uv](https://docs.astral.sh/uv/)（推荐 v0.1+）
- PostgreSQL >= 15（本地或远程）
- 银河证券 AmazingData API 账号

### 1. 克隆并进入项目

```bash
git clone git@ssh.dev.azure.com:v3/kamasylvia/Galaxy/galaxy-core
cd galaxy-core
```

### 2. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境（默认 .venv）
uv venv

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows (PowerShell)

# 安装本项目（可编辑模式）及依赖
# wheels/ 为银河私有 SDK(AmazingData/tgw,不入库):需向银河申请后放入 wheels/ 再执行第一行
uv pip install wheels/*.whl
uv pip install -e ".[dev,format]"

### 3. 配置环境变量

复制环境变量模板并填入实际值：

```bash
cp .env.example .env
```

#### 凭证管理（Infisical 优先）

业务凭证（`GALAXY_*` / `DB_*`）**以 [Infisical](https://infisical.com) 为准**，
`get_env()` 按 `Infisical → .env → 默认值` 优先级读取
（`src/galaxy_core/shared_kernel/utils/infisical_config.py`）。
`.env` 只需填 MI 启动三项（`INFISICAL_CLIENT_ID/SECRET/PROJECT_ID`），
业务凭证留空即自动从 Infisical `dev` 环境拉取；无 Infisical 的环境
（公开部署/离线）才需在本文件直填业务凭证。

编辑 `.env` 文件（**不要提交到 Git**）：

```env
# 项目根目录
PROJECT_ROOT_PATH=/path/to/your/project/root

# AmazingData API 配置（必需）
GALAXY_USERNAME=your_username
GALAXY_PASSWORD=your_password
GALAXY_HOST=galaxy_server_ip
GALAXY_PORT=galaxy_server_port

# PostgreSQL 数据库配置（必需）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=quant_db
DB_USER=quant_user
DB_PASSWORD=your_password

# 可选配置
# GALAXY_CACHE_PATH=/path/to/local/cache
# LOG_FILE_PATH=./data/logs/app.log
# DEBUG=true
# DB_ECHO=true
```

### 4. 初始化数据库表

```bash
# 初始化数据库表（运行 Alembic 迁移 + 创建 hypertable）
galaxy-core init-db

# 重建所有表（危险：会删除现有数据）
galaxy-core init-db --recreate
```

### 5. 拉取 K 线数据

使用 CLI 命令：

```bash
# 拉取单只股票 K 线数据
galaxy-core kline 600000.SH --interval day --start 20230101 --end 20231231

# 按证券类型批量拉取
galaxy-core kline SH_A --interval day --start 20230101 --end 20231231

# 拉取交易日历
galaxy-core calendar --year 2024
```

### 6. 启动自动同步调度器

```bash
# 生产环境（白天零 SDK 调用:9:00-15:30 实时订阅独占 TGW;
# 0:10 全量:非K线+日线长周期+分钟定稿覆盖;时间全读 config/settings.toml [scheduler]）
galaxy-core scheduler

# 开发环境（30 分钟周期性同步）
GALAXY_CONFIG_ENV=dev galaxy-core scheduler
```

使用 `uv run`：

```bash
uv run galaxy-core scheduler
GALAXY_CONFIG_ENV=dev uv run galaxy-core scheduler
```

#### SSH 远程不断链启动

SSH 连接断开后进程会收到 `SIGHUP` 信号而终止，使用 `nohup` 保持调度器后台运行：

```bash
nohup uv run galaxy-core scheduler > /dev/null 2>&1 &
echo $! > .scheduler.pid
```

日志由 `settings.toml` 中 `logging.log_file_pattern` 配置的 `FileHandler` 独立写入 `logs/{date}/{time}.log`，无需额外重定向。

停止：

```bash
kill $(cat .scheduler.pid)
```

#### 自动清理

每次同步周期结束后，调度器自动执行清理：

- **sync_state 表**：删除 `updated_at` 超过保留天数的旧记录
- **文件日志**：删除 `logs/YYYYMMDD/` 下超过保留天数的旧目录

配置项 `cleanup_retention_days` 控制保留天数（`config/settings.toml`）：

```toml
[scheduler]
cleanup_retention_days = 30  # 生产环境 30 天
cleanup_retention_days = 7   # 开发环境 7 天
```

触发时机：K-line 同步链（DAY → WEEK → MONTH → SEASON → YEAR → refdata → financial）全部完成后执行(分钟线已移出主链,走 0:10 独立 cover + retention)。

---

## 🔧 CLI 命令参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `galaxy-core` | 显示帮助信息 | `galaxy-core` |
| `galaxy-core init-db` | 初始化数据库表 | `galaxy-core init-db` |
| `galaxy-core kline` | 拉取 K 线数据 | `galaxy-core kline 600000.SH --interval day --start 20230101` |
| `galaxy-core calendar` | 拉取交易日历 | `galaxy-core calendar --year 2024` |
| `galaxy-core scheduler` | 启动自动同步调度器 | `galaxy-core scheduler` |

---

## ⚙️ 配置文件说明

项目使用 `config/settings.toml` 作为配置文件，结合环境变量实现灵活配置：

```toml
[amazing_data]
host = "101.230.159.234"
port = 8600
timeout = 30

[database]
pool_size = 10
max_overflow = 20
pool_timeout = 30

[sync]
default_start_year = 2013
batch_size = 1000
adjust_for_split = true

[logging]
level = "INFO"
max_size = "100MB"
backup_count = 5
```

> 敏感信息（密码、API 密钥）通过环境变量传入，详见 `.env.example`。

---

## 🧪 开发与测试

### 安装开发依赖

```bash
uv pip install -e ".[dev]"
```

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/
```

### 代码格式化与检查

```bash
ruff check .      # Lint 检查
ruff format .     # 代码格式化
mypy src/         # 类型检查
```

---

## 🔒 安全提示

- **`.env` 和 `wheels/` 中的私有文件请勿提交到版本控制**，已在 `.gitignore` 中排除。
- 业务凭证（`GALAXY_*`/`DB_*`）以 **Infisical** 为准，`get_env()` 按 `Infisical → .env → 默认值` 读取；`.env` 仅填 MI 启动三项。
- 银河证券 API 凭据**禁止硬编码**到代码中。

---

| 依赖 | 版本 | 用途 |
|------|------|------|
| `sqlalchemy` | >=2.0.0 | ORM 与数据库抽象 |
| `asyncpg` | >=0.29.0 | PostgreSQL 异步驱动 |
| `psycopg2-binary` | >=2.9.5 | PostgreSQL 同步驱动 |
| `alembic` | >=1.13.1 | 数据库迁移 |
| `python-dotenv` | >=1.0.0 | 加载 `.env` 配置 |
| `toml` | >=0.10.2 | 读取 TOML 配置文件 |
| `pandas` | >=2.0.0 | 数据处理 |
| `numpy` | >=1.24.0 | 数值计算 |
| `injector` | >=0.21.0 | 依赖注入框架 |

> 私有 SDK（`AmazingData`）需手动放入 `wheels/` 并安装（`uv pip install wheels/*.whl`）。

## 🏗️ 架构说明

### 六边形架构

项目采用六边形架构（端口与适配器模式），将业务逻辑与基础设施解耦：

- **Domain 层** — 纯业务逻辑，不依赖任何外部库（SQLAlchemy、asyncpg、SDK）
- **Ports** — Python `Protocol` 定义接口契约，domain 层通过端口访问外部资源
- **Adapters** — 实现端口接口，封装基础设施集成（SDK 调用、数据库操作）
- **Services** — 应用服务层，通过端口注入依赖，编排业务流程

| 组件 | 文件 | 职责 |
|------|------|------|
| **Domain** | `domain/` | 纯业务逻辑，无外部依赖 |
| **Ports** | `domain/ports/` | Protocol-based 接口契约（6 个端口） |
| **Services** | `services/` | 应用服务，通过端口注入依赖 |
| **Adapters** | `*/adapters/` | 基础设施适配器（SDK/DB → async） |
| **DI Container** | `di/container.py` | 依赖注入绑定（injector 框架） |
| **API Client** | `amazing_data/api/client.py` | AmazingData SDK 封装 |
| **Database** | `database/core/` | 连接管理 |
| **Models** | `database/models/` | ORM 数据模型 |
| **CLI** | `application/cli/` | 命令行接口 |
| **Scheduler** | `application/scheduler/` | 自动同步调度 |
### 数据流

```
CLI / Scheduler
        ↓
┌─ Application Layer ─────────────────────────────┐
│  Services (KlineDataService, CalendarDataService) │
│       ↓ uses                    ↓ uses           │
│  KlineProviderPort        KlineStorePort          │
└───────┬──────────────────────────┬───────────────┘
        ↓                          ↓
┌─ Adapter Layer ──────────────────────────────────┐
│  KlineProviderAdapter       KlineStoreAdapter     │
│  (asyncio.to_thread)        (AsyncSession)        │
└───────┬──────────────────────────┬───────────────┘
        ↓                          ↓
  AmazingData API              PostgreSQL/TimescaleDB
```

---

## 📜 许可证

MIT © 2026 Laniakea Kamasylvia