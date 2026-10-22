"""指数 CLI 命令参数解析单元测试."""

import argparse

import pytest

from galaxy_core.application.index.parser import create_index_parser


def _build_subparsers() -> argparse._SubParsersAction:
    """构造一个带 subparsers 的 ArgumentParser."""
    parser = argparse.ArgumentParser(prog="test")
    return parser.add_subparsers(dest="command")


class TestCreateIndexParser:
    """create_index_parser 测试."""

    def test_required_target_missing_exits(self):
        """缺 --target 应报错."""
        subparsers = _build_subparsers()
        create_index_parser(subparsers)
        with pytest.raises(SystemExit):
            subparsers.choices["index"].parse_args(["--source", "exchange"])

    def test_required_source_missing_exits(self):
        """缺 --source 应报错."""
        subparsers = _build_subparsers()
        create_index_parser(subparsers)
        with pytest.raises(SystemExit):
            subparsers.choices["index"].parse_args(["--target", "daily"])

    def test_target_invalid_choice_exits(self):
        """--target 非 choices 应报错."""
        subparsers = _build_subparsers()
        create_index_parser(subparsers)
        with pytest.raises(SystemExit):
            subparsers.choices["index"].parse_args(
                ["--target", "foo", "--source", "exchange"]
            )

    def test_source_invalid_choice_exits(self):
        """--source 非 choices 应报错."""
        subparsers = _build_subparsers()
        create_index_parser(subparsers)
        with pytest.raises(SystemExit):
            subparsers.choices["index"].parse_args(
                ["--target", "daily", "--source", "foo"]
            )

    def test_defaults_date_today_force_false(self):
        """合法最小参数集：date=None force=False."""
        subparsers = _build_subparsers()
        create_index_parser(subparsers)
        args = subparsers.choices["index"].parse_args(
            ["--target", "daily", "--source", "exchange"]
        )
        assert args.target == "daily"
        assert args.source == "exchange"
        assert args.date is None
        assert args.force is False

    def test_all_flags_parsed(self):
        """--date 与 --force 正确解析."""
        subparsers = _build_subparsers()
        create_index_parser(subparsers)
        args = subparsers.choices["index"].parse_args(
            [
                "--target", "all",
                "--source", "both",
                "--date", "20250613",
                "--force",
            ]
        )
        assert args.target == "all"
        assert args.source == "both"
        assert args.date == "20250613"
        assert args.force is True
