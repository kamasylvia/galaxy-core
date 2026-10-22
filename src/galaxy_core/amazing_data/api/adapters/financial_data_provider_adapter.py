"""财务数据提供者适配器 -- 包装 AmazingDataClient 为 FinancialDataProviderPort."""

import asyncio
import logging
from pathlib import Path

import pandas as pd

from galaxy_core.amazing_data.api.client import AmazingDataClient
from galaxy_core.domain.value_objects import FinancialDataType, FinancialRecord
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)

# 每个 API 返回 DataFrame 中需要提取为 FinancialRecord 元数据的公共字段.
# API 使用大写列名，adapter 映射到 snake_case 内部字段.
_METADATA_FIELDS: dict[str, str] = {
    "MARKET_CODE": "symbol",
    "SECURITY_NAME": "security_name",
    "STATEMENT_TYPE": "statement_type",
    "REPORT_TYPE": "report_type",
    "REPORTING_PERIOD": "reporting_period",
    "REPORT_PERIOD": "reporting_period",  # 分红配送使用 REPORT_PERIOD
    "ANN_DATE": "ann_date",
    "ACTUAL_ANN_DATE": "actual_ann_date",
    "COMP_TYPE_CODE": "comp_type_code",
}

# 三大报表的元数据列集合（用于区分元数据字段与财务数据字段）.
_STATEMENT_META_KEYS = frozenset(_METADATA_FIELDS.values())


def _api_col_to_snake_case(col: str) -> str:
    """将 API 大写列名转换为 snake_case.

    例: ACC_PAYABLE -> acc_payable, MARKET_CODE -> market_code
    """
    return col.lower()


