import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mall import db
from mall.entities import Conversation, Message


TITLE_LENGTH = 40
PREVIEW_LENGTH = 120


def derive_title(text: str) -> str:
    condensed = " ".join(text.split())
    if len(condensed) <= TITLE_LENGTH:
        return condensed
    return f"{condensed[:TITLE_LENGTH]}…"


def _serialize_message(message: Message) -> dict[str, Any]:
    return {
        "id": int(message.id),
        "role": message.role,
        "content": message.content,
        "status": message.status,
        "created_at": db.to_iso(message.created_at),
    }


def _serialize_conversation(conversation: Conversation) -> dict[str, Any]:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": db.to_iso(conversation.created_at),
        "updated_at": db.to_iso(conversation.updated_at),
    }


def list_conversations(
    session: Session,
    limit: int = 100,
) -> list[dict[str, Any]]:
    message_count = (
        select(func.count(Message.id))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )
    preview = (
        select(func.left(Message.content, PREVIEW_LENGTH))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .order_by(Message.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    statement = (
        select(Conversation, message_count, preview)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(limit)
    )

    rows = session.execute(statement).all()
    return [
        {
            **_serialize_conversation(conversation),
            "message_count": int(count),
            "preview": " ".join((preview_text or "").split()),
        }
        for conversation, count, preview_text in rows
    ]


def create_conversation(session: Session) -> dict[str, Any]:
    now = db.utc_now()
    conversation = Conversation(
        id=str(uuid.uuid4()),
        title="",
        created_at=now,
        updated_at=now,
    )
    session.add(conversation)
    session.commit()
    return _serialize_conversation(conversation)


def get_conversation(
    session: Session,
    conversation_id: str,
) -> dict[str, Any] | None:
    conversation = session.get(Conversation, conversation_id)
    return _serialize_conversation(conversation) if conversation else None


def get_conversation_detail(
    session: Session,
    conversation_id: str,
) -> dict[str, Any] | None:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        return None
    return {
        **_serialize_conversation(conversation),
        "messages": list_messages(session, conversation_id),
    }


def list_messages(
    session: Session,
    conversation_id: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if limit is None:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        )
        rows = session.scalars(statement).all()
    else:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        rows = list(reversed(session.scalars(statement).all()))

    return [_serialize_message(message) for message in rows]


def append_message(
    session: Session,
    conversation_id: str,
    role: str,
    content: str,
    status: str,
) -> dict[str, Any] | None:
    conversation = session.get(
        Conversation,
        conversation_id,
        with_for_update=True,
    )
    if conversation is None:
        return None

    now = db.utc_now()
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        status=status,
        created_at=now,
    )
    session.add(message)

    if not conversation.title and role == "user":
        conversation.title = derive_title(content)
    conversation.updated_at = now

    session.commit()
    return _serialize_message(message)


def delete_conversation(session: Session, conversation_id: str) -> bool:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        return False

    session.delete(conversation)
    session.commit()
    return True