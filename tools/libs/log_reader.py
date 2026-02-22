import os
import json
from typing import Dict, List
from tools.base import BaseTool, ToolResult
from core.config import Config

class LogReaderTool(BaseTool):
    name = "log_reader"
    description = "Lê logs de execução passados e o histórico de conversas. Use para lembrar o que foi pedido anteriormente ou revisar erros técnicos."

    parameters = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["recent_events", "search_text", "chat_history"],
                "description": "Modo de leitura: 'recent_events' para os últimos logs do sistema, 'search_text' para buscar palavras-chave, ou 'chat_history' para a conversa atual."
            },
            "limit": {
                "type": "integer",
                "description": "Número de registros para ler (padrão: 10).",
                "default": 10
            },
            "query": {
                "type": "string",
                "description": "Termo de busca (obrigatório para o modo 'search_text')."
            }
        },
        "required": ["mode"]
    }

    def run(self, mode: str, limit: int = 10, query: str = None, **kwargs) -> ToolResult:
        episodic_path = Config.DIRS["episodic"]
        
        try:
            if mode == "recent_events":
                files = sorted(os.listdir(episodic_path), reverse=True)[:limit]
                logs = []
                for f in files:
                    with open(os.path.join(episodic_path, f), "r", encoding="utf-8") as fd:
                        logs.append(json.load(fd))
                return {"success": True, "output": json.dumps(logs, indent=2), "metadata": {}}

            elif mode == "search_text":
                if not query:
                    return {"success": False, "output": "Erro: 'query' é necessário para busca.", "metadata": {}}
                
                results = []
                for f in os.listdir(episodic_path):
                    with open(os.path.join(episodic_path, f), "r", encoding="utf-8") as fd:
                        data = json.load(fd)
                        if query.lower() in str(data.get("content", "")).lower():
                            results.append(data)
                            if len(results) >= limit: break
                
                return {"success": True, "output": json.dumps(results, indent=2), "metadata": {}}

            elif mode == "chat_history":
                return {"success": True, "output": "Funcionalidade de leitura de chat_id específica requer integração com a UI.", "metadata": {}}

            return {"success": False, "output": "Modo inválido.", "metadata": {}}

        except Exception as e:
            return {"success": False, "output": f"Erro ao ler logs: {str(e)}", "metadata": {}}