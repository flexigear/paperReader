from datetime import datetime
from pydantic import BaseModel


class UploadPaperResponse(BaseModel):
    id: int
    title: str
    status: str


class PaperListItem(BaseModel):
    id: int
    title: str
    filename: str
    status: str
    created_at: datetime


class PaperDetail(BaseModel):
    id: int
    title: str
    filename: str
    status: str
    summary: dict | None
    created_at: datetime
    updated_at: datetime


class ChatMessageIn(BaseModel):
    message: str


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    source_hint: str | None
    created_at: datetime


class ChatReply(BaseModel):
    answer: ChatMessageOut
