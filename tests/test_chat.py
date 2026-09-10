import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_chat_returns_agent_reply(client: AsyncClient, mock_agent):
    response = await client.post("/chat/", json={"message": "Oi"})
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    assert body["reply"] == "Oi! Como posso te ajudar?"


@pytest.mark.anyio
async def test_chat_with_lead_passes_through(client: AsyncClient, mock_agent):
    response = await client.post(
        "/chat/",
        json={
            "message": "Quero seguro",
            "lead": {"name": "Bruno", "age": 30, "cep": "07624-954"},
        },
    )
    assert response.status_code == 200
    assert "reply" in response.json()


@pytest.mark.anyio
async def test_chat_accepts_conversation_id(client: AsyncClient, mock_agent):
    response = await client.post(
        "/chat/",
        json={"message": "Oi", "conversation_id": "conv-test-123"},
    )
    assert response.status_code == 200
    assert "reply" in response.json()
