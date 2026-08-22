# Realtime Chat API

A real-time chat backend built with FastAPI and WebSockets. Supports multiple chat rooms, JWT-authenticated WebSocket connections, live broadcast of messages across multiple server instances (via Redis pub/sub), presence tracking, typing indicators, cursor-based message pagination, rate limiting, and connection health checks.

**Live API docs:** https://<your-backend-url>.onrender.com/docs

## Features

- JWT authentication (register/login/refresh), reused across REST and WebSocket connections
- Room-based chat: create rooms, join a room's WebSocket, see who's online in real time
- Real-time message broadcast, scalable across multiple server instances via **Redis pub/sub**
- Presence tracking backed by Redis (survives restarts, shared across instances — not just in-process memory)
- Typing indicators (auto-expire after a few seconds of inactivity)
- Join/leave notifications with a live-updated online-user roster
- Every message is persisted to Postgres and retrievable as history
- **Cursor-based pagination** on message history — stable under concurrent writes, unlike offset/limit
- **Rate limiting** on auth endpoints (brute-force protection) via slowapi
- **WebSocket heartbeat (ping/pong)** — the server pings idle connections and drops ones that stop responding, so "dead" connections are cleaned up promptly instead of lingering
- Structured, typed WebSocket messages (`message`, `typing`, `user_joined`, `user_left`) so the client never has to guess what an incoming payload means
- Automated test suite with isolated test database (in-memory SQLite) and isolated fake Redis (fakeredis) — tests never touch real dev/prod data
- Containerized with Docker / Docker Compose
- CI pipeline runs the test suite on every push

## Tech Stack

- **FastAPI** — web framework, including native WebSocket support
- **SQLModel** — ORM (SQLAlchemy + Pydantic)
- **PostgreSQL** (Neon) — database, with `pool_pre_ping` to survive idle-connection drops on the free tier
- **Redis** (Upstash) — presence + pub/sub broadcast, with keepalive/health-check settings tuned for a hosted free-tier instance
- **Alembic** — schema migrations
- **python-jose** — JWT creation/verification
- **passlib[bcrypt]** — password hashing
- **slowapi** — rate limiting
- **pytest**, **pytest-asyncio**, **fakeredis** — testing
- **Docker** / **Docker Compose** — containerized local dev
- **GitHub Actions** — CI (runs tests on every push)
- Deployed on **Render**

## Project Structure

```
Realtime_Ws/
├── main.py                     # app entrypoint, middleware, router registration
├── app/
│   ├── api/                    # route modules (auth, rooms, websocket)
│   ├── core/                   # config, security, redis client, rate limiter
│   ├── db/                     # database session/engine setup
│   ├── services/                # ConnectionManager (presence + pub/sub broadcast)
│   └── tests/                   # pytest suite + conftest fixtures
├── alembic/
│   ├── versions/                 # migration files
│   └── env.py
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env                          # local secrets (not committed)
└── .env.example
```

## Setup (local development)

### Option A — with Docker (recommended)

```bash
docker compose up --build
```

This starts the API (and any local dependencies defined in `docker-compose.yml`). The API will be available at `http://127.0.0.1:8000`.

### Option B — without Docker

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
   REDIS_URL=<your Redis connection string, e.g. from Upstash>
   ```

4. Apply database migrations:
   ```bash
   alembic upgrade head
   ```

5. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

6. Open the interactive docs at `http://127.0.0.1:8000/docs`. Note: WebSocket routes don't render in Swagger UI — test them with a WebSocket client or the frontend.

## Running Tests

```bash
pytest
```

Tests run against an isolated in-memory SQLite database and an isolated `fakeredis` instance (patched in via `conftest.py`) — no test ever touches the real Postgres or Redis instance used in dev/prod.

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
| POST | `/login` | Log in, returns access + refresh tokens (rate limited) | No |
| POST | `/refresh` | Exchange a refresh token for a new access token | No |
| GET | `/me` | Get the current logged-in user's info | Yes |
| POST | `/rooms` | Create a chat room | Yes |
| GET | `/rooms` | List all rooms | Yes |
| GET | `/rooms/{room_id}` | Get a single room | Yes |
| GET | `/rooms/{room_id}/messages` | Load message history (cursor-based pagination) | Yes |
| GET | `/rooms/{room_id}/online-users` | Get the current online-user list for a room | Yes |

