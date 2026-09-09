from pydantic import BaseModel


class ConversationMessage(BaseModel):
    conversation_id: str
    message_index: int
    timestamp: str | None = None
    sender_role: str | None = None
    sender_name: str | None = None
    message_type: str | None = None
    message_body: str
    channel: str | None = None
    conversation_outcome: str | None = None
    lead_idade_informada: int | None = None
    veiculo_texto: str | None = None


class Conversation(BaseModel):
    conversation_id: str
    outcome: str | None = None
    messages: list[ConversationMessage]
