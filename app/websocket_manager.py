from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(
            f"[WS] CONNECT registered "
            f"connections={len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(
            f"[WS] DISCONNECT connections={len(self.active_connections)}"
        )

    async def broadcast(self, event: str, data: dict):
        message = {
            "event": event,
            "data": data,
        }

        for connection in self.active_connections:
            await connection.send_json(message)

    async def broadcast_audio(self, audio_bytes: bytes):
        print(
            f"[WS AUDIO] broadcast_audio ENTER "
            f"bytes={len(audio_bytes)} "
            f"connections={len(self.active_connections)}"
        )
        for connection in self.active_connections:
            print(f"[WS AUDIO] send_bytes START bytes={len(audio_bytes)}")
            try:
                await connection.send_bytes(audio_bytes)
            except Exception as exc:
                print(f"[WS AUDIO] send_bytes FAILED error={exc}")
                raise
            print(f"[WS AUDIO] send_bytes COMPLETE bytes={len(audio_bytes)}")


manager = ConnectionManager()

