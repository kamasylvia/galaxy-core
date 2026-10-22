"""ConfigLoader 扩展测试 — 点分键名解析、嵌套节访问、默认值 fallback.

注意：此测试直接使用 ConfigLoader 类（绕过 conftest 的 mock），
并通过 PROJECT_ROOT_PATH 环境变量指向真实的配置文件。
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 确保项目根目录指向正确的路径（避免 conftest mock 的影响）
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])


@pytest.fixture(autouse=True)
def _setup_env():
    """设置 PROJECT_ROOT_PATH 并重置配置缓存."""
    with patch.dict(os.environ, {"PROJECT_ROOT_PATH": _PROJECT_ROOT}):
        # 确保真实的 config_loader 模块可用
        # conftest 可能已经 mock 了该模块，需要先移除
        mocked_key = "galaxy_core.shared_kernel.utils.config_loader"
        original = sys.modules.pop(mocked_key, None)

        # 同时移除子模块以确保重新加载
        impl_key = "galaxy_core.shared_kernel.utils.config_loader._config_loader_impl"
        config_key = "galaxy_core.shared_kernel.utils.config_loader.config"
        original_impl = sys.modules.pop(impl_key, None)
        original_config = sys.modules.pop(config_key, None)

        # 重新导入真实模块
        from galaxy_core.shared_kernel.utils.config_loader._config_loader_impl import (
            ConfigLoader,
        )

        ConfigLoader.reset()
        yield ConfigLoader
        ConfigLoader.reset()

        # 恢复 mock（避免影响其他测试）
        if original is not None:
            sys.modules[mocked_key] = original
        if original_impl is not None:
            sys.modules[impl_key] = original_impl
        if original_config is not None:
            sys.modules[config_key] = original_config


class TestDottedSectionAccess:
    """测试点分 section 名访问嵌套配置."""

    def test_get_nested_batch_db_upsert(self, _setup_env):
        """sync.batch.db_upsert 应返回 100."""
        assert _setup_env.get("sync.batch", "db_upsert") == 100

    def test_get_scheduler_kline_trigger_hour(self, _setup_env):
        """scheduler.kline_trigger_hour 应返回 12(2026-08-25 改 12:00 触发)."""
        assert _setup_env.get("scheduler", "kline_trigger_hour") == 12

    def test_get_scheduler_retry_delay(self, _setup_env):
        """scheduler.retry_delay_minutes 应返回整数."""
        assert _setup_env.get("scheduler", "retry_delay_minutes") == 60

    def test_get_scheduler_data_start_year(self, _setup_env):
        """scheduler.data_start_year 应返回 2013."""
        assert _setup_env.get("scheduler", "data_start_year") == 2013


class TestFallbackDefaults:
    """测试默认值 fallback 行为."""

    def test_nonexistent_section_returns_default(self, _setup_env):
        """不存在的 section 应返回 default."""
        assert _setup_env.get("nonexistent.section", "key", "fallback") == "fallback"

    def test_nonexistent_key_returns_default(self, _setup_env):
        """存在 section 但不存在 key 时应返回 default."""
        assert _setup_env.get("sync.batch", "nonexistent_key", 99) == 99

    def test_nonexistent_section_no_default(self, _setup_env):
        """不存在的 section 且无 default 时应返回 None."""
        assert _setup_env.get("nonexistent.section", "key") is None

    def test_flat_section_still_works(self, _setup_env):
        """普通（非点分）section 访问仍然正常工作."""
        assert _setup_env.get("kline", "default_start_date") == "20130101"
