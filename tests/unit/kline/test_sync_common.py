"""sync_common 公共预处理函数单元测试.

测试 resolve_symbols() 和 prepare_sync_args() 的全部行为：
- resolve_symbols: 具体 symbol 直接保留、SecurityType 调用 get_hist_code_list、
  混合输入去重、空输入、API 失败不中断、多 SecurityType 合并
- prepare_sync_args: day/year interval 展开、None start/end、无效 interval
"""

from datetime import date
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from galaxy_core.application.kline.sync_common import (
    prepare_sync_args,
    resolve_symbols,
)


# ---------------------------------------------------------------------------
# resolve_symbols 测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_symbols_concrete_symbols_no_api_call():
    """具体 symbol 输入直接返回，get_hist_code_list 不被调用."""
    reference_provider = MagicMock()
    reference_provider.get_hist_code_list = AsyncMock()

    result = await resolve_symbols(
        ["600000.SH", "000001.SZ"],
        reference_provider,
        end_date=date(2025, 3, 28),
    )

    assert result == ["600000.SH", "000001.SZ"]
    reference_provider.get_hist_code_list.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_symbols_security_type_calls_get_hist_code_list():
    """SecurityType 输入调用 get_hist_code_list(T-1, T-1) 获取列表."""
    reference_provider = MagicMock()
    reference_provider.get_hist_code_list = AsyncMock(
        return_value=["600000.SH", "601398.SH"]
    )

    result = await resolve_symbols(
        ["SH_A"],
        reference_provider,
        end_date=date(2025, 3, 28),
    )

    reference_provider.get_hist_code_list.assert_called_once_with(
        security_type="SH_A",
        start_date=20250328,
        end_date=20250328,
        local_path=ANY,
    )
    assert "600000.SH" in result
    assert "601398.SH" in result


@pytest.mark.asyncio
async def test_resolve_symbols_mixed_input():
    """混合输入：具体 symbol 保留 + SecurityType 展开."""
    reference_provider = MagicMock()
    reference_provider.get_hist_code_list = AsyncMock(
        return_value=["600000.SH", "601398.SH"]
    )

    result = await resolve_symbols(
        ["600000.SH", "SH_A"],
        reference_provider,
        end_date=date(2025, 3, 28),
    )

    # 具体 symbol 600000.SH 保留 + SH_A 展开
    assert "600000.SH" in result
    assert "601398.SH" in result
    reference_provider.get_hist_code_list.assert_called_once_with(
        security_type="SH_A",
        start_date=20250328,
        end_date=20250328,
        local_path=ANY,
    )


@pytest.mark.asyncio
async def test_resolve_symbols_empty_input():
    """空输入返回空列表."""
    reference_provider = MagicMock()
    reference_provider.get_hist_code_list = AsyncMock()

    result = await resolve_symbols(
        [],
        reference_provider,
        end_date=date(2025, 3, 28),
    )

    assert result == []
    reference_provider.get_hist_code_list.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_symbols_api_failure_continues():
    """get_hist_code_list 抛异常时返回已有 normal_symbols，不中断."""
    reference_provider = MagicMock()
    reference_provider.get_hist_code_list = AsyncMock(
        side_effect=Exception("API error")
    )

    result = await resolve_symbols(
        ["600000.SH", "SH_A"],
        reference_provider,
        end_date=date(2025, 3, 28),
    )

    # API 失败但具体 symbol 仍保留
    assert "600000.SH" in result


@pytest.mark.asyncio
async def test_resolve_symbols_deduplication():
    """混合输入去重：具体 symbol 和展开结果重叠时只保留一个."""
    reference_provider = MagicMock()
    # get_hist_code_list 返回包含 600000.SH 的列表，与具体 symbol 重叠
    reference_provider.get_hist_code_list = AsyncMock(
        return_value=["600000.SH", "601398.SH"]
    )

    result = await resolve_symbols(
        ["600000.SH", "SH_A"],
        reference_provider,
        end_date=date(2025, 3, 28),
    )

    # 600000.SH 只出现一次
    assert result.count("600000.SH") == 1
    assert "601398.SH" in result


@pytest.mark.asyncio
async def test_resolve_symbols_multiple_security_types():
    """多个 SecurityType 输入：两次 get_hist_code_list 调用，结果合并."""
    reference_provider = MagicMock()
    reference_provider.get_hist_code_list = AsyncMock(
        side_effect=[
            ["600000.SH", "601398.SH"],
            ["000001.SZ", "000002.SZ"],
        ]
    )

    result = await resolve_symbols(
        ["SH_A", "SZ_A"],
        reference_provider,
        end_date=date(2025, 3, 28),
    )

    assert reference_provider.get_hist_code_list.call_count == 2
    assert "600000.SH" in result
    assert "000001.SZ" in result


# ---------------------------------------------------------------------------
# prepare_sync_args 测试
# ---------------------------------------------------------------------------


def test_prepare_sync_args_day_interval():
    """day interval + start/end 展开."""
    domain_interval, expanded_start, expanded_end = prepare_sync_args(
        interval="day",
        start="20230101",
        end="20231231",
    )

    assert domain_interval.value == "day"
    assert expanded_start == "20230101"
    assert expanded_end == "20231231"


def test_prepare_sync_args_year_interval():
    """year interval + 4 位 start 展开为完整日期."""
    domain_interval, expanded_start, expanded_end = prepare_sync_args(
        interval="year",
        start="2023",
        end=None,
    )

    assert domain_interval.value == "year"
    assert expanded_start == "20230101"
    assert expanded_end is None


def test_prepare_sync_args_none_start():
    """start=None 时返回 None，不展开."""
    domain_interval, expanded_start, expanded_end = prepare_sync_args(
        interval="day",
        start=None,
        end="20231231",
    )

    assert expanded_start is None
    assert expanded_end == "20231231"


def test_prepare_sync_args_none_end():
    """end=None 时返回 None，不展开."""
    domain_interval, expanded_start, expanded_end = prepare_sync_args(
        interval="day",
        start="20230101",
        end=None,
    )

    assert expanded_start == "20230101"
    assert expanded_end is None


def test_prepare_sync_args_invalid_interval():
    """无效 interval 抛 ValueError."""
    with pytest.raises(ValueError):
        prepare_sync_args(
            interval="invalid",
            start="20230101",
            end="20231231",
        )
