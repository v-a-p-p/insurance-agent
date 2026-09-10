from unittest.mock import AsyncMock

import pytest

from src.chat.tools import make_cotar_seguro, make_get_planos
from src.quote.client import QuoteClient
from src.quote.schemas import QuoteError, QuoteRequest, QuoteResponse


@pytest.fixture
def mock_quote_client():
    return AsyncMock(spec=QuoteClient)


@pytest.mark.anyio
async def test_get_planos_formatted(mock_quote_client):
    mock_quote_client.get_planos.return_value = {
        "planos": [
            {
                "id": "essencial",
                "nome": "Essencial",
                "base_mensal": 119.90,
                "franquia": 4500,
                "coberturas": ["colisao", "roubo", "furto"],
            },
            {
                "id": "premium",
                "nome": "Premium",
                "base_mensal": 339.90,
                "franquia": 1500,
                "coberturas": ["colisao", "roubo", "furto", "carro_reserva"],
            },
        ]
    }

    tool = make_get_planos(mock_quote_client)
    result = await tool.ainvoke({})

    assert "Planos disponiveis:" in result
    assert "Essencial" in result
    assert "R$ 119.90" in result
    assert "Premium" in result
    assert "R$ 339.90" in result


@pytest.mark.anyio
async def test_get_planos_empty(mock_quote_client):
    mock_quote_client.get_planos.return_value = {"planos": []}

    tool = make_get_planos(mock_quote_client)
    result = await tool.ainvoke({})

    assert "Nenhum plano disponivel" in result


@pytest.mark.anyio
async def test_cotar_seguro_success(mock_quote_client):
    mock_quote_client.post_quote.return_value = QuoteResponse(
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

    tool = make_cotar_seguro(mock_quote_client)
    result = await tool.ainvoke(
        {
            "plano_id": "completo",
            "idade": 35,
            "veiculo_ano": 2022,
            "cep": "01310-100",
        }
    )

    assert "Cotacao realizada com sucesso!" in result
    assert "Completo" in result
    assert "240.89" in result
    assert "R$ 3000" in result or "3000" in result
    assert "colisao" in result


@pytest.mark.anyio
async def test_cotar_seguro_refused(mock_quote_client):
    mock_quote_client.post_quote.return_value = QuoteError(
        error="cotacao_recusada",
        motivo="Veiculo com mais de 20 anos nao e aceito.",
    )

    tool = make_cotar_seguro(mock_quote_client)
    result = await tool.ainvoke(
        {
            "plano_id": "essencial",
            "idade": 45,
            "veiculo_ano": 2002,
        }
    )

    assert "Cotacao recusada" in result
    assert "cotacao_recusada" in result
    assert "Veiculo com mais de 20 anos" in result


@pytest.mark.anyio
async def test_cotar_seguro_uses_correct_quote_request(mock_quote_client):
    mock_quote_client.post_quote.return_value = QuoteResponse(
        plano_id="premium",
        plano_nome="Premium",
        premio_mensal=450.00,
        franquia=1500,
        coberturas=["colisao"],
        multiplicadores={"faixa_etaria": 1.4, "idade_veiculo": 1.0, "regiao": 1.0},
        carencia={"coberturas": ["roubo"], "dias": 30, "observacao": "..."},
        moeda="BRL",
    )

    tool = make_cotar_seguro(mock_quote_client)
    await tool.ainvoke(
        {
            "plano_id": "premium",
            "idade": 65,
            "veiculo_ano": 2020,
            "cep": "20000-000",
            "data_inicio": "2026-07-15",
        }
    )

    call_args = mock_quote_client.post_quote.call_args[0][0]
    assert isinstance(call_args, QuoteRequest)
    assert call_args.plano_id == "premium"
    assert call_args.idade == 65
    assert call_args.veiculo_ano == 2020
    assert call_args.cep == "20000-000"
    assert call_args.data_inicio == "2026-07-15"
