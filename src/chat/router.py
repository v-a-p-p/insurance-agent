from fastapi import APIRouter

from src.chat.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/")
async def chat(_body: ChatRequest) -> ChatResponse:
    return ChatResponse(reply="hello")
