"""共享常量.

- DEFAULT_FIRST_SYNC_DATE — Phase 03(03-03)Phase 1&2 表增量同步空表首次起点。
- CST / now_cst / localize_cst — 业务语义时间基准(北京时间),用于调度触发判断、
  日志时间戳、业务时间列写入(2026-07-17 timestamptz 改造后)。
"""

from datetime import date, datetime, time
from typing import overload
from zoneinfo import ZoneInfo

# 空表首次同步起始日期(对齐 K线 DEFAULT_START_DATE_BY_SECURITY_TYPE 的 20130101).
#
# Phase 1&2 表空表(last_sync_date 表无 (sync_type, scope_key) 记录)首次同步
# 从此日起拉全历史。见 Phase 03 D-14。
DEFAULT_FIRST_SYNC_DATE = 20130101

# 业务语义时间基准:北京时间(Asia/Shanghai, UTC+8, 无夏令时)。
#
# 生产服务器系统时区为 UTC(timedatectl: "Time zone: UTC"),但业务语义时间——
# A 股交易日、AmazingData 数据源发布、调度触发时刻(00:10 K线 / 00:00 日历检查)、
# 日志文件名与时间戳、业务时间列(trade_time/trade_date 等 timestamptz 列)——
# 均应为北京时间。所有需要"当前业务时间"的地方统一调用 now_cst(),
# 而非裸 datetime.now()(会返回 UTC)。
#
# 例外:数据库审计列(created_at/updated_at)仍用 datetime.now(timezone.utc) 写 UTC,
# 不由此常量管理——见各模型定义。业务时间列 vs 审计列的区分见 AGENTS.md
# 2026-07-17 审计。
CST = ZoneInfo("Asia/Shanghai")


def now_cst() -> datetime:
    """返回当前北京时间(带 tzinfo 的 aware datetime)。

    用于:
    - 调度触发判断(scheduler.py 主循环比较配置时刻)
    - 日志文件名({date}/{time} 占位符)和 Formatter asctime(converter)
    - 其他需要"当前业务时间"的场景

    不用于:数据库审计列(那些用 UTC,见 last_sync_date.py 等模型)。
    """
    return datetime.now(CST)


@overload
def localize_cst(dt: datetime) -> datetime: ...
@overload
def localize_cst(dt: date) -> date: ...
@overload
def localize_cst(dt: time) -> time: ...


def localize_cst(dt: datetime | date | time) -> datetime | date | time:
    """把 naive 时间值附加北京时区(若已是 aware 则转换到北京时区)。

    用于业务时间列(trade_time/trade_date 等 timestamptz 列)的写入侧:
    SDK 返回的时间字面值是北京 wall-clock(naive),入库前需 attach CST tzinfo,
    否则 asyncpg/PG 会把 naive 当 UTC 写入,造成 8 小时偏差。

    - datetime: naive → replace(tzinfo=CST);aware → astimezone(CST)
    - date/time: 不操作时区(date/time 无 tz 概念,直接返回)

    见 AGENTS.md 2026-07-17 审计:parse 入口统一 localize 是单点防错。

    Args:
        dt: naive 或 aware 的 datetime / date / time

    Returns:
        aware datetime(北京时区),或原样返回的 date/time
    """
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=CST)
        return dt.astimezone(CST)
    return dt
