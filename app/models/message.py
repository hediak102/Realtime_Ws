from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import List, Optional

class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: int = Field(foreign_key="user.id")
    room_id: int = Field(foreign_key="room.id")

class MessageRead(SQLModel):
    id: int
    content: str
    created_at: datetime
    user_id: int
    username: str
    room_id: int
class MessagesPage(SQLModel):
    messages: List[MessageRead]
    next_cursor: Optional[str] = None
    has_more: bool