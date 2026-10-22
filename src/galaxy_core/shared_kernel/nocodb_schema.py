"""库形态 shim(2026-09-28 OpenBB/Grafana 回迁后:nocodb 形态作废).

- TABLE_NAMES:canonical 英文表名 → nocodb 中文表名(单一事实源,禁止裸写中文表名字符串)
- SECURITY_TYPE_EXPAND / expand_security_type:kline security_type 列的写入形态
  (市场码 → 市场码+大类码 逗号多值串,与 qnap nocodb 副本数据形态一致)
- market_code_from_stored:读取侧从多值串还原市场码(首元素)
- coerce_nocodb_columns:写入侧 Date/Boolean/Text 列值强转
- SECURITY_TYPE_EXPAND / expand_security_type:已恒等化(2026-09-28 D4 拆列后
  security_type 恢复单市场码;函数保留仅为调用点平滑,勿新增使用)
"""

from datetime import date as _date
from datetime import datetime as _datetime

from sqlalchemy import Boolean as _SABoolean
from sqlalchemy import Date as _SADate
from sqlalchemy import DateTime as _SADateTime
from sqlalchemy import String as _SAString

from galaxy_core.shared_kernel.utils.constants import CST

# canonical 英文名(旧库/代码语义)→ nocodb 中文表名
TABLE_NAMES: dict[str, str] = {
    "kline_min1": "kline_min1",
    "kline_min3": "kline_min3",
    "kline_min5": "kline_min5",
    "kline_min10": "kline_min10",
    "kline_min15": "kline_min15",
    "kline_min30": "kline_min30",
    "kline_min60": "kline_min60",
    "kline_min120": "kline_min120",
    "kline_day": "kline_day",
    "kline_week": "kline_week",
    "kline_month": "kline_month",
    "kline_season": "kline_season",
    "kline_year": "kline_year",
    "trading_calendar": "trading_calendar",
    "stock_basic": "stock_basic",
    "backward_factor": "backward_factor",
    "index_constituent": "index_constituent",
    "index_weight": "index_weight",
    "industry_base_info": "industry_base_info",
    "industry_constituent": "industry_constituent",
    "industry_daily": "industry_daily",
    "industry_weight": "industry_weight",
    "long_hu_bang": "long_hu_bang",
    "block_trading": "block_trading",
    "margin_detail_daily": "margin_detail_daily",
    "margin_summary_daily": "margin_summary_daily",
    "akshare_sector_fund_flow_daily": "akshare_sector_fund_flow_daily",
    "balance_sheet": "balance_sheet",
    "cash_flow": "cash_flow",
    "income": "income",
    "profit_express": "profit_express",
    "profit_notice": "profit_notice",
    "dividend": "dividend",
    "last_sync_date": "last_sync_date",
    "sync_state": "sync_state",
    "enum_reference": "enum_reference",
}

# NocoDB 系统列(应用不写入;upsert 的 update_dict 必须排除,否则冲突更新
# 会把 id 置 NULL / 覆盖系统元数据)
NOCODB_SYSTEM_COLUMNS = frozenset(
    {"id", "created_at", "updated_at", "created_by", "updated_by", "nc_order", "nc_row_meta"}
)

# 市场码 → [市场码, 大类码...] 扩展映射(历史:nocodb MultiSelect 物理形态 = 逗号串;D4 后恒等,仅留作文档)
SECURITY_TYPE_EXPAND: dict[str, list[str]] = {
    "SH_A": ["SH_A", "EXTRA_STOCK_A", "EXTRA_STOCK_A_SH_SZ"],
    "SZ_A": ["SZ_A", "EXTRA_STOCK_A", "EXTRA_STOCK_A_SH_SZ"],
    "BJ_A": ["BJ_A", "EXTRA_STOCK_A"],
    "SH_ETF": ["SH_ETF", "EXTRA_ETF"],
    "SZ_ETF": ["SZ_ETF", "EXTRA_ETF"],
    "SH_INDEX": ["SH_INDEX", "EXTRA_INDEX_A", "EXTRA_INDEX_A_SH_SZ"],
    "SZ_INDEX": ["SZ_INDEX", "EXTRA_INDEX_A", "EXTRA_INDEX_A_SH_SZ"],
}


def expand_security_type(market_code: str) -> str:
    """恒等返回(D4 拆列后单市场码;保留签名避免调用点改动)."""
    return market_code


def market_code_from_stored(stored: str | None) -> str | None:
    """nocodb 多值串 → 市场码(首元素)。None 透传。"""
    if stored is None:
        return None
    return stored.split(",")[0]


# ---------------------------------------------------------------------------
# 写入侧类型强转(nocodb 形态:业务日期列 = date,布尔列 = boolean)
# ---------------------------------------------------------------------------


def _coerce_date_value(v):
    """str/int/float/datetime → date;无法解析原样返回(交 DB 报错暴露)。"""
    if isinstance(v, _datetime):
        return v.astimezone(CST).date() if v.tzinfo is not None else v.date()
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        v = str(int(v))
    s = str(v).strip()
    compact = s.replace("-", "")[:8]
    if len(compact) == 8 and compact.isdigit():
        try:
            return _date(int(compact[:4]), int(compact[4:6]), int(compact[6:8]))
        except ValueError:
            pass
    return v


def coerce_nocodb_columns(model, data_list: list[dict]) -> list[dict]:
    """把记录列表中 Date/Boolean/文本列的值强转为 date/bool/str(nocodb 形态列类型).

    Date 列:str 'YYYYMMDD'/'YYYY-MM-DD'、int、aware/naive datetime → date;
    Boolean 列:int/float → bool;
    文本列(Text/String,如 龙虎榜.flow_mark 旧 int → nocodb text):int/float → str。
    就地修改并返回 data_list。DateTime 列(naive ts)不在处理范围。
    """
    date_cols: list[str] = []
    bool_cols: list[str] = []
    text_cols: list[str] = []
    for col in model.__table__.columns:
        t = col.type
        if isinstance(t, _SADate) and not isinstance(t, _SADateTime):
            date_cols.append(col.name)
        elif isinstance(t, _SABoolean):
            bool_cols.append(col.name)
        elif isinstance(t, _SAString) and not isinstance(t, (_SADate, _SADateTime, _SABoolean)):
            text_cols.append(col.name)

    if not date_cols and not bool_cols and not text_cols:
        return data_list

    for row in data_list:
        for c in date_cols:
            v = row.get(c)
            if v is None or (isinstance(v, _date) and not isinstance(v, _datetime)):
                continue
            row[c] = _coerce_date_value(v)
        for c in bool_cols:
            v = row.get(c)
            if v is None or isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                row[c] = bool(v)
        for c in text_cols:
            v = row.get(c)
            if v is None or isinstance(v, str):
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                row[c] = str(int(v)) if isinstance(v, float) and v == int(v) else str(v)
    return data_list
