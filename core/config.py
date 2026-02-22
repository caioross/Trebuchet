import os
from pathlib import Path

class Config:
    BASE_PATH = Path(os.getcwd()).resolve()
    BASE_DIR = os.getcwd()
    DIRS = {
        "models": os.path.join(BASE_DIR, "models"),
        "cache": os.path.join(BASE_DIR, "cache"),
        "sandbox": str(BASE_PATH / "sandbox"),
        "knowledge": os.path.join(BASE_DIR, "knowledge"),
        "chroma": os.path.join(BASE_DIR, "knowledge", "chroma_db"),
        "episodic": os.path.join(BASE_DIR, "knowledge", "episodes"),
        "logs": os.path.join(BASE_DIR, "logs"),
        "auth": os.path.join(BASE_DIR, "auth"),
        "screenshots": os.path.join(BASE_DIR, "logs", "screenshots"),
        "tools_plugins": os.path.join(BASE_DIR, "tools", "plugins")
    }
    
    #MAIN_REPO = "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
    #MAIN_FILE = "Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf"
    MAIN_REPO = "Qwen/Qwen2.5-7B-Instruct-GGUF"
    MAIN_FILE = "Phi-3.5-mini-Instruct-Q4_K_M.gguf"
    FAST_REPO = "Qwen/Qwen2.5-3B-Instruct-GGUF"
    FAST_FILE = "qwen2.5-3b-instruct-q4_k_m.gguf"
    
    VISION_MODEL_FILE = "ggml-model-q4_k.gguf" 
    VISION_CLIP_FILE = "mmproj-model-f16.gguf" 
    STT_MODEL = "ggml-small_whisper.bin"
    TTS_VOICE = ""
    
    TTS_MODEL_FILE = "pt_BR-faber-medium.onnx"
    TTS_SAMPLE_RATE = 22050
    TTS_SPEAKER = "0"
    TTS_DEVICE = "cpu"
    
    STREAMING_ENABLED = True
    
    CONTEXT_SIZE = 8096

    NOTION_TOKEN = ""
    GOOGLE_CLIENT_ID = ""
    GOOGLE_CLIENT_SECRET = "" 
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

    DRY_RUN = False 
    KILL_SWITCH = False
    
    RISKY_TERMS = []

    API_HOST = "0.0.0.0"
    API_PORT = 8001

for d in Config.DIRS.values():
    os.makedirs(d, exist_ok=True)
os.environ["HF_HOME"] = Config.DIRS["cache"]
