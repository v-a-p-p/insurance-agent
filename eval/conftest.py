import json
from pathlib import Path

import pytest

from eval.judge import build_judge
from src.chat.agent import build_agent
from src.chat.model import get_chat_model
from src.quote.schemas import (
    CarenciaInfo,
    Multiplicadores,
    QuoteError,
    QuoteRequest,
    QuoteResponse,
)

SAMPLE_DIR = Path(__file__).parent / "sample"


def load_sample_conversations() -> list[dict]:
    samples = []
    for f in sorted(SAMPLE_DIR.glob("conv_*.json")):
        samples.append(json.loads(f.read_text()))
    return samples


class MockQuoteClient:
    def __init__(self):
        planos_data = {
            "planos": [
                {
                    "plano_id": "completo",
                    "plano_nome": "Completo",
                    "premio_base_mensal": 180.0,
                    "franquia": 3000,
                    "coberturas": [
                        "Colisao",
                        "Roubo e Furto",
                        "Incendio",
                        "Danos a Terceiros",
                        "Vidros",
                        "Assistencia 24h",
                    ],
                },
                {
                    "plano_id": "essencial",
                    "plano_nome": "Essencial",
                    "premio_base_mensal": 120.0,
                    "franquia": 5000,
                    "coberturas": ["Colisao", "Roubo e Furto", "Incendio"],
                },
                {
                    "plano_id": "premium",
                    "plano_nome": "Premium",
                    "premio_base_mensal": 280.0,
                    "franquia": 2000,
                    "coberturas": [
                        "Colisao",
                        "Roubo e Furto",
                        "Incendio",
                        "Danos a Terceiros",
                        "Vidros",
                        "Assistencia 24h",
                        "Carro Reserva",
                    ],
                },
            ]
        }
        self._planos = planos_data
        self._planos_map = {p["plano_id"]: p for p in planos_data["planos"]}

    async def get_planos(self) -> dict:
        return self._planos

    async def post_quote(self, request: QuoteRequest) -> QuoteResponse | QuoteError:
        if request.idade > 75:
            return QuoteError(
                error="recusada",
                motivo="Idade do condutor acima do limite aceitavel (75 anos)",
            )

        current_year = 2026
        vehicle_age = current_year - request.veiculo_ano
        if vehicle_age > 20:
            return QuoteError(
                error="recusada",
                motivo=f"Veiculo com mais de 20 anos de fabricacao ({request.veiculo_ano})",
            )

        plano = self._planos_map.get(request.plano_id, self._planos_map["essencial"])

        age_mult = 1.8 if request.idade > 60 else 1.3 if request.idade > 35 else 1.0
        vehicle_mult = 1.3 if vehicle_age > 10 else 1.1 if vehicle_age > 5 else 1.0
        region_mult = 1.3

        base = plano["premio_base_mensal"]
        premio = round(base * age_mult * vehicle_mult * region_mult, 2)

        return QuoteResponse(
            plano_id=plano["plano_id"],
            plano_nome=plano["plano_nome"],
            premio_mensal=premio,
            franquia=plano["franquia"],
            coberturas=plano["coberturas"],
            multiplicadores=Multiplicadores(
                faixa_etaria=age_mult,
                idade_veiculo=vehicle_mult,
                regiao=region_mult,
            ),
            carencia=CarenciaInfo(
                coberturas=["Colisao", "Roubo e Furto"],
                dias=30,
                observacao="Carencia padrao de 30 dias para colisao e roubo/furto",
            ),
            moeda="BRL",
        )

    async def close(self):
        pass


def build_eval_agent():
    llm = get_chat_model()
    mock_client = MockQuoteClient()
    return build_agent(llm, mock_client)


@pytest.fixture(scope="session")
def eval_judge():
    return build_judge()


@pytest.fixture(scope="session")
def eval_agent():
    return build_eval_agent()


@pytest.fixture(scope="session")
def sample_conversations():
    return load_sample_conversations()
