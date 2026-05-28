from enum import Enum
from typing import Union
import AmazingData as ad


class Interval(Enum):
    """
    数据周期枚举 - 数据库命名
    """

    MIN1 = "min1"  # 1分钟线
    MIN3 = "min3"  # 3分钟线
    MIN5 = "min5"  # 5分钟线
    MIN10 = "min10"  # 10分钟线
    MIN15 = "min15"  # 15分钟线
    MIN30 = "min30"  # 30分钟线
    MIN60 = "min60"  # 60分钟线
    MIN120 = "min120"  # 120分钟线
    DAY = "day"  # 日线
    WEEK = "week"  # 周线
    MONTH = "month"  # 月线
    SEASON = "season"  # 季度线
    YEAR = "year"  # 年线

    @classmethod
    def from_sdk_period_value(cls, sdk_period_value: int) -> "Interval":
        """
        从AmazingData SDK的Period值创建Interval枚举

        Args:
            sdk_period_value: AmazingData SDK中Period枚举的实际值

        Returns:
            Interval: 对应的Interval枚举值
        """
        # SDK Period值到Interval的映射
        mapping = {
            10000: cls.MIN1,  # min1
            10001: cls.MIN3,  # min3
            10002: cls.MIN5,  # min5
            10003: cls.MIN10,  # min10
            10004: cls.MIN15,  # min15
            10005: cls.MIN30,  # min30
            10006: cls.MIN60,  # min60
            10007: cls.MIN120,  # min120
            10008: cls.DAY,  # day
            10009: cls.WEEK,  # week
            10010: cls.MONTH,  # month
            10011: cls.SEASON,  # season
            10012: cls.YEAR,  # year
        }

        if sdk_period_value in mapping:
            return mapping[sdk_period_value]

        raise ValueError(
            f"No matching Interval enum found for SDK Period value: {sdk_period_value}"
        )

    def to_sdk_period_value(self) -> int:
        """
        将Interval枚举转换为AmazingData SDK的Period值

        Returns:
            int: 对应的AmazingData SDK中Period枚举的实际值
        """
        # Interval到SDK Period值的映射
        mapping = {
            Interval.MIN1: 10000,  # min1
            Interval.MIN3: 10001,  # min3
            Interval.MIN5: 10002,  # min5
            Interval.MIN10: 10003,  # min10
            Interval.MIN15: 10004,  # min15
            Interval.MIN30: 10005,  # min30
            Interval.MIN60: 10006,  # min60
            Interval.MIN120: 10007,  # min120
            Interval.DAY: 10008,  # day
            Interval.WEEK: 10009,  # week
            Interval.MONTH: 10010,  # month
            Interval.SEASON: 10011,  # season
            Interval.YEAR: 10012,  # year
        }

        if self in mapping:
            return mapping[self]

        raise ValueError(f"No matching SDK Period value found for Interval: {self}")

    @classmethod
    def from_value(cls, value: Union[int, str]) -> "Interval":
        """
        从数值创建Interval枚举

        Args:
            value: 数值

        Returns:
            Interval: 对应的Interval枚举值
        """
        if isinstance(value, int):
            value = str(value)

        for interval in cls:
            if interval.value == value:
                return interval

        raise ValueError(f"No Interval enum found for value: {value}")

    @classmethod
    def from_period_name(cls, period_name: str) -> "Interval":
        """
        从AmazingData SDK的Period枚举名称创建Interval枚举

        Args:
            period_name: AmazingData SDK的Period枚举名称，如 'min1', 'day' 等

        Returns:
            Interval: 对应的Interval枚举值
        """
        # 将输入的名称转换为大写以匹配Interval枚举
        period_name_lower = period_name.lower()
        try:
            # 直接使用lowercase名称查找Interval枚举
            return cls(period_name_lower)
        except ValueError:
            raise ValueError(f"No Interval enum found for period name: {period_name}")

    def to_period_name(self) -> str:
        """
        获取对应的AmazingData SDK的Period枚举名称

        Returns:
            str: AmazingData SDK的Period枚举名称
        """
        return self.value  # 返回枚举的字符串值，如 'day', 'min1' 等
