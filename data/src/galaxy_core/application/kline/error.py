"""K 线查询错误类定义.

此模块定义了用于表示 K 线查询过程中可能出现的各种错误情况的类，
以便与返回空 DataFrame 的情况区分开来。
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class KlineErrorCode(Enum):
    """K 线查询错误代码枚举."""

    # 参数错误
    INVALID_CODE = "INVALID_CODE"  # 无效的证券代码
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"  # 无效的日期范围
    INVALID_PERIOD = "INVALID_PERIOD"  # 无效的数据周期

    # 数据错误
    NO_DATA_FOUND = "NO_DATA_FOUND"  # 指定条件下无数据
    CODE_NOT_LISTED = "CODE_NOT_LISTED"  # 标的未上市
    CODE_DELISTED = "CODE_DELISTED"  # 标的已退市
    FUTURE_DATE = "FUTURE_DATE"  # 查询未来日期

    # 系统错误
    CONNECTION_ERROR = "CONNECTION_ERROR"  # 连接错误
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"  # 认证错误
    API_LIMIT_EXCEEDED = "API_LIMIT_EXCEEDED"  # API 限制超限
    INTERNAL_ERROR = "INTERNAL_ERROR"  # 内部错误
    SDK_BUG_ERROR = "SDK_BUG_ERROR"  # SDK内部错误（已知问题）

    # 其他错误
    MIXED_RESULTS = "MIXED_RESULTS"  # 混合结果（部分成功部分失败）


class KlineError(Exception):
    """K线查询错误类.

    用于表示K线查询过程中出现的错误，提供详细的错误信息和分类，
    避免与返回空DataFrame的情况混淆。
    """

    def __init__(
        self,
        error_code: KlineErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        affected_codes: Optional[List[str]] = None,
    ):
        """
        初始化K线错误对象.

        Args:
            error_code: 错误代码
            message: 错误消息
            details: 附加的详细信息
            affected_codes: 受影响的证券代码列表
        """
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.affected_codes = affected_codes or []
        self.timestamp = self._get_current_timestamp()

    def _get_current_timestamp(self) -> str:
        """获取当前时间戳."""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def __str__(self) -> str:
        """返回错误的字符串表示."""
        return f"[{self.error_code.value}] {self.message}"

    def __repr__(self) -> str:
        """返回错误的详细表示."""
        return (
            f"KlineError(error_code={self.error_code}, "
            f"message='{self.message}', "
            f"details={self.details}, "
            f"affected_codes={self.affected_codes})"
        )

    def is_parameter_error(self) -> bool:
        """判断是否为参数错误."""
        return self.error_code in [
            KlineErrorCode.INVALID_CODE,
            KlineErrorCode.INVALID_DATE_RANGE,
            KlineErrorCode.INVALID_PERIOD,
        ]

    def is_data_error(self) -> bool:
        """判断是否为数据错误."""
        return self.error_code in [
            KlineErrorCode.NO_DATA_FOUND,
            KlineErrorCode.CODE_NOT_LISTED,
            KlineErrorCode.CODE_DELISTED,
            KlineErrorCode.FUTURE_DATE,
        ]

    def is_system_error(self) -> bool:
        """判断是否为系统错误."""
        return self.error_code in [
            KlineErrorCode.CONNECTION_ERROR,
            KlineErrorCode.AUTHENTICATION_ERROR,
            KlineErrorCode.API_LIMIT_EXCEEDED,
            KlineErrorCode.INTERNAL_ERROR,
        ]

    def to_dict(self) -> Dict[str, Any]:
        """将错误对象转换为字典."""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "affected_codes": self.affected_codes,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_invalid_code(
        cls, code: str, message: Optional[str] = None
    ) -> "KlineError":
        """创建无效代码错误."""
        if message is None:
            message = f"证券代码无效: {code}"
        return cls(
            error_code=KlineErrorCode.INVALID_CODE,
            message=message,
            affected_codes=[code],
        )

    @classmethod
    def from_invalid_date_range(
        cls, start_date: str, end_date: str, message: Optional[str] = None
    ) -> "KlineError":
        """创建无效日期范围错误."""
        if message is None:
            message = f"日期范围无效: {start_date} 到 {end_date}"
        return cls(
            error_code=KlineErrorCode.INVALID_DATE_RANGE,
            message=message,
            details={"start_date": start_date, "end_date": end_date},
        )

    @classmethod
    def from_no_data_found(
        cls, codes: List[str], message: Optional[str] = None
    ) -> "KlineError":
        """创建无数据错误."""
        if message is None:
            message = f"未找到数据: {codes}"
        return cls(
            error_code=KlineErrorCode.NO_DATA_FOUND,
            message=message,
            affected_codes=codes,
        )

    @classmethod
    def from_future_date(cls, date: str, message: Optional[str] = None) -> "KlineError":
        """创建未来日期错误."""
        if message is None:
            message = f"不能查询未来日期: {date}"
        return cls(
            error_code=KlineErrorCode.FUTURE_DATE,
            message=message,
            details={"date": date},
        )

    @classmethod
    def from_connection_error(cls, message: str = "连接API服务器失败") -> "KlineError":
        """创建连接错误."""
        return cls(error_code=KlineErrorCode.CONNECTION_ERROR, message=message)

    @classmethod
    def from_authentication_error(cls, message: str = "API认证失败") -> "KlineError":
        """创建认证错误."""
        return cls(error_code=KlineErrorCode.AUTHENTICATION_ERROR, message=message)

    @classmethod
    def from_mixed_results(
        cls,
        success_codes: List[str],
        error_codes: List[str],
        message: Optional[str] = None,
    ) -> "KlineError":
        """创建混合结果错误（部分成功部分失败）."""
        if message is None:
            message = (
                f"部分查询成功: {len(success_codes)} 个成功, {len(error_codes)} 个失败"
            )
        return cls(
            error_code=KlineErrorCode.MIXED_RESULTS,
            message=message,
            details={
                "success_count": len(success_codes),
                "error_count": len(error_codes),
            },
            affected_codes=error_codes,
        )

    @classmethod
    def from_sdk_bug_error(
        cls, original_error: Exception, affected_codes: Optional[List[str]] = None
    ) -> "KlineError":
        """创建SDK内部错误（已知问题）."""
        message = (
            f"AmazingData SDK内部错误: {str(original_error)}. "
            f"这可能是SDK的已知问题，请稍后重试或联系供应商。"
        )
        return cls(
            error_code=KlineErrorCode.SDK_BUG_ERROR,
            message=message,
            details={"original_error": str(original_error)},
            affected_codes=affected_codes or [],
        )
