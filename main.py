from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI,Depends, HTTPException,WebSocketDisconnect,WebSocket,Query
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import jwt, JWTError
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import json
import asyncio

load_dotenv()

#REDIS SETUP
REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not set")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

#DB SETUP
DATABASE_URL = os.getenv("DATABASE_URL","sqlite:///database.db")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=True)

def get_session():
    with Session(engine) as session:
        yield session


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set — check your .env file")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="admin access required")
    return current_user

#MODELS

class User(SQLModel,table=True):
    id:int | None =Field(default=None,primary_key=True)
    username:str
    email:str
    hashed_password:str
    created_at:datetime = Field(default_factory=datetime.utcnow)
class Room(SQLModel,table=True):
    id:int | None =Field(default=None,primary_key=True)
    name:str
    created_at:datetime = Field(default_factory=datetime.utcnow)
    owner_id:int=Field(foreign_key="user.id")
class Message(SQLModel,table=True):
    id:int | None =Field(default=None,primary_key=True)
    content:str
    created_at:datetime = Field(default_factory=datetime.utcnow)
    user_id:int=Field(foreign_key="user.id")
    room_id:int=Field(foreign_key="room.id")
class MessageRead(SQLModel):
    id: int
    content: str
    created_at: datetime
    user_id: int
    username:str
    room_id: int
class UserCreate(SQLModel):
    username:str
    password:str
    email: str
class RefreshRequest(BaseModel):
    refresh_token: str
class RoomCreate(SQLModel):
    name: str
class UserRead(SQLModel):
    id: int
    username: str
    email: str
class ConnectionManager:
    def __init__(self):
        self.local_connections: dict[int, list[WebSocket]] = {}
        self.redis_listener_tasks: dict[int, asyncio.Task] = {}
        self.pubsubs: dict[int, any] = {}

    async def connect(self, room_id: int, websocket: WebSocket, username: str):
        await websocket.accept()
        if room_id not in self.local_connections:
            self.local_connections[room_id] = []
        self.local_connections[room_id].append(websocket)
        await redis_client.sadd(f"room:{room_id}:online", username)

        # Démarre le listener SEULEMENT s'il n'existe pas déjà pour ce salon
        if room_id not in self.redis_listener_tasks:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"room:{room_id}:channel")
            self.pubsubs[room_id] = pubsub

            async def redis_listener(room_id=room_id, pubsub=pubsub):
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data = json.loads(message["data"])
                        await self.broadcast(room_id, data)

            self.redis_listener_tasks[room_id] = asyncio.create_task(redis_listener())

    async def disconnect(self, room_id: int, websocket: WebSocket, username: str):
        if room_id in self.local_connections:
            self.local_connections[room_id] = [
                ws for ws in self.local_connections[room_id] if ws != websocket
            ]
            if not self.local_connections[room_id]:
                del self.local_connections[room_id]

                # Plus personne dans le salon SUR CE PROCESS → arrête le listener
                if room_id in self.redis_listener_tasks:
                    self.redis_listener_tasks[room_id].cancel()
                    del self.redis_listener_tasks[room_id]
                if room_id in self.pubsubs:
                    await self.pubsubs[room_id].unsubscribe(f"room:{room_id}:channel")
                    del self.pubsubs[room_id]

        await redis_client.srem(f"room:{room_id}:online", username)

    async def get_usernames(self, room_id: int) -> list[str]:
        members = await redis_client.smembers(f"room:{room_id}:online")
        return list(members)

    async def publish(self, room_id: int, message: dict):
        await redis_client.publish(f"room:{room_id}:channel", json.dumps(message))

    async def broadcast(self, room_id: int, message: dict, exclude: WebSocket = None):
        if room_id in self.local_connections:
            dead_connections = []
            for connection in self.local_connections[room_id]:
                if connection != exclude:
                    try:
                        await connection.send_json(message)
                    except Exception:
                        dead_connections.append(connection)
            for dead in dead_connections:
                self.local_connections[room_id].remove(dead)

manager = ConnectionManager()
#APP SETUP

app = FastAPI()
origins = [
    "http://localhost:5173",
    "https://chat-frontend-86mu.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "api is running"}

@app.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# APP-JWT-AUTH2-REQUESTS
@app.post("/register")
async def register(user:UserCreate,session:Session=Depends(get_session)):
    existing = session.exec(select(User).where(User.username == user.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="username already taken")
    new_user = User(username=user.username,email=user.email, hashed_password=hash_password(user.password))
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return {"message": "user created", "username": new_user.username}

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(),session:Session=Depends(get_session)):
    user=session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password,user.hashed_password):
        raise HTTPException(status_code=401,detail="incorrect username or password")
    token = create_access_token({"sub": user.username})
    refresh_token = create_refresh_token({"sub": user.username})
    return {"access_token": token,"refresh_token": refresh_token, "token_type": "bearer"} 

@app.post("/refresh")
async def refresh_access_token(body: RefreshRequest, session: Session = Depends(get_session)):
    credentials_exception = HTTPException(status_code=401, detail="invalid refresh token")
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise credentials_exception

    new_access_token = create_access_token({"sub": user.username})
    return {"access_token": new_access_token, "token_type": "bearer"}

#WebSocket connexions

@app.websocket("/ws/{room_id}")
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, token: str = Query(...), session: Session = Depends(get_session)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.close(code=1008)
        return

    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        await websocket.close(code=1008)
        return

    room = session.get(Room, room_id)
    if room is None:
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
                new_message = Message(content=content, user_id=user.id, room_id=room_id)
                session.add(new_message)
                session.commit()

                await manager.publish(room_id, {
                    "type": "message",
                    "username": user.username,
                    "content": content,
                })
            elif event_type == "typing":
                await manager.publish(room_id, {
                    "type": "typing",
                    "username": user.username,
                })
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(room_id, websocket, user.username)
        online_users = await manager.get_usernames(room_id)
        await manager.publish(room_id, {
            "type": "user_left",
            "username": user.username,
            "online_users": online_users,
        })

# ROOM CRUD 
  
@app.post("/rooms")
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

@app.get("/rooms")
async def get_rooms(session: Session = Depends(get_session)):
    rooms = session.exec(select(Room)).all()
    return rooms

@app.get("/rooms/{room_id}")
async def get_room(room_id: int, session: Session = Depends(get_session)):
    room = session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")
    return room

# CHARGER HISTORIQUE DE MSG
@app.get("/rooms/{room_id}/messages", response_model=List[MessageRead])
async def get_room_messages(
    room_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    room = session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room not found")

    messages = session.exec(
        select(Message).where(Message.room_id == room_id).order_by(Message.created_at)
    ).all()
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
@app.get("/redis-test")
async def redis_test():
    await redis_client.set("test_key", "hello upstash")
    value = await redis_client.get("test_key")
    return {"value": value}