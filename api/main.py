"""FastAPI app entrypoint for the Somrit backend layer."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from core.config import DEFAULT
from core.scoring import score

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load/score once so the first slider move is instant."""
    score(DEFAULT)
    yield


app = FastAPI(title="FlowLine API", version="0.1.0", lifespan=lifespan)

# Hackathon shortcut — open CORS (known demo trade-off).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - started) * 1000
    logger.info("%s %s %.1fms", request.method, request.url.path, ms)
    return response
