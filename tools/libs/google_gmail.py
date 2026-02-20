import os
import base64
from email.message import EmailMessage
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

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

class GmailTool(BaseTool):
    name = "gmail_tool"
    description = "Interage com o Gmail para ler os últimos emails (não lidos) ou enviar novos emails."

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "A ação a ser executada: 'read_emails' (ler caixa de entrada) ou 'send_email' (enviar um email).",
                "enum": ["read_emails", "send_email"]
            },
            "max_results": {
                "type": "integer",
                "description": "Quantos emails ler (usado apenas em 'read_emails'). Padrão é 5."
            },
            "to": {
                "type": "string",
                "description": "O endereço de email do destinatário. Usado apenas em 'send_email'."
            },
            "subject": {
                "type": "string",
                "description": "O assunto do email. Usado apenas em 'send_email'."
            },
            "body": {
                "type": "string",
                "description": "O corpo/conteúdo da mensagem do email. Usado apenas em 'send_email'."
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
                "description": "Caminho onde o token de acesso do Gmail será guardado.",
                "default": "configs/gmail_token.json"
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

    def run(self, action: str, max_results: int = 5, to: str = "", subject: str = "", body: str = "", config: dict = None, **kwargs) -> ToolResult:
        if not GOOGLE_LIBS_INSTALLED:
            return {
                "success": False, 
                "output": "Erro: Bibliotecas do Google em falta. Execute: pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib", 
                "metadata": {"error": "missing_dependencies"}
            }

        cred_path = config.get("credentials_path", "configs/credentials.json") if config else "configs/credentials.json"
        token_path = config.get("token_path", "configs/gmail_token.json") if config else "configs/gmail_token.json"

        os.makedirs(os.path.dirname(cred_path) if os.path.dirname(cred_path) else ".", exist_ok=True)

        try:
            print(f"[GMAIL] A autenticar no Google...")
            creds = self._authenticate(cred_path, token_path)
            service = build('gmail', 'v1', credentials=creds)

            if action == "read_emails":
                print(f"[GMAIL] A procurar os últimos {max_results} emails não lidos...")

                results = service.users().messages().list(userId='me', labelIds=['INBOX'], q="is:unread", maxResults=max_results).execute()
                messages = results.get('messages', [])

                if not messages:
                    return {"success": True, "output": "Não tem emails novos/não lidos na sua caixa de entrada.", "metadata": {"count": 0}}

                output_lines = ["Últimos emails não lidos:"]
                
                for msg in messages:
                    msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                    payload = msg_data.get('payload', {})
                    headers = payload.get('headers', [])
                    
                    sender = "Desconhecido"
                    msg_subject = "Sem Assunto"
                    
                    for header in headers:
                        if header['name'] == 'From':
                            sender = header['value']
                        elif header['name'] == 'Subject':
                            msg_subject = header['value']
                            
                    snippet = msg_data.get('snippet', '')
                    
                    output_lines.append(f"De: {sender}\n   Assunto: {msg_subject}\n   Resumo: {snippet}...\n")

                return {"success": True, "output": "\n".join(output_lines), "metadata": {"count": len(messages)}}

            elif action == "send_email":
                if not to or not subject or not body:
                    return {"success": False, "output": "Erro: 'to', 'subject' e 'body' são obrigatórios para enviar um email.", "metadata": {}}

                print(f"[GMAIL] A enviar email para '{to}'...")
                
                message = EmailMessage()
                message.set_content(body)
                message['To'] = to
                message['From'] = 'me'
                message['Subject'] = subject

                encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
                create_message = {'raw': encoded_message}

                send_message = service.users().messages().send(userId="me", body=create_message).execute()
                
                return {
                    "success": True, 
                    "output": f"Email enviado com sucesso para {to}!\nID da mensagem: {send_message['id']}", 
                    "metadata": {"message_id": send_message['id']}
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
            return {"success": False, "output": f"Ocorreu um erro na API do Gmail: {error}", "metadata": {"error": "api_error"}}
        except Exception as e:
            return {"success": False, "output": f"Erro interno na ferramenta do Gmail: {str(e)}", "metadata": {"error": "internal_error"}}