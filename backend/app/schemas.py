from datetime import datetime
from pydantic import BaseModel


class UploadPaperResponse(BaseModel):
    id: int
    title: str
    status: str
    duplicate: bool = False
    duplicate_of: int | None = None
    message: str | None = None


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
    summary_version: int
    summary_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChatMessageIn(BaseModel):
    message: str
    update_summary: bool = False


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    source_hint: str | None
    created_at: datetime


class ChatReply(BaseModel):
    answer: ChatMessageOut
    summary: dict | None
    summary_version: int
    summary_updated_at: datetime | None
