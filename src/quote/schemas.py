from pydantic import BaseModel, Field


class QuoteRequest(BaseModel):
    plano_id: str = Field(default="essencial")
    idade: int = Field(ge=0, le=200)
    veiculo_ano: int = Field(ge=1950, le=2100)
    cep: str | None = None
    data_inicio: str | None = Field(default=None)


class PrimeiroPagamentoProRata(BaseModel):
    dias_no_mes: int
    dias_cobrados: int
    valor_primeiro_pagamento: float


class CarenciaInfo(BaseModel):
    coberturas: list[str]
    dias: int
    observacao: str


class Multiplicadores(BaseModel):
    faixa_etaria: float
    idade_veiculo: float
    regiao: float


class QuoteResponse(BaseModel):
    plano_id: str
    plano_nome: str
    premio_mensal: float
    franquia: int
    coberturas: list[str]
    multiplicadores: Multiplicadores
    carencia: CarenciaInfo
    moeda: str
    primeiro_pagamento_pro_rata: PrimeiroPagamentoProRata | None = None


class QuoteError(BaseModel):
    error: str
    motivo: str | None = Field(default=None)
    message: str | None = Field(default=None)
    detalhe: str | None = Field(default=None)
