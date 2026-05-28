# Kline 技术设计文档

> 本文件只描述 **当前采用的技术设计与实现约束**。当前推进状态请看 `boards/kline/plan.md`，阶段归档请看 `boards/kline/tasks.md`。

## 1. 目标

`kline` 功能用于批量获取证券历史 K 线数据，并将数据同步到数据库，供后续查询与分析使用。

当前设计目标：

- 支持 CLI 批量输入证券代码或 `SecurityType`。
- 通过 AmazingData API 获取历史 K 线数据。
- 按周期写入 TimescaleDB 分表。
- 基于交易日历与完整性检查决定是否需要同步。
- 当 `start` 省略时，按证券类型自动推导默认起始时间。
- 以同步摘要作为主输出，而不是直接输出完整 K 线明细。

---

## 2. 设计原则

- **先校验，再同步**：命令层先完成参数与代码校验。
- **数据库优先**：若数据库已完整覆盖目标范围，则不重复调用 API。
- **按周期分层处理**：不同周期采用不同完整性检查策略。
- **非交易日不补数据**：缺口识别只针对理论上应存在的数据点。
- **默认起点集中管理**：`start=None` 的默认日期只保留一套映射来源。
- **输出面向执行结果**：CLI 以同步摘要为主，减少噪音输出。

---

## 3. 总体架构

```text
CLI command
  ↓
参数解析与校验
  ↓
symbols 解析 / SecurityType 展开
  ↓
start 缺省时按 symbol 推导默认起点
  ↓
按 interval 标准化 start/end
  ↓
完整性检查
  ├─ 完整 → 直接返回成功摘要
  └─ 不完整 → 调用 API 同步
                    ↓
              保存到数据库
                    ↓
               返回同步结果
```

---

## 4. 模块职责

### 4.1 命令层与兼容入口

**文件**：`src/galaxy_db_bridge/application/kline/command.py`

职责：

- 构建 `kline` 子命令。
- 解析 `symbols`、`interval`、`start`、`end`。
- 调用 symbols 校验逻辑。
- 在 `start` 缺失时，基于最终 symbol 列表推导默认起始日期。
- 让 `KLineCommandService.get_kline()` 在单 symbol 兼容查询路径上复用同一默认起点规则。
- 调用完整性检查与同步主流程。
- 输出同步摘要与错误信息。

### 4.2 时间工具层

**文件**：`src/galaxy_db_bridge/shared_kernel/utils/time_parser.py`

职责：

- 维护文档来源的默认开始日期映射。
- 根据单个 symbol 推导默认开始日期。
- 对多 symbol 请求返回统一的请求级默认开始日期。
- 继续负责 `validate_start_end_by_period()` 等日期精度标准化逻辑。

### 4.3 证券类型推断

**文件**：`src/galaxy_db_bridge/shared_kernel/utils/symbol_validator.py`

职责：

- 复用 `infer_security_type()` 判断具体 symbol 的证券类型。
- 继续负责 `SecurityType` 展开与 symbol 格式校验。
- 不承载默认起始日期映射本身。

### 4.4 结果模型

**文件**：`src/galaxy_db_bridge/application/kline/result.py`

职责：

- 定义 `KlineSyncResult` 等结果结构。
- 统一命令层与服务层的结果表达。

### 4.5 数据服务层

**文件**：`src/galaxy_db_bridge/database/services/kline.py`

职责：

- 查询数据库中的 K 线数据。
- 按周期定位对应表模型。
- 保存 API 返回的数据。
- 提供数据范围、数据合并等基础能力。
- 对旧完整性接口提供兼容包装，但不再作为主流程规则来源。

### 4.6 同步服务层

**文件**：`src/galaxy_db_bridge/database/services/kline_data_sync.py`

职责：

- 根据 symbol、周期和时间范围决定是否需要同步。
- 调用 AmazingData API 获取缺失数据。
- 处理空返回、异常返回与 SDK 已知错误。
- 将数据写回数据库。

### 4.7 完整性检查器

**文件**：`src/galaxy_db_bridge/database/services/kline_completeness_checker.py`

职责：

- 统一数据完整性检查模型。
- 针对不同周期选择不同检查策略。
- 输出完整性结果、覆盖率与缺失范围。

---

## 5. 输入与参数设计

### 5.1 支持的输入形式

`symbols` 支持以下形式：

- 单个证券代码。
- 多个证券代码列表。
- 单个 `SecurityType`。
- 证券代码与 `SecurityType` 混合列表。

### 5.2 周期参数

`interval` 支持从分钟线到年线的多种周期，并映射到 AmazingData SDK 对应的 `Period` 值。

### 5.3 时间参数

`start` 与 `end` 的处理分两层：

1. **默认起点归一化**
   - 当 `start` 显式传入时，直接使用用户值。
   - 当 `start=None` 时，按 AmazingData 文档中的数据起点推导默认值：
     - 股票 / 指数 / 债券 / 场内基金：`20130101`
     - 期权：`20150101`
     - 港股通：`20230101`
     - 中金所期货：`20100401`
     - 大商所期货：`20130601`
     - 郑商所期货：`20110101`
     - 上期所 / 上海国际能源交易中心期货：`20190801`
   - 对混合 symbol 请求，统一取各 symbol 默认起点中的最大值。

