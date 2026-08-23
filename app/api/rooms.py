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

    # Requête optimisée avec JOIN
    query = (
        select(Message, User)
        .join(User, Message.user_id == User.id)
        .where(Message.room_id == room_id)
    )

    # Filtrage par curseur
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        query = query.where(
            or_(
                Message.created_at < cursor_created_at,
                and_(Message.created_at == cursor_created_at, Message.id < cursor_id),
            )
        )

    query = query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
    
    # Exec renvoie des tuples (Message, User)
    rows = session.exec(query).all()

    has_more = len(rows) > limit
    rows = list(rows[:limit])
    
    # 1. Calcul du next_cursor AVANT d'inverser la liste (sur le message le plus ancien)
    next_cursor = None
    if has_more and rows:
        oldest_message, _ = rows[-1]  # Le dernier élément du tableau temporaire est le plus ancien
        next_cursor = encode_cursor(oldest_message.created_at, oldest_message.id)

    # 2. Remettre les messages dans l'ordre chronologique (du plus ancien au plus récent)
    rows.reverse()

    # 3. Construction de la réponse DTO
    result = [
        MessageRead(
            id=m.id,
            content=m.content,
            created_at=m.created_at,
            user_id=m.user_id,
            username=author.username if author else "inconnu",
            room_id=m.room_id,
        )
        for m, author in rows
    ]

    return MessagesPage(messages=result, next_cursor=next_cursor, has_more=has_more)