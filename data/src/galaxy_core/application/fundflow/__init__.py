"""资金流向数据命令模块（akshare + AmazingData 手动同步入口）."""

from galaxy_core.application.fundflow.command import handle_fundflow_command_async
from galaxy_core.application.fundflow.parser import create_fundflow_parser

__all__ = ["create_fundflow_parser", "handle_fundflow_command_async"]
