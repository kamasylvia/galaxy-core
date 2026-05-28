import sys
from pathlib import Path

# Add gen/ to path so absolute imports like `sync.v1.sync_pb2` resolve
_GEN_DIR = Path(__file__).parent.parent.parent / "gen"
if str(_GEN_DIR) not in sys.path:
    sys.path.insert(0, str(_GEN_DIR))

from connectrpc.request import RequestContext
from sync.v1.sync_pb2 import EchoRequest, EchoResponse
from sync.v1.sync_connect import SyncService, SyncServiceASGIApplication


class SyncServiceImpl(SyncService):
    async def echo(
        self, request: EchoRequest, ctx: RequestContext
    ) -> EchoResponse:
        return EchoResponse(message=request.message)


app = SyncServiceASGIApplication(SyncServiceImpl())
