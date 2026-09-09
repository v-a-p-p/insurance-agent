import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_chat_skeleton(client: AsyncClient):
    response = await client.post("/chat/", json={"message": "anything"})
    assert response.status_code == 200
    assert response.json() == {"reply": "hello"}


@pytest.mark.anyio
async def test_chat_with_lead(client: AsyncClient):
    response = await client.post(
        "/chat/",
        json={
            "message": "Quero seguro",
            "lead": {"name": "Bruno", "age": 30, "cep": "07624-954"},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "hello"}
