from sqlalchemy import Column, String, Date, UniqueConstraint
from .kline import Base

class EmptyQueryResult(Base):
    """缓存 API 返回空结果的记录.

    用于标记某些证券在特定日期范围内经 API 确认无数据，
    避免重复进行无效的 API 查询。
    """
    __tablename__ = "empty_query_results"

    symbol = Column(String(20), primary_key=True, comment="证券代码")
    interval = Column(String(20), primary_key=True, comment="K 线周期")
    start_date = Column(Date, primary_key=True, comment="查询开始日期")
    end_date = Column(Date, primary_key=True, comment="查询结束日期")

    def __repr__(self) -> str:
        return f"<EmptyQueryResult(symbol={self.symbol}, interval={self.interval}, range={self.start_date}~{self.end_date})>"