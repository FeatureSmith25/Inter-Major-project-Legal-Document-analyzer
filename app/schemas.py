from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document: str
    page: int | None = None
    section: str | None = None
    clause: str | None = None
    text: str


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


class QuestionResponse(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool


class ComparisonChange(BaseModel):
    category: str
    old: str | None
    new: str | None
    change: str
    source: list[Citation]
