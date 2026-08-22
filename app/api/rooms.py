from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.db.session import get_session
from app.api.auth import get_current_user
from app.models.user import User
from app.models.room import Room, RoomCreate
from app.models.message import Message, MessageRead,MessagesPage
from app.core.pagination import encode_cursor, decode_cursor
from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload
# ---> AJOUTE OU VÉRIFIE CETTE LIGNE <---
router = APIRouter(prefix="/rooms", tags=["Rooms"])

@router.post("", response_model=Room)
async def create_room(
    room: RoomCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_room = Room(name=room.name, owner_id=current_user.id)
    session.add(db_room)
    session.commit()
    session.refresh(db_room)
    return db_room

@router.get("", response_model=List[Room])
async def get_rooms(session: Session = Depends(get_session)):
    return session.exec(select(Room)).all()

@router.get("/{room_id}", response_model=Room)
async def get_room(room_id: int, session: Session = Depends(get_session)):
    room = session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

@router.get("/{room_id}/messages", response_model=MessagesPage)
async def get_room_messages(
    room_id: int,
    session: Session = Depends(get_session),
    limit: int = 20,
    cursor: str | None = None,
):
    room = session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Requête simple sans joinedload
    query = select(Message).where(Message.room_id == room_id)

    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        query = query.where(
            or_(
                Message.created_at < cursor_created_at,
                and_(Message.created_at == cursor_created_at, Message.id < cursor_id),
            )
        )

    query = query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
    
    messages_db = session.exec(query).all()

    has_more = len(messages_db) > limit
    messages_db = list(messages_db[:limit])
    messages_db.reverse()

    next_cursor = None
    if has_more and messages_db:
        oldest = messages_db[0]
        next_cursor = encode_cursor(oldest.created_at, oldest.id)

    # Récupération de l'utilisateur via session.get
    result = []
    for m in messages_db:
        author = session.get(User, m.user_id)
        result.append(
            MessageRead(
                id=m.id,
                content=m.content,
                created_at=m.created_at,
                user_id=m.user_id,
                username=author.username if author else "inconnu",
                room_id=m.room_id,
            )
        )

    return MessagesPage(messages=result, next_cursor=next_cursor, has_more=has_more)