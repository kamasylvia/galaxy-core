"""CLI/Scheduler 公共预处理模块.

提供 resolve_symbols() 和 prepare_sync_args() 两个核心函数，
统一 CLI 和 Scheduler 的 symbol 解析与日期预处理逻辑 (D-05, D-09)。
"""

import logging
from datetime import date
from pathlib import Path

from galaxy_core.domain.date_range.parser import expand_date_to_full
from galaxy_core.domain.ports.reference_provider import ReferenceProviderPort
from galaxy_core.domain.value_objects import Interval as DomainInterval
from galaxy_core.shared_kernel.enums.security_type import SecurityType
from galaxy_core.shared_kernel.utils.config_loader import get_section

logger = logging.getLogger(__name__)


async def resolve_symbols(
    input_list: list[str],
    reference_provider: ReferenceProviderPort,
    end_date: date,
    local_path: str | None = None,
) -> list[str]:
    """统一 symbol 解析 — 二段逻辑：SecurityType -> get_hist_code_list，具体 symbol 直接保留.

    Args:
        input_list: 输入列表，可包含 SecurityType 名称（如 "SH_A"）或具体 symbol（如 "600000.SH"）
        reference_provider: 参考数据提供者端口
        end_date: 结束日期，用于 get_hist_code_list(T-1, T-1) 过滤退市
        local_path: SDK 本地缓存路径，None 时从配置读取

    Returns:
        去重后的 symbol 列表
    """
    if local_path is None:
        raw_cache = get_section("amazing_data").get("local_path", "./data/local_cache/")
        local_path = str(Path(raw_cache).resolve())
        if raw_cache.endswith("/"):
            local_path += "/"
    security_type_names = {sec_type.name for sec_type in SecurityType}

    security_types: list[str] = []
    normal_symbols: list[str] = []

    for item in input_list:
        if item in security_type_names:
            security_types.append(item)
        else:
            normal_symbols.append(item)

    if not security_types:
        return normal_symbols

    expanded: list[str] = []
    date_int = int(end_date.strftime("%Y%m%d"))

    for sec_type in security_types:
        try:
            codes = await reference_provider.get_hist_code_list(
                security_type=sec_type,
                start_date=date_int,
                end_date=date_int,
                local_path=local_path,
            )
            expanded.extend(codes)
            logger.info(f"{sec_type} 展开为 {len(codes)} 只")
        except Exception as e:
            logger.warning(f"展开 {sec_type} 失败: {e}")

    all_codes = list(set(normal_symbols + expanded))
    return all_codes


def prepare_sync_args(
    interval: str,
    start: str | None,
    end: str | None,
) -> tuple[DomainInterval, str | None, str | None]:
    """统一 Interval 转换 + 日期展开.

    Args:
        interval: 周期字符串（如 "day", "min1", "year"）
        start: 开始日期字符串，None 时不展开
        end: 结束日期字符串，None 时不展开

    Returns:
        (domain Interval, 展开后 start, 展开后 end)
    """
    domain_interval = DomainInterval(interval)

    if start is not None:
        start = expand_date_to_full(start, interval, is_end=False)
    if end is not None:
        end = expand_date_to_full(end, interval, is_end=True)

    return domain_interval, start, end
