"""
证券类型枚举

该模块定义了AmazingData API兼容的证券类型枚举。
"""

from enum import StrEnum


# AmazingData API原始枚举类型
class SecurityType(StrEnum):
    """代码类型security_type(沪深北) - AmazingData API原始枚举"""

    EXTRA_STOCK_A = "EXTRA_STOCK_A"
    """上交所A股、深交所A股和北交所的股票列表"""

    SH_A = "SH_A"
    """上交所A股的股票列表"""

    SZ_A = "SZ_A"
    """深交所A股的股票列表"""

    BJ_A = "BJ_A"
    """北交所的股票列表"""

    EXTRA_STOCK_A_SH_SZ = "EXTRA_STOCK_A_SH_SZ"
    """上交所A股和深交所A股的股票列表"""

    EXTRA_INDEX_A_SH_SZ = "EXTRA_INDEX_A_SH_SZ"
    """上交所和深交所指数列表"""

    EXTRA_INDEX_A = "EXTRA_INDEX_A"
    """上交所、深交所和北交所的指数列表"""

    SH_INDEX = "SH_INDEX"
    """上交所指数列表"""

    SZ_INDEX = "SZ_INDEX"
    """深交所指数列表"""

    BJ_INDEX = "BJ_INDEX"
    """北交所的指数列表"""

    SH_ETF = "SH_ETF"
    """上交所的ETF列表"""

    SZ_ETF = "SZ_ETF"
    """深交所的ETF列表"""

    EXTRA_ETF = "EXTRA_ETF"
    """上交所、深交所的ETF列表"""

    SH_KZZ = "SH_KZZ"
    """上交所的可转债列表"""

    SZ_KZZ = "SZ_KZZ"
    """深交所的可转债列表"""

    EXTRA_KZZ = "EXTRA_KZZ"
    """上交所、深交所的可转债列表"""

    SH_HKT = "SH_HKT"
    """沪港通"""

    SZ_HKT = "SZ_HKT"
    """深港通"""

    EXTRA_HKT = "EXTRA_HKT"
    """沪深港通"""

    SH_GLRA = "SH_GLRA"
    """上交所逆回购"""

    SZ_GLRA = "SZ_GLRA"
    """深交所逆回购"""

    EXTRA_GLRA = "EXTRA_GLRA"
    """沪深逆回购"""


class SecurityTypeFuture(StrEnum):
    """代码类型security_type(期货交易所) - AmazingData API原始枚举"""

    EXTRA_FUTURE = "EXTRA_FUTURE"
    """期货, 包含中金所/上期所/大商所/郑商所/上海国际能源交易中心所"""

    ZJ_FUTURE = "ZJ_FUTURE"
    """期货, 包含中金所"""

    SQ_FUTURE = "SQ_FUTURE"
    """期货, 包含上期所"""

    DS_FUTURE = "DS_FUTURE"
    """期货, 包含大商所"""

    ZS_FUTURE = "ZS_FUTURE"
    """期货, 包含郑商所"""

    SN_FUTURE = "SN_FUTURE"
    """期货, 包含上海国际能源交易中心所"""


class SecurityTypeOption(StrEnum):
    """代码类型security_type(期权) - AmazingData API原始枚举"""

    EXTRA_ETF_OP = "EXTRA_ETF_OP"
    """ETF期权, 上交所/深交所"""

    SH_OPTION = "SH_OPTION"
    """ETF期权, 包含上交所"""

    SZ_OPTION = "SZ_OPTION"
    """ETF期权, 包含深交所"""
