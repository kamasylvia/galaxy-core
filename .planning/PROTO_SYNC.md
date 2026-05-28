# Proto Sync Notes

## Proto Source Location
The single source of truth for protobuf schemas is `galaxy-web/proto/`.
All `.proto` changes must be made in the galaxy-web repository.

## Generated Code
Python generated stubs are output to `src/galaxy_db_sync/gen/` by `buf generate`.
This directory is **gitignored** — do not commit generated code.

## Regeneration
From the galaxy-web repository:
```bash
just gen-python
# or
cd proto && buf generate --template buf.gen.python.yaml
```

## Dependencies
- `connectrpc` Python package >=0.9.0,<0.10.0
- `protoc-gen-connectrpc` dev dependency (for local fallback)

## ASGI Server
The gRPC server runs as an ASGI application via uvicorn:
```bash
uv run python -m galaxy_db_sync.application.grpc.server
```
