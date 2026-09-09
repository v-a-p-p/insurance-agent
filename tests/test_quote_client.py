import pytest
from respx import MockRouter

from src.quote.client import QuoteClient
from src.quote.schemas import QuoteError, QuoteRequest, QuoteResponse


@pytest.fixture
def mock_quote_service():
    with MockRouter() as router:
        yield router


@pytest.mark.anyio
async def test_get_planos(mock_quote_service):
    mock_quote_service.get("http://localhost:8000/planos").respond(
        json={"planos": [{"id": "essencial", "nome": "Essencial"}]}
    )

    async with QuoteClient(base_url="http://localhost:8000", timeout=30.0) as client:
        result = await client.get_planos()
        assert result == {"planos": [{"id": "essencial", "nome": "Essencial"}]}


@pytest.mark.anyio
async def test_post_quote_happy_path(mock_quote_service):
    response_json = {
        "plano_id": "completo",
        "plano_nome": "Completo",
        "premio_mensal": 240.89,
        "franquia": 3000,
        "coberturas": ["colisao", "roubo", "furto"],
        "multiplicadores": {"faixa_etaria": 1.0, "idade_veiculo": 1.0, "regiao": 1.0},
        "carencia": {
            "coberturas": ["roubo", "furto"],
            "dias": 30,
            "observacao": "...",
        },
        "moeda": "BRL",
    }
    mock_quote_service.post("http://localhost:8000/quote").respond(json=response_json)

    async with QuoteClient(base_url="http://localhost:8000", timeout=30.0) as client:
        result = await client.post_quote(QuoteRequest(idade=35, veiculo_ano=2022))
        assert isinstance(result, QuoteResponse)
        assert result.premio_mensal == 240.89


@pytest.mark.anyio
async def test_post_quote_refused(mock_quote_service):
    mock_quote_service.post("http://localhost:8000/quote").respond(
        status_code=422,
        json={
            "error": "cotacao_recusada",
            "motivo": "Veiculo com mais de 20 anos nao e aceito.",
        },
    )

    async with QuoteClient(base_url="http://localhost:8000", timeout=30.0) as client:
        result = await client.post_quote(QuoteRequest(idade=35, veiculo_ano=2002))
        assert isinstance(result, QuoteError)
        assert result.error == "cotacao_recusada"
        assert result.motivo == "Veiculo com mais de 20 anos nao e aceito."


@pytest.mark.anyio
async def test_post_quote_server_error(mock_quote_service):
    mock_quote_service.post("http://localhost:8000/quote").respond(
        status_code=500,
        json={"error": "upstream_unavailable", "message": "Indisponivel"},
    )

    async with QuoteClient(base_url="http://localhost:8000", timeout=30.0) as client:
        result = await client.post_quote(QuoteRequest(idade=35, veiculo_ano=2022))
        assert isinstance(result, QuoteError)
        assert result.error == "upstream_unavailable"
