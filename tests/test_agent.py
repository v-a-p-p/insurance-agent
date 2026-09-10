from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.chat.agent import (
    AgentState,
    ClassificationResult,
    build_agent,
)
from src.quote.schemas import QuoteError, QuoteResponse


def _make_state(**overrides) -> AgentState:
    defaults = {
        "messages": [],
        "lead": {},
        "planos": None,
        "quote": None,
        "conversation_id": "e2e-test",
        "tried_plans": [],
        "next": "",
    }
    defaults.update(overrides)
    return defaults


class TestHappyPath:
    @pytest.mark.anyio
    async def test_full_conversation_to_successful_quote(self):
        call_count = {"count": 0}

        def classify_side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return ClassificationResult(
                    intent="respond", reply="Ola! Como posso ajudar?"
                )
            return ClassificationResult(
                intent="qualify",
                reply="Perfeito! Vou fazer sua cotacao.",
                lead_update={"age": 35, "veiculo_ano": 2020, "cep": "01310-100"},
            )

        structured = MagicMock()
        structured.invoke.side_effect = classify_side_effect

        llm = MagicMock()
        llm.with_structured_output.return_value = structured
        llm.invoke.return_value = AIMessage(
            content="Gostaria de seguir com esse plano?"
        )

        mock_quote = AsyncMock()
        mock_quote.get_planos.return_value = {"planos": []}
        mock_quote.post_quote.return_value = QuoteResponse(
            plano_id="completo",
            plano_nome="Completo",
            premio_mensal=240.89,
            franquia=3000,
            coberturas=["colisao", "roubo", "furto", "terceiros", "vidros"],
            multiplicadores={"faixa_etaria": 1.0, "idade_veiculo": 1.0, "regiao": 1.0},
            carencia={
                "coberturas": ["roubo", "furto"],
                "dias": 30,
                "observacao": "...",
            },
            moeda="BRL",
        )

        agent = build_agent(llm, mock_quote)

        t1 = _make_state(messages=[HumanMessage(content="Oi")])
        r1 = await agent.ainvoke(t1, {"configurable": {"thread_id": "e2e-1"}})
        assert "Ola" in str(r1["messages"][-1].content)

        t2 = _make_state(
            messages=list(r1["messages"])
            + [HumanMessage(content="Tenho 35 anos, Honda Civic 2020, CEP 01310-100")],
            lead=r1.get("lead", {}),
        )
        r2 = await agent.ainvoke(t2, {"configurable": {"thread_id": "e2e-2"}})
        assert r2.get("quote") is not None
        assert len(r2["messages"]) > 0


class TestRefusalPath:
    @pytest.mark.anyio
    async def test_quote_refused_auto_retry_next_plan(self):
        structured = MagicMock()
        structured.invoke.return_value = ClassificationResult(
            intent="qualify",
            reply="Vou cotar!",
            lead_update={"age": 35, "veiculo_ano": 2020, "cep": "01310-100"},
        )
        llm = MagicMock()
        llm.with_structured_output.return_value = structured
        llm.invoke.return_value = AIMessage(content="Seu plano ficou assim...")

        mock_quote = AsyncMock()
        mock_quote.get_planos.return_value = {"planos": []}
        mock_quote.post_quote.side_effect = [
            QuoteError(error="cotacao_recusada", motivo="regiao"),
            QuoteResponse(
                plano_id="essencial",
                plano_nome="Essencial",
                premio_mensal=150.00,
                franquia=4500,
                coberturas=["colisao", "roubo"],
                multiplicadores={
                    "faixa_etaria": 1.0,
                    "idade_veiculo": 1.0,
                    "regiao": 1.0,
                },
                carencia={"coberturas": [], "dias": 30, "observacao": ""},
                moeda="BRL",
            ),
        ]

        agent = build_agent(llm, mock_quote)
        state = _make_state(
            messages=[HumanMessage(content="Quero cotar")],
            lead={"age": 35, "veiculo_ano": 2020, "cep": "01310-100"},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "e2e-r"}})
        tried = result.get("tried_plans", [])
        assert "completo" in tried
        assert "essencial" in tried

    @pytest.mark.anyio
    async def test_all_plans_refused_graceful_response(self):
        structured = MagicMock()
        structured.invoke.return_value = ClassificationResult(
            intent="qualify",
            reply="Vou cotar!",
            lead_update={"age": 80, "veiculo_ano": 1980, "cep": "01310-100"},
        )
        llm = MagicMock()
        llm.with_structured_output.return_value = structured
        llm.invoke.return_value = AIMessage(content="Ola!")

        mock_quote = AsyncMock()
        mock_quote.get_planos.return_value = {"planos": []}
        mock_quote.post_quote.return_value = QuoteError(
            error="cotacao_recusada", motivo="Idade acima do limite"
        )

        agent = build_agent(llm, mock_quote)
        state = _make_state(
            messages=[HumanMessage(content="Tenho 80 anos, carro 1980")],
            lead={"age": 80, "veiculo_ano": 1980},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "e2e-all"}})
        last_msg = str(result["messages"][-1].content)
        assert (
            "atendentes" in last_msg.lower() or "entrar em contato" in last_msg.lower()
        )


class TestMissingData:
    @pytest.mark.anyio
    async def test_agent_asks_for_missing_fields(self):
        llm = MagicMock()
        structured = MagicMock()
        structured.invoke.return_value = ClassificationResult(
            intent="qualify", reply="Entendi!", lead_update={"age": 35}
        )
        llm.with_structured_output.return_value = structured
        llm.invoke.return_value = AIMessage(content="Qual o ano do seu veiculo?")

        mock_quote = AsyncMock()
        agent = build_agent(llm, mock_quote)
        state = _make_state(
            messages=[HumanMessage(content="Tenho 35 anos")],
            lead={"age": 35},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "e2e-md"}})
        last_msg = str(result["messages"][-1].content)
        assert "veiculo" in last_msg.lower() or "ano" in last_msg.lower()
