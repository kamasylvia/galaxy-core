"""API 侧分批策略 — 以内存预算为锚的自适应 chunk_size 计算。

核心原理:
- 固定的是**每批的最大行数(内存预算)**,而非 symbols 数。
- chunk_size = 内存预算行数 / 每 symbol 行数。
- 每 symbol 行数 = f(窗口天数, 周期),运行时从 (query_end - query_start) 算出。
- 不设 API symbols 上限 —— SDK 连接是复用的(ensure_logged_in 只检查 flag),
  内存预算本身就能控制每批行数(=内存),无需额外 symbols cap。

这样同一个配置在所有场景下都正确:
- 全量首启(day 13年 ~3159行/只):chunk = 158万/3159 ≈ 500(分批防 OOM)
- 增量(day 1天 1行/只):chunk = 158万/1 = 158万(一次拉完,不分批)
- 全量 week(631行/只):chunk = 158万/631 ≈ 2500(数据稀疏自动放大,更少 API 调用)

配置入口:
- ``api_batch_rows``:每批最大行数(内存预算,默认 1580000 ≈ 全量 day 500 只的安全水位)。
  调此值即可线性控制所有周期/窗口/数据类型的内存占用。

稀疏类(financial/stock_basic/constituent)数据密度极低(~50 行/只或更少),
整组传安全(AGENTS.md 2026-07-04 实测),不分批。
"""

from datetime import date

from galaxy_core.shared_kernel.utils.config_loader import get_config

# K 线周期:每单位周期的交易日数(用于估算 每 symbol 行数)。
# week ≈ 5 交易日,month ≈ 20,season ≈ 60,year ≈ 240(均按 A 股年 ~243 交易日折算)。
KLINE_INTERVAL_TRADING_DAYS: dict[str, int] = {
    "day": 1,
    "week": 5,
    "month": 20,
    "season": 60,
    "year": 240,
}

# 默认内存预算:全量 day 500 只 × ~3159 行/只 ≈ 158 万行 ≈ 2.5GB(实测安全水位)。
_DEFAULT_BATCH_ROWS = 1_580_000

# 日度行情类(fundflow/industry_daily)的 codes 数硬上限。
# SDK 对大批量 codes 严重变慢/卡死/返空(实测 fundflow >200 只、industry_daily
# 7 天窗口 resolve_daily_chunk_size 算出 22 万导致一次传 511 codes 卡死)。
# 大窗口(全量 day 13 年)内存预算主导 chunk=500,小窗口(增量 7 天)被此 cap 拦到 100。
_DEFAULT_DAILY_CODE_CAP = 100

# K 线 codes 数硬上限(2026-08-06 新增)。
# SDK get_kline 对 3000+ 只 code_list 的 day 增量不稳定:8/4 用 SDK universe
# 5536 只一次传成功(AM 状态好),8/6 DB fallback 8045 只(含 BJ)混合一次传
# 静默只查 BJ 340 只、沪深全丢,且补数时 SZ 3948 只单市场大组也卡死(无查询发出)。
# 修法:市场分组(SH/SZ/BJ 独立调用)+ 组内 cap 分批。增量窗口原本不分批
# (内存预算 158 万),现被此 cap 拦到 500/批(实测 500 只/批安全,AGENTS.md 2026-07-04)。
# 全量大窗口内存预算本就 ~500,cap 不改变全量行为。
_DEFAULT_KLINE_CODE_CAP = 500


def _read_kline_code_cap() -> int:
    """读取 K 线 codes 上限([sync.batch] kline_code_cap,默认 500)。"""
    val = get_config("sync.batch", "kline_code_cap", _DEFAULT_KLINE_CODE_CAP)
    if not isinstance(val, int) or val <= 0:
        return _DEFAULT_KLINE_CODE_CAP
    return val


def _read_batch_rows() -> int:
    """读取每批最大行数([sync.batch] api_batch_rows,默认 1580000)。"""
    val = get_config("sync.batch", "api_batch_rows", _DEFAULT_BATCH_ROWS)
    if not isinstance(val, int) or val <= 0:
        return _DEFAULT_BATCH_ROWS
    return val


