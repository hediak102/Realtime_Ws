import asyncio
import websockets
import json 

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJoZWRpIiwiZXhwIjoxNzg3MzA4MDI4fQ.F1-2G5Fd-hhWOw0Mhd-qRV_6eomtnyYPleilRms3P1g"
ROOM_ID = 1

async def listen(websocket):
    try:
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
    except websockets.exceptions.ConnectionClosed:
        pass

async def send(websocket):
    while True:
        # Permet à asyncio d'interrompre proprement input()
        message = await asyncio.to_thread(input, "> ")
        if message.strip().lower() in ["/quit", "exit"]:
            break
        if message.strip() == "":
            continue
        await websocket.send(json.dumps({"type": "message", "content": message}))

async def main():
    uri = f"ws://127.0.0.1:8000/ws/{ROOM_ID}?token={TOKEN}"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to room. Type /quit or Ctrl+C to leave.")
            # return_when=asyncio.FIRST_COMPLETED permet de fermer si l'une des deux tâches s'arrête
            listen_task = asyncio.create_task(listen(websocket))
            send_task = asyncio.create_task(send(websocket))
            
            done, pending = await asyncio.wait(
                [listen_task, send_task], 
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nDisconnected properly.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass