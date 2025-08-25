from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI(title="Git Diff Viewer", version="0.1.0")

# Get the project root directory (two levels up from src/reviewer/server.py)
BASE_DIR = Path(__file__).parent.parent.parent

@app.get("/")
async def read_index() -> FileResponse:
    """Serve the main index.html file."""
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"index.html not found at {index_path}")
    return FileResponse(index_path)

def main() -> None:
    """Entry point for the reviewer-server command."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()