class InfoDataProviderAdapter:
    """FinancialDataProviderPort 实现 -- 包装 AmazingDataClient InfoData 接口.

    asyncio.to_thread() 集中在此 adapter 层，应用层代码完全异步.
    """

    def __init__(self, client: AmazingDataClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _get_local_path(self) -> str:
        """从配置获取本地缓存路径."""
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        local_path = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            local_path += "/"
        return local_path

    @staticmethod
    def _normalize_to_dict(
        data: dict[str, pd.DataFrame] | pd.DataFrame,
    ) -> dict[str, pd.DataFrame]:
        """将 SDK 返回数据统一为 dict[str, DataFrame] 格式.

        业绩快报/业绩预告的 SDK 方法可能返回单个 DataFrame（按 symbol 分组）
        而非 dict[str, DataFrame]。

        分红(dividend)的 SDK 返回格式是 dict[str, Series]（键=列名，值=Series），
        与文档声明的 dict {code: DataFrame} 不符。此处检测并转置为 DataFrame。
        """
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return {}
            return {"_all": data}
        if isinstance(data, dict):
            # 检测 dividend 格式: dict[str, Series]（列名→Series）
            # 正常格式是 dict[str, DataFrame]（code→DataFrame）
            if data:
                first_val = next(iter(data.values()))
                if isinstance(first_val, pd.Series):
                    # dividend 横向格式: 列名→Series，Series 的 index 是行号
                    # pd.DataFrame(data) 将其转置为正常的行式 DataFrame
                    try:
                        df = pd.DataFrame(data)
                        if not df.empty:
                            return {"_all": df}
                    except Exception:
                        pass
            return data
        return {}

    @staticmethod
    def _safe_str(value: object) -> str | None:
        """安全提取字符串值，处理 NaN/None."""
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        result = str(value)
        # 过滤 'nan' / 'None' 等无效字符串
        if result.lower() in ("nan", "none", "nat", ""):
            return None
        return result

    @staticmethod
    def _safe_float(value: object) -> float | None:
        """安全提取浮点值，处理 NaN/None."""
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        try:
            result = float(value)
            if pd.isna(result):
                return None
            return result
        except (ValueError, TypeError):
            return None

    def _extract_metadata(self, record: dict[str, object]) -> dict[str, str | None]:
        """从 DataFrame 行提取元数据字段.

        API 列名大小写不确定（不同接口可能使用不同大小写），
        使用大小写不敏感查找.

        Returns:
            包含 snake_case 键的元数据字典
        """
        # 构建大小写不敏感的列名查找表
        lower_to_original: dict[str, str] = {k.lower(): k for k in record}

        metadata: dict[str, str | None] = {}
        for api_col, snake_key in _METADATA_FIELDS.items():
            original_key = lower_to_original.get(api_col.lower())
            if original_key is not None:
                metadata[snake_key] = self._safe_str(record[original_key])
            elif snake_key not in metadata:
                metadata[snake_key] = None
        return metadata

    def _extract_financial_fields(
        self,
        record: dict[str, object],
        data_type: FinancialDataType,
    ) -> dict[str, object]:
        """从 DataFrame 行提取财务数据字段（排除元数据列）.

        业绩快报/业绩预告无 statement_type 元数据字段.

        Returns:
            动态字段字典 {snake_case_field_name: value}
        """
        # 构建需要排除的列名集合（大小写不敏感）
        exclude_lower = {api_col.lower() for api_col in _METADATA_FIELDS}
        # created_at / updated_at 也需要排除
        exclude_lower.update({"created_at", "updated_at"})

        fields: dict[str, object] = {}
        for col, value in record.items():
            col_lower = col.lower()
            if col_lower in exclude_lower:
                continue
            snake_key = _api_col_to_snake_case(col)
            # 对字符串和浮点值做安全转换
            if isinstance(value, str):
                fields[snake_key] = self._safe_str(value)
            else:
                fields[snake_key] = self._safe_float(value)
        return fields

    def _dataframe_to_records(
        self,
        data: dict[str, pd.DataFrame],
        data_type: FinancialDataType,
    ) -> list[FinancialRecord]:
        """将 SDK 返回的 dict[str, DataFrame] 转换为 FinancialRecord 列表.

        Args:
            data: SDK 返回的原始数据，键为 symbol，值为 DataFrame
            data_type: 财务数据类型

        Returns:
            FinancialRecord 列表
        """
        records: list[FinancialRecord] = []
        total_rows = 0

        for code, df in data.items():
            if df is None or df.empty:
                continue

            df_reset = df.reset_index()
            rows = df_reset.to_dict("records")
            total_rows += len(rows)

            for row in rows:
                metadata = self._extract_metadata(row)

                # symbol: 优先从 metadata 取，fallback 到 code 参数
                symbol = metadata.get("symbol") or code
                reporting_period = metadata.get("reporting_period")
                if not reporting_period:
                    logger.warning(f"跳过无 reporting_period 的记录: {code}")
                    continue

                # 三大报表有 statement_type，快报/预告为 None
                statement_type = metadata.get("statement_type")

                ann_date = metadata.get("ann_date")
                actual_ann_date = metadata.get("actual_ann_date")

                # 提取财务数据字段
                financial_fields = self._extract_financial_fields(row, data_type)

                records.append(
                    FinancialRecord(
                        symbol=symbol,
                        reporting_period=reporting_period,
                        statement_type=statement_type,
                        ann_date=ann_date,
                        actual_ann_date=actual_ann_date,
                        data_type=data_type,
                        fields=financial_fields,
                    )
                )

        logger.debug(
            f"转换 {data_type.value} 数据: {len(data)} 个代码, "
            f"{total_rows} 行 -> {len(records)} 条 FinancialRecord"
        )
        return records

    # ------------------------------------------------------------------
    # FinancialDataProviderPort 实现
    # ------------------------------------------------------------------

    async def get_balance_sheet(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]:
        """获取资产负债表."""
        local_path = self._get_local_path()
        data: dict[str, pd.DataFrame] = await asyncio.to_thread(
            self._client.get_balance_sheet,
            code_list=symbols,
            local_path=local_path,
            begin_date=int(begin_date),
            end_date=int(end_date),
        )
        if not data:
            return []
        return self._dataframe_to_records(data, FinancialDataType.BALANCE_SHEET)

    async def get_cash_flow(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]:
        """获取现金流量表."""
        local_path = self._get_local_path()
        data: dict[str, pd.DataFrame] = await asyncio.to_thread(
            self._client.get_cash_flow,
            code_list=symbols,
            local_path=local_path,
            begin_date=int(begin_date),
            end_date=int(end_date),
        )
        if not data:
            return []
        return self._dataframe_to_records(data, FinancialDataType.CASH_FLOW)

    async def get_income_statement(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]:
        """获取利润表."""
        local_path = self._get_local_path()
        data: dict[str, pd.DataFrame] = await asyncio.to_thread(
            self._client.get_income_statement,
            code_list=symbols,
            local_path=local_path,
            begin_date=int(begin_date),
            end_date=int(end_date),
        )
        if not data:
            return []
        return self._dataframe_to_records(data, FinancialDataType.INCOME)

    async def get_profit_express(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]:
        """获取业绩快报."""
        local_path = self._get_local_path()
        data = await asyncio.to_thread(
            self._client.get_profit_express,
            code_list=symbols,
            local_path=local_path,
            begin_date=int(begin_date),
            end_date=int(end_date),
        )
        data = self._normalize_to_dict(data)
        if not data:
            return []
        return self._dataframe_to_records(data, FinancialDataType.PROFIT_EXPRESS)

    async def get_profit_notice(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]:
        """获取业绩预告."""
        local_path = self._get_local_path()
        data = await asyncio.to_thread(
            self._client.get_profit_notice,
            code_list=symbols,
            local_path=local_path,
            begin_date=int(begin_date),
            end_date=int(end_date),
        )
        data = self._normalize_to_dict(data)
        if not data:
            return []
        return self._dataframe_to_records(data, FinancialDataType.PROFIT_NOTICE)

    async def get_dividend(
        self,
        symbols: list[str],
        begin_date: str,
        end_date: str,
    ) -> list[FinancialRecord]:
        """获取分红配送."""
        local_path = self._get_local_path()
        data = await asyncio.to_thread(
            self._client.get_dividend,
            code_list=symbols,
            local_path=local_path,
            begin_date=int(begin_date),
            end_date=int(end_date),
        )
        data = self._normalize_to_dict(data)
        if not data:
            return []
        return self._dataframe_to_records(data, FinancialDataType.DIVIDEND)
