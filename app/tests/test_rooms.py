import pytest

@pytest.mark.asyncio
async def test_create_and_get_rooms(client):
    # 1. Enregistrer et connecter un utilisateur
    await client.post(
        "/register",
        json={"username": "hedi", "email": "hedi@example.com", "password": "password123"}
    )
    login_res = await client.post(
        "/login",
        data={"username": "hedi", "password": "password123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Créer un salon
    create_res = await client.post(
        "/rooms",
        json={"name": "General Chat"},
        headers=headers
    )
    assert create_res.status_code == 200
    room_data = create_res.json()
    assert room_data["name"] == "General Chat"

    # 3. Récupérer la liste des salons
    get_res = await client.get("/rooms")
    assert get_res.status_code == 200
    rooms = get_res.json()
    assert len(rooms) == 1
    assert rooms[0]["name"] == "General Chat"