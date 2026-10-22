"""资金流向数据命令参数解析模块."""

from typing import Any


def create_fundflow_parser(subparsers: Any) -> Any:
    """创建 fundflow subparser.

    Args:
        subparsers: argparse subparsers 对象

    Returns:
        配置好的 fundflow parser

    Per Phase 02 D-11(2026-06-19 范围修订, 见 02-SCOPE-REVISION-REPORT.md):
    资金流向数据(akshare 板块 + AmazingData 龙虎榜/大宗/两融)手动同步入口。
    默认 skip(与 scheduler 一致),``--force`` 绕过 is_synced 强制重跑。
    单 job(无 ``--source``),target 路由在 job 内部完成
    (02-PLAN-07 的 ``run_daily(today, target)`` 分派)。
    """
    parser = subparsers.add_parser(
        "fundflow",
        help="同步资金流向数据（akshare + AmazingData）",
        description=(
            "手动触发资金流向数据同步（板块资金流 + 龙虎榜/大宗/两融）。"
            "默认尊重 SyncStateManager 幂等状态（已同步则跳过），--force 强制重跑。"
        ),
    )

    parser.add_argument(
        "--target",
        required=True,
        choices=[
            "sector",
            "longhu",
            "block",
            "margin",
            "all",
        ],
        help=(
            "同步目标：\n"
            "- sector: 板块资金流（akshare）\n"
            "- longhu: 龙虎榜（AmazingData）\n"
            "- block: 大宗交易（AmazingData）\n"
            "- margin: 两融汇总 + 明细（AmazingData）\n"
            "- all: 全部 5 类"
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
        help=("强制重跑：绕过 is_synced 幂等检查，但仍写状态标记（避免下次 scheduler 重复跑）。"),
    )

    return parser
