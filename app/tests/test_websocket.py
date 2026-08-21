from fastapi.testclient import TestClient
from main import app 
from app.db.session import get_session
def test_websocket_connect_success(session):
    # Note : utilise 'session' (sync), pas 'client' (async) pour ce test précis
    def get_session_override():
        return session
    app.dependency_overrides[get_session] = get_session_override

    client = TestClient(app)

    client.post("/register", json={
        "username": "hedi_ws", "email": "ws@example.com", "password": "password123"
    })
    login_res = client.post("/login", data={
        "username": "hedi_ws", "password": "password123"
    })
    token = login_res.json()["access_token"]

    room_res = client.post("/rooms", json={"name": "WS Room"},
        headers={"Authorization": f"Bearer {token}"})
    room_id = room_res.json()["id"]

    with client.websocket_connect(f"/ws/{room_id}?token={token}") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "user_joined"
        assert data["username"] == "hedi_ws"

    app.dependency_overrides.clear()