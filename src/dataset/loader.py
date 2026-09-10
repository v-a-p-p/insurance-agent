from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.dataset.schemas import Conversation, ConversationMessage

DEFAULT_PATH = Path("namastex-fde-challenge/dataset/conversations.parquet")


@lru_cache(maxsize=1)
def _load_default_conversations() -> tuple[Conversation, ...]:
    df = pd.read_parquet(DEFAULT_PATH)

    conversations: list[Conversation] = []
    for conv_id, group in df.groupby("conversation_id"):
        sorted_group = group.sort_values("message_index")
        messages = [
            ConversationMessage(**row.to_dict()) for _, row in sorted_group.iterrows()
        ]
        outcome = sorted_group.iloc[0].get("conversation_outcome", None)
        conversations.append(
            Conversation(conversation_id=conv_id, outcome=outcome, messages=messages)
        )

    return tuple(conversations)


def load_conversations(path: Path | None = None) -> list[Conversation]:
    if path is None or path == DEFAULT_PATH:
        return list(_load_default_conversations())

    df = pd.read_parquet(path)
    conversations: list[Conversation] = []
    for conv_id, group in df.groupby("conversation_id"):
        sorted_group = group.sort_values("message_index")
        messages = [
            ConversationMessage(**row.to_dict()) for _, row in sorted_group.iterrows()
        ]
        outcome = sorted_group.iloc[0].get("conversation_outcome", None)
        conversations.append(
            Conversation(conversation_id=conv_id, outcome=outcome, messages=messages)
        )

    return conversations
