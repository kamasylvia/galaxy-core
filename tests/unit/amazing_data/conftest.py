"""Pytest bootstrap for AmazingData client tests."""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock


SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "galaxy_core"

for package_name, package_path in {
    "galaxy_core": SRC_ROOT,
    "galaxy_core.amazing_data": SRC_ROOT / "amazing_data",
    "galaxy_core.amazing_data.api": SRC_ROOT / "amazing_data" / "api",
}.items():
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_path)]
        sys.modules[package_name] = package

if "galaxy_core.shared_kernel.utils.config_loader" not in sys.modules:
    config_loader = types.ModuleType("galaxy_core.shared_kernel.utils.config_loader")
    config_loader.get_config = lambda *args, **kwargs: None
    sys.modules["galaxy_core.shared_kernel.utils.config_loader"] = config_loader

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
