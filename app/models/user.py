from datetime import datetime
from pydantic import BaseModel
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str
    email: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(SQLModel):
    username: str
    password: str
    email: str

class UserRead(SQLModel):
    id: int
    username: str
    email: str

class RefreshRequest(BaseModel):
    refresh_token: str