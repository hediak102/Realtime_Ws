# app/core/pagination.py
import base64
import json
from datetime import datetime

def encode_cursor(created_at: datetime, message_id: int) -> str:
    payload = json.dumps({"created_at": created_at.isoformat(), "id": message_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()

def decode_cursor(cursor: str) -> tuple[datetime, int]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    return datetime.fromisoformat(payload["created_at"]), payload["id"]