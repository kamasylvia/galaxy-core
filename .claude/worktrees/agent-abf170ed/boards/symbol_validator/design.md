# Symbol Validator 技术设计文档

> 本文件只描述 **当前采用的技术设计与实现约束**。当前推进状态请看 `boards/symbol_validator/plan.md`，阶段归档请看 `boards/symbol_validator/tasks.md`。

## 1. 目标

`symbol_validator` 用于统一处理上层传入的证券标识，并提供两类能力：

- **本地静态能力**：格式校验、代码标准化、输入解析、证券类型推断。
- **动态展开能力**：当输入包含 `SecurityType` 时，通过 AmazingData 获取对应历史代码列表。

当前设计目标：

- 尽量先用本地规则完成快速筛选与标准化。
- 在确有需要时才依赖 AmazingData 做 `SecurityType` 展开。
- 让 K 线命令等上层只复用统一入口，不再散落维护代码段规则。

---

## 2. 设计原则

- **本地优先**：普通代码先走本地格式校验与标准化。
- **能力分层**：静态规则与动态展开在同一模块中共存，但职责边界明确。
- **类型集中**：证券类型推断规则集中在 `symbol_validator.py`。
- **避免冗余 API 调用**：`SecurityType` 展开前先做层级去重。
- **输出面向上层复用**：解析结果与有效代码列表都可直接被 CLI / 服务层消费。

---

## 3. 总体架构

```text
User input
  ↓
parse_symbols()
  ↓
分类为 symbol / security_type
  ├─ symbol
  │    ↓
  │  validate_symbol_format()
  │    ↓
  │  normalize_symbol()
  │
  └─ security_type
       ↓
     filter_most_precise_security_types()
       ↓
     get_valid_symbols_from_input()
       ↓
     AmazingData get_hist_code_list()

  ↓
Normalized symbols / expanded codes
```

---

## 4. 模块职责

### 4.1 格式校验

**函数**：`validate_symbol_format(symbol: str) -> bool`

职责：

- 识别 6 位数字代码。
- 识别带合法后缀的证券代码。
- 识别 `SecurityType` 枚举名。
- 识别期货和期权格式。
- 复用 `is_code_suffix_match()` 做代码段与后缀匹配校验。

### 4.2 标准化

**函数**：`normalize_symbol(symbol: str) -> str`

职责：

- 为 6 位数字自动补后缀。
- 对期货代码补 `.FUTURE`。
- 对期权代码补 `.OPTION`。
- 对已有后缀的输入直接返回。

### 4.3 输入解析

**函数**：`parse_symbols(value: str) -> list[tuple[str, str]]`

职责：

- 支持单个 symbol。
- 支持逗号列表与方括号列表。
- 支持普通代码与 `SecurityType` 混合输入。
- 输出 `("symbol", value)` 或 `("security_type", value)` 结构。

### 4.4 类型推断

**函数**：

- `infer_security_type()`
- `get_all_possible_security_types()`

职责：

- 根据代码段、后缀和品种规则推断证券类型。
- 提供“单一最可能类型”与“从具体到宽泛的候选类型集合”两类能力。

### 4.5 层级过滤

**函数**：

- `get_security_type_hierarchy()`
- `filter_most_precise_security_types()`

职责：

- 表达 `SecurityType` 的父子层级。
- 在输入包含多个宽泛 / 具体类型时优先保留更精确的上层调用意图，减少重复展开。

### 4.6 动态展开

**函数**：`get_valid_symbols_from_input()`

职责：

- 将 `SecurityType` 输入展开为真实代码列表。
- 先对普通代码做本地格式初筛与标准化。
- 动态导入 AmazingData client，避免静态循环依赖。

---

## 5. 本地规则设计

### 5.1 普通证券代码

支持：

- 6 位数字（如 `600000`）。
- 带交易所后缀的 6 位代码（如 `600000.SH`、`000001.SZ`、`920001.BJ`）。

### 5.2 期货与期权

支持：

