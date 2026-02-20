import os
from typing import Dict, Any
from tools.base import BaseTool, ToolResult

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_INSTALLED = True
except ImportError:
    GOOGLE_LIBS_INSTALLED = False

SCOPES = ['https://www.googleapis.com/auth/tasks']

class GoogleTasksTool(BaseTool):
    name = "google_tasks_tool"
    description = "Interage com o Google Tasks para listar tarefas pendentes ou criar novas tarefas."

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "A ação a executar: 'list_tasks' (listar tarefas pendentes) ou 'create_task' (criar uma nova tarefa).",
                "enum": ["list_tasks", "create_task"]
            },
            "task_list_id": {
                "type": "string",
                "description": "O ID da lista de tarefas. Por norma, use '@default' para a lista principal.",
                "default": "@default"
            },
            "title": {
                "type": "string",
                "description": "O título ou nome da nova tarefa. Usado apenas na ação 'create_task'."
            },
            "notes": {
                "type": "string",
                "description": "Detalhes ou anotações adicionais para a tarefa. Usado apenas na ação 'create_task'."
            }
        },
        "required": ["action"]
    }

    config_schema = {
        "type": "object",
        "properties": {
            "credentials_path": {
                "type": "string",
                "description": "Caminho para o ficheiro credentials.json transferido da Google Cloud.",
                "default": "configs/credentials.json"
            },
            "token_path": {
                "type": "string",
                "description": "Caminho onde o token de acesso do Tasks será guardado.",
                "default": "configs/tasks_token.json"
            }
        }
    }

    def _authenticate(self, credentials_path: str, token_path: str):
        creds = None
        
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(f"Ficheiro de credenciais não encontrado em: {credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())
                
        return creds

    def run(self, action: str, task_list_id: str = "@default", title: str = "", notes: str = "", config: dict = None, **kwargs) -> ToolResult:
        if not GOOGLE_LIBS_INSTALLED:
            return {
                "success": False, 
                "output": "Erro: Bibliotecas do Google em falta. Execute: pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib", 
                "metadata": {"error": "missing_dependencies"}
            }

        cred_path = config.get("credentials_path", "configs/credentials.json") if config else "configs/credentials.json"
        token_path = config.get("token_path", "configs/tasks_token.json") if config else "configs/tasks_token.json"

        os.makedirs(os.path.dirname(cred_path) if os.path.dirname(cred_path) else ".", exist_ok=True)

        try:
            print(f"[TASKS] A autenticar no Google Tasks...")
            creds = self._authenticate(cred_path, token_path)
            service = build('tasks', 'v1', credentials=creds)

            if action == "list_tasks":
                print(f"[TASKS] A procurar tarefas pendentes na lista '{task_list_id}'...")
                
                results = service.tasks().list(tasklist=task_list_id, showCompleted=False, showHidden=False).execute()
                items = results.get('items', [])

                if not items:
                    return {"success": True, "output": "Não tem tarefas pendentes nesta lista. Tudo em dia!", "metadata": {"count": 0}}

                output_lines = ["As suas tarefas pendentes:"]
                for item in items:
                    task_title = item.get('title', 'Sem Título')
                    task_notes = item.get('notes', '')
                    
                    if task_notes:
                        output_lines.append(f"- [ ] {task_title} (Detalhes: {task_notes})")
                    else:
                        output_lines.append(f"- [ ] {task_title}")

                return {"success": True, "output": "\n".join(output_lines), "metadata": {"count": len(items)}}

            elif action == "create_task":
                if not title:
                    return {"success": False, "output": "Erro: 'title' é obrigatório para criar uma tarefa.", "metadata": {}}

                print(f"[TASKS] A criar a tarefa '{title}'...")
                
                task_body = {
                    'title': title,
                    'notes': notes
                }

                result = service.tasks().insert(tasklist=task_list_id, body=task_body).execute()
                
                return {
                    "success": True, 
                    "output": f"Tarefa '{title}' adicionada com sucesso à sua lista!", 
                    "metadata": {"task_id": result.get('id')}
                }

            else:
                return {"success": False, "output": f"Ação desconhecida: {action}", "metadata": {}}

        except FileNotFoundError:
            return {
                "success": False,
                "output": "Ficheiro 'credentials.json' não encontrado. Guarde-o na pasta especificada.",
                "metadata": {"error": "missing_credentials"}
            }
        except HttpError as error:
            return {"success": False, "output": f"Ocorreu um erro na API do Google Tasks: {error}", "metadata": {"error": "api_error"}}
        except Exception as e:
            return {"success": False, "output": f"Erro interno na ferramenta do Tasks: {str(e)}", "metadata": {"error": "internal_error"}}