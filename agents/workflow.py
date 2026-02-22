from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.nodes import TrebuchetNodes

class TrebuchetOrchestrator:
    def __init__(self):
        self.nodes = TrebuchetNodes()

    def build(self):
        workflow = StateGraph(AgentState)
    
        workflow.set_entry_point("classifier")
        workflow.add_node("orchestrator", self.nodes.orchestrator)
        
        workflow.add_node("tool_executor", self.nodes.tool_executor) 
        workflow.add_node("critic", self.nodes.critic)
        workflow.add_node("chat_mode", self.nodes.pure_chat)
        
        workflow.set_entry_point("classifier")
        
        workflow.add_conditional_edges(
            "classifier",
            lambda x: "chat_mode" if x.get("current_mode") == "chat" else "orchestrator",
            {"chat_mode": "chat_mode", "orchestrator": "orchestrator"}
        )
        
        workflow.add_edge("orchestrator", "tool_executor")
        workflow.add_conditional_edges(
            "tool_executor",
            lambda x: END if x.get("status") == "finished" else "critic",
            {END: END, "critic": "critic"}
        )
        workflow.add_edge("critic", "orchestrator")
        
        workflow.add_edge("chat_mode", END)
        return workflow.compile()