- 期货：字母 + 数字，再补或校验 `.FUTURE`。
- 期权：数字或带交易所片段的代码，再补或校验 `.OPTION`。
- 多段格式如 `10003737.CZC.OPTION` 由带后缀分支处理。

### 5.3 `SecurityType`

支持直接把 `SecurityType` 枚举名当作合法输入，并在解析结果中保留为 `security_type` 项，供后续动态展开。

### 5.4 后缀匹配

`is_code_suffix_match()` 负责：

- 检查 6 位代码与 `.SH/.SZ/.BJ` 的匹配关系。
- 校验期货代码与 `.FUTURE` 的匹配关系。
- 校验期权代码与 `.OPTION` 的匹配关系。

---

## 6. 类型推断设计

### 6.1 推断覆盖范围

当前推断规则已覆盖：

- A 股股票。
- ETF。
- 指数。
- 可转债。
- 港股通。
- 国债逆回购。
- 期货。
- 期权。

### 6.2 双层输出

- `infer_security_type()`：返回一个最可能的类型或 `None`。
- `get_all_possible_security_types()`：返回一个从更具体到更宽泛的候选列表，供上层做后续筛选。

### 6.3 层级关系用途

层级关系用于避免出现：

- 既传 `EXTRA_STOCK_A`，又传 `SH_A` / `SZ_A`。
- 既传 `EXTRA_ETF`，又传 `SH_ETF` / `SZ_ETF`。

这使 `get_valid_symbols_from_input()` 在展开前就能减少不必要的远端调用。

---

## 7. 动态展开设计

### 7.1 触发条件

只有当输入列表中包含 `SecurityType` 时，`get_valid_symbols_from_input()` 才会调用 AmazingData 获取真实代码列表。

### 7.2 处理流程

1. 拆分普通 symbol 与 `SecurityType`。
2. 对普通 symbol 做 `validate_symbol_format()` + `normalize_symbol()`。
3. 对 `SecurityType` 做层级过滤。
4. 动态导入 `amazing_data_client` 与配置加载器。
5. 使用 `get_hist_code_list()` 获取时间范围内的历史代码列表。
6. 与普通 symbol 合并后去重返回。

### 7.3 约束

- 动态展开依赖 AmazingData SDK 与本地配置。
- 该过程不是“纯校验”，而是“输入扩展 + 代码筛选”。
- 文档与调用方都不应把它误写为已删除能力。

---

## 8. 对外导出设计

**文件**：`src/galaxy_db_bridge/shared_kernel/utils/__init__.py`

当前公共导出包括：

- `validate_symbol_format`
- `normalize_symbol`
- `parse_symbols`
- `get_valid_symbols_from_input`

这说明上层依然把 symbol validator 当作包含动态展开入口的公共工具包来使用。

---

## 9. 测试设计

### 9.1 核心自动化测试

- `tests/core/symbol_validator/test_format_validation.py`

覆盖内容：

- 格式校验。
- 标准化。
- 输入解析。
- 基础异常处理。
- 部分 ETF / 期货 / 期权规则。

### 9.2 辅助性脚本验证

- `tests/unit/test_52_fix.py`
- `tests/unit/test_security_type_inference.py`
- `tests/unit/test_additional_prefixes.py`

这些文件更接近脚本式验证，说明当前类型推断的自动化断言仍不如格式校验部分稳定。

---

## 10. 已知约束

- 模块当前同时承担静态规则与动态展开，职责较多，后续修改时必须明确是改哪一层能力。
- `get_valid_symbols_from_input()` 使用动态导入来避免循环依赖，调用链较隐式，排障时需要关注配置与 AmazingData client。
- 当前自动化测试对类型推断与层级过滤的覆盖弱于格式校验与解析。

---

## 11. 结论

`symbol_validator` 当前的真实设计是“本地格式规则引擎 + 可选 SecurityType 动态展开入口”的组合，而不是单纯的离线格式校验器。后续维护的重点不是重新讨论是否保留 API 能力，而是保持两类能力的边界清晰、规则集中、文档与实际实现一致。
