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

SCOPES = ['https://www.googleapis.com/auth/documents']

class GoogleDocsTool(BaseTool):
    name = "google_docs_tool"
    description = "Interage com o Google Docs para ler o conteúdo de documentos, criar novos documentos ou adicionar texto."

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "A ação a executar: 'read_document' (ler um documento), 'create_document' (criar um novo) ou 'append_text' (adicionar texto ao final).",
                "enum": ["read_document", "create_document", "append_text"]
            },
            "document_id": {
                "type": "string",
                "description": "O ID do documento (a sequência longa de caracteres no URL do Google Docs). Usado em 'read_document' e 'append_text'."
            },
            "title": {
                "type": "string",
                "description": "O título do novo documento. Usado apenas na ação 'create_document'."
            },
            "text": {
                "type": "string",
                "description": "O texto a adicionar. Usado apenas na ação 'append_text'."
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
                "description": "Caminho onde o token de acesso do Docs será guardado.",
                "default": "configs/docs_token.json"
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

    def _extract_text(self, elements: list) -> str:
        text = ""
        for value in elements:
            if 'paragraph' in value:
                elements = value.get('paragraph').get('elements')
                for elem in elements:
                    if 'textRun' in elem:
                        text += elem.get('textRun').get('content')
            elif 'table' in value:
                table = value.get('table')
                for row in table.get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        text += self._extract_text(cell.get('content', [])) + " | "
                    text += "\n"
            elif 'tableOfContents' in value:
                text += self._extract_text(value.get('tableOfContents').get('content', []))
        return text

    def run(self, action: str, document_id: str = "", title: str = "", text: str = "", config: dict = None, **kwargs) -> ToolResult:
        if not GOOGLE_LIBS_INSTALLED:
            return {
                "success": False, 
                "output": "Erro: Bibliotecas do Google em falta. Execute: pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib", 
                "metadata": {"error": "missing_dependencies"}
            }

        cred_path = config.get("credentials_path", "configs/credentials.json") if config else "configs/credentials.json"
        token_path = config.get("token_path", "configs/docs_token.json") if config else "configs/docs_token.json"

        os.makedirs(os.path.dirname(cred_path) if os.path.dirname(cred_path) else ".", exist_ok=True)

        try:
            print(f"[DOCS] A autenticar no Google Docs...")
            creds = self._authenticate(cred_path, token_path)
            service = build('docs', 'v1', credentials=creds)

            if action == "read_document":
                if not document_id:
                    return {"success": False, "output": "Erro: 'document_id' é obrigatório para ler um documento.", "metadata": {}}

                print(f"[DOCS] A ler documento: {document_id}...")
                document = service.documents().get(documentId=document_id).execute()
                doc_title = document.get('title')
                doc_content = document.get('body').get('content')
                
                full_text = self._extract_text(doc_content)

                if not full_text.strip():
                    return {"success": True, "output": f"O documento '{doc_title}' está vazio.", "metadata": {"title": doc_title, "chars": 0}}

                output_text = f"Conteúdo de '{doc_title}':\n\n{full_text}"
                return {"success": True, "output": output_text[:8000], "metadata": {"title": doc_title, "chars": len(full_text)}}

            elif action == "create_document":
                if not title:
                    return {"success": False, "output": "Erro: 'title' é obrigatório para criar um documento.", "metadata": {}}

                print(f"[DOCS] A criar novo documento '{title}'...")
                document = service.documents().create(body={'title': title}).execute()
                new_doc_id = document.get('documentId')
                
                return {
                    "success": True, 
                    "output": f"Documento '{title}' criado com sucesso!\nID: {new_doc_id}\nURL: https://docs.google.com/document/d/{new_doc_id}/edit", 
                    "metadata": {"document_id": new_doc_id}
                }

            elif action == "append_text":
                if not document_id or not text:
                    return {"success": False, "output": "Erro: 'document_id' e 'text' são obrigatórios para adicionar texto.", "metadata": {}}

                print(f"[DOCS] A adicionar texto ao documento: {document_id}...")
                
                requests = [
                    {
                        'insertText': {
                            'location': {
                                'index': 1,
                                'segmentId': ''
                            }
                        }
                    }
                ]
                

                requests = [
                    {
                        'insertText': {
                            'endOfSegmentLocation': {
                                'segmentId': ''
                            },
                            'text': f"\n{text}"
                        }
                    }
                ]

                service.documents().batchUpdate(documentId=document_id, body={'requests': requests}).execute()
                
                return {
                    "success": True, 
                    "output": f"Texto adicionado com sucesso ao documento {document_id}.", 
                    "metadata": {"document_id": document_id}
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
            return {"success": False, "output": f"Ocorreu um erro na API do Google Docs: {error}", "metadata": {"error": "api_error"}}
        except Exception as e:
            return {"success": False, "output": f"Erro interno na ferramenta do Docs: {str(e)}", "metadata": {"error": "internal_error"}}