"""Pytest configuration for kline tests.

This conftest.py provides mocking for AmazingData SDK and config_loader
to avoid import errors during test collection.
"""

import sys
import types
from unittest.mock import MagicMock

# Mock AmazingData SDK before any galaxy_core imports
if "AmazingData" not in sys.modules:
    amazing_data = types.ModuleType("AmazingData")

    def login(*args, **kwargs):
        return None

    def logout(*args, **kwargs):
        return None

    class BaseData:
        def get_calendar(self, *args, **kwargs):
            return MagicMock()

    class InfoData:
        pass

    class MarketData:
        def __init__(self, *args, **kwargs):
            pass

    amazing_data.login = login
    amazing_data.logout = logout
    amazing_data.BaseData = BaseData
    amazing_data.InfoData = InfoData
    amazing_data.MarketData = MarketData
    sys.modules["AmazingData"] = amazing_data

# Mock akshare (used by trading_calendar.py)
if "akshare" not in sys.modules:
    akshare = types.ModuleType("akshare")
    akshare.tool_trade_date_hist_sina = lambda *args, **kwargs: MagicMock()
    sys.modules["akshare"] = akshare

# Mock tgw (used by AmazingData SDK)
if "tgw" not in sys.modules:
    sys.modules["tgw"] = types.SimpleNamespace()

# Mock config_loader to avoid toml dependency — 返回默认值而非空 dict
if "galaxy_core.shared_kernel.utils.config_loader" not in sys.modules:
    config_loader = types.ModuleType("galaxy_core.shared_kernel.utils.config_loader")

    def _mock_get_config(*args, **kwargs):
        if len(args) >= 3:
            return args[2]
        return kwargs.get("default")

    config_loader.get_config = _mock_get_config
    config_loader.get_section = lambda *args, **kwargs: {}
    sys.modules["galaxy_core.shared_kernel.utils.config_loader"] = config_loader
