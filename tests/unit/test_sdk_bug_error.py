"""SDKBugError 异常类测试 — 层级关系、客户端抛出、调用方捕获行为."""

import pytest

from galaxy_core.shared_kernel.exceptions import (
    GalaxyDBBridgeError,
    SDKBugError,
    SDKError,
)


class TestSDKBugErrorHierarchy:
    """测试 SDKBugError 的异常层级关系."""

    def test_sdk_bug_error_inherits_galaxy_db_bridge_error(self):
        """SDKBugError 应继承 GalaxyDBBridgeError."""
        assert issubclass(SDKBugError, GalaxyDBBridgeError)

    def test_sdk_bug_error_not_subclass_of_sdk_error(self):
        """SDKBugError 不应是 SDKError 的子类（平级关系）。"""
        assert not issubclass(SDKBugError, SDKError)

    def test_sdk_bug_error_has_original_error_attr(self):
        """SDKBugError 应包含 original_error 属性."""
        original = TypeError("test error")
        err = SDKBugError(message="test", original_error=original)
        assert err.original_error is original

    def test_sdk_bug_error_original_error_default_none(self):
        """SDKBugError 的 original_error 默认为 None."""
        err = SDKBugError(message="test")
        assert err.original_error is None

    def test_sdk_bug_error_message(self):
        """SDKBugError 应正确保存 message."""
        err = SDKBugError(message="SDK bug occurred")
        assert "SDK bug occurred" in str(err)


class TestSDKBugErrorCatching:
    """测试调用方对 SDKBugError 的捕获行为."""

    def test_sdk_bug_error_catchable_as_galaxy_db_bridge_error(self):
        """SDKBugError 可被 GalaxyDBBridgeError 捕获."""
        with pytest.raises(GalaxyDBBridgeError):
            raise SDKBugError(message="test")

    def test_sdk_bug_error_not_catchable_as_sdk_error(self):
        """SDKBugError 不应被 SDKError 捕获."""
        with pytest.raises(SDKBugError):
            try:
                raise SDKBugError(message="test")
            except SDKError:
                pytest.fail("SDKBugError should not be caught by SDKError")
