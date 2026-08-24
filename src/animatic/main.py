from fastapi import FastAPI
from animatic.api.health import router as health_router
from animatic.api.beats import router as beats_router

app = FastAPI(title="Animatic", version="0.1.0")
app.include_router(health_router)
app.include_router(beats_router)
