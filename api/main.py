"""FastAPI routes only. Run from project root:  python -m api.main"""
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import core

load_dotenv(Path(__file__).parent / ".env")
ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=core.warmup, daemon=True).start()
    if core.AUTOSTART:
        core.start()
    yield


app = FastAPI(title="Smart Obstacle Alert API (Wi-Fi)", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])


class Reading(BaseModel):
    distance: int


class NameIn(BaseModel):
    name: str = ""


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/sensor")          # ESP32 posts here over Wi-Fi
def sensor(r: Reading):
    core.update_distance(r.distance)
    return {"ok": True}


@app.get("/api/state")
def state():
    return core.get_state()


@app.post("/api/start")
def start():
    core.start()
    return {"running": True}


@app.post("/api/stop")
def stop():
    core.stop()
    return {"running": False}


@app.post("/api/repeat")
def repeat():
    return core.repeat_last()


@app.post("/api/name")           # dashboard saves the user name used in alerts
def set_name(n: NameIn):
    return {"name": core.set_name(n.name)}


if __name__ == "__main__":
    uvicorn.run("api.main:app", host=os.getenv("API_HOST", "0.0.0.0"),
                port=int(os.getenv("API_PORT", "8000")))
