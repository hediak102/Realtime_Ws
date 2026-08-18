import asyncio
import websockets

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJub3Vzc2EiLCJleHAiOjE3ODcwOTc2NjF9.vz2g2-PWV0j8JiXPhiiqMb4vsHIO9SVSP60RPhuZDUw"
async def listen(websocket):
    while True:
        message = await websocket.recv()
        print(f"\n📩 {message}\n> ", end="")

async def send(websocket):
    while True:
        message = await asyncio.to_thread(input, "> ")
        await websocket.send(message)

async def main():
    uri = f"ws://127.0.0.1:8000/ws/1?token={TOKEN}"
    async with websockets.connect(uri) as websocket:
        await asyncio.gather(listen(websocket), send(websocket))

asyncio.run(main())