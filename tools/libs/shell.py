import subprocess
import os
import platform
from typing import Dict, Any, List
from core.config import Config
from tools.base import BaseTool, ToolResult

class ShellTool(BaseTool):
    name = "shell"
    description = "Executa comandos de terminal. Use para listar arquivos, manipular sistema ou executar scripts."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "O comando a ser executado (ex: 'ls -la', 'pip install pandas')."
            }
        },
        "required": ["command"]
    }

    config_schema = {
        "type": "object",
        "properties": {
            "timeout": {
                "type": "integer",
                "description": "Timeout (segundos)",
                "default": 30,
                "minimum": 5,
                "maximum": 300
            },
            "max_lines": {
                "type": "integer",
                "description": "Máximo de linhas na saída",
                "default": 50,
                "minimum": 10,
                "maximum": 500
            },
            "safe_mode": {
                "type": "boolean",
                "description": "Bloquear comandos perigosos",
                "default": True
            },
            "shell_type": {
                "type": "string",
                "description": "Tipo de Shell",
                "default": "auto",
                "enum": ["auto", "powershell", "cmd", "bash"]
            }
        }
    }

    def _is_safe(self, command: str) -> bool:
        blacklist = [
            "rm -rf /", ":(){ :|:& };:", "mkfs", "dd if=/dev",
            "format c:", "rd /s /q c:\\", "del /f /s /q c:\\windows"
        ]
        cmd_lower = command.lower()
        for bad in blacklist:
            if bad in cmd_lower:
                return False
        return True

    def run(self, command: str, config: dict = None, **kwargs) -> ToolResult:
        defaults = {
            "timeout": 30,
            "max_lines": 50,
            "safe_mode": True,
            "shell_type": "auto"
        }
        cfg = defaults.copy()
        if config:
            cfg.update(config)

        if cfg["safe_mode"] and not self._is_safe(command):
            return {
                "success": False, 
                "output": "Ação Bloqueada: O comando contém padrões considerados perigosos pelo 'Safe Mode'. Desative-o nas configurações se tiver certeza.",
                "metadata": {"security_blocked": True}
            }

        sandbox_path = Config.DIRS["sandbox"]
        if not os.path.exists(sandbox_path):
            os.makedirs(sandbox_path)

        system = platform.system()
        shell_cmd = []
        
        if cfg["shell_type"] == "auto":
            if system == "Windows":
                shell_cmd = ["powershell", "-Command", command]
            else:
                shell_cmd = ["/bin/bash", "-c", command]
        elif cfg["shell_type"] == "powershell":
            shell_cmd = ["powershell", "-Command", command]
        elif cfg["shell_type"] == "cmd":
            shell_cmd = ["cmd.exe", "/c", command]
        elif cfg["shell_type"] == "bash":
            shell_cmd = ["/bin/bash", "-c", command]

        try:
            result = subprocess.run(
                shell_cmd,
                capture_output=True,
                text=True,
                cwd=sandbox_path, 
                timeout=int(cfg["timeout"])
            )
            
            full_output = result.stdout
            if result.stderr:
                full_output += f"\n[STDERR]:\n{result.stderr}"

            lines = full_output.splitlines()
            max_lines = int(cfg["max_lines"])
            
            if len(lines) > max_lines:
                preview = "\n".join(lines[:max_lines])
                full_output = f"{preview}\n\n... [Saída truncada: {len(lines) - max_lines} linhas ocultas. Aumente o limite nas configurações]"

            if result.returncode != 0:
                return {
                    "success": False, 
                    "output": f"Erro (Exit Code {result.returncode}):\n{full_output}", 
                    "metadata": {"exit_code": result.returncode}
                }

            final_output = full_output.strip() or "Comando executado com sucesso (sem retorno visual)."
            
            return {
                "success": True, 
                "output": final_output, 
                "metadata": {"execution_time": "N/A"}
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False, 
                "output": f"Erro: O comando excedeu o tempo limite de {cfg['timeout']}s.", 
                "metadata": {"error": "timeout"}
            }
        except Exception as e:
            return {
                "success": False, 
                "output": f"Erro de execução: {str(e)}", 
                "metadata": {"error": str(e)}
            }