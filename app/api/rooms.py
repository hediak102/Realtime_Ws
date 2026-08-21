from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.db.session import get_session
from app.api.auth import get_current_user
from app.models.user import User
from app.models.room import Room, RoomCreate
from app.models.message import Message, MessageRead

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

@router.get("/{room_id}/messages", response_model=List[MessageRead])
async def get_room_messages(
    room_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 10,
):
    room = session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    query = select(Message).where(Message.room_id == room_id).order_by(Message.created_at.desc()).offset(skip).limit(limit)
    messages = session.exec(query).all()
    messages.reverse()
    
    result = []
    for m in messages:
        author = session.get(User, m.user_id)
        result.append(MessageRead(
            id=m.id,
            content=m.content,
            created_at=m.created_at,
            user_id=m.user_id,
            username=author.username if author else "inconnu",
            room_id=m.room_id,
        ))
    return result

