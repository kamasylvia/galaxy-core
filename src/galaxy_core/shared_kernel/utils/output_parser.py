"""输出参数解析工具."""


def parse_output(value: str | None) -> tuple[str, str | None]:
    """解析 output 参数.

    Returns:
        (output_type, output_path): 输出类型和路径
        output_type: "terminal", "database", "file"
    """
    if value is None:
        return "terminal", None

    value_lower = value.lower()

    # 数据库相关关键字
    db_keywords = ["db", "database", "pg", "postgres", "postgresql"]
    if value_lower in db_keywords:
        return "database", None

    # CSV 文件
    if value_lower.endswith(".csv"):
        return "file", value

    # 默认为终端输出
    return "terminal", None
