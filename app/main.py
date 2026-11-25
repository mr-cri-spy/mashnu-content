from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.content import router as content_router
from app.api.telegram_hook import router as telegram_router
from app.db.models import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mashnu Content Engine", lifespan=lifespan)
app.include_router(content_router)
app.include_router(telegram_router)


@app.get("/health")
def health():
    return {"ok": True}
