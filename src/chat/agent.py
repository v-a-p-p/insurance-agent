import operator
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
from typing_extensions import TypedDict

from src.chat.model import get_chat_model
from src.chat.prompt import build_system_prompt
from src.config import settings
from src.quote.client import QuoteClient
from src.quote.schemas import QuoteRequest, QuoteResponse


class LeadExtraction(BaseModel):
    age: int | None = None
    veiculo_ano: int | None = None
    vehicle_model: str | None = None
    cep: str | None = None
    data_inicio: str | None = None


class ClassificationResult(BaseModel):
    intent: Literal["respond", "qualify"]
    lead_update: LeadExtraction | None = None


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    lead: dict
    planos: dict | None
    quote: dict | None
    conversation_id: str
    tried_plans: Annotated[list[str], operator.add]
    next: str


DEFAULT_PLAN_ORDER = ["completo", "essencial", "premium"]

FIELD_LABELS = {
    "age": "idade",
    "veiculo_ano": "ano do veiculo",
    "vehicle_model": "modelo do veiculo",
    "cep": "CEP",
    "data_inicio": "data de inicio",
}


def _extract_lead_from_message(
    message: str, lead: dict, model
) -> ClassificationResult:
    lead_str = _serialize_lead(lead)
    system = SystemMessage(
        content=(
            "Voce e um classificador de mensagens de leads para cotacao de seguro auto.\n"
            "Sua unica funcao e classificar e extrair dados. NAO gere respostas.\n\n"
            f"Dados ja coletados: {lead_str}\n\n"
            "DADOS DE QUALIFICACAO (apenas estes campos):\n"
            "- age: idade do condutor (numero inteiro)\n"
            "- veiculo_ano: ano de fabricacao do veiculo (numero inteiro)\n"
            "- vehicle_model: modelo do veiculo (string)\n"
            "- cep: CEP de pernoite (string)\n"
            "- data_inicio: data de inicio da vigencia (string, formato YYYY-MM-DD)\n\n"
            "NAO sao dados de qualificacao: email, telefone, WhatsApp, CPF, RG, nome, "
            "audio, mensagem de voz.\n\n"
            "REGRAS:\n"
            "- Se a mensagem contiver APENAS cumprimento, pergunta, contato (email/telefone/"
            "WhatsApp), CPF, audio ou confirmacao → intent='respond', lead_update=null\n"
            "- Se a mensagem contiver dados de qualificacao NOVOS (nao ja coletados) → "
            "intent='qualify' e preencha apenas os campos novos em lead_update\n"
            "- Se os dados ja foram todos coletados antes → intent='respond', lead_update=null"
        )
    )
    structured = model.with_structured_output(ClassificationResult)
    return structured.invoke([system, HumanMessage(content=message)])


def _serialize_lead(lead: dict) -> str:
    parts = []
    if lead.get("age"):
        parts.append(f"idade: {lead['age']}")
    if lead.get("veiculo_ano"):
        parts.append(f"ano do veiculo: {lead['veiculo_ano']}")
    if lead.get("vehicle_model"):
        parts.append(f"modelo do veiculo: {lead['vehicle_model']}")
    if lead.get("cep"):
        parts.append(f"CEP: {lead['cep']}")
    if lead.get("data_inicio"):
        parts.append(f"data de inicio: {lead['data_inicio']}")
    return ", ".join(parts) if parts else "(nenhum dado ainda)"


def _serialize_quote(quote: dict | None) -> str:
    if not quote or not quote.get("success"):
        return "Nenhuma cotacao apresentada ainda."
    return (
        f"Cotacao ja apresentada:\n"
        f"  Plano: {quote['plano_nome']} ({quote['plano_id']})\n"
        f"  Valor mensal: {quote.get('moeda', 'BRL')} {quote['premio_mensal']}\n"
        f"  Franquia: {quote.get('moeda', 'BRL')} {quote['franquia']}\n"
        f"  Coberturas: {', '.join(quote.get('coberturas', []))}"
    )


