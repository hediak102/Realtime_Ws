import pytest
import pytest_asyncio
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from main import app
from app.db.session import get_session
from app.core.security import create_access_token

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