"""Akshare 相关的枚举定义."""

from enum import StrEnum


class AkshareMarket(StrEnum):
    """Akshare 市场代码枚举.

    定义了 Akshare 中使用的市场代码，包括：
    - 标准英文代码（SSE, SZSE, BSE）
    - 常用简写（SH, SZ, BJ）
    - 中文名称
    """

    # 标准英文代码
    SSE = "SSE"  # 上海证券交易所
    SZSE = "SZSE"  # 深圳证券交易所
    BSE = "BSE"  # 北京证券交易所

    # 常用简写
    SH = "SH"  # 上交所简写
    SZ = "SZ"  # 深交所简写
    BJ = "BJ"  # 北交所简写

    # 中文全称
    SHANGHAI_STOCK_EXCHANGE = "上海证券交易所"
    SHENZHEN_STOCK_EXCHANGE = "深圳证券交易所"
    BEIJING_STOCK_EXCHANGE = "北京证券交易所"

    # 中文简称
    SHANGHAI_EXCHANGE = "上交所"
    SHENZHEN_EXCHANGE = "深交所"
    BEIJING_EXCHANGE = "北交所"

    @classmethod
    def get_normalized_market(cls, market: str) -> str:
        """获取标准化的市场代码.

        将各种形式的市场标识统一转换为对应的标准英文代码（SSE、SZSE 或 BSE）。

        Args:
            market: 市场代码或名称

        Returns:
            标准化的市场代码（SSE、SZSE 或 BSE）
        """
        # 映射表：各种输入 -> 标准代码
        mapping = {
            # 上海证券交易所
            cls.SSE: cls.SSE,
            cls.SH: cls.SSE,
            cls.SHANGHAI_STOCK_EXCHANGE: cls.SSE,
            cls.SHANGHAI_EXCHANGE: cls.SSE,
            # 深圳证券交易所
            cls.SZSE: cls.SZSE,
            cls.SZ: cls.SZSE,
            cls.SHENZHEN_STOCK_EXCHANGE: cls.SZSE,
            cls.SHENZHEN_EXCHANGE: cls.SZSE,
            # 北京证券交易所
            cls.BSE: cls.BSE,
            cls.BJ: cls.BSE,
            cls.BEIJING_STOCK_EXCHANGE: cls.BSE,
            cls.BEIJING_EXCHANGE: cls.BSE,
        }

        return mapping.get(market, market)

    @classmethod
    def is_valid_market(cls, market: str) -> bool:
        """检查是否为有效的市场代码.

        Args:
            market: 市场代码或名称

        Returns:
            是否为有效的市场代码
        """
        return market in cls._value2member_map_

    @property
    def is_china_market(self) -> bool:
        """判断是否为国内市场.

        Returns:
            是否为国内市场（SSE、SZSE、BSE 及其变体）
        """
        china_markets = {
            AkshareMarket.SSE,
            AkshareMarket.SZSE,
            AkshareMarket.BSE,
            AkshareMarket.SH,
            AkshareMarket.SZ,
            AkshareMarket.BJ,
            AkshareMarket.SHANGHAI_STOCK_EXCHANGE,
            AkshareMarket.SHENZHEN_STOCK_EXCHANGE,
            AkshareMarket.BEIJING_STOCK_EXCHANGE,
            AkshareMarket.SHANGHAI_EXCHANGE,
            AkshareMarket.SHENZHEN_EXCHANGE,
            AkshareMarket.BEIJING_EXCHANGE,
        }
        return self in china_markets