def _recent_history(messages: list, n: int = 6) -> str:
    if not messages:
        return "(sem historico)"
    recent = messages[-n:]
    lines = []
    for msg in recent:
        role = "lead" if isinstance(msg, HumanMessage) else "Camila"
        content = msg.content if hasattr(msg, "content") else str(msg)
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines)


def build_agent(llm, quote_client: QuoteClient) -> CompiledStateGraph:
    system_prompt = build_system_prompt()

    def classify_intent(state: AgentState, config: RunnableConfig) -> dict:
        messages = state.get("messages", [])
        lead = state.get("lead", {})

        if not messages:
            return {"lead": lead, "next": "respond"}

        last_msg = messages[-1]
        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        result = _extract_lead_from_message(content, lead, llm)
        updated_lead = dict(lead)
        if result.lead_update is not None:
            extraction = result.lead_update.model_dump(exclude_none=True)
            updated_lead.update(extraction)

        return {
            "lead": updated_lead,
            "next": result.intent,
        }

    def qualify_lead(state: AgentState) -> dict:
        lead = state.get("lead", {})
        quote = state.get("quote")
        required = ["age", "veiculo_ano"]
        missing = [f for f in required if not lead.get(f)]

        if not missing:
            if quote and quote.get("success"):
                return {"next": "respond_contextual"}
            return {"next": "quote"}

        lead_str = _serialize_lead(lead)
        missing_labels = [FIELD_LABELS.get(f, f) for f in missing]
        ask_prompt = (
            f"Dados ja coletados do lead: {lead_str}\n"
            f"Dados ainda faltando: {', '.join(missing_labels)}.\n"
            f"Gere uma mensagem amigavel perguntando pelos dados faltantes. "
            f"Seja direta e simpatica, em portugues brasileiro. "
            f"Responda APENAS com a mensagem, sem prefixos."
        )
        response = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=ask_prompt)]
        )
        return {
            "messages": [AIMessage(content=response.content)],
            "next": "respond",
        }

    def respond_to_lead(state: AgentState) -> dict:
        messages = state.get("messages", [])
        lead = state.get("lead", {})
        quote = state.get("quote")

        last_msg = ""
        if messages:
            last = messages[-1]
            last_msg = last.content if hasattr(last, "content") else str(last)

        lead_str = _serialize_lead(lead)
        quote_str = _serialize_quote(quote)
        history = _recent_history(messages[:-1]) if len(messages) > 1 else "(primeira mensagem)"

        context_prompt = (
            f"Historico recente da conversa:\n{history}\n\n"
            f"Dados do lead: {lead_str}\n"
            f"{quote_str}\n\n"
            f"O lead acabou de dizer: \"{last_msg}\"\n\n"
            f"Responda como Camila de forma contextual e apropriada. "
            f"Se o lead forneceu contato (email, WhatsApp, telefone), agradeca e "
            f"pergunte se quer seguir com a cotacao ja apresentada. "
            f"Se o lead esta cumprimentando ou confirmando algo, responda de forma "
            f"simpatica e direta. "
            f"Se a mensagem for um audio ou 'mensagem de voz', peca para o lead "
            f"enviar por texto. "
            f"Se o lead diz 'preciso pensar' ou 'qualquer coisa me chama', "
            f"seja compreensiva e deixe aberto para ele voltar quando quiser. "
            f"Se ja existe uma cotacao apresentada, SEMPRE faca referencia a ela "
            f"e pergunte se o lead quer seguir com o plano. "
            f"Responda APENAS com a mensagem, sem prefixos."
        )
        response = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=context_prompt)]
        )
        return {"messages": [AIMessage(content=response.content)]}

    async def request_quote(state: AgentState) -> dict:
        lead = state.get("lead", {})
        tried = list(state.get("tried_plans", []))
        planos = state.get("planos")

        if planos is None:
            planos = await quote_client.get_planos()

        plano_id = next((p for p in DEFAULT_PLAN_ORDER if p not in tried), None)
        if plano_id is None:
            return {
                "quote": {"error": "all_refused", "motivo": ""},
                "next": "decide",
            }

        idade = lead.get("age", 0)
        veiculo_ano = lead.get("veiculo_ano", 0)
        cep = lead.get("cep")
        data_inicio = lead.get("data_inicio")

        result = await quote_client.post_quote(
            QuoteRequest(
                plano_id=plano_id,
                idade=idade,
                veiculo_ano=veiculo_ano,
                cep=cep or None,
                data_inicio=data_inicio or None,
            )
        )

        if isinstance(result, QuoteResponse):
            quote_dict = {
                "success": True,
                "plano_id": result.plano_id,
                "plano_nome": result.plano_nome,
                "premio_mensal": result.premio_mensal,
                "franquia": result.franquia,
                "coberturas": result.coberturas,
                "moeda": result.moeda,
            }
        else:
            quote_dict = {
                "success": False,
                "error": result.error,
                "motivo": result.motivo or result.message or "",
            }

        return {
            "quote": quote_dict,
            "planos": planos,
            "tried_plans": [plano_id],
            "next": "decide",
        }

    def decide(state: AgentState) -> dict:
        quote = state.get("quote")
        tried = list(state.get("tried_plans", []))

        if not quote:
            return {
                "messages": [
                    AIMessage(content="Ainda nao tenho uma cotacao para apresentar.")
                ],
                "next": "respond",
            }

        if quote.get("success"):
            cot = quote
            coberturas = ", ".join(cot.get("coberturas", []))
            reply = (
                f"Otima noticia! Sua cotacao do plano **{cot['plano_nome']}** "
                f"ficou assim:\n\n"
                f"Valor mensal: {cot.get('moeda', 'BRL')} {cot['premio_mensal']:.2f}\n"
                f"Franquia: {cot.get('moeda', 'BRL')} {cot['franquia']:.0f}\n"
                f"Coberturas: {coberturas}\n\n"
                f"Gostaria de seguir com esse plano?"
            )
            return {
                "messages": [AIMessage(content=reply)],
                "next": "respond",
            }

        untried = [p for p in DEFAULT_PLAN_ORDER if p not in tried]
        if untried:
            return {"next": "retry"}

        error = quote.get("error", "")
        motivo = quote.get("motivo", "")
        reply = (
            "Infelizmente nao consegui gerar uma cotacao no momento. "
            + (f"Motivo: {motivo}" if motivo else f"Erro: {error}")
            + " Um de nossos atendentes vai entrar em contato para te ajudar. "
            "Posso ajudar com mais alguma coisa?"
        )
        return {
            "messages": [AIMessage(content=reply)],
            "next": "respond",
        }

    def route_after_classify(state: AgentState) -> str:
        return "qualify_lead" if state.get("next") == "qualify" else "respond_to_lead"

    def route_after_qualify(state: AgentState) -> str:
        nxt = state.get("next")
        if nxt == "quote":
            return "request_quote"
        if nxt == "respond_contextual":
            return "respond_to_lead"
        return "respond"

    def route_after_decide(state: AgentState) -> str:
        return "request_quote" if state.get("next") == "retry" else "respond"

    builder = StateGraph(AgentState)

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("qualify_lead", qualify_lead)
    builder.add_node("respond_to_lead", respond_to_lead)
    builder.add_node("request_quote", request_quote)
    builder.add_node("decide", decide)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {"qualify_lead": "qualify_lead", "respond_to_lead": "respond_to_lead"},
    )
    builder.add_conditional_edges(
        "qualify_lead",
        route_after_qualify,
        {
            "request_quote": "request_quote",
            "respond_to_lead": "respond_to_lead",
            "respond": END,
        },
    )
    builder.add_edge("request_quote", "decide")
    builder.add_conditional_edges(
        "decide",
        route_after_decide,
        {
            "request_quote": "request_quote",
            "respond": END,
        },
    )
    builder.add_edge("respond_to_lead", END)

    return builder.compile(checkpointer=MemorySaver())


_agent: CompiledStateGraph | None = None


def get_agent() -> CompiledStateGraph:
    global _agent
    if _agent is None:
        llm = get_chat_model()
        quote_client = QuoteClient(
            base_url=settings.quote_service_url,
            timeout=settings.quote_service_timeout,
        )
        _agent = build_agent(llm, quote_client)
    return _agent