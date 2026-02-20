from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uvicorn
import threading
from agents.workflow import TrebuchetOrchestrator
from agents.state import AgentState
from core.config import Config

app = FastAPI(title="Trebuchet API v3.0")
orchestrator = TrebuchetOrchestrator()
graph = orchestrator.build()

class MissionRequest(BaseModel):
    objective: str

@app.get("/")
def read_root():
    return {"status": "Trebuchet v3.0 ONLINE", "mode": "Hybrid Compute (CPU/GPU)"}

def run_agent_sync(objective: str):
    # Initial state must match AgentState TypedDict in agents/state.py
    initial: AgentState = {
        "objective": objective,
        "status": "architecting",
        "micro_task_queue": [],
        "completed_log": [],
        "current_micro_task": "",
        "last_tool_output": "",
        "error_counter": 0,
        "pending_approval": None,
        "last_error": None,
        "failed_task": None
    }
    
    # Executa o grafo
    # Nota: Em produção, isso deveria salvar o estado em DB
    for event in graph.stream(initial):
        # Aqui poderiamos logar ou enviar via WebSocket
        pass 

@app.post("/mission")
async def start_mission(mission: MissionRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_agent_sync, mission.objective)
    return {"message": "Mission Started", "objective": mission.objective}

def start():
    uvicorn.run(app, host=Config.API_HOST, port=Config.API_PORT)
