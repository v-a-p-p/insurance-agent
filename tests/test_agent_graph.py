from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.chat.agent import (
    AgentState,
    ClassificationResult,
    build_agent,
)
from src.quote.schemas import QuoteError, QuoteResponse


def _make_mock_llm_for_classify(
    intent: str, reply: str, lead_update: dict | None = None
):
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke.return_value = ClassificationResult(
        intent=intent, reply=reply, lead_update=lead_update or {}
    )
    llm.with_structured_output.return_value = structured
    return llm


def _make_full_mock_llm(
    intent: str = "respond",
    classify_reply: str = "",
    lead_update: dict | None = None,
    qualify_response: str = "",
):
    llm = _make_mock_llm_for_classify(intent, classify_reply, lead_update)
    if qualify_response:
        llm.invoke.return_value = AIMessage(content=qualify_response)
    return llm


def _make_state(**overrides) -> AgentState:
    defaults = {
        "messages": [],
        "lead": {},
        "planos": None,
        "quote": None,
        "conversation_id": "test",
        "tried_plans": [],
        "next": "",
    }
    defaults.update(overrides)
    return defaults


class TestClassifyIntent:
    @pytest.mark.anyio
    async def test_greeting_routes_to_respond(self):
        llm = _make_mock_llm_for_classify("respond", "Ola! Como posso ajudar?")
        mock_quote = AsyncMock()
        agent = build_agent(llm, mock_quote)

        state = _make_state(messages=[HumanMessage(content="Oi")])
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "t1"}})
        assert "Ola" in str(result["messages"][-1].content)

    @pytest.mark.anyio
    async def test_quote_data_routes_to_qualify(self):
        llm = _make_mock_llm_for_classify(
            "qualify",
            "Entendi! Vou verificar seus dados.",
            {"age": 35, "veiculo_ano": 2020},
        )
        mock_quote = AsyncMock()
        mock_quote.get_planos.return_value = {"planos": []}
        mock_quote.post_quote.return_value = QuoteResponse(
            plano_id="completo",
            plano_nome="Completo",
            premio_mensal=200.00,
            franquia=3000,
            coberturas=["colisao"],
            multiplicadores={"faixa_etaria": 1.0, "idade_veiculo": 1.0, "regiao": 1.0},
            carencia={"coberturas": [], "dias": 30, "observacao": ""},
            moeda="BRL",
        )
        agent = build_agent(llm, mock_quote)

        state = _make_state(
            messages=[HumanMessage(content="Tenho 35 anos, carro 2020")],
            lead={"age": 35, "veiculo_ano": 2020},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "t2"}})
        result_lead = result.get("lead", {})
        assert result_lead.get("age") == 35


class TestQualifyLead:
    @pytest.mark.anyio
    async def test_complete_data_routes_to_quote(self):
        llm = _make_mock_llm_for_classify("qualify", "", {})
        mock_quote = AsyncMock()
        mock_quote.get_planos.return_value = {"planos": []}
        mock_quote.post_quote.return_value = QuoteResponse(
            plano_id="completo",
            plano_nome="Completo",
            premio_mensal=200.00,
            franquia=3000,
            coberturas=["colisao"],
            multiplicadores={"faixa_etaria": 1.0, "idade_veiculo": 1.0, "regiao": 1.0},
            carencia={"coberturas": [], "dias": 30, "observacao": ""},
            moeda="BRL",
        )
        agent = build_agent(llm, mock_quote)

        state = _make_state(
            messages=[HumanMessage(content="Oi")],
            lead={"age": 35, "veiculo_ano": 2020},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "t3"}})
        assert result.get("quote") is not None

    @pytest.mark.anyio
    async def test_missing_data_asks_for_fields(self):
        llm = _make_full_mock_llm(
            intent="qualify",
            classify_reply="Entendi!",
            lead_update={"age": 35},
            qualify_response="Qual o ano do seu veiculo?",
        )
        mock_quote = AsyncMock()
        agent = build_agent(llm, mock_quote)

        state = _make_state(
            messages=[HumanMessage(content="Tenho 35 anos")],
            lead={"age": 35},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "t4"}})
        assert "veiculo" in str(result["messages"][-1].content).lower()


