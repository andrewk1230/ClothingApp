from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: Phase 1 — load ML models into GPU memory
    # from app.ml.clip_model import load_clip
    # from app.ml.yolo_model import load_yolo
    # load_clip(settings.clip_model, settings.clip_pretrained)
    # load_yolo(settings.yolo_weights_path)

    # TODO: Phase 2 — start APScheduler for scraping
    # from app.scraper.scheduler import start_scheduler
    # start_scheduler()

    print("GrailSeeker API started")
    yield
    print("GrailSeeker API shutting down")


app = FastAPI(
    title="GrailSeeker API",
    description="Visual search engine for second-hand clothing",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Phase 6 — restrict to app origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import auth, history, listings, saved, search

app.include_router(search.router)
app.include_router(listings.router)
app.include_router(saved.router)
app.include_router(history.router)
app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
