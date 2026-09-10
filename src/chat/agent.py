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


class ClassificationResult(BaseModel):
    intent: Literal["respond", "qualify"]
    reply: str | None = None
    lead_update: dict | None = None


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    lead: dict
    planos: dict | None
    quote: dict | None
    conversation_id: str
    tried_plans: Annotated[list[str], operator.add]
    next: str


DEFAULT_PLAN_ORDER = ["completo", "essencial", "premium"]


def _extract_lead_from_message(message: str, model) -> ClassificationResult:
    system = SystemMessage(
        content=(
            "Voce e um extrator de dados de leads. "
            "Analise a mensagem do lead e extraia os campos abaixo. "
            "Se a mensagem for apenas um cumprimento (oi, ola, bom dia), "
            "intent = 'respond'. "
            "Se a mensagem contiver dados de qualificacao (idade, veiculo, CEP, "
            "data de inicio), intent = 'qualify' e preencha lead_update. "
            "Se a mensagem for uma pergunta ou outra coisa, intent = 'respond'."
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


def build_agent(llm, quote_client: QuoteClient) -> CompiledStateGraph:
    system_prompt = build_system_prompt()

    def classify_intent(state: AgentState, config: RunnableConfig) -> dict:
        messages = state.get("messages", [])
        lead = state.get("lead", {})

        if not messages:
            return {"lead": lead, "next": "respond"}

        last_msg = messages[-1]
        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        result = _extract_lead_from_message(content, llm)
        updated_lead = dict(lead)
        if result.lead_update:
            updated_lead.update(result.lead_update)

        return {
            "messages": [AIMessage(content=result.reply or "")],
            "lead": updated_lead,
            "next": result.intent,
        }

    def qualify_lead(state: AgentState) -> dict:
        lead = state.get("lead", {})
        required = ["age", "veiculo_ano"]
        missing = [f for f in required if not lead.get(f)]

        if not missing:
            return {"next": "quote"}

        lead_str = _serialize_lead(lead)
        ask_prompt = (
            f"Dados ja coletados do lead: {lead_str}\n"
            f"Dados ainda faltando: {', '.join(missing)}.\n"
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
        return "qualify_lead" if state.get("next") == "qualify" else "respond"

    def route_after_qualify(state: AgentState) -> str:
        return "request_quote" if state.get("next") == "quote" else "respond"

    def route_after_decide(state: AgentState) -> str:
        return "request_quote" if state.get("next") == "retry" else "respond"

    builder = StateGraph(AgentState)

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("qualify_lead", qualify_lead)
    builder.add_node("request_quote", request_quote)
    builder.add_node("decide", decide)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {"qualify_lead": "qualify_lead", "respond": END},
    )
    builder.add_conditional_edges(
        "qualify_lead",
        route_after_qualify,
        {"request_quote": "request_quote", "respond": END},
    )
    builder.add_edge("request_quote", "decide")
    builder.add_conditional_edges(
        "decide",
        route_after_decide,
        {"request_quote": "request_quote", "respond": END},
    )

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
