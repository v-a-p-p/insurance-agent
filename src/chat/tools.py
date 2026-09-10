from langchain_core.tools import tool

from src.quote.client import QuoteClient
from src.quote.schemas import QuoteRequest, QuoteResponse


def make_get_planos(quote_client: QuoteClient):
    @tool
    async def get_planos() -> str:
        """Consulta a tabela de planos de seguro disponiveis, com precos base,
        franquias e coberturas de cada plano.

        Use esta ferramenta para listar os planos ao lead ou quando precisar
        saber quais planos estao disponiveis.
        """
        data = await quote_client.get_planos()
        planos = data.get("planos", [])
        if not planos:
            return "Nenhum plano disponivel no momento."

        lines = ["Planos disponiveis:"]
        for p in planos:
            coberturas = ", ".join(p.get("coberturas", []))
            lines.append(
                f"- {p['nome']} ({p['id']}): R$ {p['base_mensal']:.2f}/mes, "
                f"franquia R$ {p['franquia']:.0f}, cobre: {coberturas}"
            )
        return "\n".join(lines)

    return get_planos


def make_cotar_seguro(quote_client: QuoteClient):
    @tool
    async def cotar_seguro(
        plano_id: str,
        idade: int,
        veiculo_ano: int,
        cep: str | None = None,
        data_inicio: str | None = None,
    ) -> str:
        """Solicita uma cotacao de seguro para o lead.

        Use esta ferramenta quando tiver os dados necessarios do lead (idade,
        ano do veiculo, CEP) para gerar uma cotacao real.

        Args:
            plano_id: ID do plano (essencial, completo, premium).
            idade: Idade do condutor principal.
            veiculo_ano: Ano de fabricacao do veiculo.
            cep: CEP de pernoite do veiculo (opcional).
            data_inicio: Data de inicio da vigencia no formato YYYY-MM-DD (opcional).
        """
        request = QuoteRequest(
            plano_id=plano_id,
            idade=idade,
            veiculo_ano=veiculo_ano,
            cep=cep,
            data_inicio=data_inicio,
        )
        result = await quote_client.post_quote(request)

        if isinstance(result, QuoteResponse):
            coberturas = ", ".join(result.coberturas)
            response = (
                f"Cotacao realizada com sucesso!\n"
                f"Plano: {result.plano_nome} ({result.plano_id})\n"
                f"Premio mensal: {result.moeda} {result.premio_mensal:.2f}\n"
                f"Franquia: {result.moeda} {result.franquia:.0f}\n"
                f"Coberturas: {coberturas}\n"
                f"Multiplicadores aplicados: "
                f"faixa etaria {result.multiplicadores.faixa_etaria}x, "
                f"idade veiculo {result.multiplicadores.idade_veiculo}x, "
                f"regiao {result.multiplicadores.regiao}x"
            )
            if result.carencia:
                cob_carencia = ", ".join(result.carencia.coberturas)
                response += (
                    f"\nCarencia de {result.carencia.dias} dias para: {cob_carencia}"
                )
            if result.primeiro_pagamento_pro_rata:
                ppr = result.primeiro_pagamento_pro_rata
                response += (
                    f"\nPrimeiro pagamento (pro-rata): "
                    f"{result.moeda} {ppr.valor_primeiro_pagamento:.2f} "
                    f"({ppr.dias_cobrados} de {ppr.dias_no_mes} dias)"
                )
            return response

        motivo = result.motivo or result.message or result.detalhe or ""
        return f"Cotacao recusada para o plano {plano_id}. Erro: {result.error}. " + (
            f"Motivo: {motivo}" if motivo else ""
        )

    return cotar_seguro
