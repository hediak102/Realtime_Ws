from datetime import datetime
from sqlmodel import SQLModel, Field

class Room(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner_id: int = Field(foreign_key="user.id")

class RoomCreate(SQLModel):
    name: str