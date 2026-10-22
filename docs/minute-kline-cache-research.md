# 分钟线缓存方案调研

> **问题**:分钟线(K线 min1~min120)计划采用缓存制,每天清空。
> 有说法称"PG18 可以替代 Redis",评估该说法是否适用于本场景,并对比可用方案。

---

## 一、"PG18 替代 Redis"是什么

PostgreSQL 18(2025-09-25 发布)发布后,社区出现一批"用 PG 替代 Redis 做缓存"的热文。其核心方案是:

- **`UNLOGGED` 表 + JSONB**:unlogged 表跳过 WAL(预写日志),写性能接近 Redis
- **场景**:API 响应缓存、session、feature flag——即 **KV blob 缓存**
- **TTL**:PG **没有原生 TTL**,需 `pg_cron` 定时 DELETE 或应用层过期判断

### 性能对比(社区 benchmark)

| 指标 | Redis | PG unlogged 表 |
|---|---|---|
| 写延迟 | ~0.05–0.095 ms | ~0.08–0.68 ms |
| 吞吐 | 更高基线 | ~485K TPS(报告值) |
| 崩溃安全 | 缓存(volatile) | unlogged 崩溃丢数据 |
| 架构复杂度 | 独立服务 | 单数据库 |

**结论**:PG unlogged 在 KV 缓存场景确实接近 Redis(延迟差 ~10x 但绝对值都 < 1ms),且省一个组件。

### 为什么不适用于我们的分钟线

| 维度 | "PG18 替代 Redis" | 我们的分钟线 |
|---|---|---|
| 数据模型 | KV blob(key→JSONB) | **结构化时间序列**(symbol×time→OHLCV) |
| 查询方式 | key 查 value | **列式 SQL**(OHLCV 范围查询、聚合) |
| TTL 粒度 | 秒级/分钟级(key 过期) | **日级**(交易日收盘后清空) |
| TTL 实现 | 手动 pg_cron DELETE | TimescaleDB 原生 `drop_chunks`(已有能力) |
| 数据量 | KB 级/条 | **每交易日 ~240 条/symbol × 5500 股 = 132 万条/天/周期** |

分钟线是高吞吐结构化时序数据,不是 KV blob。"PG18 替代 Redis"方案是为后者设计的。

---

## 二、我们已有的更优工具:TimescaleDB

项目**已经在用 TimescaleDB**(kline 13 表全是 hypertable)。TimescaleDB 原生提供 retention/compression,正是为"高频时序数据 + 按时间清空"设计的。

### 现状(Explore 调研确认)

1. **8 张分钟线表已全部存在**(`kline_min1`~`kline_min120`),ORM + 迁移 + hypertable 全齐,目前为空
2. **K线同步链路完全参数化**——开通分钟线只需在 `settings.toml` 的 `enabled_intervals` 加周期名,**零代码改动**
3. **scheduler 已预留** `run_minute()` 是主链第一步,被 `enabled_intervals` 关着
4. **缺的是 retention policy**——全项目无任何 `add_retention_policy`/`drop_chunks`/`compression`

### TimescaleDB 三件套(无需引入新组件)

| 机制 | SQL | 作用 |
|---|---|---|
| chunk 切分 | `SELECT set_chunk_time_interval('kline_min1', INTERVAL '1 day')` | 分钟表按 1 天切 chunk,与"日级清空"对齐 |
| retention policy | `SELECT add_retention_policy('kline_min1', INTERVAL '2 days')` | TimescaleDB 后台 job 自动 drop 过期 chunk(**原生 TTL,无需 pg_cron/应用代码**) |
| compression policy(可选) | `SELECT add_compression_policy('kline_min1', INTERVAL '1 day')` | 旧 chunk 压缩,节省空间(如保留 >1 天) |

**`drop_chunks` vs `DELETE`**:drop_chunks 按整个 chunk 批量删除并释放磁盘,远快于逐行 DELETE(且不产生 bloat)。这是 TimescaleDB 相对原生 PG 的核心优势。

---

## 三、三种方案对比

### 方案 A:TimescaleDB retention(推荐)

```
migration: set_chunk_time_interval 1天 + add_retention_policy
配置:     settings.toml enabled_intervals 加 min1/min5/...
代码:     零改动(scheduler/SDK/service 全参数化)
```

