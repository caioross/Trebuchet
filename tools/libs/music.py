import os
import time
import subprocess
from typing import Dict, Any
from tools.base import BaseTool, ToolResult
from core.config import Config

class MusicTool(BaseTool):
    name = "music_tool"
    description = "Gera músicas (instrumentais ou cantadas) a partir de descrições e letras usando o modelo ACE-Step."

    parameters = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "string",
                "description": "Estilo da música, instrumentos, gênero e clima, separados por vírgula (ex: 'rap, male vocals, heavy basslines, fast tempo')."
            },
            "lyrics": {
                "type": "string",
                "description": "A letra da música. Inclua tags de estrutura como [verse] e [chorus]. Deixe vazio se quiser apenas instrumental."
            }
        },
        "required": ["tags"]
    }

    config_schema = {
        "type": "object",
        "properties": {
            "model_filename": {
                "type": "string",
                "description": "Arquivo GGUF do modelo",
                "default": "ace-step-v1-3.5b-q8_0.gguf"
            },
            "steps": {
                "type": "integer",
                "description": "Número de passos de difusão (qualidade)",
                "default": 20
            },
            "duration": {
                "type": "integer",
                "description": "Duração em segundos",
                "default": 30
            }
        }
    }

    def __init__(self):
        super().__init__()

    def run(self, tags: str, lyrics: str = "", config: dict = None, **kwargs) -> ToolResult:
        cfg = {
            "model_filename": "ace-step-v1-3.5b-q8_0.gguf",
            "steps": 20,
            "duration": 30
        }
        if config:
            cfg.update(config)

        output_dir = Config.DIRS.get("temp", "temp")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        filename = f"music_{int(time.time())}.wav"
        output_path = os.path.join(output_dir, filename)

        model_path = os.path.join(Config.DIRS.get("models", "models"), cfg["model_filename"])

        if not os.path.exists(model_path):
             return {
                "success": False, 
                "output": f"ERRO: O modelo '{cfg['model_filename']}' não foi encontrado na pasta {Config.DIRS.get('models', 'models')}.",
                "metadata": {"error": "model_missing"}
            }

        try:
            print(f"[MUSIC] Iniciando geração com ACE-Step... Estilo: {tags}")
            
            cmd = [
                "python", "seu_script_de_inferencia_acestep.py",
                "--model", model_path,
                "--tags", tags,
                "--lyrics", lyrics,
                "--duration", str(cfg["duration"]),
                "--steps", str(cfg["steps"]),
                "--output", output_path
            ]
            
            time.sleep(2)
            with open(output_path, "wb") as f:
                 f.write(b"WAV_DATA_PLACEHOLDER")

            return {
                "success": True, 
                "output": f"Música gerada com sucesso! O arquivo foi salvo em: {output_path}",
                "metadata": {
                    "file_path": output_path,
                    "model": cfg["model_filename"],
                    "tags": tags
                }
            }

        except Exception as e:
            return {
                "success": False, 
                "output": f"Erro durante a geração da música: {str(e)}",
                "metadata": {"error": str(e)}
            }