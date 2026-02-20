import os
import json
import time
import uuid
import hashlib
import datetime
from typing import List, Dict, Any, Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from core.config import Config

class DomainClassifier:
    
    @staticmethod
    def infer(source_type: str, metadata: Dict) -> str:
        if "domain" in metadata:
            return metadata["domain"]
            
        tool = metadata.get("tool", "")
        if tool in ["github", "shell", "git", "python", "code_interpreter"]:
            return "code"
        if tool in ["search", "google", "browser", "ddg"]:
            return "web"
        if tool in ["notion"]:
            return "notion"
        if tool in ["desktop"]:
            return "system"
            
        filename = metadata.get("filename", "")
        if filename:
            ext = os.path.splitext(filename)[1].lower()
            if ext in [".py", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".rs", ".go", ".java", ".php", ".sh"]:
                return "code"
            if ext in [".md", ".txt", ".json", ".csv", ".pdf"]:
                return "knowledge"
                
        if source_type == "planner_reasoning":
            return "internal_thought"
            
        return "general"

class ChunkingEngine:
    @staticmethod
    def split(text: str, domain: str, metadata: Dict) -> List[str]:
        chunk_size = metadata.get("chunk_size", 1000)
        chunk_overlap = metadata.get("chunk_overlap", 200)

        if domain == "code":
            filename = metadata.get("filename", "")
            ext = os.path.splitext(filename)[1].lower() if filename else ""
            
            lang_map = {
                ".py": Language.PYTHON, ".js": Language.JS, ".ts": Language.TS,
                ".tsx": Language.TS, ".java": Language.JAVA, ".cpp": Language.CPP,
                ".go": Language.GO, ".rs": Language.RUST, ".php": Language.PHP,
                ".rb": Language.RUBY, ".html": Language.HTML, 
                ".md": Language.MARKDOWN, ".sol": Language.SOL
            }
            language = lang_map.get(ext)
            
            if language:
                splitter = RecursiveCharacterTextSplitter.from_language(
                    language=language,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
                return splitter.split_text(text)
            
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        return splitter.split_text(text)

class EpisodicStore:
    def __init__(self, base_path: str):
        self.base_path = base_path
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

    def log(self, event_id: str, content: str, type: str, meta: Dict):
        entry = {
            "id": event_id,
            "timestamp": meta.get("timestamp", time.time()),
            "iso_time": meta.get("iso_time", datetime.datetime.now().isoformat()),
            "type": type,
            "thread_id": meta.get("thread_id", "unknown"),
            "domain": meta.get("domain", "general"),
            "content": content,
            "metadata": meta
        }

        fname = os.path.join(self.base_path, f"{int(entry['timestamp']*1000)}_{type}.json")
        try:
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[MEMORY] Failed to write episodic log: {e}")

    def get_recent(self, limit: int = 10) -> List[Dict]:
        try:
            files = sorted(os.listdir(self.base_path), reverse=True)[:limit]
            history = []
            for f in files:
                try:
                    with open(os.path.join(self.base_path, f), "r", encoding="utf-8") as fd:
                        history.append(json.load(fd))
                except: pass
            return history[::-1]
        except:
            return []

class VectorStoreAdapter:
    def __init__(self, persist_dir: str):
        self.embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.chroma = Chroma(
            persist_directory=persist_dir,
            embedding_function=self.embedder,
            collection_metadata={"hnsw:space": "cosine"}
        )

    def add(self, text: str, metadata: Dict, doc_id: str):
        clean_meta = {}
        for k, v in metadata.items():
            if v is None: continue

            if isinstance(v, (str, int, float, bool)):
                clean_meta[k] = v
            else:
                clean_meta[k] = str(v)
        
        self.chroma.add_texts([text], metadatas=[clean_meta], ids=[doc_id])

    def search(self, query: str, k: int = 5, filters: Optional[Dict] = None, score_threshold: float = 0.4):
        results = self.chroma.similarity_search_with_score(query, k=k, filter=filters)
        return [doc for doc, score in results if score < score_threshold]

class MemoryManager:
    _instance = None

    def __init__(self):
        self.classifier = DomainClassifier()
        self.chunker = ChunkingEngine()
        
        for d in Config.DIRS.values():
            os.makedirs(d, exist_ok=True)

        self.episodic = EpisodicStore(Config.DIRS["episodic"])
        self.vector_store = VectorStoreAdapter(Config.DIRS["chroma"])
        
        self.ingested_path = os.path.join(Config.DIRS["knowledge"], ".ingested.json")
        self.ingested_hashes = self._load_cache()
        
        print("[MEMORY] Sincronizando base de conhecimento...")
        self._sync_knowledge_base()
        self._sync_codebase()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def ingest_universal(self, content: str, source_type: str, metadata: Dict = None, thread_id: str = "system"):
        if not content: return
        if metadata is None: metadata = {}
        
        domain = self.classifier.infer(source_type, metadata)
        timestamp = time.time()
        base_id = str(uuid.uuid4())
        
        rich_metadata = metadata.copy()
        rich_metadata.update({
            "source_type": source_type,
            "tool": metadata.get("tool", "unknown"),
            "domain": domain,
            "timestamp": timestamp,
            "iso_time": datetime.datetime.fromtimestamp(timestamp).isoformat(),
            "ingest_base_id": base_id,
            "thread_id": thread_id 
        })
        
        self.episodic.log(base_id, content, source_type, rich_metadata)
        
        if content:
            chunks = self.chunker.split(content, domain, rich_metadata)
            
            for i, chunk in enumerate(chunks):
                chunk_meta = rich_metadata.copy()
                chunk_meta["chunk_index"] = i
                chunk_meta["total_chunks"] = len(chunks)
                chunk_meta["ingest_id"] = f"{base_id}_{i}" 
                
                self.vector_store.add(chunk, chunk_meta, chunk_meta["ingest_id"])

    def retrieve(self, query: str, k: int = 5, thread_id: Optional[str] = None) -> str:
        filters = {}
        if thread_id:
            filters = {
                "$or": [
                    {"thread_id": {"$eq": thread_id}},
                    {"domain": {"$eq": "system"}}
                ]
            }
\
        docs = self.vector_store.search(query, k=k, filters=filters)
        
        if not docs:
            return ""

        context_parts = []
        for doc in docs:
            src = doc.metadata.get("source_type", "unknown")
            entry = (
                f"<memory_entry source='{src}' thread='{doc.metadata.get('thread_id')}'>\n"
                f"{doc.page_content}\n"
                f"</memory_entry>"
            )
            context_parts.append(entry)
            
        return "<memory_context>\n" + "\n".join(context_parts) + "\n</memory_context>"

    def _load_cache(self):
        if os.path.exists(self.ingested_path):
            try:
                with open(self.ingested_path, "r", encoding="utf-8") as f: return set(json.load(f))
            except: return set()
        return set()

    def _save_cache(self):
        with open(self.ingested_path, "w", encoding="utf-8") as f: json.dump(list(self.ingested_hashes), f)

    def _sync_knowledge_base(self):
        if not os.path.exists(Config.DIRS["knowledge"]): return
        
        for root, _, files in os.walk(Config.DIRS["knowledge"]):
            if "chroma_db" in root or "episodes" in root: continue
            for f in files:
                if not f.endswith((".md", ".txt", ".py", ".json", ".js", ".html")): continue
                path = os.path.join(root, f)
                try:
                    content = open(path, encoding="utf-8", errors="ignore").read()
                    file_hash = hashlib.md5(content.encode()).hexdigest()
                    if file_hash in self.ingested_hashes: continue
                    self.ingest_universal(content, "file_content", {"filename": f, "path": path}, thread_id="system")
                    self.ingested_hashes.add(file_hash)
                except: pass
        self._save_cache()

    def _sync_codebase(self):
        system_folders = ["agents", "tools", "core", "memory", "interface"]
        project_root = os.getcwd() 

        for folder in system_folders:
            folder_path = os.path.join(project_root, folder)
            if not os.path.exists(folder_path): continue

            for root, _, files in os.walk(folder_path):
                for f in files:
                    if f.endswith(".py"): 
                        path = os.path.join(root, f)
                        try:
                            content = open(path, encoding="utf-8", errors="ignore").read()
                            
                            file_hash = hashlib.md5(content.encode()).hexdigest()
                            if file_hash in self.ingested_hashes: continue
                            
                            print(f"   👁️ [AUTO-LEITURA] Aprendendo: {folder}/{f}")
                            self.ingest_universal(
                                content, 
                                "system_source_code", 
                                {
                                    "filename": f, 
                                    "path": path, 
                                    "module": folder,
                                    "description": f"Código fonte do sistema Trebuchet: módulo {folder}"
                                },
                                thread_id="system"
                            )
                            self.ingested_hashes.add(file_hash)
                        except Exception as e: 
                            print(f"Erro ao ler {f}: {e}")
        
        self._save_cache()