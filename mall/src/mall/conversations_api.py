from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from mall import conversations, db
from mall.models import (
    ConversationDetail,
    ConversationSummary,
    Message,
    MessageCreate,
)


def get_session() -> Iterator[Session]:
    """Provide an ORM session, refusing requests until the schema exists."""
    if not db.ensure_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=db.unavailable_detail(),
        )
    with db.session() as session:
        yield session


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    session: Session = Depends(get_session),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[dict[str, Any]]:
    return conversations.list_conversations(session, limit)


@router.post(
    "",
    response_model=ConversationDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return {**conversations.create_conversation(session), "messages": []}


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    detail = conversations.get_conversation_detail(session, conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return detail


@router.get("/{conversation_id}/messages", response_model=list[Message])
def list_messages(
    conversation_id: str,
    session: Session = Depends(get_session),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    if conversations.get_conversation(session, conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversations.list_messages(session, conversation_id, limit)


@router.post(
    "/{conversation_id}/messages",
    response_model=Message,
    status_code=status.HTTP_201_CREATED,
)
def append_message(
    conversation_id: str,
    payload: MessageCreate,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    message = conversations.append_message(
        session,
        conversation_id,
        payload.role,
        payload.content,
        payload.status,
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return message


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    session: Session = Depends(get_session),
) -> Response:
    if not conversations.delete_conversation(session, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)