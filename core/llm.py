import os
import sys
import asyncio
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
from core.config import Config

try:
    from llama_cpp import Llama
except ImportError:
    print("CRITICAL: Biblioteca 'llama_cpp' não encontrada. Instale com: pip install llama-cpp-python")
    sys.exit(1)

class LLMEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        print("[LLM] Inicializando Engine...")
        model_path = os.path.join(Config.DIRS["models"], Config.MAIN_FILE)
        
        if not os.path.exists(model_path):
            print(f"❌ Modelo não encontrado em: {model_path}")
            self.model_missing = True
        else:
            self.model_missing = False
            self.llm = Llama(
                model_path=model_path,
                n_ctx=Config.CONTEXT_SIZE,
                n_gpu_layers=-1,
                verbose=False,
                n_batch=512,
                chat_format="chatml" 
            )
        
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._initialized = True

    async def chat(self, messages: List[Dict], temperature: float = 0.7) -> str:
        if self.model_missing:
            return "ERRO: Modelo não encontrado. Verifique o caminho no config.py."

        loop = asyncio.get_running_loop()
        
        def _run_inference():
            try:
                response = self.llm.create_chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=2048
                )
                return response["choices"][0]["message"]["content"]
            except Exception as e:
                return f"Error generating response: {str(e)}"

        return await loop.run_in_executor(self.executor, _run_inference)