def _read_daily_code_cap() -> int:
    """读取日度类的 codes 上限([sync.batch] daily_code_cap,默认 100)。"""
    val = get_config("sync.batch", "daily_code_cap", _DEFAULT_DAILY_CODE_CAP)
    if not isinstance(val, int) or val <= 0:
        return _DEFAULT_DAILY_CODE_CAP
    return val


def _window_days(query_start: str, query_end: str) -> int:
    """从 YYYYMMDD 起止日期算窗口天数(下限 1,防除零)。"""
    try:
        ds = date(int(query_start[:4]), int(query_start[4:6]), int(query_start[6:8]))
        de = date(int(query_end[:4]), int(query_end[4:6]), int(query_end[6:8]))
        delta = (de - ds).days
        return max(1, delta)
    except (ValueError, IndexError):
        return 1


def resolve_kline_chunk_size(interval_value: str, query_start: str, query_end: str) -> int:
    """K 线:按窗口天数 + 周期估算 每 symbol 行数,反推 chunk_size。

    Args:
        interval_value: 周期字符串(day/week/month/season/year)
        query_start: 窗口起始(YYYYMMDD)
        query_end: 窗口结束(YYYYMMDD)

    Returns:
        chunk_size(symbols 数)。窗口越小/周期越长 → 每 symbol 行数越少 → chunk 越大。
        全量 day(3159行/只)→ 500;增量 day(1行/只)→ 158 万,但被 kline_code_cap(默认 500)
        拦下 —— SDK 对 3000+ 只 code_list 的 day 增量不稳定(2026-08-06 实锤)。
    """
    batch_rows = _read_batch_rows()
    cap = _read_kline_code_cap()
    days = _window_days(query_start, query_end)
    trading_days_per_unit = KLINE_INTERVAL_TRADING_DAYS.get(interval_value, 1)
    rows_per_symbol = max(1, days // trading_days_per_unit)
    return max(1, min(batch_rows // rows_per_symbol, cap))


def resolve_daily_chunk_size(query_start: str, query_end: str) -> int:
    """日度行情类(非 K 线):industry_daily — 按 window 估算 + codes 数 cap。

    这些数据是日度粒度(每交易日 1 行/symbol),与 K 线 day 同模型。
    内存预算主导大窗口(全量 day 13 年 → chunk≈500);小窗口(增量 7 天 →
    batch_rows/days=22 万)会被 codes_cap(daily_code_cap 默认 100)拦下,
    避免一次传数千 codes 让 SDK 卡死/返空(2026-07-17 industry_daily 实锤)。
    """
    batch_rows = _read_batch_rows()
    cap = _read_daily_code_cap()
    days = _window_days(query_start, query_end)
    return max(1, min(batch_rows // days, cap))


def resolve_weight_chunk_size() -> int:
    """成分股二维展开类(industry_weight):独立小基准(默认 20 指数/批)。

    industry_weight 每指数 × 每日 × 多成分股,密度远高于日度行情,
    倍率/行数模型不适用(二维展开,每指数成分数不定)。
    用独立配置 weight_chunk_size(指数数,非 symbols),实测 20 安全。
    """
    val = get_config("sync.batch", "weight_chunk_size", 20)
    if not isinstance(val, int) or val <= 0:
        return 20
    return val


def resolve_fundflow_chunk_size() -> int:
    """资金流向 per-symbol 三表(long_hu_bang/block_trading/margin_detail):固定上限。

    fundflow 三表是事件驱动(只在上榜/大宗/两融日有数据),不是纯日度,
    内存预算模型的"每 symbol 行数 = 窗口天数"假设不成立。
    且 SDK 对大批量(>200 只)严重变慢(实测 100 只=7s, 200 只=30s, 319 只=超时)。
    用固定上限 100(实测安全),不走内存预算。
    """
    val = get_config("sync.batch", "fundflow_chunk_size", 100)
    if not isinstance(val, int) or val <= 0:
        return 100
    return val
