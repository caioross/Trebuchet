import requests
import json
from typing import Dict, Any
from tools.base import BaseTool, ToolResult

class NotionTool(BaseTool):
    name = "notion_tool"
    description = "Interage com o Notion para buscar páginas/databases, ler propriedades e adicionar blocos de texto."

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "A ação desejada: 'search' (buscar), 'get_page' (ler propriedades) ou 'append_text' (adicionar texto).",
                "enum": ["search", "get_page", "append_text"]
            },
            "query": {
                "type": "string",
                "description": "Texto para pesquisar no Notion. Usado apenas na ação 'search'."
            },
            "page_id": {
                "type": "string",
                "description": "O ID da página (aquela sequência de letras/números na URL). Usado em 'get_page' e 'append_text'."
            },
            "text": {
                "type": "string",
                "description": "O texto a ser adicionado na página. Usado apenas na ação 'append_text'."
            }
        },
        "required": ["action"]
    }

    config_schema = {
        "type": "object",
        "properties": {
            "notion_api_key": {
                "type": "string",
                "description": "Integration Token do Notion (Secret Key).",
                "default": ""
            },
            "notion_version": {
                "type": "string",
                "description": "Versão da API do Notion.",
                "default": "2022-06-28"
            }
        }
    }

    def run(self, action: str, query: str = "", page_id: str = "", text: str = "", config: dict = None, **kwargs) -> ToolResult:
        api_key = config.get("notion_api_key") if config else ""
        notion_version = config.get("notion_version", "2022-06-28") if config else "2022-06-28"

        if not api_key:
            return {
                "success": False,
                "output": "Erro: 'notion_api_key' não foi fornecida nas configurações. Crie uma integração no Notion e adicione o token.",
                "metadata": {"error": "missing_api_key"}
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": notion_version,
            "Content-Type": "application/json"
        }
        base_url = "https://api.notion.com/v1"

        try:
            print(f"[NOTION] Executando ação: {action}")

            if action == "search":
                payload = {"query": query} if query else {}
                response = requests.post(f"{base_url}/search", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                if not results:
                    return {"success": True, "output": "Nenhum resultado encontrado no Notion para esta busca.", "metadata": {"count": 0}}
                
                output_lines = ["Resultados encontrados no Notion:"]
                for item in results:
                    obj_type = item.get("object")
                    item_id = item.get("id")
                    
                    title = "Sem Título"
                    if obj_type == "page" and "properties" in item:
                        for prop in item["properties"].values():
                            if prop["type"] == "title" and prop["title"]:
                                title = prop["title"][0]["plain_text"]
                                break
                    elif obj_type == "database" and "title" in item and item["title"]:
                        title = item["title"][0]["plain_text"]

                    url = item.get("url", "Sem URL")
                    output_lines.append(f"- [{obj_type.upper()}] {title} (ID: {item_id})\n  URL: {url}")

                return {"success": True, "output": "\n".join(output_lines), "metadata": {"count": len(results)}}

            elif action == "get_page":
                if not page_id:
                    return {"success": False, "output": "Erro: 'page_id' é obrigatório para ler uma página.", "metadata": {}}
                
                response = requests.get(f"{base_url}/pages/{page_id}", headers=headers)
                response.raise_for_status()
                data = response.json()
                
                url = data.get("url")
                props = data.get("properties", {})
                
                prop_summary = []
                for key, val in props.items():
                    prop_type = val.get("type")
                    prop_summary.append(f"- {key} ({prop_type})")
                    
                output = f"Página encontrada!\nURL: {url}\n\nPropriedades disponíveis:\n" + "\n".join(prop_summary)
                return {"success": True, "output": output, "metadata": {"page_id": page_id}}

            elif action == "append_text":
                if not page_id or not text:
                    return {"success": False, "output": "Erro: 'page_id' e 'text' são obrigatórios para adicionar texto.", "metadata": {}}
                
                payload = {
                    "children": [
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": text}
                                    }
                                ]
                            }
                        }
                    ]
                }
                response = requests.patch(f"{base_url}/blocks/{page_id}/children", json=payload, headers=headers)
                response.raise_for_status()
                
                return {"success": True, "output": f"Texto adicionado com sucesso à página {page_id}!", "metadata": {"page_id": page_id}}

            else:
                return {"success": False, "output": f"Ação desconhecida: {action}", "metadata": {}}

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return {"success": False, "output": "Erro de autenticação: Verifique se sua 'notion_api_key' está correta.", "metadata": {"error": "auth_failed"}}
            elif e.response.status_code == 404:
                return {"success": False, "output": "Página não encontrada ou o seu Bot não tem acesso a ela (lembre-se de adicionar a conexão na página do Notion).", "metadata": {"error": "not_found"}}
            else:
                return {"success": False, "output": f"Erro na API do Notion: {e.response.text}", "metadata": {"error": "http_error"}}
                
        except Exception as e:
            return {"success": False, "output": f"Erro interno na ferramenta do Notion: {str(e)}", "metadata": {"error": "internal_error"}}