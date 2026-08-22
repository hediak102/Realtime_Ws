from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, rooms, websocket
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
# 1. Initialiser le Limiter basé sur l'IP distante
from app.core.limiter import limiter

app = FastAPI(title="Realtime Chat API")

# 2. Attacher l'état du limiter à l'application FastAPI
app.state.limiter = limiter

#3. Ajouter la gestion personnalisée de l'erreur 429
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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