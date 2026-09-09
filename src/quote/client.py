from typing import Annotated

import httpx
from fastapi import Depends

from src.config import settings
from src.quote.schemas import QuoteError, QuoteRequest, QuoteResponse


class QuoteClient:
    def __init__(self, base_url: str, timeout: float):
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(timeout)
        )

    async def get_planos(self) -> dict:
        response = await self._client.get("/planos")
        response.raise_for_status()
        return response.json()

    async def post_quote(self, request: QuoteRequest) -> QuoteResponse | QuoteError:
        response = await self._client.post("/quote", json=request.model_dump())
        if response.is_success:
            return QuoteResponse(**response.json())
        return QuoteError(**response.json())

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


def get_quote_client() -> QuoteClient:
    return QuoteClient(
        base_url=settings.quote_service_url,
        timeout=settings.quote_service_timeout,
    )


QuoteClientDep = Annotated[QuoteClient, Depends(get_quote_client)]
