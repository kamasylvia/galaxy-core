"""TimescaleDB 集成测试."""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_timescale_hypertables_exist(db_manager):
    """测试 TimescaleDB hypertables 存在."""
    async with db_manager.session() as session:
        result = await session.execute(
            text(
                "SELECT hypertable_name FROM timescaledb_information.hypertables "
                "ORDER BY hypertable_name"
            )
        )
        tables = [row[0] for row in result.fetchall()]
        assert "kline_day" in tables, f"kline_day 未找到，现有 hypertables: {tables}"
        assert "kline_min1" in tables, f"kline_min1 未找到，现有 hypertables: {tables}"
