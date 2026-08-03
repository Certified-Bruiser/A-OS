from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.providers import registry
from app.providers.factory import ProviderFactory
from app.websocket_manager import manager
from app.agent_runtime import AgentOSRuntime
from app.conversation.state import AssistantState
from app.audio.engine import AudioEngine
from app.llm.service import LLMService
from app.tts.service import TTSService
from app.memory.service import MemoryService

app = FastAPI(title="AgentOS")

# -----------------------------
# Services
# -----------------------------
factory = ProviderFactory(registry)
audio_engine = AudioEngine()
stt = factory.create_stt("sarvam")
llm = factory.create_llm("perplexity")
tts = factory.create_tts("sarvam")
memory = MemoryService()

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Global state
# -----------------------------
assistant_state = "idle"

async def set_state(state: AssistantState):
    global assistant_state

    assistant_state = state

    await manager.broadcast(
        "state",
        {"value": assistant_state}
    )

# -----------------------------
# Runtime (NOW set_state exists)
# -----------------------------
runtime = AgentOSRuntime(
    audio_engine=audio_engine,
    stt=stt,
    llm=llm,
    tts=tts,
    memory=memory,
    manager=manager,
    set_state=set_state,
)

# -----------------------------
# Routes
# -----------------------------
@app.get("/")
async def root():
    return {"message": "AgentOS Backend is Running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/start")
async def start():
    await runtime.start()
    return {"status": "started"}

@app.post("/stop")
async def stop():
    await runtime.stop()
    return {"status": "stopped"}

# -----------------------------
# WebSocket
# -----------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Send current state immediately
    await websocket.send_json({
        "event": "state",
        "data": {
            "value": assistant_state
        }
    })

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)

