from fastapi import FastAPI
from animatic.api.health import router as health_router

app = FastAPI(title="Animatic", version="0.1.0")
app.include_router(health_router)
