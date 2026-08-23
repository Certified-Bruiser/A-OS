from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from app.providers import registry
from app.providers.factory import ProviderFactory
from app.websocket_manager import manager
from app.agent_runtime import AgentOSRuntime
from app.agents.model import Agent
from app.agents.registry import AgentRegistry
from app.conversation.state import AssistantState
from app.audio.engine import AudioEngine
from app.llm.service import LLMService
from app.tts.service import TTSService
from app.memory.service import MemoryService

app = FastAPI(title="AgentOS")
agent_registry = AgentRegistry()
VALID_AGENT_STATUSES = {"DRAFT", "TESTING", "PUBLISHED"}


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    goal: str = ""


class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = Field(default=None, min_length=1)
    goal: str | None = None


def agent_response(agent: Agent):
    data = {
        **agent.configuration,
        "id": agent.id,
        "name": agent.name,
        "goal": agent.goal,
        "description": agent.description,
        "capabilities": agent.capabilities,
        "knowledge_sources": agent.knowledge_sources,
        "channels": agent.channels,
        "status": agent.status,
        "version": agent.version,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }

    return data


def request_configuration(payload: BaseModel):
    return payload.model_dump(exclude_unset=True)


def normalized_status(value):
    normalized = str(value).upper()
    if normalized not in VALID_AGENT_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid agent status")
    return normalized

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

    if isinstance(state, AssistantState):
        assistant_state = state.value
    else:
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


@app.post("/agents", status_code=201)
async def create_agent(payload: AgentCreateRequest):
    configuration = request_configuration(payload)
    name = payload.name.strip()

    if not name:
        raise HTTPException(status_code=422, detail="Agent name is required")

    goal = configuration.get("goal") or configuration.get("goals") or ""
    status = normalized_status(configuration.get("status", "draft"))
    agent = Agent(
        name=name,
        goal=goal,
        description=configuration.get("description", ""),
        capabilities=configuration.get("enabledTools", []),
        knowledge_sources=configuration.get("knowledgeSources", []),
        channels=configuration.get("channels", []),
        status=status,
        configuration=configuration,
    )
    agent_registry.save(agent)

    return agent_response(agent)


@app.get("/agents")
async def list_agents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str = Query(default=""),
    status: str | None = None,
):
    agents = agent_registry.list_agents()
    search_term = search.strip().lower()
    status_term = normalized_status(status) if status else None

    if search_term:
        agents = [
            agent for agent in agents
            if search_term in agent.name.lower()
            or search_term in agent.description.lower()
        ]

    if status_term:
        agents = [agent for agent in agents if agent.status.upper() == status_term]

    agents.sort(key=lambda agent: agent.updated_at, reverse=True)
    total = len(agents)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": [agent_response(agent) for agent in agents[start:end]],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    agent = agent_registry.get(agent_id)

    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent_response(agent)


@app.patch("/agents/{agent_id}")
async def update_agent(agent_id: str, payload: AgentUpdateRequest):
    agent = agent_registry.get(agent_id)

    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    updates = request_configuration(payload)
    if "name" in updates:
        updates["name"] = updates["name"].strip()
        if not updates["name"]:
            raise HTTPException(status_code=422, detail="Agent name is required")

    agent.configuration.update(updates)
    agent.name = updates.get("name", agent.name)
    agent.goal = updates.get("goal", updates.get("goals", agent.goal))
    agent.description = updates.get("description", agent.description)
    agent.capabilities = updates.get("enabledTools", agent.capabilities)
    agent.knowledge_sources = updates.get("knowledgeSources", agent.knowledge_sources)
    agent.channels = updates.get("channels", agent.channels)
    agent.status = normalized_status(updates.get("status", agent.status))
    agent.updated_at = datetime.utcnow().isoformat()
    agent_registry.save(agent)

    return agent_response(agent)


@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    if not agent_registry.delete(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"status": "deleted", "id": agent_id}

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

