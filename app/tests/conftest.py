import pytest
import pytest_asyncio
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from main import app
from app.db.session import get_session
from app.core.security import create_access_token
from main import redis_client
import fakeredis.aioredis

# Base de données SQLite éphémère en mémoire RAM
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest_asyncio.fixture(name="client")
async def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
        
    app.dependency_overrides.clear()

@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "testuser"})
    return {"Authorization": f"Bearer {token}"}
@pytest_asyncio.fixture(autouse=True)
async def cleanup_redis():
    yield
    # S'exécute automatiquement après chaque test
    await redis_client.flushall()
@pytest_asyncio.fixture(autouse=True)
async def use_fake_redis(monkeypatch):
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("main.redis_client", fake_redis)
    yield
    await fake_redis.flushall()