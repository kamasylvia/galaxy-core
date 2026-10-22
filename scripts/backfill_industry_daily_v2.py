#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""backfill_industry_daily_v2 — 绕过 job 链,raw client 小批小窗回填行业日行情.

背景:2026-08-27 排查,7/9 起 industry_daily 断档。AM 服务端数据完好
(单批≤20 codes、窗口≤25 自然日稳定返回),但 CLI/job 进程内调用始终
空返(根因待查,见 HISTORY)。本脚本独立进程直连 SDK + 直写 DB。

用法: uv run scripts/backfill_industry_daily_v2.py [beginYYYYMMDD endYYYYMMDD]
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("backfill")

import pandas as pd  # noqa: E402
from galaxy_core.shared_kernel.utils.infisical_config import get_env  # noqa: E402

GAL_DSN = (
    f"host={get_env('DB_HOST')} port={get_env('DB_PORT', '5432')} "
    f"dbname={get_env('DB_NAME', 'galaxy')} user={get_env('DB_USER')} "
    f"password={get_env('DB_PASSWORD')}"
)


def parse_df_to_rows(df: pd.DataFrame, index_code: str) -> list[tuple]:
    """SDK df(index=日期,列名大写 API 字段)→ 行元组(按 行业日行情 实际列序).

    列: index_code, trade_date, open, high, low, close, pre_close,
        volume, amount, pb, pe, total_cap, a_float_cap
    """
    d = df.reset_index()
    date_col = d.columns[0]

    def f(col):
        v = r.get(col)
        return float(v) if pd.notna(v) else None

    rows = []
    for _, r in d.iterrows():
        rows.append(
            (
                index_code,
                pd.to_datetime(r[date_col]).date(),
                f("OPEN"), f("HIGH"), f("LOW"), f("CLOSE"),
                f("PRE_CLOSE"),
                f("VOLUME"), f("AMOUNT"),
                f("PB"), f("PE"),
                f("TOTAL_SHARES"), f("FREE_SHARES"),
            )
        )
    return rows


async def main():
    import psycopg2
    from psycopg2.extras import execute_values

    begin = int(sys.argv[1]) if len(sys.argv) > 1 else 20260710
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 20260827

    from datetime import date, timedelta

    # 窗口切段(25 自然日)
    segs = []
    cur = date(begin // 10000, begin // 100 % 100, begin % 100)
    stop = date(end // 10000, end // 100 % 100, end % 100)
    while cur <= stop:
        se = min(cur + timedelta(days=24), stop)
        segs.append((cur.strftime("%Y%m%d"), se.strftime("%Y%m%d")))
        cur = se + timedelta(days=1)

    from galaxy_core.amazing_data.api.client import AmazingDataClient

    client = AmazingDataClient()
    await asyncio.to_thread(
        client.initialize,
        get_env("GALAXY_USERNAME"),
        get_env("GALAXY_PASSWORD"),
        get_env("GALAXY_HOST"),
        int(get_env("GALAXY_PORT", "8600")),
    )
    bi = await asyncio.to_thread(client.get_industry_base_info, local_path="./data/local_cache/", is_local=False)
    codes_all = sorted(set(bi["INDEX_CODE"].tolist()))
    log.info(f"codes={len(codes_all)} segs={len(segs)} range={begin}~{end}")

    conn = psycopg2.connect(GAL_DSN)
    total_saved = 0
    seen_dates = set()
    # 并发度 1(SDK 不并发);每段逐批
    for b, e in segs:
        for i in range(0, len(codes_all), 20):
            chunk = codes_all[i : i + 20]
            try:
                res = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.get_industry_daily, code_list=chunk,
                        local_path="./data/local_cache/", is_local=False,
                        begin_date=int(b), end_date=int(e),
                    ), timeout=90)
            except BaseException as exc:
                log.warning(f"{b}~{e} batch{i}: {type(exc).__name__}")
                await asyncio.sleep(3)
                continue
            n = sum(len(v) for v in res.values())
            if n == 0:
                log.warning(f"{b}~{e} batch{i//20}: EMPTY")
                continue
            sql_rows = []
            for ic, df in res.items():
                sql_rows.extend(parse_df_to_rows(df, ic))
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    '''INSERT INTO "行业日行情"
                       (index_code, trade_date, open, high, low, close, pre_close,
                        volume, amount, pb, pe, total_cap, a_float_cap)
                       VALUES %s
                       ON CONFLICT (index_code, trade_date) DO UPDATE SET
                         open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                         close=EXCLUDED.close, volume=EXCLUDED.volume,
                         amount=EXCLUDED.amount, pre_close=EXCLUDED.pre_close,
                         pb=EXCLUDED.pb, pe=EXCLUDED.pe, total_cap=EXCLUDED.total_cap,
                         a_float_cap=EXCLUDED.a_float_cap, updated_at=now()''',
                    sql_rows,
                    page_size=500,
                )
            conn.commit()
            total_saved += len(sql_rows)
            for r in sql_rows:
                seen_dates.add(str(r[1]))
            log.info(f"{b}~{e} batch{i//20}: {len(sql_rows)} 行入库")
    log.info(f"DONE total_saved={total_saved} dates={min(seen_dates) if seen_dates else '-'}~{max(seen_dates) if seen_dates else '-'}")
    conn.close()


asyncio.run(main())
