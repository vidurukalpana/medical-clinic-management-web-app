from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

MAX_MESSAGE_LENGTH = 1000
MAX_HISTORY_MESSAGES = 20


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH
        ),
    ]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_HISTORY_MESSAGES)

    @model_validator(mode="after")
    def require_user_question_last(self) -> "ChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("The last message must be the user's question.")
        return self


class ChatReply(BaseModel):
    reply: str
