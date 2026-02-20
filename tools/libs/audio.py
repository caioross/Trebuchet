import os
import gc
from typing import Dict, Any
from tools.base import BaseTool, ToolResult
from core.config import Config

IMPORT_ERROR = None
try:
    from faster_whisper import WhisperModel
except ImportError as e:
    WhisperModel = None
    IMPORT_ERROR = str(e)
except Exception as e:
    WhisperModel = None
    IMPORT_ERROR = f"Erro inesperado no import: {str(e)}"

class HearingTool(BaseTool):
    name = "hearing_tool"
    description = "Transcreve ou traduz arquivos de áudio para texto usando Whisper local."

    parameters = {
        "type": "object",
        "properties": {
            "audio_path": {
                "type": "string",
                "description": "Caminho absoluto do arquivo de áudio (ex: 'C:/audios/reuniao.mp3')."
            }
        },
        "required": ["audio_path"]
    }

    config_schema = {
        "type": "object",
        "properties": {
            "model_size": {
                "type": "string",
                "description": "Tamanho do Modelo (maior = mais preciso, mais lento)",
                "default": "base",
                "enum": ["tiny", "base", "small", "medium", "large-v3"]
            },
            "device": {
                "type": "string",
                "description": "Dispositivo de Processamento",
                "default": "auto",
                "enum": ["auto", "cpu", "cuda"]
            },
            "task": {
                "type": "string",
                "description": "Tarefa (transcrever ou traduzir p/ inglês)",
                "default": "transcribe",
                "enum": ["transcribe", "translate"]
            },
            "compute_type": {
                "type": "string",
                "description": "Tipo de Computação (precisão vs velocidade)",
                "default": "int8",
                "enum": ["int8", "float16", "float32"]
            }
        }
    }

    def run(self, audio_path: str, config: dict = None, **kwargs) -> ToolResult:
        if WhisperModel is None:
            return {
                "success": False, 
                "output": f"Falha ao carregar biblioteca 'faster-whisper'.\nErro Técnico: {IMPORT_ERROR}\n\n(Dica: Se for erro de DLL no Windows, verifique se zlibwapi.dll e cuDNN estão no PATH).",
                "metadata": {"error": "import_error"}
            }
        defaults = {
            "model_size": "base",
            "device": "auto",
            "task": "transcribe",
            "compute_type": "int8"
        }
        cfg = defaults.copy()
        if config:
            cfg.update(config)

        if not os.path.exists(audio_path):
            temp_path = os.path.join(Config.DIRS.get("temp", "temp"), audio_path)
            if os.path.exists(temp_path):
                audio_path = temp_path
            else:
                return {
                    "success": False, 
                    "output": f"Arquivo de áudio não encontrado: {audio_path}",
                    "metadata": {"error": "file_not_found"}
                }

        model = None
        try:
            print(f"👂 [AUDIO] Carregando Whisper ({cfg['model_size']} | {cfg['device']})...")
            
            model = WhisperModel(
                model_size_or_path=cfg["model_size"],
                device=cfg["device"],
                compute_type=cfg["compute_type"],
                download_root=os.path.join(Config.DIRS["cache"], "whisper")
            )

            print(f"👂 [AUDIO] Processando: {os.path.basename(audio_path)}...")
            
            segments, info = model.transcribe(
                audio_path, 
                beam_size=5, 
                task=cfg["task"]
            )

            full_text = ""
            for segment in segments:
                full_text += segment.text + " "

            duration = info.duration
            language = info.language
            prob = info.language_probability

            print(f"👂 [AUDIO] Concluído ({duration:.1f}s). Idioma detectado: {language} ({prob:.0%})")
            
            return {
                "success": True,
                "output": f"TRANSCRIÇÃO ({language.upper()}): {full_text.strip()}",
                "metadata": {
                    "duration": duration,
                    "language": language,
                    "model": cfg["model_size"]
                }
            }

        except Exception as e:
            return {
                "success": False,
                "output": f"Erro na transcrição: {str(e)}",
                "metadata": {"error": str(e)}
            }
            
        finally:
            if model:
                del model
            gc.collect()