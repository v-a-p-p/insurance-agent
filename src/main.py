from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.chat.router import router as chat_router
from src.config import settings
from src.quote.client import QuoteClient


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    client = QuoteClient(
        base_url=settings.quote_service_url,
        timeout=settings.quote_service_timeout,
    )
    try:
        yield
    finally:
        await client.close()


app = FastAPI(title="Insurance Agent", lifespan=lifespan)

app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
