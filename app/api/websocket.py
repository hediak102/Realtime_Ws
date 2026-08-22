from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlmodel import Session, select
from jose import jwt, JWTError

from app.db.session import get_session
from app.core.config import settings
from app.models.user import User
from app.models.room import Room
from app.models.message import Message
from app.services.connection import manager

router = APIRouter(tags=["WebSocket"])

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: int,
    token: str = Query(...),
    session: Session = Depends(get_session),
):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if username is None:
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.close(code=1008)
        return

    user = session.exec(select(User).where(User.username == username)).first()
    room = session.get(Room, room_id)
    if not user or not room:
        await websocket.close(code=1008)
        return

    await manager.connect(room_id, websocket, user.username)

    online_users = await manager.get_usernames(room_id)
    await manager.publish(room_id, {
        "type": "user_joined",
        "username": user.username,
        "online_users": online_users,
    })

    try:
        while True:
            raw = await websocket.receive_json()
            event_type = raw.get("type")

            if event_type == "message":
                content = raw.get("content", "")
                temp_id = raw.get("tempId")

                new_message = Message(content=content, user_id=user.id, room_id=room_id)
                session.add(new_message)
                session.commit()

                await manager.publish(room_id, {
                    "type": "message",
                    "username": user.username,
                    "content": content,
                    "tempId": temp_id,
                })
            elif event_type == "typing":
                await manager.publish(room_id, {
                    "type": "typing",
                    "username": user.username,
                })
            elif event_type == "stop_typing":
                await manager.publish(room_id, {
                    "type": "stop_typing",
                    "username": user.username,
                })
    except WebSocketDisconnect:
        pass
    finally:
        is_fully_disconnected = await manager.disconnect(room_id, websocket, user.username)
        if is_fully_disconnected:
            online_users = await manager.get_usernames(room_id)
            await manager.publish(room_id, {
                "type": "user_left",
                "username": user.username,
                "online_users": online_users,
            })