"""gRPC 服务入口.

从 DI 容器获取 service 实例，注入到 gRPC 服务实现中。
"""

import uvicorn

from galaxy_core.application.grpc.echo_service import app
from galaxy_core.di.container import create_container

# 创建 DI 容器，获取 service 实例
# 当前 gRPC 只有 echo service，service 实例预留供后续 RPC 实现使用
container = create_container()
kline_service = container.kline_service()
calendar_service = container.calendar_service()
reference_service = container.reference_service()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=50052)
