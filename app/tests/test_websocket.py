import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.mark.asyncio
async def test_websocket_unauthorized():
    # Connexion rejetée si le token est invalide
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/1?token=invalid_token"):
            pass

@pytest.mark.asyncio
async def test_websocket_connect_success(client):
    # 1. Inscription et connexion pour avoir un token valide
    await client.post(
        "/register",
        json={"username": "hedi_ws", "email": "ws@example.com", "password": "password123"}
    )
    login_res = await client.post(
        "/login",
        data={"username": "hedi_ws", "password": "password123"}
    )
    token = login_res.json()["access_token"]

    # 2. Créer une room REST
    room_res = await client.post(
        "/rooms",
        json={"name": "WS Room"},
        headers={"Authorization": f"Bearer {token}"}
    )
    room_id = room_res.json()["id"]

    # 3. Tester la connexion WebSocket
    test_client = TestClient(app)
    with test_client.websocket_connect(f"/ws/{room_id}?token={token}") as websocket:
        # Le premier message reçu lors du join doit être l'événement user_joined
        data = websocket.receive_json()
        assert data["type"] == "user_joined"
        assert data["username"] == "hedi_ws"