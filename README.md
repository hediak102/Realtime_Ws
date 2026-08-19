# Realtime Chat API

A real-time chat backend built with FastAPI and WebSockets. Supports multiple chat rooms, JWT-authenticated WebSocket connections, live broadcast of messages, presence tracking (who's online), typing indicators, and persistent message history.

**Live API docs:** https://<your-backend-url>.onrender.com/docs

## Features

- JWT authentication (register/login/refresh), reused across REST and WebSocket connections
- Room-based chat: create rooms, join a room's WebSocket, see who's online
- Real-time message broadcast to everyone in a room
- Typing indicators (auto-expire after a few seconds of inactivity)
- Join/leave notifications, with a live-updated list of online users
- Every message is persisted to the database and available as history via REST
- Structured, typed WebSocket messages (`message`, `typing`, `user_joined`, `user_left`) so the client never has to guess what an incoming payload means

## Tech Stack

- **FastAPI** — web framework, including native WebSocket support
- **SQLModel** — ORM (SQLAlchemy + Pydantic)
- **PostgreSQL** (Neon) — database
- **Alembic** — schema migrations
- **python-jose** — JWT creation/verification
- **passlib[bcrypt]** — password hashing
- Deployed on **Render**

## Project Structure

```
Realtime_Ws/
├── main.py                 # app, models, REST routes, WebSocket endpoint, ConnectionManager
├── alembic/
│   ├── versions/            # migration files
│   └── env.py
├── alembic.ini
├── requirements.txt
├── .env                      # local secrets (not committed)
└── .env.example
```

## Setup (local development)

1. Clone the repo and create a virtual environment:
   ```bash
   git clone <repo-url>
   cd Realtime_Ws
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file:
   ```
   SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
   DATABASE_URL=sqlite:///database.db
   ```
   (Leave `DATABASE_URL` unset to default to local SQLite, or point it at a PostgreSQL/Neon instance.)

4. Apply database migrations:
   ```bash
   alembic upgrade head
   ```

5. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

6. Open the interactive docs at `http://127.0.0.1:8000/docs`. Note: WebSocket routes don't render in Swagger UI — test them with a WebSocket client or the frontend.

## Database Migrations

Whenever a model changes:

```bash
alembic revision --autogenerate -m "describe the change"
# review the generated file in alembic/versions/ before applying
alembic upgrade head
```

## API Overview

### REST

| Method | Route | Description | Auth required |
|---|---|---|---|
| POST | `/register` | Create a new user account | No |
| POST | `/login` | Log in, returns access + refresh tokens | No |
| POST | `/refresh` | Exchange a refresh token for a new access token | No |
| GET | `/me` | Get the current logged-in user's info | Yes |
| POST | `/rooms` | Create a chat room | Yes |
| GET | `/rooms` | List all rooms | Yes |
| GET | `/rooms/{room_id}` | Get a single room | Yes |
| GET | `/rooms/{room_id}/messages` | Load a room's message history | Yes |

### WebSocket

| Route | Description |
|---|---|
| `ws://.../ws/{room_id}?token={access_token}` | Connect to a room's live chat. The JWT is passed as a query parameter since WebSocket connections can't carry custom headers the way HTTP requests can. |

**Message shape (client → server):**
```json
{ "type": "message", "content": "hello!" }
{ "type": "typing" }
```

**Message shape (server → client):**
```json
{ "type": "message", "username": "hedi", "content": "hello!" }
{ "type": "typing", "username": "hedi" }
{ "type": "user_joined", "username": "hedi", "online_users": ["hedi", "noussa"] }
{ "type": "user_left", "username": "hedi", "online_users": ["noussa"] }
```

## Deployment

Deployed on Render as a Web Service, with PostgreSQL hosted on Neon.

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment variables required:** `SECRET_KEY`, `DATABASE_URL`

Migrations are applied automatically on every deploy, before the server starts.

## Known Limitations

- Connection state (who's online, per room) lives in server memory — it resets on restart and wouldn't be shared across multiple server instances without an external store like Redis. Fine for a single-instance deployment.
- WebSocket disconnects that aren't "clean" (e.g. a browser tab killed abruptly) can take a moment to be detected server-side.
