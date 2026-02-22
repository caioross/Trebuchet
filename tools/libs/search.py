from ddgs import DDGS
from tools.base import BaseTool, ToolResult
import json

class SearchTool(BaseTool):
    name = "search"
    description = "Busca na web (DuckDuckGo) com filtros avançados"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "O termo ou pergunta para pesquisar no DuckDuckGo"
            }
        },
        "required": ["query"]
    }
    
    config_schema = {
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Máximo de resultados",
                "default": 5,
                "minimum": 1,
                "maximum": 20
            },
            "region": {
                "type": "string",
                "description": "Região da busca",
                "default": "wt-wt",
                "enum": ["wt-wt", "br-pt", "us-en", "uk-en", "de-de", "fr-fr", "es-es"]
            },
            "timelimit": {
                "type": "string",
                "description": "Limite de tempo (d=dia, w=sem, m=mês)",
                "default": "None",
                "enum": ["None", "d", "w", "m", "y"]
            },
            "safesearch": {
                "type": "string",
                "description": "Filtro de segurança",
                "default": "moderate",
                "enum": ["on", "moderate", "off"]
            },
            "include_urls": {
                "type": "boolean",
                "description": "Incluir links nas respostas",
                "default": True
            }
        }
    }
    
    def run(self, query: str, config: dict = None, **kwargs) -> ToolResult:
        defaults = {
            "max_results": 5,
            "region": "wt-wt",
            "timelimit": "None",
            "safesearch": "moderate",
            "include_urls": True
        }
        
        cfg = defaults.copy()
        if config:
            cfg.update(config)

        time_limit = cfg["timelimit"]
        if time_limit == "None":
            time_limit = None

        try:
            results = []
            with DDGS() as ddgs:
                ddg_gen = ddgs.text(
                    query,
                    region=cfg["region"],
                    safesearch=cfg["safesearch"],
                    timelimit=time_limit,
                    max_results=int(cfg["max_results"])
                )
                results = list(ddg_gen)

            if not results:
                return {
                    "success": True, 
                    "output": f"Nenhum resultado encontrado para: {query}", 
                    "metadata": {"count": 0}
                }

            formatted_output = []
            for i, r in enumerate(results, 1):
                title = r.get('title', 'Sem título')
                body = r.get('body', 'Sem descrição')
                link = r.get('href', '')
                
                entry = f"[{i}] Título: {title}\n    Resumo: {body}"
                if cfg["include_urls"]:
                    entry += f"\n    Link: {link}"
                
                formatted_output.append(entry)

            final_text = "\n\n".join(formatted_output)

            return {
                "success": True,
                "output": final_text,
                "metadata": {
                    "count": len(results),
                    "raw_results": results
                }
            }

        except Exception as e:
            return {
                "success": False,
                "output": f"Erro ao realizar busca: {str(e)}",
                "metadata": {"error": str(e)}
            }