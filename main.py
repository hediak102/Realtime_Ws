from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, rooms, websocket

app = FastAPI(title="Realtime Chat API")

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

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(websocket.router)

@app.get("/")
async def read_root():
    return {"message": "api is running"}