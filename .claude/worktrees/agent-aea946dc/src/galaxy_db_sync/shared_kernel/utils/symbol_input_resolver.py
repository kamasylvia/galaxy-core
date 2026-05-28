"""证券输入解析模块."""

from galaxy_db_sync.shared_kernel.enums.security_type import SecurityType
from galaxy_db_sync.shared_kernel.utils.symbol_validator import (
    validate_symbol_format,
    normalize_symbol,
)
from galaxy_db_sync.shared_kernel.utils.symbol_type_inference import (
    filter_most_precise_security_types,
)
import logging
from typing import List, Tuple


def parse_symbols(value: str) -> list[tuple[str, str]]:
    """解析 symbols 参数.

    支持格式:
    - 单代码: "600000.SH" 或 "600000" (自动补全后缀)
    - 列表: "[600000.SH, 000001.SZ]" 或 "600000,000001"
    - SecurityType: "SH_A", "SZ_ETF" 等
    - 混合列表: "[600000, SH_ETF]" (代码和SecurityType混合)
    """
    value = value.strip()

    # 检查是否是列表格式 [symbol1, symbol2, ...]
    if value.startswith("[") and value.endswith("]"):
        content = value[1:-1].strip()
        if not content:
            return []
        items = [s.strip() for s in content.split(",") if s.strip()]
    else:
        items = [s.strip() for s in value.split(",") if s.strip()]

    # 验证每个项目的格式
    for item in items:
        if not validate_symbol_format(item):
            raise ValueError(
                f"无效的证券代码格式: {item}。支持的格式：6位数字、SecurityType、"
                "6位数字带合法后缀(.SH/.SZ/.BJ)、期货代码带.FUTURE后缀或期权代码带.OPTION后缀"
            )

    # 检查是否包含 SecurityType
    security_type_names = {sec_type.name for sec_type in SecurityType}

    result: list[tuple[str, str]] = []
    for item in items:
        if item in security_type_names:
            result.append(("security_type", item))
        else:
            normalized = normalize_symbol(item)
            result.append(("symbol", normalized))

    return result


def get_valid_symbols_from_input(
    input_list: List[str], start_date: str = "20200101", end_date: str = "20301231"
) -> List[str]:
    """
    从输入列表获取有效的证券代码列表。

    对于 SecurityType 的入参，先过滤出最精确的 SecurityType 以减少 API 调用，
    然后传入 get_hist_code_list 获得代码列表。
    对于非 SecurityType 的代码，进行初筛。

    Args:
        input_list: 输入的证券代码列表，可能包含 SecurityType 或普通代码
        start_date: 开始日期，用于获取 SecurityType 的历史代码列表
        end_date: 结束日期，用于获取 SecurityType 的历史代码列表

    Returns:
        List[str]: 有效的证券代码列表
    """
    security_type_names = {sec_type.name for sec_type in SecurityType}

    security_types = []
    normal_symbols = []

    # 分离 SecurityType 和普通代码
    for item in input_list:
        if item in security_type_names:
            security_types.append(item)
        else:
            if validate_symbol_format(item):
                normalized = normalize_symbol(item)
                normal_symbols.append(normalized)

    # 对 SecurityType 进行层级检测，选出最精确的类型
    precise_security_types = filter_most_precise_security_types(security_types)

    # 获取 SecurityType 对应的代码列表
    security_type_codes = []
    if precise_security_types:
        # 动态导入，避免循环导入
        from galaxy_db_sync.amazing_data.api.client import amazing_data_client
        from galaxy_db_sync.shared_kernel.utils.config_loader import get_section
        from galaxy_db_sync.shared_kernel.utils.time_parser import convert_date_string_to_int
        from datetime import datetime, timedelta

        amazing_data_config = get_section("amazing_data")
        local_path = amazing_data_config.get("local_path", "./cache")

        for sec_type in precise_security_types:
            try:
                # 转换日期格式
                if start_date and len(start_date) <= 4:
                    start_int = int(start_date[:4]) * 10000 + 101
                else:
                    start_int = (
                        convert_date_string_to_int(start_date, "day", is_end_date=False)
                        if start_date
                        else 20200101
                    )

                if end_date:
                    end_int = convert_date_string_to_int(end_date, "day", is_end_date=True)
                else:
                    yesterday = datetime.now() - timedelta(days=1)
                    end_int = int(yesterday.strftime("%Y%m%d"))

                logging.info(
                    f"get_hist_code_list 调用参数: security_type={sec_type}, "
                    f"start_date={start_int}, end_date={end_int}, local_path={local_path}"
                )

                codes = amazing_data_client.get_hist_code_list(
                    security_type=sec_type,
                    start_date=start_int,
                    end_date=end_int,
                    local_path=local_path,
                )
                security_type_codes.extend(codes)
                logging.info(f"通过 {sec_type} 获取到 {len(codes)} 个代码")
            except Exception as e:
                logging.warning(f"获取 {sec_type} 的代码列表时出错: {e}")

    # 合并所有代码列表并去重
    all_codes = list(set(normal_symbols + security_type_codes))

    return all_codes