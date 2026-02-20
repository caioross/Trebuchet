import os
import gc
import time
from typing import Dict, Any
from tools.base import BaseTool, ToolResult
from core.config import Config

try:
    import torch
    from diffusers import HunyuanVideoPipeline
    from diffusers.utils import export_to_video
except ImportError:
    torch = None

class HunyuanVideoTool(BaseTool):
    name = "hunyuan_video"
    description = "Gera vídeos a partir de descrições em texto usando o modelo HunyuanVideo."

    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Descrição detalhada do vídeo em inglês."
            }
        },
        "required": ["prompt"]
    }

    config_schema = {
        "type": "object",
        "properties": {
            "width": {
                "type": "integer",
                "description": "Largura do vídeo",
                "default": 384
            },
            "height": {
                "type": "integer",
                "description": "Altura do vídeo",
                "default": 256
            },
            "frames": {
                "type": "integer",
                "description": "Quantidade de quadros",
                "default": 17
            },
            "steps": {
                "type": "integer",
                "description": "Passos de inferência",
                "default": 15
            }
        }
    }

    def __init__(self):
        super().__init__()
        self.model_filename = "hunyuan-video-t2v-720p-Q4_K_M.gguf" 

    def run(self, prompt: str, config: dict = None, **kwargs) -> ToolResult:
        if torch is None:
            return {
                "success": False, 
                "output": "ERRO: Instale os pacotes necessários: pip install torch diffusers transformers accelerate imageio[ffmpeg]", 
                "metadata": {"error": "import_error"}
            }

        defaults = {
            "width": 384,
            "height": 256,
            "frames": 17,
            "steps": 15
        }
        cfg = defaults.copy()
        if config:
            cfg.update(config)

        model_full_path = os.path.join(Config.DIRS.get("models", "models"), self.model_filename)

        if not os.path.exists(model_full_path):
            return {
                "success": False, 
                "output": f"ERRO: Modelo '{self.model_filename}' não encontrado em {Config.DIRS.get('models', 'models')}.",
                "metadata": {"error": "model_missing"}
            }

        temp_dir = Config.DIRS.get("temp", "temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        output_file = os.path.join(temp_dir, f"video_hunyuan_{int(time.time())}.mp4")
        pipe = None

        try:
            print(f"[VIDEO] Carregando modelo GGUF... (O offload para a RAM será ativado)")
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            pipe = HunyuanVideoPipeline.from_single_file(
                model_full_path, 
                torch_dtype=torch.float16
            )

            pipe.enable_model_cpu_offload() 
            pipe.enable_vae_slicing()
            pipe.enable_vae_tiling()

            print(f"[VIDEO] Processando frames para: '{prompt[:40]}...'")
            
            video_frames = pipe(
                prompt=prompt,
                width=int(cfg["width"]),
                height=int(cfg["height"]),
                num_frames=int(cfg["frames"]),
                num_inference_steps=int(cfg["steps"])
            ).frames[0]

            export_to_video(video_frames, output_file, fps=15)
            
            print(f"[VIDEO] Concluído: {output_file}")
            return {
                "success": True,
                "output": f"Vídeo gerado com sucesso! Arquivo salvo em: {output_file}",
                "metadata": {
                    "file_path": output_file,
                    "resolution": f"{cfg['width']}x{cfg['height']}",
                    "frames": cfg["frames"]
                }
            }

        except Exception as e:
            return {
                "success": False,
                "output": f"Erro interno na ferramenta de vídeo: {str(e)}",
                "metadata": {"error": str(e)}
            }

        finally:
            if pipe:
                del pipe
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()