# Symbol Validator 当前推进计划

> 本文件只负责 **当前进度管理**。历史归档请看 `boards/symbol_validator/tasks.md`，技术设计请看 `boards/symbol_validator/design.md`。

## 1. 当前结论

- **当前阶段**：基础能力已完成，进入口径维护。
- **当前焦点**：保持“本地格式校验 + 可选 SecurityType 展开”两类能力的边界清晰。
- **当前判断**：`symbol_validator.py` 现已不是纯格式校验器，而是同时承载格式校验、代码标准化、SecurityType 推断以及基于 AmazingData 的代码展开入口。

---

## 2. 当前状态看板

| 事项 | 状态 | 说明 |
| --- | --- | --- |
| 格式校验 | 已完成 | `validate_symbol_format()` 已支持 6 位代码、后缀、期货、期权与 `SecurityType` |
| 代码标准化 | 已完成 | `normalize_symbol()` 可自动补齐 `.SH/.SZ/.BJ/.FUTURE/.OPTION` |
| 输入解析 | 已完成 | `parse_symbols()` 已支持单值、逗号列表、方括号列表和混合输入 |
| 证券类型推断 | 已完成 | `infer_security_type()` / `get_all_possible_security_types()` 已覆盖股票、ETF、指数、可转债、期货、期权 |
| SecurityType 层级过滤 | 已完成 | `filter_most_precise_security_types()` 已用于减少冗余展开 |
| API 展开入口 | 已完成 | `get_valid_symbols_from_input()` 仍会调用 AmazingData 展开 `SecurityType` |
| 基础测试 | 已完成 | `tests/core/symbol_validator/test_format_validation.py` 已覆盖核心格式与解析场景 |

---

## 3. 当前结论后的维护重点

### 3.1 已完成收口项

- `validate_symbol_format()` 已覆盖普通证券、ETF、期货、期权和 `SecurityType` 格式。
- `normalize_symbol()` 已内置按代码前缀推断交易所后缀的规则。
- `parse_symbols()` 已成为 CLI 参数解析的直接复用入口。
- `infer_security_type()` 与 `get_all_possible_security_types()` 已承担较完整的证券类型推断职责。
- `get_valid_symbols_from_input()` 仍保留，并通过 `AmazingData` 获取 `SecurityType` 对应代码列表。
- `src/galaxy_db_bridge/shared_kernel/utils/__init__.py` 仍显式导出 `get_valid_symbols_from_input()` 供上层使用。

### 3.2 当前维护边界

- 后续若只修改“格式合法性”，应优先调整 `validate_symbol_format()` / `normalize_symbol()` / `is_code_suffix_match()`，不要误改 API 展开逻辑。
- 后续若调整 `SecurityType` 输入行为，应同步检查 `get_valid_symbols_from_input()`、类型层级关系与 K 线命令层调用口径。
- 文档必须明确区分：
  - **本地静态能力**：格式校验、标准化、解析、类型推断；
  - **依赖 AmazingData 的动态能力**：`SecurityType` 展开到真实代码列表。

### 3.3 当前验证结果

- 直接测试文件：
  - `tests/core/symbol_validator/test_format_validation.py`
- 辅助性验证脚本 / 试验文件：
  - `tests/unit/test_52_fix.py`
  - `tests/unit/test_security_type_inference.py`
  - `tests/unit/test_additional_prefixes.py`
- 当前基线结论：核心格式校验与解析能力已有自动化覆盖，部分证券类型前缀验证仍以脚本式试验文件为主。

### 3.4 文档维护要求

- `plan.md` 只保留当前状态、边界和风险。
- `tasks.md` 只记录阶段归档与历史结论。
- `design.md` 只描述当前实际采用的“双层能力”设计，不再沿用“已完全移除 API 能力”的旧表述。

---

## 4. 当前推荐维护顺序

### Maintenance A：保持本地规则稳定

- [x] 格式校验入口已统一到 `validate_symbol_format()`。
- [x] 标准化规则已统一到 `normalize_symbol()`。
- [x] 输入解析已统一到 `parse_symbols()`。

### Maintenance B：保持类型推断与层级一致

- [x] `infer_security_type()` 已覆盖当前主要证券类型。
- [x] `get_all_possible_security_types()` 已提供从具体到宽泛的候选集合。
- [x] `filter_most_precise_security_types()` 已承担去冗余职责。

### Maintenance C：约束 API 展开边界

- [x] `get_valid_symbols_from_input()` 仅在 `SecurityType` 需要展开时调用 AmazingData。
- [x] 普通 symbol 仍先走本地格式初筛与标准化。
- [x] 当前文档结构已与 `boards/kline` 风格对齐。

---

## 5. 验收标准

以下条目全部满足后，可继续视为“已完成、仅维护”：

- [x] 普通代码、后缀代码、期货、期权和 `SecurityType` 格式均可被识别。
- [x] 6 位代码可按当前规则自动补齐后缀。
- [x] 混合输入可被解析为 symbol / `security_type` 两类结果。
- [x] 证券类型推断与层级过滤能力可供上层直接复用。
- [x] `SecurityType` 输入仍可通过 AmazingData 展开为代码列表。
- [x] 三份文档职责已与 `boards/kline` 对齐。

---

## 6. 后续维护风险

### 风险 1：文档口径继续失真

- 旧文档把模块描述成“只保留格式校验”，但当前代码仍保留 `get_valid_symbols_from_input()` 和类型层级逻辑，若不持续修正文档，后续容易误删或误用现有能力。

### 风险 2：本地规则与动态展开耦合加深

- 若把格式校验规则、类型推断规则和 API 展开规则混写，会增加排障难度，并让简单格式修改引发远端依赖回归。

### 风险 3：测试覆盖与实际能力不对齐

- 当前自动化测试主要覆盖格式校验与解析，部分类型推断仍以脚本式文件存在，后续若大改推断规则，容易缺少稳定断言。

---

## 7. 后续更新模板

### 本轮目标

- 目标 1：保持本地规则与动态展开边界清晰。
- 目标 2：补充类型推断或输入解析相关验证。

### 本轮完成

- [ ] 已同步状态变化。
- [ ] 已更新相关测试 / 文档。

### 本轮发现

- 问题：
- 影响：
- 结论：

### 下一步

- [ ] 下一步 1
- [ ] 下一步 2
