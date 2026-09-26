from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.config import Settings, get_settings
from app.dependencies import DatabaseSession
from app.schemas.chatbot import ChatReply, ChatRequest
from app.services.chatbot import ChatModel, OllamaChatModel, answer_question

router = APIRouter(prefix="/chatbot", tags=["chatbot"])
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_chat_model(settings: AppSettings) -> ChatModel:
    return OllamaChatModel(
        settings.chatbot_base_url,
        settings.chatbot_model,
        settings.chatbot_timeout_seconds,
    )


@router.post(
    "/messages",
    response_model=ChatReply,
    summary="Ask the clinic assistant a question",
    responses={503: {"description": "The chat assistant is unavailable"}},
)
def ask_question(
    chat: ChatRequest,
    response: Response,
    db: DatabaseSession,
    settings: AppSettings,
    model: Annotated[ChatModel, Depends(get_chat_model)],
) -> ChatReply:
    response.headers["Cache-Control"] = "no-store"
    return ChatReply(reply=answer_question(db, model, chat.messages, settings.timezone))