#### Cursor-based pagination

```
GET /rooms/{room_id}/messages?limit=20
GET /rooms/{room_id}/messages?limit=20&cursor=<next_cursor from previous response>
```

Response shape:
```json
{
  "messages": [...],
  "next_cursor": "opaque-base64-string-or-null",
  "has_more": true
}
```

The cursor encodes the timestamp and id of the oldest message in the current page, so paging further back stays correct even if new messages arrive concurrently — unlike plain `offset`/`limit`, which can skip or duplicate rows under concurrent writes.

### WebSocket

| Route | Description |
|---|---|
| `ws://.../ws/{room_id}?token={access_token}` | Connect to a room's live chat. The JWT is passed as a query parameter since WebSocket connections can't carry custom headers the way HTTP requests can. |

**Message shape (client → server):**
```json
{ "type": "message", "content": "hello!", "tempId": "client-generated-id" }
{ "type": "typing" }
```

**Message shape (server → client):**
```json
{ "type": "message", "username": "hedi", "content": "hello!", "tempId": "client-generated-id" }
{ "type": "typing", "username": "hedi" }
{ "type": "user_joined", "username": "hedi", "online_users": ["hedi", "noussa"] }
{ "type": "user_left", "username": "hedi", "online_users": ["noussa"] }
```

`tempId` is optional — the frontend uses it to reconcile an optimistically-rendered message with the server-confirmed one, without waiting for the round trip to show the message on screen.

## How Broadcast Scales Across Instances

Presence and message delivery don't rely on a single process's in-memory state:

1. A message received on any server instance is **published** to a Redis channel for that room (`room:{id}:channel`)
2. Every instance with at least one active connection to that room is **subscribed** to the same channel
3. Each instance relays incoming pub/sub messages only to its own locally-connected WebSocket clients

This means the app can run as multiple replicas behind a load balancer and still broadcast correctly to everyone in a room, regardless of which instance they're connected to.

## WebSocket Heartbeat (Ping/Pong)

WebSocket connections can die silently — a closed laptop lid, a dropped Wi-Fi signal, a phone switching networks — without ever sending a proper close frame. Without a heartbeat, the server has no way to tell a silently-dead connection apart from one that's just quiet, so it keeps it registered indefinitely: it stays counted in the room's presence list and the server keeps trying to write to it.

To handle this, the server pings every open connection at a regular interval. If a connection doesn't respond within the expected window, the server treats it as dead, removes it from `ConnectionManager`, updates the room's presence in Redis, and broadcasts a `user_left` event — the same cleanup path used for a normal disconnect.

This keeps the online-user list accurate and prevents the local connection list and Redis presence set from slowly accumulating stale, disconnected clients over time.

## Rate Limiting

Auth endpoints are rate limited with **slowapi** to blunt brute-force login/registration attempts — a client hammering `/login` or `/register` gets throttled with a `429 Too Many Requests` response instead of being able to try unlimited credentials per second.

WebSocket message sends are also throttled per connection, so a single client can't flood a room (or the Redis pub/sub channel) with messages faster than the app is designed to handle.

## Docker

The project is fully containerized:

```bash
docker compose up --build
```

`docker-compose.yml` defines the API service (and, if configured, any local dependencies). Environment variables are read the same way as running without Docker — via `.env` or variables injected by the compose file — so switching between Docker and a local venv doesn't change how the app is configured, only how it's run.

Rebuild (`--build`) whenever the code or dependencies change; if your compose setup mounts the project directory as a volume, `uvicorn --reload` picks up code changes without a rebuild.

## CI/CD

A GitHub Actions workflow runs on every push:

- Installs dependencies
- Runs the full `pytest` suite (against the isolated in-memory SQLite + fakeredis setup — no real Postgres/Redis credentials needed in CI)

This catches regressions before they reach `main` or get deployed, and means the test suite isn't just something that runs on one developer's machine — it's enforced on every change.

## Deployment

Deployed on Render as a Web Service, with PostgreSQL hosted on Neon and Redis hosted on Upstash.

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment variables required:** `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`

Migrations are applied automatically on every deploy, before the server starts. CI runs the test suite on every push before deployment.