2. **周期精度标准化**
   - 年线：按年处理。
   - 季线 / 月线：按周期边界做输入标准化，但完整性判断使用最后交易日语义。
   - 日线 / 周线：按自然日期补全。
   - 分钟级别：按更细粒度时间补全。

约束：

- 无法推断 symbol 类型时直接报错，不静默兜底到某个通用起始日期。
- `validate_start_end_by_period()` 继续只负责日期长度 / 精度裁剪。

---

## 6. 默认起始时间设计

### 6.1 来源

默认起始时间来自 `docs/AmazingData/Markdown/AmazingData开发手册/2. 功能介绍/2.2 数据详情.md` 的数据起点描述。

### 6.2 单 symbol 规则

对单个具体 symbol：

- 先通过 `infer_security_type()` 得到类型。
- 再用统一映射表取该类型的默认开始日期。
- CLI 的单代码输入与 `KLineCommandService.get_kline()` 的兼容查询入口都使用这同一条规则。

### 6.3 混合 symbol 规则

对多个 symbol 的同一次请求：

- 先分别计算每个 symbol 的默认开始日期。
- 请求级 `start` 取这些日期中的最大值。

这样做的目的：

- 保持当前 CLI 仍然只有一个共享时间窗口。
- 避免对不支持的更早历史区间发起无意义查询。
- 不把“逐 symbol 独立时间窗口”复杂度引入当前同步链路。

---

## 7. 完整性检查设计

### 7.1 设计目标

完整性检查用于回答以下问题：

> 在用户请求的 symbol、interval、start、end 范围内，数据库现有数据是否已经足够完整，以至于可以跳过 API 同步？

### 7.2 分层策略

当前采用分层策略：

- **长周期（月线及以上）**：使用连续性检查。
- **短周期（周线及以下）**：使用交易日对比检查。

### 7.3 一致性要求

最终主流程需要满足：

- 命令层与同步层使用一致的完整性判断口径。
- 缺失区间识别逻辑与完整性检查结果保持一致。
- 非交易日不会误触发补数。
- `CompletenessResult` 作为命令层、兼容接口与同步层共享的结果模型。
- 默认起始日期在进入完整性检查前已完成归一化。

---

## 8. 同步流程设计

### 8.1 主流程

1. 命令层完成参数校验。
2. symbols 校验与展开。
3. 若 `start` 缺失，则推导请求级默认 `start`。
4. 调用 `validate_start_end_by_period()` 标准化日期精度。
5. 调用 `kline_completeness_checker.check()` 检查数据库完整性。
6. 若不完整，则直接使用 `CompletenessResult.missing_ranges` 计算需要同步的数据范围。
7. 调用 AmazingData API 获取缺失数据。
8. 保存到数据库。
9. 返回同步结果摘要。

### 8.2 同步结果结构

当前使用 `KlineSyncResult` 表达同步结果，核心字段包括：

- `success_count`
- `synced_records`
- `failed_codes`
- `message`

### 8.3 非交易日处理

当前处理原则：

- 完整性检查阶段只把理论上应存在的数据点纳入缺口判断。
- 短周期通过交易日历过滤非交易日。
- 长周期通过“最后交易日”语义避免把自然周期末误判为缺口。
- 因此非交易日范围不会进入正常补数流程。

---

## 9. SecurityType 优化设计

### 9.1 设计目标

在用户输入 `SecurityType` 时，尽量减少无效 API 调用与重复展开。

### 9.2 采用策略

- 定义 `SecurityType` 层级关系。
- 过滤冗余的上层 / 下层类型。
- 只保留最有代表性的类型进行展开。
- 对普通代码先做本地格式初筛，减少 API 压力。
- 展开后的具体代码再参与默认开始日期推导。

### 9.3 设计收益

- 减少 `get_hist_code_list` 调用次数。
- 缩小返回代码集合规模。
- 提升大批量输入下的整体性能。
- 避免针对不支持的历史时间窗口发起无意义请求。

---

## 10. 错误处理设计

### 10.1 错误分类

- 参数错误：输入格式、日期范围、周期无效。
- 数据错误：无数据、数据不完整、代码无效。
- 系统错误：数据库连接、配置问题、API 调用失败。
- SDK 错误：AmazingData 已知 bug。
- 默认起点错误：symbol 类型不可推断或缺少映射。

### 10.2 默认起点失败处理

当前处理原则：

- 若 `start=None` 且无法推断 symbol 类型，直接失败。
- 若已推断出类型但缺少默认起始日期映射，直接失败。
- 不静默退回 `20130101` 等通用日期，避免把问题伪装成正常查询。

---

## 11. 测试设计

### 11.1 测试范围

当前重点覆盖：

- 命令层显式 `start` 行为不变。
- 兼容入口显式 `start` 行为不变。
- `start=None` 时各证券类型默认起点正确。
- 混合 symbol 请求使用最大默认起点。
- 单 symbol 兼容查询入口在 `start=None` 时复用同一默认起点规则。
- 默认起点推导后的日期仍会经过 `validate_start_end_by_period()`。
- 默认起点推导失败时命令返回失败。
- `boards/` 迁移后文档路径与本地工具设置一致。
