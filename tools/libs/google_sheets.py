import os
from typing import Dict, Any, List
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

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class GoogleSheetsTool(BaseTool):
    name = "google_sheets_tool"
    description = "Interage com o Google Sheets para ler dados ou adicionar novas linhas a uma folha de cálculo."

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "A ação a ser executada: 'read_range' (ler um intervalo de células) ou 'append_row' (adicionar uma nova linha no final).",
                "enum": ["read_range", "append_row"]
            },
            "spreadsheet_id": {
                "type": "string",
                "description": "O ID da folha de cálculo (é a sequência longa de letras e números que se encontra no URL do Google Sheets)."
            },
            "range_name": {
                "type": "string",
                "description": "O nome da página e/ou intervalo. Ex: 'Página1!A1:D10' para ler, ou apenas 'Página1' para adicionar uma linha."
            },
            "values": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Uma lista de valores a inserir (cada item representa uma coluna). Usado apenas na ação 'append_row'."
            }
        },
        "required": ["action", "spreadsheet_id", "range_name"]
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
                "description": "Caminho onde o token de acesso do Sheets será guardado.",
                "default": "configs/sheets_token.json"
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

    def run(self, action: str, spreadsheet_id: str, range_name: str, values: List[str] = None, config: dict = None, **kwargs) -> ToolResult:
        if not GOOGLE_LIBS_INSTALLED:
            return {
                "success": False, 
                "output": "Erro: Bibliotecas do Google em falta. Execute: pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib", 
                "metadata": {"error": "missing_dependencies"}
            }

        cred_path = config.get("credentials_path", "configs/credentials.json") if config else "configs/credentials.json"
        token_path = config.get("token_path", "configs/sheets_token.json") if config else "configs/sheets_token.json"

        os.makedirs(os.path.dirname(cred_path) if os.path.dirname(cred_path) else ".", exist_ok=True)

        try:
            print(f"[SHEETS] A autenticar no Google Sheets...")
            creds = self._authenticate(cred_path, token_path)
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()

            if action == "read_range":
                print(f"[SHEETS] A ler intervalo '{range_name}'...")
                
                result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
                rows = result.get('values', [])

                if not rows:
                    return {"success": True, "output": f"Nenhum dado encontrado no intervalo {range_name}.", "metadata": {"count": 0}}

                output_lines = [f"Dados lidos de {range_name}:"]
                for row in rows:
                    output_lines.append(" | ".join([str(cell) for cell in row]))

                return {
                    "success": True, 
                    "output": "\n".join(output_lines), 
                    "metadata": {"rows_read": len(rows)}
                }

            elif action == "append_row":
                if not values:
                    return {"success": False, "output": "Erro: O parâmetro 'values' (lista de colunas) é obrigatório para adicionar uma linha.", "metadata": {}}

                print(f"[SHEETS] A adicionar linha à página '{range_name}'...")
                
                body = {'values': [values]}
                
                result = sheet.values().append(
                    spreadsheetId=spreadsheet_id, 
                    range=range_name,
                    valueInputOption="USER_ENTERED", 
                    body=body
                ).execute()
                
                updates = result.get('updates', {})
                cells_updated = updates.get('updatedCells', 0)
                updated_range = updates.get('updatedRange', 'Desconhecido')

                return {
                    "success": True, 
                    "output": f"Linha adicionada com sucesso! {cells_updated} células atualizadas no intervalo {updated_range}.", 
                    "metadata": {"cells_updated": cells_updated, "updated_range": updated_range}
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
            return {"success": False, "output": f"Ocorreu um erro na API do Google Sheets: {error}", "metadata": {"error": "api_error"}}
        except Exception as e:
            return {"success": False, "output": f"Erro interno na ferramenta do Sheets: {str(e)}", "metadata": {"error": "internal_error"}}