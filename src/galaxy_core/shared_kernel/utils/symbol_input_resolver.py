"""证券输入解析模块."""

from galaxy_core.shared_kernel.enums.security_type import SecurityType
from galaxy_core.shared_kernel.utils.symbol_validator import (
    validate_symbol_format,
    normalize_symbol,
)
from galaxy_core.shared_kernel.utils.symbol_type_inference import (
    filter_most_precise_security_types,
)
from galaxy_core.domain.symbol.resolver import parse_symbols
import logging
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from galaxy_core.amazing_data.api.client import AmazingDataClient

__all__ = ["parse_symbols", "get_valid_symbols_from_input"]


def get_valid_symbols_from_input(
    input_list: List[str],
    client: "AmazingDataClient",
    start_date: str = "20200101",
    end_date: str = "20301231",
) -> List[str]:
    """
    从输入列表获取有效的证券代码列表。

    对于 SecurityType 的入参，先过滤出最精确的 SecurityType 以减少 API 调用，
    然后传入 get_stock_list 获得当前活跃代码列表。
    对于非 SecurityType 的代码，进行初筛。

    Args:
        input_list: 输入的证券代码列表，可能包含 SecurityType 或普通代码
        client: AmazingDataClient 实例（通过 DI 注入）
        start_date: 保留参数（兼容性），不再使用
        end_date: 保留参数（兼容性），不再使用

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
        for sec_type in precise_security_types:
            try:
                logging.info(f"get_stock_list 调用参数: security_type={sec_type}")

                df = client.get_stock_list(security_type=sec_type)
                codes = df.index.tolist() if df is not None and not df.empty else []
                security_type_codes.extend(codes)
                logging.info(f"通过 {sec_type} 获取到 {len(codes)} 个代码")
            except Exception as e:
                logging.warning(f"获取 {sec_type} 的代码列表时出错: {e}")

    # 合并所有代码列表并去重
    all_codes = list(set(normal_symbols + security_type_codes))

    return all_codes
