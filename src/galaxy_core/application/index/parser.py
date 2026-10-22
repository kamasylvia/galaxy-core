"""指数数据命令参数解析模块."""

from typing import Any


def create_index_parser(subparsers: Any) -> Any:
    """创建 index subparser.

    Args:
        subparsers: argparse subparsers 对象

    Returns:
        配置好的 index parser

    Per Phase 01：交易所指数 + 行业指数手动同步入口。默认 skip（与 scheduler
    一致），`--force` 绕过 is_synced 强制重跑。
    """
    parser = subparsers.add_parser(
        "index",
        help="同步指数数据（交易所指数 / 行业指数）",
        description=(
            "手动触发交易所指数 + 行业指数同步。"
            "默认尊重 SyncStateManager 幂等状态（已同步则跳过），"
            "--force 强制重跑。"
        ),
    )

    parser.add_argument(
        "--target",
        required=True,
        choices=["daily", "dimensions", "all"],
        help=(
            "同步目标：\n"
            "- daily: 日度行情/权重（紧跟 K线 day）\n"
            "- dimensions: 维度数据（成分股周度 + 基本信息月度，紧跟 refdata）\n"
            "- all: 两者都跑"
        ),
    )

    parser.add_argument(
        "--source",
        required=True,
        choices=["exchange", "industry", "both"],
        help=(
            "数据源：\n"
            "- exchange: 交易所指数（成分股 + 5 大指数权重）\n"
            "- industry: 行业指数（基本信息 + 成分股 + 日行情 + 权重）\n"
            "- both: 两者都跑"
        ),
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help=(
            "目标日期 (YYYYMMDD)，省略则取今天。"
            "用于回补历史交易日；T+1 门控由 scheduler 自动链负责，手动 CLI 不重复门控。"
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "强制重跑：绕过 is_synced 幂等检查，但仍写状态标记"
            "（避免下次 scheduler 重复跑）。"
        ),
    )

    return parser
