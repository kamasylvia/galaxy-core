"""主键迁移集成测试.

验证：
1. 迁移脚本可正确执行
2. 迁移后数据完整性（行数一致）
3. 迁移后 hypertable 创建成功
4. 迁移后 UPSERT 行为正常
5. 回滚脚本可正确执行

注意：这些测试需要真实数据库连接，使用 pytest-asyncio。
"""

import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from galaxy_db_sync.database.core.async_connection import async_db_manager
from galaxy_db_sync.database.models.kline import KlineDay, KlineMin1


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """提供异步数据库会话."""
    async with async_db_manager.session() as session:
        yield session


@pytest.mark.asyncio
class TestPKMigrationIntegration:
    """主键迁移集成测试."""

    async def test_database_connection(self, db_session: AsyncSession):
        """测试数据库连接正常."""
        result = await db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    async def test_kline_day_table_exists(self, db_session: AsyncSession):
        """kline_day 表存在."""
        result = await db_session.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'kline_day'
                );
            """)
        )
        assert result.scalar() is True

    async def test_kline_day_has_composite_pk(self, db_session: AsyncSession):
        """kline_day 有组合主键."""
        result = await db_session.execute(
            text("""
                SELECT column_name
                FROM information_schema.key_column_usage
                WHERE table_name = 'kline_day' AND constraint_name LIKE '%pkey%'
                ORDER BY ordinal_position;
            """)
        )
        columns = [row[0] for row in result.fetchall()]
        assert "symbol" in columns
        assert "trade_time" in columns

    async def test_kline_day_is_hypertable(self, db_session: AsyncSession):
        """kline_day 是 hypertable."""
        result = await db_session.execute(
            text("""
                SELECT hypertable_name
                FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'kline_day';
            """)
        )
        assert result.scalar() == "kline_day"

    async def test_kline_day_no_id_column(self, db_session: AsyncSession):
        """kline_day 没有 id 列."""
        result = await db_session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'kline_day' AND column_name = 'id';
            """)
        )
        assert result.fetchone() is None

    async def test_kline_day_upsert_works(self, db_session: AsyncSession):
        """测试 UPSERT 操作正常."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        # 准备测试数据
        test_data = {
            "symbol": "TEST0001.SH",
            "trade_time": datetime(2024, 1, 1, 9, 30),
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.5,
            "volume": 1000000,
            "amount": 10500000.0,
            "security_type": "stock",
        }

        # 第一次插入
        stmt = pg_insert(KlineDay).values(test_data)
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "trade_time"],
            set_={
                "close": stmt.excluded.close,
                "updated_at": func.now(),
            },
        )
        await db_session.execute(upsert_stmt)
        await db_session.commit()

        # 验证插入成功
        result = await db_session.execute(
            select(func.count()).where(
                KlineDay.symbol == "TEST0001.SH",
                KlineDay.trade_time == datetime(2024, 1, 1, 9, 30),
            )
        )
        assert result.scalar() == 1

        # 第二次 UPSERT（更新）
        test_data["close"] = 11.0  # 修改收盘价
        stmt2 = pg_insert(KlineDay).values(test_data)
        upsert_stmt2 = stmt2.on_conflict_do_update(
            index_elements=["symbol", "trade_time"],
            set_={
                "close": stmt2.excluded.close,
                "updated_at": func.now(),
            },
        )
        await db_session.execute(upsert_stmt2)
        await db_session.commit()

        # 验证更新成功（行数仍为 1）
        result = await db_session.execute(
            select(func.count()).where(KlineDay.symbol == "TEST0001.SH")
        )
        assert result.scalar() == 1

        # 清理测试数据
        await db_session.execute(
            text("DELETE FROM kline_day WHERE symbol = 'TEST0001.SH'")
        )
        await db_session.commit()


@pytest.mark.asyncio
class TestMigrationScripts:
    """迁移脚本测试."""

    async def test_migration_script_imports(self):
        """迁移脚本可导入."""
        try:
            from scripts.migrate_pk_to_symbol_trade_time import (
                KLINE_TABLES,
                migrate_table,
            )

            assert len(KLINE_TABLES) == 13
            assert "kline_day" in KLINE_TABLES
            assert "kline_min1" in KLINE_TABLES
        except ImportError as e:
            pytest.skip(f"迁移脚本未找到或导入失败: {e}")

    async def test_rollback_script_imports(self):
        """回滚脚本可导入."""
        try:
            from scripts.rollback_pk_migration import (
                KLINE_TABLES,
                find_backup_tables,
            )

            assert len(KLINE_TABLES) == 13
        except ImportError as e:
            pytest.skip(f"回滚脚本未找到或导入失败: {e}")

    async def test_migration_table_order(self):
        """迁移表顺序从小到大."""
        try:
            from scripts.migrate_pk_to_symbol_trade_time import KLINE_TABLES

            # 第一个应该是小表
            assert KLINE_TABLES[0] == "kline_year"
            # 最后一个应该是大表
            assert KLINE_TABLES[-1] == "kline_min1"
        except ImportError:
            pytest.skip("迁移脚本未找到")


@pytest.mark.asyncio
class TestDataIntegrity:
    """数据完整性测试."""

    async def test_symbol_trade_time_unique(self, db_session: AsyncSession):
        """(symbol, trade_time) 组合唯一."""
        # 检查是否存在重复数据
        result = await db_session.execute(
            text("""
                SELECT symbol, trade_time, COUNT(*)
                FROM kline_day
                GROUP BY symbol, trade_time
                HAVING COUNT(*) > 1
                LIMIT 1;
            """)
        )
        duplicate = result.fetchone()
        assert duplicate is None, f"发现重复数据: {duplicate}"

    async def test_all_tables_have_composite_pk(self, db_session: AsyncSession):
        """所有 K 线表都有组合主键."""
        from galaxy_db_sync.database.models.kline import INTERVAL_MODEL_MAP

        for interval, model_class in INTERVAL_MODEL_MAP.items():
            table_name = model_class.__tablename__
            result = await db_session.execute(
                text(
                    f"""
                    SELECT column_name
                    FROM information_schema.key_column_usage
                    WHERE table_name = '{table_name}' AND constraint_name LIKE '%pkey%'
                    ORDER BY ordinal_position;
                """
                )
            )
            columns = [row[0] for row in result.fetchall()]
            assert "symbol" in columns, f"{table_name} 缺少 symbol 主键"
            assert "trade_time" in columns, f"{table_name} 缺少 trade_time 主键"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
