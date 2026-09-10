import pytest
from httpx import ASGITransport, AsyncClient

from src.chat import agent as agent_module
from src.main import app


class FakeAgent:
    def __init__(self, reply: str = "Oi! Como posso te ajudar?"):
        self.reply = reply

    async def ainvoke(self, input_state, config=None):
        from langchain_core.messages import AIMessage

        messages = [AIMessage(content=self.reply)]
        return {
            "messages": messages,
            "lead": {},
            "quote": None,
            "planos": None,
            "tried_plans": [],
            "next": "respond",
        }


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def mock_agent():
    fake = FakeAgent()
    app.dependency_overrides[agent_module.get_agent] = lambda: fake
    yield fake
    app.dependency_overrides.pop(agent_module.get_agent, None)
    agent_module._agent = None