| 项 | 评价 |
|---|---|
| 适配度 | ✅ 天生为时序+TTL 设计 |
| 复杂度 | ✅ 最低(1 个 migration + 1 行配置) |
| 清空效率 | ✅ drop_chunks 秒级 |
| 查询能力 | ✅ 原生 SQL |
| 崩溃安全 | ✅ 普通表,不丢数据 |
| 新组件 | ❌ 无(已有 TimescaleDB) |

### 方案 B:PG18 unlogged 表(社区热文方案)

```
新建 unlogged 表 + JSONB 存储 + pg_cron 定时 TRUNCATE/DELETE
完全绕过现有 kline_minN 表和 KlineDataService 链路
```

| 项 | 评价 |
|---|---|
| 适配度 | ❌ KV blob 设计,非时序 |
| 复杂度 | ❌ 高(新表+TTL 逻辑+绕过现有链路) |
| 清空效率 | ⚠️ TRUNCATE 快但全表;DELETE 慢且产 bloat |
| 查询能力 | ❌ JSONB 解析,非列式 |
| 崩溃安全 | ❌ unlogged 崩溃丢当天数据 |
| 新组件 | ⚠️ pg_cron 扩展 |

### 方案 C:混合(TimescaleDB retention + unlogged)

分钟表改 `UNLOGGED` + TimescaleDB retention。

| 项 | 评价 |
|---|---|
| 写性能 | ✅ unlogged 跳 WAL,写入更快 |
| 崩溃安全 | ⚠️ 崩溃丢当天数据(但分钟线是缓存,可接受?) |
| 复杂度 | ⚠️ 中(需评估 unlogged hypertable 是否被 TimescaleDB 完整支持) |

**注意**:TimescaleDB 对 unlogged hypertable 的支持需验证(chunk 操作/compression 可能受限)。风险较高。

---

## 四、方案 A 的落地步骤(如果选择 TimescaleDB retention)

1. **新建 alembic migration**(对当前 head):
   ```sql
   -- 8 张分钟表:1 天 chunk + retention policy
   SELECT set_chunk_time_interval('kline_min1',  INTERVAL '1 day');
   SELECT set_chunk_time_interval('kline_min3',  INTERVAL '1 day');
   -- ... min5/10/15/30/60/120 同理

   -- retention:保留 N 天(可选 compression)
   SELECT add_retention_policy('kline_min1', INTERVAL '7 days');
   -- ...
   ```
2. **配置**: `settings.toml` 的 `enabled_intervals` 加 `"min1", "min5", ...`
3. **scheduler**: `run_minute()` 自动开始同步(已接好,只差开关)
4. **可选**:加 `[kline.minute_retention_days]` 配置项控制保留天数

### 待决定的设计点

- **保留天数**:纯缓存(1~2 天)还是短期保留(7/30 天)+ compression?
- **启用哪些周期**:8 个全开,还是先开 min1/min5/min15/min30/min60 这 5 个常用的?
- **chunk 间隔**:1 天(对齐清空)还是更细(如 4 小时,查询更快)?
- **是否 unlogged**:方案 A(普通表,安全)还是方案 C(unlogged,更快但崩溃丢数据)?

---

## 五、结论

**"PG18 替代 Redis"不适用于分钟线场景。** 该说法针对 KV blob 缓存,我们的分钟线是结构化高吞吐时序数据。

**推荐方案 A(TimescaleDB retention)**:我们已有 TimescaleDB,retention policy 是它原生设计的 TTL 机制,比 PG18 unlogged 方案简单(1 个 migration + 1 行配置)、高效(drop_chunks 秒级)、安全(普通表不丢数据)。无需引入任何新组件。

参考来源:
- [PostgreSQL 18 release notes](https://www.postgresql.org/docs/release/18.0/)
- [Redis is fast – I'll cache in Postgres (Dizzy Zone)](https://dizzy.zone/2025/09/24/Redis-is-fast-Ill-cache-in-Postgres/)
- [TimescaleDB Data retention overview](https://www.tigerdata.com/docs/reference/timescaledb/data-retention)
- [TimescaleDB add_retention_policy](https://www.tigerdata.com/docs/build/data-management/data-retention/create-a-retention-policy)
- [Best Practices for TimescaleDB Massive Delete (Stormatics)](https://stormatics.tech/blogs/best-practices-for-timescaledb-massive-delete-operations)
