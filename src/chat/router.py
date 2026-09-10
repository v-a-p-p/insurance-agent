import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from src.chat.agent import get_agent
from src.chat.schemas import ChatRequest, ChatResponse, Lead

router = APIRouter(prefix="/chat", tags=["chat"])

AgentDep = Annotated[CompiledStateGraph, Depends(get_agent)]


def _lead_to_state(lead: Lead) -> dict:
    state: dict = {}
    if lead.age is not None:
        state["age"] = lead.age
    if lead.vehicle_year is not None:
        state["veiculo_ano"] = lead.vehicle_year
    if lead.cep is not None:
        state["cep"] = lead.cep
    if lead.vehicle_model is not None:
        state["vehicle_model"] = lead.vehicle_model
    return state


def _last_ai_reply(result: dict) -> str:
    for message in reversed(result.get("messages", [])):
        if isinstance(message, AIMessage) and message.content:
            return str(message.content)
    return ""


@router.post("/")
async def chat(request: ChatRequest, agent: AgentDep) -> ChatResponse:
    conversation_id = request.conversation_id or str(uuid.uuid4())

    input_state: dict = {"messages": [HumanMessage(content=request.message)]}
    if request.lead is not None:
        input_state["lead"] = _lead_to_state(request.lead)

    result = await agent.ainvoke(
        input_state,
        config={"configurable": {"thread_id": conversation_id}},
    )

    return ChatResponse(reply=_last_ai_reply(result))
