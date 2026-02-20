import base64
import os
import gc
from typing import Dict, Any
from tools.base import BaseTool, ToolResult
from core.config import Config

try:
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import Llava15ChatHandler
except ImportError:
    Llama = None

class VisionTool(BaseTool):
    name = "vision_tool"
    description = "Analisa imagens locais ou captura a tela para extrair informações visuais."

    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Caminho do arquivo (ex: 'C:/img.jpg') ou 'screenshot' para capturar a tela."
            },
            "prompt": {
                "type": "string",
                "description": "O que você quer saber sobre a imagem? (Ex: 'Descreva a cena', 'Leia o texto do erro')."
            }
        },
        "required": ["image_path", "prompt"]
    }

    config_schema = {
        "type": "object",
        "properties": {
            "temperature": {
                "type": "number",
                "description": "Criatividade (0.1 = preciso, 1.0 = criativo)",
                "default": 0.1,
                "minimum": 0.0,
                "maximum": 1.0
            },
            "max_tokens": {
                "type": "integer",
                "description": "Máximo de tokens na resposta",
                "default": 512,
                "minimum": 64,
                "maximum": 2048
            },
            "gpu_layers": {
                "type": "integer",
                "description": "Camadas na GPU (-1 = todas, 0 = CPU)",
                "default": -1,
                "minimum": -1,
                "maximum": 100
            },
            "context_size": {
                "type": "integer",
                "description": "Tamanho do Contexto (n_ctx)",
                "default": 2048,
                "enum": [2048, 4096]
            }
        }
    }

    def __init__(self):
        super().__init__()
        self.model_filename = "llava-v1.5-7b-Q4_K.gguf"
        self.mmproj_filename = "mmproj-model-f16.gguf"

    def _load_image_as_base64(self, path: str) -> str:
        if path.lower() == "screenshot":
            try:
                import pyautogui
                import io
                screenshot = pyautogui.screenshot()
                buffered = io.BytesIO()
                screenshot.save(buffered, format="JPEG")
                img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                return f"data:image/jpeg;base64,{img_b64}"
            except ImportError:
                raise ImportError("Biblioteca 'pyautogui' necessária para screenshots.")
        
        if not os.path.exists(path):
            temp_path = os.path.join(Config.DIRS.get("temp", "temp"), path)
            if os.path.exists(temp_path):
                path = temp_path

        if not os.path.exists(path):
            raise FileNotFoundError(f"Imagem não encontrada: {path}")
            
        with open(path, "rb") as image_file:
            img_b64 = base64.b64encode(image_file.read()).decode("utf-8")
            return f"data:image/jpeg;base64,{img_b64}"

    def run(self, image_path: str, prompt: str, config: dict = None, **kwargs) -> ToolResult:
        if Llama is None:
            return {"success": False, "output": "Erro: Biblioteca 'llama-cpp-python' não instalada.", "metadata": {"error": "import_error"}}

        defaults = {
            "temperature": 0.1,
            "max_tokens": 512,
            "gpu_layers": -1,
            "context_size": 2048
        }
        cfg = defaults.copy()
        if config:
            cfg.update(config)

        model_full_path = os.path.join(Config.DIRS["models"], self.model_filename)
        mmproj_full_path = os.path.join(Config.DIRS["models"], self.mmproj_filename)

        if not os.path.exists(model_full_path):
             return {
                "success": False, 
                "output": f"ERRO: Modelo '{self.model_filename}' não encontrado em {Config.DIRS['models']}.",
                "metadata": {"error": "model_missing"}
            }
        if not os.path.exists(mmproj_full_path):
             return {
                "success": False, 
                "output": f"ERRO: Projetor '{self.mmproj_filename}' não encontrado. O LLaVA precisa deste arquivo.",
                "metadata": {"error": "mmproj_missing"}
            }

        llm_vision = None
        try:
            print(f"[VISION] Carregando LLaVA... (GPU Layers: {cfg['gpu_layers']})")
            
            image_data_uri = self._load_image_as_base64(image_path)
            chat_handler = Llava15ChatHandler(clip_model_path=mmproj_full_path)

            llm_vision = Llama(
                model_path=model_full_path,
                chat_handler=chat_handler,
                n_ctx=int(cfg["context_size"]),
                n_gpu_layers=int(cfg["gpu_layers"]),
                verbose=False,
                logits_all=False 
            )

            messages = [
                {"role": "system", "content": "You are a helpful assistant that describes images accurately."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_uri}}
                    ]
                }
            ]

            print(f"[VISION] Analisando...")
            response = llm_vision.create_chat_completion(
                messages=messages,
                max_tokens=int(cfg["max_tokens"]),
                temperature=float(cfg["temperature"])
            )

            output_text = response["choices"][0]["message"]["content"]
            
            return {
                "success": True, 
                "output": output_text,
                "metadata": {
                    "tokens_used": response["usage"]["total_tokens"],
                    "model": self.model_filename
                }
            }

        except Exception as e:
            return {
                "success": False, 
                "output": f"Erro durante análise visual: {str(e)}",
                "metadata": {"error": str(e)}
            }
            
        finally:
            if llm_vision:
                del llm_vision
                gc.collect()