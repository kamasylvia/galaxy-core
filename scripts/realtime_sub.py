import asyncio
import logging
import signal
import sys
import threading
from collections import defaultdict
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("realtime_sub")

PERIODS = ["min1", "min3", "min5", "min10", "min15", "min30", "min60", "min120"]
FLUSH_SECONDS = 10
_running = True


def _handle_signal(signum, frame):
    global _running
    log.info(f"收到信号 {signum},准备退出")
    _running = False


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def get_universe() -> list[str]:
    """7221 只(A 股+北交,去 ETF/LOF)+ 指数,用 stock_basic 现表."""
    import asyncpg

    from galaxy_core.shared_kernel.utils.infisical_config import get_env

    async def _fetch():
        conn = await asyncpg.connect(
            host=get_env("DB_HOST", "127.0.0.1"),
            port=int(get_env("DB_PORT", "5432")),
            database=get_env("DB_NAME", "galaxy"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
        )
        try:
            rows = await conn.fetch(
                "SELECT symbol FROM stock_basic"
                " WHERE symbol NOT LIKE '159%' AND symbol NOT LIKE '511%'"
                " AND symbol NOT LIKE '512%' AND symbol NOT LIKE '513%'"
            )
            return [r["symbol"] for r in rows]
        finally:
            await conn.close()

    return asyncio.run(_fetch())


def is_trading_day() -> bool:
    """今日是否交易日(查 trading_calendar,失败默认是,宁可空跑)。"""
    import asyncpg

    from galaxy_core.shared_kernel.utils.infisical_config import get_env

    async def _check():
        conn = await asyncpg.connect(
            host=get_env("DB_HOST", "127.0.0.1"),
            port=int(get_env("DB_PORT", "5432")),
            database=get_env("DB_NAME", "galaxy"),
            user=get_env("DB_USER"),
            password=get_env("DB_PASSWORD"),
        )
        try:
            row = await conn.fetchrow(
                "SELECT 1 FROM trading_calendar WHERE trade_date = CURRENT_DATE"
            )
            return row is not None
        finally:
            await conn.close()

    try:
        return asyncio.run(_check())
    except Exception as e:
        log.warning(f"交易日历查询失败,默认按交易日跑: {e}")
        return True


class BarBuffer:
    """回调攒批:period → list[KlineBar],定时 flush upsert."""

    def __init__(self):
        self._lock = threading.Lock()
        self._bufs: dict[str, list] = defaultdict(list)

    def add(self, period: str, bar) -> None:
        with self._lock:
            self._bufs[period].append(bar)

    def drain(self) -> dict[str, list]:
        with self._lock:
            out = dict(self._bufs)
            self._bufs = defaultdict(list)
            return out


async def _upsert_batch(period: str, bars: list) -> int:
    """一批 bar upsert 对应分钟表(is_final=false)。"""
    from galaxy_core.database.core.async_connection import AsyncDatabaseManager
    from galaxy_core.database.services.adapters.kline_store_adapter import KlineStoreAdapter
    from galaxy_core.domain.value_objects import Interval, KlineBar, SecurityType

    interval = Interval(period)
    kline_bars = []
    for b in bars:
        # SDK OnKLine 回调对象: code/trade_time/open/high/low/close/volume/amount
        code = getattr(b, "code", None) or b.get("code")
        tt = getattr(b, "trade_time", None) or b.get("trade_time")
        if isinstance(tt, str):
            tt = datetime.fromisoformat(tt)
        kline_bars.append(
            KlineBar(
                symbol=code,
                trade_time=tt,
                open=getattr(b, "open", None) if not isinstance(b, dict) else b.get("open"),
                high=getattr(b, "high", None) if not isinstance(b, dict) else b.get("high"),
                low=getattr(b, "low", None) if not isinstance(b, dict) else b.get("low"),
                close=getattr(b, "close", None) if not isinstance(b, dict) else b.get("close"),
                volume=getattr(b, "volume", None) if not isinstance(b, dict) else b.get("volume"),
                amount=getattr(b, "amount", None) if not isinstance(b, dict) else b.get("amount"),
                security_type=SecurityType.EXTRA_STOCK_A,
                is_final=False,
            )
        )
    mgr = AsyncDatabaseManager()
    mgr.initialize()
    try:
        adapter = KlineStoreAdapter(mgr)
        await adapter.save_kline(kline_bars, interval)
    finally:
        await mgr.close()
    return len(kline_bars)


def _flusher(buf: BarBuffer, stop_event: threading.Event):
    """后台线程:每 FLUSH_SECONDS drain 全 period upsert。"""
    while not stop_event.is_set():
        stop_event.wait(FLUSH_SECONDS)
        batches = buf.drain()
        total = sum(len(v) for v in batches.values())
        if not total:
            continue
        for period, bars in batches.items():
            if not bars:
                continue
            try:
                n = asyncio.run(_upsert_batch(period, bars))
                log.info(f"flush {period}: {n} bars (is_final=false)")
            except Exception as e:
                log.error(f"flush {period} 失败({len(bars)} bars 丢弃): {e}")


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    if not dry_run and not is_trading_day():
        log.info("今日非交易日,直接退出")
        return 0

    universe = get_universe()
    log.info(f"universe: {len(universe)} 只")
    if not universe:
        log.error("universe 为空,退出")
        return 1

    buf = BarBuffer()
    stop_event = threading.Event()
    flusher = threading.Thread(target=_flusher, args=(buf, stop_event), daemon=True)
    flusher.start()

    if dry_run:
        # mock bar 验证 DB 写入路径
        log.info("dry-run: 写入 1 条 mock bar 验证路径")
        mock_bar = {
            "code": universe[0],
            "trade_time": datetime.now().replace(second=0, microsecond=0),
            "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2,
            "volume": 1000, "amount": 10200.0,
        }
        n = asyncio.run(_upsert_batch("min1", [mock_bar]))
        log.info(f"dry-run 写入 {n} 条,完成")
        stop_event.set()
        return 0

    import AmazingData as ad

    from galaxy_core.shared_kernel.utils.infisical_config import get_env

    ad.login(
        username=get_env("GALAXY_USERNAME"),
        password=get_env("GALAXY_PASSWORD"),
        host=get_env("GALAXY_HOST"),
        port=int(get_env("GALAXY_PORT", "8100")),
    )
    sub_data = ad.SubscribeData()

    for period in PERIODS:
        period_value = getattr(ad.constant.Period, period).value

        def make_handler(p):
            def on_kline(data, _period):
                # data 可能是单个 Kline 或 list
                items = data if isinstance(data, list) else [data]
                for item in items:
                    buf.add(p, item)

            on_kline.__name__ = f"on_kline_{p}"
            return on_kline

        sub_data.register(code_list=universe, period=period_value)(make_handler(period))
        log.info(f"已订阅 {period} ({len(universe)} 只)")

    log.info("订阅启动,9:00–15:30 常驻 (Ctrl-C 或信号退出)")
    try:
        sub_data.run()  # 阻塞直到信号/异常
    finally:
        stop_event.set()
    return 0 if not _running else 0


if __name__ == "__main__":
    sys.exit(main())
