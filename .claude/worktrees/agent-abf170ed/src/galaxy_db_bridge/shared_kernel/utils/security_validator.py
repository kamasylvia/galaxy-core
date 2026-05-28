"""
证券代码验证和类型识别工具模块

该模块提供对证券代码字符串列表的参数校验功能，
能够自动补全证券代码后缀并识别对应的证券类型。
"""

from typing import List, Dict, Tuple, Optional, Union
from enum import Enum
from galaxy_db_bridge.shared_kernel.enums.security_type import (
    SecurityType,
    SecurityTypeFuture,
    SecurityTypeOption,
)
from galaxy_db_bridge.amazing_data.api.client import AmazingDataClient


class ValidationResult(Enum):
    """验证结果枚举"""

    VALID = "valid"  # 有效证券代码
    INVALID = "invalid"  # 无效证券代码
    UNKNOWN = "unknown"  # 未知证券代码（格式正确但不在系统中）
    AMBIGUOUS = "ambiguous"  # 格式模糊，无法确定类型


class SecurityValidator:
    """证券代码验证器"""

    def __init__(self):
        """初始化验证器"""
        self._client = AmazingDataClient()
        self._code_cache: Dict[str, str] = {}  # 缓存已验证的代码
        self._type_cache: Dict[str, SecurityType] = {}  # 缓存已知类型

    def validate_codes(
        self, codes: List[str], security_types: Optional[List[SecurityType]] = None
    ) -> Dict[str, Tuple[ValidationResult, Optional[SecurityType], str]]:
        """
        批量验证证券代码

        Args:
            codes: 证券代码列表
            security_types: 限制的证券类型列表，默认为None表示不限制

        Returns:
            dict: {原始代码: (验证结果, 证券类型, 标准化代码)}
        """
        results = {}

        for code in codes:
            result, sec_type, standardized_code = self.validate_single_code(
                code, security_types
            )
            results[code] = (result, sec_type, standardized_code)

        return results

    def validate_single_code(
        self, code: str, security_types: Optional[List[SecurityType]] = None
    ) -> Tuple[ValidationResult, Optional[SecurityType], str]:
        """
        验证单个证券代码

        Args:
            code: 证券代码
            security_types: 限制的证券类型列表

        Returns:
            tuple: (验证结果, 证券类型, 标准化代码)
        """
        # 首先尝试从缓存获取
        if code in self._code_cache:
            cached_type = self._type_cache.get(code)
            if security_types is None or cached_type in security_types:
                return ValidationResult.VALID, cached_type, self._code_cache[code]

        # 标准化输入代码
        standardized_code = self._standardize_code(code)

        # 尝试识别证券类型
        detected_type = self._detect_security_type(standardized_code)

        # 如果指定了类型限制，检查是否符合
        if security_types is not None and detected_type not in security_types:
            return ValidationResult.INVALID, None, standardized_code

        # 验证代码是否真实存在
        if self._verify_code_exists(standardized_code, detected_type):
            # 存入缓存
            self._code_cache[code] = standardized_code
            self._type_cache[code] = detected_type
            return ValidationResult.VALID, detected_type, standardized_code
        else:
            # 代码格式正确但不存在于系统中
            return ValidationResult.UNKNOWN, detected_type, standardized_code

    def _standardize_code(self, code: str) -> str:
        """
        标准化证券代码，自动补全后缀

        Args:
            code: 输入的证券代码

        Returns:
            str: 标准化后的证券代码
        """
        if not isinstance(code, str):
            raise ValueError("证券代码必须是字符串")

        # 移除首尾空格并转为大写
        code = code.strip().upper()

        # 如果已经有后缀（包含点号），直接返回
        if "." in code:
            return code

        # 根据代码长度和前缀推断市场并添加后缀
        if len(code) == 6:
            # A股代码
            if code.startswith(("000", "001", "002", "003", "080", "031")):
                # 深圳市场
                return f"{code}.SZ"
            elif code.startswith(("600", "601", "603", "605", "688", "689")):
                # 上海市场
                return f"{code}.SH"
            elif code.startswith("8"):
                # 北交所
                return f"{code}.BJ"
            else:
                # 默认按A股处理，可能是上海或深圳
                # 这里可以更精确地根据前缀判断
                if self._is_shanghai_stock(code):
                    return f"{code}.SH"
                else:
                    return f"{code}.SZ"
        elif len(code) == 8:
            # 期货代码通常为8位
            if self._is_future_code(code):
                return f"{code}.CFE"  # 中金所为例
            # 期权代码也可能为8位
            elif self._is_option_code(code):
                return f"{code}.SSE"  # 上交所期权为例
        elif len(code) == 5:
            # 港股代码
            return f"{code}.HK"

        # 如果无法推断，则返回原代码
        return code

    def _detect_security_type(self, code: str) -> Optional[SecurityType]:
        """
        根据标准化后的代码检测证券类型

        Args:
            code: 标准化后的证券代码

        Returns:
            Optional[SecurityType]: 检测到的证券类型
        """
        if "." not in code:
            return None

        code_part, market_part = code.split(".", 1)
        market_part = market_part.upper()

        # 根据代码和市场部分判断证券类型，使用AmazingData API中实际存在的类型
        if market_part in ["SH", "SZ"]:
            if len(code_part) == 6:
                if code_part.startswith(("688", "689")):
                    return SecurityType.SH_A  # 科创板属于上海A股
                elif code_part.startswith(("002", "300")):
                    return SecurityType.SZ_A  # 创业板属于深圳A股
                elif code_part.startswith("8"):
                    return SecurityType.BJ_A  # 北交所股票
                else:
                    # 根据前缀判断是上海还是深圳的股票
                    if code_part.startswith(("600", "601", "603", "605")):
                        return SecurityType.SH_A
                    else:
                        return SecurityType.SZ_A
        elif market_part == "BJ":
            return SecurityType.BJ_A  # 北交所
        elif market_part == "HK":
            # AmazingData API中没有直接的港股类型，使用沪深港通类型
            return SecurityType.EXTRA_HKT
        elif market_part in ["CFE", "SHFE", "DCE", "CZCE"]:
            # AmazingData API中的期货类型
            return SecurityType.EXTRA_FUTURE
        elif market_part in ["SSE", "SZSE"]:
            # AmazingData API中的期权类型
            return SecurityType.EXTRA_ETF_OP

        return None

    def _verify_code_exists(
        self, code: str, security_type: Optional[SecurityType]
    ) -> bool:
        """
        验证证券代码是否真实存在于系统中

        Args:
            code: 标准化的证券代码
            security_type: 证券类型

        Returns:
            bool: 是否存在
        """
        # 由于我们无法直接访问AmazingDataClient的私有属性，
        # 这里采用基于规则的验证方式，而非实际调用API
        # 在实际应用中，这里应该调用API验证代码的存在性
        return self._validate_by_rules(code, security_type)

    def _validate_by_rules(
        self, code: str, security_type: Optional[SecurityType]
    ) -> bool:
        """
        基于规则验证代码有效性

        Args:
            code: 标准化后的代码
            security_type: 证券类型

        Returns:
            bool: 是否有效
        """
        if not code or "." not in code:
            return False

        code_part, market_part = code.split(".", 1)
        market_part = market_part.upper()

        # 根据市场和代码长度进行验证
        if market_part in ["SH", "SZ"]:
            if len(code_part) != 6:
                return False
            # 检查代码是否由数字组成
            if not code_part.isdigit():
                return False
        elif market_part == "BJ":
            if len(code_part) != 6:
                return False
            if not code_part.isdigit():
                return False
        elif market_part == "HK":
            if len(code_part) != 5:
                return False
            if not code_part.isdigit():
                return False
        elif market_part in ["CFE", "SHFE", "DCE", "CZCE"]:
            # 期货代码规则
            if len(code_part) != 8:
                return False
        elif market_part in ["SSE", "SZSE"]:
            # 期权代码规则
            if len(code_part) != 8:
                return False

        return True

    def _is_shanghai_stock(self, code: str) -> bool:
        """
        判断是否为上海市场股票

        Args:
            code: 6位股票代码

        Returns:
            bool: 是否为上海市场股票
        """
        # 根据代码前缀判断
        shanghai_prefixes = ["600", "601", "603", "605", "688", "689"]
        return any(code.startswith(prefix) for prefix in shanghai_prefixes)

    def _is_future_code(self, code: str) -> bool:
        """
        判断是否为期货行情代码

        Args:
            code: 代码字符串

        Returns:
            bool: 是否为期货代码
        """
        # 期货代码通常以字母开头，例如IF、IC、CU等
        if len(code) >= 2 and code[:2].isalpha():
            return True
        # 或者以数字开头，如特定的期货品种编码
        return False

    def _is_option_code(self, code: str) -> bool:
        """
        判断是否为期权代码

        Args:
            code: 代码字符串

        Returns:
            bool: 是否为期权代码
        """
        # 期权代码有特定的命名规则，例如以510050开头的ETF期权
        # 或者包含特定的月份和行权价标识
        if len(code) >= 6:
            # 检查是否符合期权代码的常见模式
            if code.startswith(("11", "12", "13", "14", "15")):  # ETF期权
                return True
            if code.startswith(("51", "56", "58")):  # ETF期权
                return True
            if code.startswith(("10", "11", "12", "13", "14", "15")):  # 股票期权
                return True
        return False


def validate_security_codes(
    codes: List[str], security_types: Optional[List[SecurityType]] = None
) -> Dict[str, Tuple[ValidationResult, Optional[SecurityType], str]]:
    """
    便捷函数：批量验证证券代码

    Args:
        codes: 证券代码列表
        security_types: 限制的证券类型列表

    Returns:
        dict: {原始代码: (验证结果, 证券类型, 标准化代码)}
    """
    validator = SecurityValidator()
    return validator.validate_codes(codes, security_types)


if __name__ == "__main__":
    # 示例使用
    codes = ["000001", "600000.SH", "AAPL", "IF2303.CFE"]
    results = validate_security_codes(codes)

    for original_code, (status, sec_type, standardized) in results.items():
        print(f"原始代码: {original_code}")
        print(f"  验证结果: {status.value}")
        print(f"  证券类型: {sec_type.value if sec_type else 'Unknown'}")
        print(f"  标准化代码: {standardized}")
        print("---")
