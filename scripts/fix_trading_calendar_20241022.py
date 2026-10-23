#!/usr/bin/env python3
"""一次性修复 trading_calendar Fri/Sun 互换(2026-10-22)。

根因:某次全量重写把 is_trading_day 写偏(Fri↔Sun 互换,2024-01 起整表)。
以 akshare tool_trade_date_hist_sina 为真相源,按日期 UPDATE 标志位。
只改 is_trading_day,不动其他列。改完对账:周五全 t、周日全 f。
"""

import asyncio

import asyncpg
import pandas as pd

import akshare as ak
from galaxy_core.shared_kernel.utils.infisical_config import get_env


async def main() -> int:
    df = ak.tool_trade_date_hist_sina()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    truth = set(df["trade_date"].tolist())
    print(f"akshare 真相源: {len(truth)} 个交易日")

    conn = await asyncpg.connect(
        host=get_env("DB_HOST", "127.0.0.1"),
        port=int(get_env("DB_PORT", "5432")),
        database=get_env("DB_NAME", "galaxy"),
        user=get_env("DB_USER"),
        password=get_env("DB_PASSWORD"),
    )
    try:
        rows = await conn.fetch("SELECT trade_date FROM trading_calendar")
        n_fix = 0
        for r in rows:
            d = r["trade_date"]
            # date 列读出可能是 date 或 aware datetime
            if hasattr(d, "date"):
                d = d.date()
            want = d in truth
            cur = await conn.fetchval(
                "SELECT is_trading_day FROM trading_calendar WHERE trade_date = $1", d
            )
            if cur != want:
                await conn.execute(
                    "UPDATE trading_calendar SET is_trading_day = $1 WHERE trade_date = $2",
                    want, d,
                )
                n_fix += 1
        print(f"修正 {n_fix} 行")
        # 对账
        bad_fri = await conn.fetchval(
            "SELECT count(*) FROM trading_calendar "
            "WHERE to_char(trade_date,'Dy')='Fri' AND is_trading_day = false"
        )
        bad_sun = await conn.fetchval(
            "SELECT count(*) FROM trading_calendar "
            "WHERE to_char(trade_date,'Dy')='Sun' AND is_trading_day = true"
        )
        print(f"残留: 周五标f={bad_fri}, 周日标t={bad_sun}")
        return 0 if (bad_fri == 0 and bad_sun == 0) else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
