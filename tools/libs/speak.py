import os
import torch
import sounddevice as sd
import numpy as np
from typing import Dict, Any
from tools.base import BaseTool, ToolResult
from core.config import Config

class SpeakTool(BaseTool):
    name = "speak"
    description = "Transforma texto em fala (TTS) usando IA Neural local. Use para dar voz ao assistente."

    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "O texto a ser falado."
            }
        },
        "required": ["text"]
    }

    config_schema = {
        "type": "object",
        "properties": {
            "speaker": {
                "type": "string",
                "description": "ID da Voz (depende do modelo)",
                "default": "aidar", 
                "enum": ["aidar", "baya", "kseniya", "xenia", "random"] 
            },
            "sample_rate": {
                "type": "integer",
                "description": "Qualidade (Hz)",
                "default": 48000,
                "enum": [8000, 24000, 48000]
            },
            "device": {
                "type": "string",
                "description": "Dispositivo de Execução",
                "default": "cpu",
                "enum": ["cpu", "cuda"]
            }
        }
    }

    def __init__(self):
        super().__init__()

        self.model_path = os.path.join(Config.DIRS["models"], Config.TTS_MODEL_FILE)
        self.model = None
        self.current_device = "cpu"

    def _load_model(self, device_name: str):

        if self.model is not None and self.current_device == device_name:
            return True

        if not os.path.exists(self.model_path):
            return False

        try:
            print(f"[SPEAK] Carregando modelo TTS em {device_name}...")
            device = torch.device(device_name)

            self.model = torch.jit.load(self.model_path, map_location=device)
            self.model.eval()
            self.current_device = device_name
            return True
            
        except Exception as e:
            print(f"[SPEAK] Erro ao carregar modelo: {e}")
            return False

    def run(self, text: str, config: dict = None, **kwargs) -> ToolResult:
        defaults = {
            "speaker": "aidar",
            "sample_rate": 48000,
            "device": "cpu"
        }
        cfg = defaults.copy()
        if config:
            cfg.update(config)

        if not os.path.exists(self.model_path):
             return {
                "success": False, 
                "output": f"ERRO CRÍTICO: Modelo de voz não encontrado em '{self.model_path}'. Por favor, baixe o modelo 'silero_pt_v4.pt' e coloque na pasta 'models'.",
                "metadata": {"error": "file_not_found"}
            }

        if not self._load_model(cfg["device"]):
             return {
                 "success": False, 
                 "output": "Falha técnica ao inicializar o motor de voz (Torch JIT Load Error).",
                 "metadata": {"error": "load_error"}
            }

        try:

            audio = self.model(
                text,
                speaker=cfg["speaker"],
                sample_rate=int(cfg["sample_rate"]),
                put_accent=True,
                put_yo=True
            )

            audio_np = audio.cpu().numpy()

            sd.play(audio_np, int(cfg["sample_rate"]))
            sd.wait() 
            
            return {
                "success": True, 
                "output": f"Falei: '{text}'",
                "metadata": {
                    "sample_rate": cfg["sample_rate"],
                    "speaker": cfg["speaker"]
                }
            }

        except Exception as e:
            return {
                "success": False, 
                "output": f"Erro durante a síntese de voz: {str(e)}",
                "metadata": {"error": str(e)}
            }