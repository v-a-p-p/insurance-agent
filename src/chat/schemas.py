from pydantic import BaseModel


class Lead(BaseModel):
    name: str
    age: int | None = None
    cep: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    cpf: str | None = None


class ChatRequest(BaseModel):
    message: str
    lead: Lead | None = None
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
