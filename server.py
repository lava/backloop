from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path

app = FastAPI(title="Git Diff Viewer", version="0.1.0")

# Get the directory where server.py is located
BASE_DIR = Path(__file__).parent

@app.get("/")
async def read_index() -> FileResponse:
    """Serve the main index.html file."""
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"index.html not found at {index_path}")
    return FileResponse(index_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)