"""增量同步范围解析 mixin(Phase 1&2 表共用,03-03).

job 继承本 mixin,通过 self._last_sync_store(LastSyncDateStore 实例)解析
增量 [begin, end] 区间。统一逻辑:
- last 存在 → begin = last + 1 day(正常增量)
- last None(空表首次) → begin = first_sync_date(默认 DEFAULT_FIRST_SYNC_DATE=20130101)
- end = today(YYYYMMDD)

设计要点:
- 不依赖具体 store 实现,仅约定 self._last_sync_store.get_last_sync_date(sync_type, scope_key)
- _max_date_from_records 空记录返 None,调用方据此不调 set_last_sync_date(D-08)
"""

from datetime import date, timedelta


class IncrementalSyncMixin:
    """增量同步范围解析 mixin。

    要求子类提供 `self._last_sync_store`(LastSyncDateStore 实例)。
    """

    async def _resolve_incremental_range(
        self,
        sync_type: str,
        scope_key: str | None,
        today: date,
        first_sync_date: int | None = None,
    ) -> tuple[int, int]:
        """解析增量 [begin, end] 区间。

        Args:
            sync_type: 数据类标识(index_weight/long_hu_bang/akshare_sector_fund_flow/...)
            scope_key: natural key(index_code/market_code/channel);全市场汇总表 None
            today: 当天日期
            first_sync_date: 空表首次起点(默认 DEFAULT_FIRST_SYNC_DATE=20130101)

        Returns:
            (begin, end) 两个 YYYYMMDD int。begin = last+1 或 first_sync_date,
            end = today。
        """
        from galaxy_core.shared_kernel.utils.constants import (
            DEFAULT_FIRST_SYNC_DATE,
        )

        if first_sync_date is None:
            first_sync_date = DEFAULT_FIRST_SYNC_DATE
        end = int(today.strftime("%Y%m%d"))
        last = await self._last_sync_store.get_last_sync_date(sync_type, scope_key)
        if last is not None:
            begin = int((last + timedelta(days=1)).strftime("%Y%m%d"))
        else:
            begin = first_sync_date
        return begin, end

    @staticmethod
    def _max_date_from_records(
        records: list, date_attr: str = "trade_date"
    ) -> date | None:
        """从 records 找 MAX date。

        空 records 或全 None → None(调用方据此不调 set_last_sync_date,D-08)。

        Args:
            records: 值对象列表(如 AkshareSectorFundFlow / LongHuBang)
            date_attr: 日期属性名(默认 trade_date;部分表用 date/index_code 等)

        Returns:
            max date 或 None
        """
        if not records:
            return None
        dates = [
            getattr(r, date_attr)
            for r in records
            if getattr(r, date_attr, None) is not None
        ]
        return max(dates) if dates else None
