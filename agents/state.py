from typing import TypedDict, List, Literal, Optional, Dict, Annotated
import operator

class AgentState(TypedDict):
    thread_id: str
    chat_history: Annotated[List[Dict], operator.add]       
    objective: str
    status: Literal["architecting", "building", "finished", "error_recovery", "awaiting_approval"]
    
    current_mode: Literal["chat", "task"]
    final_response: Optional[str]
    agent_config: Optional[Dict]
    micro_task_queue: List[str]
    completed_log: Annotated[List[str], operator.add]
    
    current_micro_task: str
    current_thought: str
    last_tool_output: str
    error_counter: int 

    pending_approval: Optional[str]
    last_error: Optional[str]
    failed_task: Optional[str]