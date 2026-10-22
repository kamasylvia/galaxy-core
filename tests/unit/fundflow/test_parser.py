"""资金流向 CLI 命令参数解析单元测试."""

import argparse

import pytest

from galaxy_core.application.fundflow.parser import create_fundflow_parser


def _build_subparsers() -> argparse._SubParsersAction:
    """构造一个带 subparsers 的 ArgumentParser."""
    parser = argparse.ArgumentParser(prog="test")
    return parser.add_subparsers(dest="command")


class TestCreateFundFlowParser:
    """create_fundflow_parser 测试."""

    def test_target_required_missing_exits(self):
        """缺 --target 应报错."""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        with pytest.raises(SystemExit):
            subparsers.choices["fundflow"].parse_args([])

    def test_target_invalid_choice_exits(self):
        """--target 非 choices 应报错."""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        with pytest.raises(SystemExit):
            subparsers.choices["fundflow"].parse_args(["--target", "foo"])

    def test_target_all_accepted(self):
        """--target all 解析成功."""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        args = subparsers.choices["fundflow"].parse_args(["--target", "all"])
        assert args.target == "all"

    def test_target_sector_accepted(self):
        """--target sector 解析成功."""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        args = subparsers.choices["fundflow"].parse_args(["--target", "sector"])
        assert args.target == "sector"

    def test_removed_choices_rejected(self):
        """范围修订回归:未启用 target(stock/north/market/industry_pe)应被拒绝."""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        for removed in ["stock", "north", "market", "industry_pe"]:
            with pytest.raises(SystemExit):
                subparsers.choices["fundflow"].parse_args(["--target", removed])

    def test_target_margin_accepted(self):
        """--target margin 解析成功（job 内部跑 summary + detail）."""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        args = subparsers.choices["fundflow"].parse_args(["--target", "margin"])
        assert args.target == "margin"

    def test_no_source_argument(self):
        """fundflow 无 --source（单 job，与 index 子命令区别）。"""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        with pytest.raises(SystemExit):
            subparsers.choices["fundflow"].parse_args(["--target", "all", "--source", "akshare"])

    def test_date_default_none(self):
        """--date 默认 None（command 层转 today）。"""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        args = subparsers.choices["fundflow"].parse_args(["--target", "all"])
        assert args.date is None

    def test_date_parsed(self):
        """--date YYYYMMDD 原样透传（command 层转 date 对象）。"""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        args = subparsers.choices["fundflow"].parse_args(["--target", "all", "--date", "20260616"])
        assert args.date == "20260616"

    def test_force_default_false(self):
        """--force 默认 False。"""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        args = subparsers.choices["fundflow"].parse_args(["--target", "all"])
        assert args.force is False

    def test_force_set_true(self):
        """--force 解析为 True。"""
        subparsers = _build_subparsers()
        create_fundflow_parser(subparsers)
        args = subparsers.choices["fundflow"].parse_args(["--target", "all", "--force"])
        assert args.force is True
