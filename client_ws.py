import asyncio
import websockets
import json 

# Remplace par un vrai token obtenu via POST /login
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJoZWRpIiwiZXhwIjoxNzg3MTM0NTU4fQ.X4n4oPyiyYhwTzZDH5EYGGdTy2lwv7sOUaefejgGea4"
ROOM_ID = 1  # remplace par ton vrai room_id

async def listen(websocket):
    while True:
        raw = await websocket.recv()
        data = json.loads(raw)

        if data["type"] == "message":
            print(f"\n💬 {data['username']}: {data['content']}\n> ", end="")
        elif data["type"] == "typing":
            print(f"\n✏️  {data['username']} est en train d'écrire...\n> ", end="")
        elif data["type"] == "user_joined":
            print(f"\n🟢 {data['username']} a rejoint — en ligne: {data['online_users']}\n> ", end="")
        elif data["type"] == "user_left":
            print(f"\n🔴 {data['username']} a quitté — en ligne: {data['online_users']}\n> ", end="")

async def send(websocket):
    while True:
        message = await asyncio.to_thread(input, "> ")
        if message.strip() == "":
            continue
        await websocket.send(json.dumps({"type": "message", "content": message}))

async def main():
    uri = f"ws://127.0.0.1:8000/ws/{ROOM_ID}?token={TOKEN}"
    async with websockets.connect(uri) as websocket:
        await asyncio.gather(listen(websocket), send(websocket))

asyncio.run(main())