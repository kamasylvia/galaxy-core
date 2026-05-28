# Symbol Validator 任务台账（归档）

> 本文件只保留 **阶段归档与历史结论**。当前推进状态请看 `boards/symbol_validator/plan.md`，技术设计请看 `boards/symbol_validator/design.md`。

## 1. 文档职责

- `plan.md`：当前状态、维护边界、风险、下一步。
- `tasks.md`：历史阶段结果归档。
- `design.md`：当前采用的技术设计。

---

## 2. 历史阶段归档总览

| 阶段 | 主题 | 当前归档结论 |
| --- | --- | --- |
| Phase 1 | 本地格式校验与标准化 | 已完成，基础格式校验、标准化与解析能力已建立 |
| Phase 2 | 证券类型支持扩展 | 已完成，已支持 ETF、期货、期权与更多代码段规则 |
| Phase 3 | 证券类型推断能力 | 已完成，类型推断与候选集合能力已沉淀 |
| Phase 4 | SecurityType 层级过滤 | 已完成，已支持去冗余与更精确的类型选择 |
| Phase 5 | 与上层联动与文档收口 | 已完成，K 线等上层仍可复用 `get_valid_symbols_from_input()` |

---

## 3. 已沉淀为基线能力的内容

以下内容已经进入当前代码基线，不再作为独立推进项：

- `validate_symbol_format()` 本地格式校验。
- `normalize_symbol()` 代码标准化。
- `parse_symbols()` 输入解析。
- `is_code_suffix_match()` 后缀与代码段匹配校验。
- `infer_security_type()` 与 `get_all_possible_security_types()` 类型推断。
- `get_security_type_hierarchy()` 与 `filter_most_precise_security_types()` 层级过滤。
- `get_valid_symbols_from_input()` 对 `SecurityType` 的动态展开。
- `src/galaxy_db_bridge/shared_kernel/utils/__init__.py` 的公共导出。

---

## 4. 当前归档视角

### 4.1 阶段目标

让 symbol validator 同时承担两类稳定能力：

1. 本地、快速、无需网络的格式校验与标准化；
2. 在上层需要时，基于 `SecurityType` 进行动态代码展开。

### 4.2 当前归档判断

- 状态：`已完成`
- 归档结论：
  - 当前模块不只是格式校验器，还保留了 `SecurityType` 展开入口。
  - 本地格式规则已覆盖普通证券、ETF、指数、可转债、期货和期权等主要场景。
  - 类型推断与层级过滤能力已从临时逻辑沉淀为复用函数。
  - 上层命令仍可通过 `get_valid_symbols_from_input()` 获取展开后的有效代码列表。

### 4.3 收口后归档结论

- 本地规则与动态展开已经在同一模块中共存，但职责边界已可被文档明确描述。
- K 线等上层依赖的 `SecurityType` 展开能力仍然有效，不应被误认为已移除。
- 核心格式校验与解析能力已有自动化测试基线。
- 当前文档分工已与 `boards/kline` 风格对齐。

---

## 5. 维护约定

后续维护本文件时，只做两类事情：

1. 模块能力边界、导出接口或联动方式发生变化后，更新对应归档结论。
2. 若 `SecurityType` 动态展开或本地推断规则发生实质变化，同步更新第 4 节。

不要在本文件中继续记录原始需求提示、逐文件待办清单或过时的“功能已删除”叙述。
