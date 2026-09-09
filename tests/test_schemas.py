import pytest
from pydantic import ValidationError

from src.chat.schemas import ChatRequest, Lead
from src.quote.schemas import QuoteRequest, QuoteResponse


def test_lead_valid():
    lead = Lead(name="Bruno", age=30, cep="07624-954")
    assert lead.name == "Bruno"
    assert lead.age == 30


def test_chat_request_message_only():
    r = ChatRequest(message="Oi, quero seguro")
    assert r.message == "Oi, quero seguro"
    assert r.lead is None


def test_chat_request_with_lead():
    r = ChatRequest(
        message="Meu carro é um Sandero 2022",
        lead=Lead(name="Bruno", age=30, cep="07624-954"),
    )
    assert r.lead.name == "Bruno"
    assert r.lead.age == 30


def test_quote_request_valid():
    qr = QuoteRequest(plano_id="completo", idade=35, veiculo_ano=2022, cep="01310-100")
    assert qr.plano_id == "completo"


def test_quote_request_default_plano():
    qr = QuoteRequest(idade=35, veiculo_ano=2022)
    assert qr.plano_id == "essencial"


def test_quote_response_from_dict():
    qr_dict = {
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
    qr_response = QuoteResponse(**qr_dict)
    assert qr_response.premio_mensal == 240.89


def test_quote_request_negative_idade():
    with pytest.raises(ValidationError):
        QuoteRequest(plano_id="completo", idade=-1, veiculo_ano=2022)


def test_quote_request_too_old_vehicle():
    with pytest.raises(ValidationError):
        QuoteRequest(plano_id="completo", idade=35, veiculo_ano=1800)


def test_quote_request_missing_idade():
    with pytest.raises(ValidationError):
        QuoteRequest(plano_id="completo", veiculo_ano=2022)


def test_quote_request_missing_veiculo_ano():
    with pytest.raises(ValidationError):
        QuoteRequest(plano_id="completo", idade=35)


def test_quote_request_idade_out_of_range():
    with pytest.raises(ValidationError):
        QuoteRequest(plano_id="completo", idade=201, veiculo_ano=2022)


def test_quote_response_with_pro_rata():
    qr_dict = {
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
        "primeiro_pagamento_pro_rata": {
            "dias_no_mes": 30,
            "dias_cobrados": 15,
            "valor_primeiro_pagamento": 120.45,
        },
    }
    qr_response = QuoteResponse(**qr_dict)
    assert qr_response.primeiro_pagamento_pro_rata is not None
    assert qr_response.primeiro_pagamento_pro_rata.valor_primeiro_pagamento == 120.45
