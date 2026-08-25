from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from animatic.api.beats import router as beats_router
from animatic.api.cut import router as cut_router
from animatic.api.health import router as health_router

app = FastAPI(title="Animatic", version="0.1.0")
app.include_router(health_router)
app.include_router(beats_router)
app.include_router(cut_router)

_WEB = Path(__file__).parent / "web"

# Mounted under /static rather than at "/" so the API routes above keep
# priority and the demo page can be served explicitly at "/".
if _WEB.is_dir():
    app.mount("/static", StaticFiles(directory=_WEB), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        """The demo shell — anonymous, no auth, no upload of the script."""
        return FileResponse(_WEB / "index.html", media_type="text/html")
