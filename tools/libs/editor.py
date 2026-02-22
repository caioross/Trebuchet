import os
from typing import Dict, Any
from tools.base import BaseTool, ToolResult
from core.config import Config

class ToolEditorTool(BaseTool):
    name = "tool_editor"
    description = "Lê ou escreve código-fonte em arquivos Python do sistema. Essencial para corrigir (self-healing) ou atualizar ferramentas que estão apresentando erros."

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write"],
                "description": "Ação a realizar: 'read' para ler o arquivo, 'write' para reescrever o arquivo inteiro com as correções."
            },
            "file_path": {
                "type": "string",
                "description": "Caminho relativo do arquivo (ex: 'tools/libs/shell.py' ou 'tools/plugins/meu_plugin.py')."
            },
            "content": {
                "type": "string",
                "description": "Novo conteúdo integral para o arquivo Python (usado apenas na ação 'write')."
            }
        },
        "required": ["action", "file_path"]
    }

    def run(self, action: str, file_path: str, content: str = "", config: dict = None, **kwargs) -> ToolResult:
        if "tools" not in file_path and "agents" not in file_path:
            return {
                "success": False, 
                "output": "Ação bloqueada: Por segurança, o editor só tem permissão para alterar arquivos nos diretórios 'tools/' e 'agents/'.", 
                "metadata": {}
            }

        full_path = os.path.join(Config.BASE_DIR, file_path)

        try:
            if action == "read":
                if not os.path.exists(full_path):
                    return {"success": False, "output": f"Arquivo não encontrado: {full_path}", "metadata": {}}
                
                with open(full_path, "r", encoding="utf-8") as f:
                    code = f.read()
                
                return {"success": True, "output": f"Conteúdo de {file_path}:\n\n{code}", "metadata": {"file": file_path}}
            
            elif action == "write":
                if not content:
                    return {"success": False, "output": "Erro: 'content' é obrigatório para a ação 'write'.", "metadata": {}}
                
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                    
                return {
                    "success": True, 
                    "output": f"Arquivo {file_path} reescrito com sucesso! A nova lógica da ferramenta já está salva.", 
                    "metadata": {"file": file_path}
                }
            
            else:
                return {"success": False, "output": f"Ação desconhecida: {action}", "metadata": {}}
                
        except Exception as e:
            return {"success": False, "output": f"Erro fatal ao manipular o arquivo: {str(e)}", "metadata": {"error": str(e)}}