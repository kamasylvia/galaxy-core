# Galaxy DB Bridge

> 📥 从银河证券 **AmazingData** 接口拉取行情数据，并持久化至 **PostgreSQL** 数据库。
> 本项目是一个独立的数据库桥接项目，连接 AmazingData API 与 PostgreSQL 数据库。

---

## 📁 目录结构

```
galaxy-db-bridge/                     # 项目根目录
├── pyproject.toml                    # 项目元数据 & 依赖声明
├── README.md                         # 项目文档
├── .gitignore                        # Git 忽略配置
├── .python-version                   # Python 版本 (3.13)
├── .env                              # 环境变量文件
├── .env.example                      # 环境变量模板
├── config/
│   └── settings.toml                 # 应用配置（TOML 格式）
├── docs/
│   └── AmazingData开发手册.pdf       # AmazingData API 手册
├── wheels/                           # 私有 .whl 文件（如官方 SDK）
├── src/
│   └── galaxy_db_bridge/           # 主包
│       ├── __init__.py               # 包初始化 & 核心导出
│       ├── __main__.py               # 包入口: python -m galaxy_db_bridge
│       │
│       ├── amazing_data/             # AmazingData API 相关模块
│       │   ├── api/                  # API 封装
│       │   │   ├── __init__.py
│       │   │   ├── client.py         # AmazingData 客户端连接
│       │   │   └── lazy_client.py    # 延迟加载客户端
│       │   ├── enums/                # 枚举定义
│       │   │   ├── __init__.py
│       │   │   ├── period.py         # 周期枚举
│       │   │   └── security_type.py  # 证券类型枚举
│       │   ├── models/               # 数据模型
│       │   │   ├── __init__.py
│       │   │   ├── financial.py      # 财务数据模型
│       │   │   └── market.py         # 行情数据模型
│       │   └── services/             # 业务服务
│       │       └── __init__.py
│       │
│       ├── application/              # 应用层
│       │   └── cli/                  # 命令行工具
│       │       ├── __init__.py
│       │       └── commands.py       # CLI 命令实现
│       │
│       ├── postgresql/               # PostgreSQL 相关模块
│       │   ├── db/                   # 数据库访问层
│       │   │   ├── __init__.py
│       │   │   └── connection.py     # 数据库连接管理
│       │   ├── models/               # 数据模型
│       │   │   └── __init__.py
│       │   └── services/             # 业务服务层
│       │       ├── __init__.py
│       │       ├── data_sync_service.py  # 数据同步服务
│       │       └── transformers.py       # 数据转换器
│       │
│       └── shared_kernel/            # 共享核心模块
│           ├── __init__.py
│           ├── config/               # 配置管理
│           │   ├── __init__.py
│           │   ├── config.py         # 配置类定义
│           │   └── _config_loader_impl.py # 配置加载实现
│           ├── enums/                # 通用枚举
│           │   ├── __init__.py
│           │   ├── div_progress.py   # 分红进度枚举
│           │   ├── market.py         # 市场枚举
│           │   ├── progress.py       # 进度枚举
│           │   ├── report_type.py    # 报告类型枚举
│           │   ├── security_status.py # 证券状态枚举
│           │   ├── statement_type.py # 报表类型枚举
│           │   └── trading_phase_code.py # 交易阶段代码枚举
│           └── utils/                # 工具函数
│               └── __init__.py
└── tests/                            # 测试
    ├── __init__.py
    └── api_test/                     # API 测试
        └── client_test.py            # 客户端测试
```

> 💡 **设计理念**: `src/` 下采用扁平结构，主入口通过 `python -m galaxy_db_bridge` 调用 `__main__.py`。

---

## ⚙️ 快速开始

### 前置要求

- Python >= 3.13, < 3.14
- [uv](https://docs.astral.sh/uv/)（推荐 v0.1+）
- PostgreSQL >= 18（本地或远程）
- 银河证券 AmazingData API 账号

### 1. 克隆并进入项目

```bash
git clone https://kamasylvia@dev.azure.com/kamasylvia/Kamasylvia/_git/galaxy-db-bridge
cd galaxy-db-bridge
```

### 2. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境（默认 .venv）
uv venv

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows (PowerShell)

# 安装本项目（可编辑模式）及依赖
uv pip install wheels/*.whl
uv pip install -e ".[dev,format]"
```

### 3. 配置环境变量

复制环境变量模板并填入实际值：

```bash
cp .env.example .env
```

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
python -m galaxy_db_bridge --init-db
```

或使用 Python API：

```python
from galaxy_db_bridge import init_database
init_database()
```

### 5. 拉取历史数据

使用 CLI 命令：

```bash
# 拉取 K 线数据
galaxy-db-bridge fetch --symbol 600000.SH --start 2020-01-01 --end 2024-12-31 --data-type kline

# 拉取快照数据
galaxy-db-bridge fetch --symbol 600000.SH --start 2020-01-01 --end 2024-12-31 --data-type snapshot
```

### 6. 同步数据到数据库

```bash
# 增量同步
galaxy-db-bridge sync

# 全量同步
galaxy-db-bridge sync --full
```

---

## 🔧 CLI 命令参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `galaxy-db-bridge` | 显示帮助信息 | `galaxy-db-bridge` |
| `galaxy-db-bridge fetch` | 拉取历史数据 | `galaxy-db-bridge fetch -s 600000.SH --start 2024-01-01 --end 2024-12-31` |
| `galaxy-db-bridge sync` | 同步数据到数据库 | `galaxy-db-bridge sync --full` |
| `galaxy-db-bridge realtime` | 启动实时数据订阅（预留） | `galaxy-db-bridge realtime` |

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
pytest tests/
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
- 银河证券 API 凭据应通过环境变量注入，**禁止硬编码**到代码中。
- 生产环境建议使用密钥管理服务（如 Vault）管理敏感信息。

---

## 📦 依赖说明

| 依赖 | 版本 | 用途 |
|------|------|------|
| `requests` | >=2.31.0 | 调用 AmazingData REST API |
| `sqlalchemy` | >=2.0.0 | ORM 与数据库抽象 |
| `psycopg2-binary` | >=2.9.0 | PostgreSQL 驱动 |
| `python-dotenv` | >=1.0.0 | 加载 `.env` 配置 |
| `toml` | >=0.10.2 | 读取 TOML 配置文件 |

> 私有 SDK（如 `amazing-data-client`）需手动放入 `wheels/` 并安装。

---

## 🏗️ 架构说明

### 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| **API Client** | `api/client.py` | AmazingData API 连接与请求封装 |
| **Config Loader** | `config_loader.py` | 配置加载（TOML + 环境变量） |
| **Models** | `models/` | SQLAlchemy ORM 数据模型 |
| **Database** | `db/connection.py` | 数据库连接池管理 |
| **Services** | `services/` | 业务逻辑：数据同步、转换 |
| **CLI** | `cli/commands.py` | 命令行接口 |

### 数据流

```
AmazingData API
      ↓
[ API Client ] → [ Transformers ] → [ Database ]
      ↑                                    ↓
[ Config Loader ] ← [ .env + settings.toml ]
```

---

## 🤝 协作指南

- **共享数据库 Schema** → 见 `docs/schema.sql`（如有）

---

## 📜 许可证

MIT © 2026 Laniakea Kamasylvia