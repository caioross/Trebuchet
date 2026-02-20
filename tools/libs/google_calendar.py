import os
import datetime
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

SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarTool(BaseTool):
    name = "google_calendar_tool"
    description = "Interage com o Google Calendar para listar os próximos eventos ou criar novos eventos e reuniões."

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "A ação a ser executada: 'list_events' (ver agenda) ou 'create_event' (marcar compromisso).",
                "enum": ["list_events", "create_event"]
            },
            "max_results": {
                "type": "integer",
                "description": "Quantos eventos listar (usado apenas em 'list_events'). Padrão é 5."
            },
            "summary": {
                "type": "string",
                "description": "O título do evento. Usado apenas em 'create_event'."
            },
            "description": {
                "type": "string",
                "description": "A descrição ou detalhes do evento. Usado apenas em 'create_event'."
            },
            "start_time": {
                "type": "string",
                "description": "Data e hora de início no formato ISO (ex: '2023-10-25T10:00:00-03:00'). Usado apenas em 'create_event'."
            },
            "end_time": {
                "type": "string",
                "description": "Data e hora de término no formato ISO (ex: '2023-10-25T11:00:00-03:00'). Usado apenas em 'create_event'."
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
                "description": "Caminho onde o token de acesso gerado será guardado.",
                "default": "configs/token.json"
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

    def run(self, action: str, max_results: int = 5, summary: str = "", description: str = "", start_time: str = "", end_time: str = "", config: dict = None, **kwargs) -> ToolResult:
        if not GOOGLE_LIBS_INSTALLED:
            return {
                "success": False, 
                "output": "Erro: As bibliotecas do Google não estão instaladas. Execute: pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib", 
                "metadata": {"error": "missing_dependencies"}
            }

        cred_path = config.get("credentials_path", "configs/credentials.json") if config else "configs/credentials.json"
        token_path = config.get("token_path", "configs/token.json") if config else "configs/token.json"

        os.makedirs(os.path.dirname(cred_path) if os.path.dirname(cred_path) else ".", exist_ok=True)

        try:
            print(f"[CALENDAR] A autenticar no Google...")
            creds = self._authenticate(cred_path, token_path)
            service = build('calendar', 'v3', credentials=creds)

            if action == "list_events":
                print(f"[CALENDAR] A procurar os próximos {max_results} eventos...")
                now = datetime.datetime.utcnow().isoformat() + 'Z'
                events_result = service.events().list(
                    calendarId='primary', timeMin=now,
                    maxResults=max_results, singleEvents=True,
                    orderBy='startTime').execute()
                events = events_result.get('items', [])

                if not events:
                    return {"success": True, "output": "Não tem eventos futuros agendados no seu calendário.", "metadata": {"count": 0}}

                output_lines = ["Próximos eventos na sua agenda:"]
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    output_lines.append(f"- {start}: {event.get('summary', 'Sem Título')}")
                
                return {"success": True, "output": "\n".join(output_lines), "metadata": {"count": len(events)}}

            elif action == "create_event":
                if not summary or not start_time or not end_time:
                    return {"success": False, "output": "Erro: 'summary', 'start_time' e 'end_time' são obrigatórios para criar um evento.", "metadata": {}}

                print(f"[CALENDAR] A criar evento: '{summary}'...")
                event_body = {
                    'summary': summary,
                    'description': description,
                    'start': {
                        'dateTime': start_time,
                    },
                    'end': {
                        'dateTime': end_time,
                    },
                }

                event = service.events().insert(calendarId='primary', body=event_body).execute()
                return {
                    "success": True, 
                    "output": f"Evento '{summary}' criado com sucesso!\nLink: {event.get('htmlLink')}", 
                    "metadata": {"event_id": event.get('id')}
                }

            else:
                return {"success": False, "output": f"Ação desconhecida: {action}", "metadata": {}}

        except FileNotFoundError as e:
            return {
                "success": False,
                "output": "Ficheiro 'credentials.json' do Google não encontrado. Por favor, crie as credenciais OAuth na Google Cloud e guarde-as no caminho especificado.",
                "metadata": {"error": "missing_credentials"}
            }
        except HttpError as error:
            return {"success": False, "output": f"Ocorreu um erro na API do Google Calendar: {error}", "metadata": {"error": "api_error"}}
        except Exception as e:
            return {"success": False, "output": f"Erro interno na ferramenta do Calendar: {str(e)}", "metadata": {"error": "internal_error"}}