class TestRequestQuote:
    @pytest.mark.anyio
    async def test_stores_quote_response_in_state(self):
        llm = _make_mock_llm_for_classify("qualify", "", {})
        mock_quote = AsyncMock()
        mock_quote.get_planos.return_value = {"planos": []}
        mock_quote.post_quote.return_value = QuoteResponse(
            plano_id="completo",
            plano_nome="Completo",
            premio_mensal=240.89,
            franquia=3000,
            coberturas=["colisao", "roubo"],
            multiplicadores={"faixa_etaria": 1.0, "idade_veiculo": 1.0, "regiao": 1.0},
            carencia={"coberturas": [], "dias": 30, "observacao": ""},
            moeda="BRL",
        )
        agent = build_agent(llm, mock_quote)

        state = _make_state(
            messages=[HumanMessage(content="Oi")],
            lead={"age": 35, "veiculo_ano": 2020, "cep": "01310-100"},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "t5"}})
        quote = result.get("quote")
        assert quote is not None
        assert quote.get("success") is True
        assert quote["plano_nome"] == "Completo"


class TestDecide:
    @pytest.mark.anyio
    async def test_success_responds_with_quote(self):
        llm = _make_full_mock_llm(
            intent="qualify",
            classify_reply="Vou cotar!",
            lead_update={"age": 35, "veiculo_ano": 2020},
            qualify_response="Ola!",
        )
        mock_quote = AsyncMock()
        mock_quote.get_planos.return_value = {"planos": []}
        mock_quote.post_quote.return_value = QuoteResponse(
            plano_id="completo",
            plano_nome="Completo",
            premio_mensal=240.89,
            franquia=3000,
            coberturas=["colisao", "roubo"],
            multiplicadores={"faixa_etaria": 1.0, "idade_veiculo": 1.0, "regiao": 1.0},
            carencia={"coberturas": [], "dias": 30, "observacao": ""},
            moeda="BRL",
        )
        agent = build_agent(llm, mock_quote)

        state = _make_state(
            messages=[HumanMessage(content="Oi")],
            lead={"age": 35, "veiculo_ano": 2020},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "t6"}})
        last_msg = str(result["messages"][-1].content)
        assert "240.89" in last_msg or "Completo" in last_msg

    @pytest.mark.anyio
    async def test_refusal_auto_retries(self):
        llm = _make_full_mock_llm(
            intent="qualify",
            classify_reply="Vou cotar!",
            lead_update={"age": 35, "veiculo_ano": 2020},
            qualify_response="Ola!",
        )
        mock_quote = AsyncMock()
        mock_quote.get_planos.return_value = {"planos": []}
        mock_quote.post_quote.side_effect = [
            QuoteError(error="cotacao_recusada", motivo="idade"),
            QuoteResponse(
                plano_id="essencial",
                plano_nome="Essencial",
                premio_mensal=100.00,
                franquia=4500,
                coberturas=["colisao"],
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
            messages=[HumanMessage(content="Oi")],
            lead={"age": 35, "veiculo_ano": 2020},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "t7"}})
        tried = result.get("tried_plans", [])
        assert "completo" in tried
        assert "essencial" in tried

    @pytest.mark.anyio
    async def test_all_refused_explains(self):
        llm = _make_full_mock_llm(
            intent="qualify",
            classify_reply="Vou cotar!",
            lead_update={"age": 35, "veiculo_ano": 2020},
            qualify_response="Ola!",
        )
        mock_quote = AsyncMock()
        mock_quote.get_planos.return_value = {"planos": []}
        mock_quote.post_quote.return_value = QuoteError(
            error="cotacao_recusada", motivo="idade"
        )
        agent = build_agent(llm, mock_quote)

        state = _make_state(
            messages=[HumanMessage(content="Oi")],
            lead={"age": 35, "veiculo_ano": 2020},
        )
        result = await agent.ainvoke(state, {"configurable": {"thread_id": "t8"}})
        last_msg = str(result["messages"][-1].content)
        assert (
            "atendentes" in last_msg.lower() or "entrar em contato" in last_msg.lower()
        )
