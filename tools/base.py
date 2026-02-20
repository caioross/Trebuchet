from typing import Dict, Optional, TypedDict, Any

class ToolResult(TypedDict):
    success: bool
    output: str
    metadata: Optional[Dict]

class BaseTool:
    name: str = "base_tool"
    description: str = "Base description"
    parameters: Dict = {
        "type": "object", 
        "properties": {}, 
        "required": []
    }
    config_schema: Dict = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def __init__(self, name: str = None, description: str = None, parameters: Dict = None, config_schema: Dict = None, **kwargs):
        if name:
            self.name = name
        if description:
            self.description = description
        if parameters:
            self.parameters = parameters
        if config_schema:
            self.config_schema = config_schema

    def run(self, **kwargs) -> ToolResult:
        raise NotImplementedError("Tool must implement run method")