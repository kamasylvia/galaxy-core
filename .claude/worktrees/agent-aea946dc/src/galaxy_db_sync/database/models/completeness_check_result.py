"""完整性检查结果追踪模型."""

from sqlalchemy import Column, String, Date, Integer, DateTime, Text, Boolean
from sqlalchemy.sql import func
from .kline import Base


class CompletenessCheckResult(Base):
    """完整性检查结果追踪表.

    记录每次完整性检查的结果，用于：
    1. 追踪缺失数据的修复进度
    2. 区分新发现的缺失和已知的缺失
    3. 避免重复触发 API 修复已知缺失
    """

    __tablename__ = "completeness_check_results"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 证券信息
    symbol = Column(String(20), nullable=False, index=True, comment="证券代码")
    interval = Column(String(20), nullable=False, index=True, comment="K 线周期")

    # 检查范围
    check_start = Column(Date, nullable=False, index=True, comment="检查开始日期")
    check_end = Column(Date, nullable=False, index=True, comment="检查结束日期")

    # 缺失范围
    missing_start = Column(Date, nullable=False, comment="缺失区间开始")
    missing_end = Column(Date, nullable=False, comment="缺失区间结束")

    # 状态追踪
    is_confirmed_missing = Column(
        Boolean, default=False, comment="是否已确认缺失（API 返回空）"
    )
    confirmation_reason = Column(
        String(50), nullable=True, comment="确认原因: API_EMPTY, SUSPENDED, DELISTED 等"
    )
    api_empty_checked_at = Column(
        DateTime, nullable=True, comment="API 检查时间"
    )

    # 元数据
    discovered_at = Column(
        DateTime, default=func.now(), comment="发现时间"
    )
    last_checked_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), comment="最后检查时间"
    )
    notes = Column(Text, nullable=True, comment="备注")

    def __repr__(self) -> str:
        return (
            f"<CompletenessCheckResult("
            f"symbol={self.symbol}, interval={self.interval}, "
            f"missing={self.missing_start}~{self.missing_end}, "
            f"confirmed={self.is_confirmed_missing})>"
        )


class MissingDataConfirmation(Base):
    """缺失数据确认表.

    当尝试修复缺失时，如果 API 返回空，记录确认信息。
    用于区分：
    1. 停牌期间的缺失（正常，不需要修复）
    2. API 确实无数据（可能退市、未上市等）
    """

    __tablename__ = "missing_data_confirmations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    symbol = Column(String(20), nullable=False, index=True, comment="证券代码")
    interval = Column(String(20), nullable=False, index=True, comment="K 线周期")

    # 缺失范围
    missing_start = Column(Date, nullable=False, comment="缺失开始日期")
    missing_end = Column(Date, nullable=False, comment="缺失结束日期")

    # 确认信息
    confirmation_type = Column(
        String(50), nullable=False, comment="确认类型: API_EMPTY, SUSPENDED, DELISTED"
    )
    api_response = Column(Text, nullable=True, comment="API 响应详情")
    confirmed_at = Column(DateTime, default=func.now(), comment="确认时间")

    # 关联信息
    trading_days_in_range = Column(
        Integer, nullable=True, comment="范围内的交易日数（停牌时应为 0）"
    )

    def __repr__(self) -> str:
        return (
            f"<MissingDataConfirmation("
            f"symbol={self.symbol}, range={self.missing_start}~{self.missing_end}, "
            f"type={self.confirmation_type})>"
        )