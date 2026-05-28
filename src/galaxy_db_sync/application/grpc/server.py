import uvicorn
from galaxy_db_sync.application.grpc.echo_service import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=50052)
