import pytest

@pytest.mark.asyncio
async def test_register_user(client):
    response = await client.post(
        "/register",
        json={"username": "hedi", "email": "hedi@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "hedi"

@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    # Premier enregistrement
    await client.post(
        "/register",
        json={"username": "hedi", "email": "hedi@example.com", "password": "password123"}
    )
    # Deuxième enregistrement avec le même nom
    response = await client.post(
        "/register",
        json={"username": "hedi", "email": "autre@example.com", "password": "password123"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already taken"

@pytest.mark.asyncio
async def test_login_success(client):
    # Créer l'utilisateur
    await client.post(
        "/register",
        json={"username": "hedi", "email": "hedi@example.com", "password": "password123"}
    )
    # Se connecter
    response = await client.post(
        "/login",
        data={"username": "hedi", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"