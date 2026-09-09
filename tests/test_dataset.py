from src.dataset.loader import load_conversations
from src.dataset.schemas import Conversation, ConversationMessage


def test_load_conversations():
    convs = load_conversations()
    assert len(convs) > 0
    assert all(isinstance(c, Conversation) for c in convs)
    assert all(isinstance(m, ConversationMessage) for m in convs[0].messages)


def test_messages_ordered():
    convs = load_conversations()
    for conv in convs[:5]:
        indices = [m.message_index for m in conv.messages]
        assert indices == sorted(indices), (
            f"Messages not sorted in {conv.conversation_id}"
        )


def test_conversation_id_present():
    convs = load_conversations()
    for conv in convs[:10]:
        assert conv.conversation_id
        assert len(conv.messages) > 0
