import json
import asyncio
from fastapi import WebSocket
from app.core.redis import redis_client

class ConnectionManager:
    def __init__(self):
        self.local_connections: dict[int, list[WebSocket]] = {}
        self.redis_listener_tasks: dict[int, asyncio.Task] = {}
        self.pubsubs: dict[int, any] = {}

    async def connect(self, room_id: int, websocket: WebSocket, username: str):
        await websocket.accept()
        if room_id not in self.local_connections:
            self.local_connections[room_id] = []
        self.local_connections[room_id].append(websocket)
        
        await redis_client.hincrby(f"room:{room_id}:user_count", username, 1)
        await redis_client.sadd(f"room:{room_id}:online", username)

        if room_id not in self.redis_listener_tasks:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"room:{room_id}:channel")
            self.pubsubs[room_id] = pubsub

            async def redis_listener(room_id=room_id, pubsub=pubsub):
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data = json.loads(message["data"])
                        await self.broadcast(room_id, data)

            self.redis_listener_tasks[room_id] = asyncio.create_task(redis_listener())

    async def disconnect(self, room_id: int, websocket: WebSocket, username: str) -> bool:
        if room_id in self.local_connections:
            self.local_connections[room_id] = [
                ws for ws in self.local_connections[room_id] if ws != websocket
            ]
            if not self.local_connections[room_id]:
                del self.local_connections[room_id]

                if room_id in self.redis_listener_tasks:
                    self.redis_listener_tasks[room_id].cancel()
                    del self.redis_listener_tasks[room_id]
                if room_id in self.pubsubs:
                    await self.pubsubs[room_id].unsubscribe(f"room:{room_id}:channel")
                    del self.pubsubs[room_id]

        count = await redis_client.hincrby(f"room:{room_id}:user_count", username, -1)
        if count <= 0:
            await redis_client.srem(f"room:{room_id}:online", username)
            await redis_client.hdel(f"room:{room_id}:user_count", username)
            return True
        return False

    async def get_usernames(self, room_id: int) -> list[str]:
        members = await redis_client.smembers(f"room:{room_id}:online")
        return list(members)

    async def publish(self, room_id: int, message: dict):
        await redis_client.publish(f"room:{room_id}:channel", json.dumps(message))

    async def broadcast(self, room_id: int, message: dict, exclude: WebSocket = None):
        if room_id in self.local_connections:
            dead_connections = []
            for connection in self.local_connections[room_id]:
                if connection != exclude:
                    try:
                        await connection.send_json(message)
                    except Exception:
                        dead_connections.append(connection)
            for dead in dead_connections:
                self.local_connections[room_id].remove(dead)

manager = ConnectionManager()