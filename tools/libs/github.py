import requests
import base64
from typing import Dict, Any
from tools.base import BaseTool, ToolResult

class GitHubTool(BaseTool):
    name = "github_tool"
    description = "Interage com a API do GitHub para buscar repositórios, ler documentações (README) e visualizar issues."

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "A ação a ser executada na API do GitHub.",
                "enum": ["search_repositories", "get_repository", "get_readme", "get_issue"]
            },
            "repo_name": {
                "type": "string",
                "description": "Nome do repositório no formato 'dono/repo' (ex: 'torvalds/linux'). Usado para get_repository, get_readme e get_issue."
            },
            "search_query": {
                "type": "string",
                "description": "Termo para pesquisar repositórios. Usado apenas na ação search_repositories."
            },
            "issue_number": {
                "type": "integer",
                "description": "Número da issue ou pull request. Usado apenas na ação get_issue."
            }
        },
        "required": ["action"]
    }

    config_schema = {
        "type": "object",
        "properties": {
            "github_token": {
                "type": "string",
                "description": "Personal Access Token (PAT) do GitHub. Opcional para buscas públicas, mas evita limites de taxa da API.",
                "default": ""
            }
        }
    }

    def run(self, action: str, repo_name: str = "", search_query: str = "", issue_number: int = 0, config: dict = None, **kwargs) -> ToolResult:
        headers = {"Accept": "application/vnd.github.v3+json"}

        if config and config.get("github_token"):
            headers["Authorization"] = f"token {config['github_token']}"

        base_url = "https://api.github.com"

        try:
            print(f"[GITHUB] Executando ação: {action}")

            if action == "search_repositories":
                if not search_query:
                    return {"success": False, "output": "Erro: 'search_query' é obrigatório para pesquisar repositórios.", "metadata": {}}
                
                response = requests.get(f"{base_url}/search/repositories", params={"q": search_query, "per_page": 5}, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                items = [f"- {item['full_name']}: {item['description']} ({item['stargazers_count']} stars)" for item in data.get("items", [])]
                output_text = "Repositórios encontrados:\n" + "\n".join(items) if items else "Nenhum repositório encontrado."
                return {"success": True, "output": output_text, "metadata": {"count": len(items)}}

            elif action == "get_repository":
                if not repo_name:
                    return {"success": False, "output": "Erro: 'repo_name' é obrigatório.", "metadata": {}}
                
                response = requests.get(f"{base_url}/repos/{repo_name}", headers=headers)
                response.raise_for_status()
                data = response.json()
                
                output = (
                    f"Repositório: {data['full_name']}\n"
                    f"Descrição: {data.get('description', 'Sem descrição')}\n"
                    f"Linguagem Principal: {data.get('language', 'N/A')}\n"
                    f"Stars: {data['stargazers_count']} | Forks: {data['forks_count']}"
                )
                return {"success": True, "output": output, "metadata": {"repo": data['full_name']}}

            elif action == "get_readme":
                if not repo_name:
                    return {"success": False, "output": "Erro: 'repo_name' é obrigatório.", "metadata": {}}
                
                response = requests.get(f"{base_url}/repos/{repo_name}/readme", headers=headers)
                response.raise_for_status()
                data = response.json()
                
                content = base64.b64decode(data['content']).decode('utf-8')
                return {"success": True, "output": f"README de {repo_name}:\n\n{content[:3000]}...", "metadata": {"repo": repo_name}}

            elif action == "get_issue":
                if not repo_name or not issue_number:
                    return {"success": False, "output": "Erro: 'repo_name' e 'issue_number' são obrigatórios.", "metadata": {}}
                
                response = requests.get(f"{base_url}/repos/{repo_name}/issues/{issue_number}", headers=headers)
                response.raise_for_status()
                data = response.json()
                
                output = (
                    f"Issue #{data['number']}: {data['title']}\n"
                    f"Status: {data['state']}\n"
                    f"Autor: {data['user']['login']}\n\n"
                    f"Corpo da Issue:\n{data.get('body', 'Sem corpo fornecido.')[:1500]}..."
                )
                return {"success": True, "output": output, "metadata": {"issue": data['number']}}

            else:
                return {"success": False, "output": f"Ação desconhecida: {action}", "metadata": {}}

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403 or e.response.status_code == 401:
                return {
                    "success": False,
                    "output": "Erro de Autenticação ou Limite de Taxa da API atingido. Forneça um 'github_token' válido nas configurações.",
                    "metadata": {"error": "rate_limit_or_auth"}
                }
            elif e.response.status_code == 404:
                return {"success": False, "output": "Recurso não encontrado. Verifique se o nome do repositório ou número da issue estão corretos.", "metadata": {"error": "not_found"}}
            
            return {"success": False, "output": f"Erro de requisição HTTP: {str(e)}", "metadata": {"error": "http_error"}}
            
        except Exception as e:
            return {"success": False, "output": f"Erro interno na ferramenta do GitHub: {str(e)}", "metadata": {"error": "internal_error"}}