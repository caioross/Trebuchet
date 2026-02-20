from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.nodes import TrebuchetNodes

class TrebuchetOrchestrator:
    def __init__(self):
        self.nodes = TrebuchetNodes()

    def build(self):
        workflow = StateGraph(AgentState)
        
        workflow.add_node("classifier", self.nodes.classifier)
        workflow.add_node("chat_mode", self.nodes.pure_chat)
        workflow.add_node("agent", self.nodes.unified_agent)
        
        workflow.set_entry_point("classifier")
        
        def route_decision(state):
            mode = state.get("current_mode", "task")
            if "chat" in mode:
                return "chat_mode"
            return "agent"

        workflow.add_conditional_edges(
            "classifier",
            route_decision,
            {
                "chat_mode": "chat_mode",
                "agent": "agent"
            }
        )
        
        workflow.add_edge("chat_mode", END)
        
        def worker_router(state):
            if state.get("status") == "finished":
                return END
            return "agent"

        workflow.add_conditional_edges("agent", worker_router)
        
        return workflow.compile()