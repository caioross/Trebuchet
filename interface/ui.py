from nicegui import ui, app
import asyncio
import base64
import time
from pathlib import Path
import sys
import json
import uuid
import glob
import logging
import queue
from datetime import datetime
from tools.registry import ToolRegistry
sys_log_queue = queue.Queue()

class StreamRedirector:
    def __init__(self, original_stream, stream_type='info'):
        self.original_stream = original_stream
        self.stream_type = stream_type
        self.buffer = ""

    def write(self, data):
        if self.original_stream:
            self.original_stream.write(data) 
        
        self.buffer += data
        if '\n' in self.buffer:
            lines = self.buffer.split('\n')
            for line in lines[:-1]:
                if line.strip():
                    sys_log_queue.put((line, self.stream_type))
            self.buffer = lines[-1]

    def flush(self):
        if self.original_stream:
            self.original_stream.flush()

    def isatty(self):
        return False

    def __getattr__(self, name):
        return getattr(self.original_stream, name)

# 1. Captura prints nativos e erros de crash
sys.stdout = StreamRedirector(sys.stdout, 'info')
sys.stderr = StreamRedirector(sys.stderr, 'error')

# 2. Captura os logs das bibliotecas ocultas (FastAPI, Transformers, etc)
class QueueLoggerHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            # Define a cor baseada na gravidade do log
            ltype = 'error' if record.levelno >= logging.ERROR else 'warning' if record.levelno >= logging.WARNING else 'info'
            sys_log_queue.put((msg, ltype))
        except Exception:
            pass



queue_handler = QueueLoggerHandler()
queue_handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
logging.getLogger().addHandler(queue_handler)
logging.getLogger().setLevel(logging.INFO)


HISTORY_DIR = Path(r"E:\Trebuchet\knowledge\chats")
HISTORY_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = Path(r"E:\Trebuchet\temp")
if not UPLOAD_DIR.parent.exists():
    UPLOAD_DIR = Path("temp")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

tool_registry = ToolRegistry()
app.add_static_files('/public', 'public')

C_BG_MAIN = '#09090b'
C_BG_SEC = '#18181b' 
C_BORDER = '#27272a'
C_ACCENT = '#6366f1'
C_ACCENT_HOVER = '#4f46e5'
C_TEXT_MAIN = '#f4f4f5'
C_TEXT_SEC = '#a1a1aa'




@ui.page('/')
async def main_page():
    ui.add_head_html(f'''
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
            
            :root {{
                --nicegui-default-padding: 0;
                --nicegui-default-gap: 0;
            }}
            
            body {{
                background-color: {C_BG_MAIN};
                color: {C_TEXT_MAIN};
                font-family: 'Inter', sans-serif;
                overflow: hidden; /* App-like feel */
            }}
            
            /* Glassmorphism Classes */
            .glass {{
                background: rgba(24, 24, 27, 0.7);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border-top: 1px solid rgba(255,255,255,0.05);
            }}
            
            /* Custom Scrollbars */
            .scroll-hide::-webkit-scrollbar {{ display: none; }}
            
            .custom-scroll::-webkit-scrollbar {{
                width: 5px;
                height: 5px;
            }}
            .custom-scroll::-webkit-scrollbar-track {{
                background: transparent;
            }}
            .custom-scroll::-webkit-scrollbar-thumb {{
                background: {C_BORDER};
                border-radius: 3px;
            }}
            .custom-scroll::-webkit-scrollbar-thumb:hover {{
                background: {C_TEXT_SEC};
            }}

            /* Component Styles */
            .thinking-process {{
                border-left: 2px solid {C_ACCENT};
                background: rgba(99, 102, 241, 0.05);
                padding: 10px;
                border-radius: 0 8px 8px 0;
            }}
            
            .log-font {{
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                line-height: 1.5;
                word-break: break-word;
            }}

            .msg-bubble-user {{
                background-color: {C_ACCENT};
                color: white;
                border-radius: 12px 12px 0 12px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}

            .msg-bubble-bot {{
                background-color: transparent;
                border: 1px solid {C_BORDER};
                border-radius: 12px 12px 12px 0;
            }}
            
            .sidebar-item {{
                transition: all 0.2s;
                color: {C_TEXT_SEC};
                border-radius: 6px;
            }}
            .sidebar-item:hover {{
                background-color: {C_BORDER};
                color: {C_TEXT_MAIN};
            }}
            .sidebar-item-active {{
                background-color: {C_ACCENT};
                color: white !important;
            }}
        </style>

        <script>
            // Ponte para enviar dados do JS para o Python via componente Vue oculto
            window.sendToBridge = (type, data) => {{
                const bridge = getElement('data-bridge');
                if (bridge) {{
                    bridge.$emit('update:modelValue', type + '|||' + data);
                }}
            }};
            
            // Lógica de Gravação de Áudio
            let mediaRecorder;
            let audioChunks = [];

            async function toggleRecording() {{
                if (mediaRecorder && mediaRecorder.state === "recording") {{
                    mediaRecorder.stop();
                    return "stopped";
                }} else {{
                    try {{
                        const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                        mediaRecorder = new MediaRecorder(stream);
                        audioChunks = [];
                        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                        mediaRecorder.onstop = () => {{
                            const blob = new Blob(audioChunks, {{ type: 'audio/webm' }});
                            const reader = new FileReader();
                            reader.readAsDataURL(blob);
                            reader.onloadend = () => window.sendToBridge('AUDIO', reader.result);
                        }};
                        mediaRecorder.start();
                        return "started";
                    }} catch (err) {{
                        console.error("Erro mic:", err);
                        return "error";
                    }}
                }}
            }}

            // Lógica de Paste (Imagem)
            document.addEventListener('paste', (e) => {{
                const items = (e.clipboardData || e.originalEvent.clipboardData).items;
                for (let item of items) {{
                    if (item.type.indexOf("image") === 0) {{
                        const blob = item.getAsFile();
                        const reader = new FileReader();
                        reader.onload = (event) => window.sendToBridge('PASTE', event.target.result);
                        reader.readAsDataURL(blob);
                    }}
                }}
            }});
        </script>
    ''')

    current_chat_id = str(uuid.uuid4())
    
    session = {
        "running": False,
        "history": [],
        "attachments": [],
        "config": {
            "tools": {},
            "model": "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
            "temperature": 0.7,
            "max_steps": 10
        }
    }
    
    
    def open_tool_settings(tool_name, tool_obj):
        with ui.dialog() as settings_dialog, ui.card():
            ui.label(f'Configurações: {tool_name}').classes('text-lg font-bold mb-4')
            
            if tool_name not in session["config"]["tools"]:
                session["config"]["tools"][tool_name] = {"enabled": True, "settings": {}}
            
            current_settings = session["config"]["tools"][tool_name]["settings"]
            schema = getattr(tool_obj, 'config_schema', {}).get('properties', {})
            
            if not schema:
                ui.label('Nenhuma configuração disponível para esta ferramenta.').classes('italic text-zinc-500')
            else:
                with ui.column().classes('gap-4 min-w-[300px]'):
                    for field, props in schema.items():
                        field_type = props.get('type', 'string')
                        label = props.get('description', field)
                        default = props.get('default')
                        
                        if field not in current_settings:
                            current_settings[field] = default
                            
                        if field_type == 'boolean':
                            ui.switch(label).bind_value(current_settings, field)
                        elif field_type == 'integer':
                            ui.number(label=label, value=default).bind_value(current_settings, field)
                        elif 'enum' in props:
                            ui.select(props['enum'], label=label).bind_value(current_settings, field)
                        else:
                            ui.input(label=label).bind_value(current_settings, field)

            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Fechar', on_click=settings_dialog.close).props('flat')
        
        settings_dialog.open()
        
        
    def save_current_chat():
        if not session["history"]: return
        
        filepath = HISTORY_DIR / f"{current_chat_id}.json"
        
  
        title = "Nova Conversa"
        if len(session["history"]) > 0:
            first_msg = session["history"][0]["content"][:30]
            title = first_msg + "..." if len(first_msg) >= 30 else first_msg

        data = {
            "id": current_chat_id,
            "title": title,
            "timestamp": datetime.now().isoformat(),
            "messages": session["history"],
            "config": session["config"]
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        refresh_history_sidebar() 

   
    def load_chat(file_id):
        nonlocal current_chat_id
        try:
            filepath = HISTORY_DIR / f"{file_id}.json"
            if not filepath.exists(): return
            
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            current_chat_id = data["id"]
            session["history"] = data["messages"]
            session["config"] = data.get("config", session["config"])
            
         
            messages_container.clear()
            for msg in session["history"]:
                render_message(msg["role"], msg["content"])
                
            ui.notify(f'Conversa "{data["title"]}" carregada!', type='positive')
            
        except Exception as e:
            ui.notify(f"Erro ao carregar: {e}", type='negative')

  
    def start_new_chat():
        nonlocal current_chat_id
        save_current_chat() 
        
        current_chat_id = str(uuid.uuid4())
        session["history"] = []
        session["attachments"] = []
        messages_container.clear()
        update_attachments_ui() 
        ui.notify("Nova conversa iniciada", position='top')
        
        
    async def handle_bridge(e):
        if not e.value or '|||' not in e.value: return
        
        type_label, data_base64 = e.value.split('|||', 1)
        prefix = "paste" if type_label == 'PASTE' else "audio"
        ext = "png" if type_label == 'PASTE' else "webm"
        filename = f"{prefix}_{int(time.time())}.{ext}"
        filepath = UPLOAD_DIR / filename
        
        try:
            _, encoded = data_base64.split(",", 1)
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(encoded))
            
            session["attachments"].append(str(filepath.absolute()))
            update_attachments_ui()
            ui.notify(f"{type_label} recebido com sucesso", color='positive', position='top')
        except Exception as err:
            ui.notify(f"Erro no upload: {err}", color='negative')
        
        bridge_input.value = ""

    def remove_attachment(path):
        if path in session["attachments"]:
            session["attachments"].remove(path)
        update_attachments_ui()

    def update_attachments_ui():
        attachments_container.clear()
        with attachments_container:
            for path in session["attachments"]:
                with ui.row().classes('bg-zinc-800 rounded px-2 py-1 items-center gap-2 border border-zinc-700'):
                    ui.icon('attach_file', size='xs', color='zinc-400')
                    ui.label(Path(path).name).classes('text-xs text-zinc-300 max-w-[150px] truncate')
                    ui.button(icon='close', on_click=lambda p=path: remove_attachment(p)).props('flat dense size=xs color=red')

    with ui.row().classes('w-full h-screen no-wrap gap-0 bg-[#09090b]'):
        
        with ui.column().classes('w-64 h-full border-r border-zinc-800 bg-[#0c0c0e] flex-none flex flex-col p-4 gap-4'):
            
            with ui.row().classes('items-center gap-3 px-2 mb-2'):
                with ui.element('div').classes('bg-indigo-600 rounded-lg p-1.5 shadow-lg shadow-indigo-500/20'):
                    ui.icon('castle', color='white', size='sm')
                ui.label('TREBUCHET').classes('font-bold text-lg tracking-tight text-white')
            
            ui.button('Novo Chat', icon='add', on_click=start_new_chat).classes('w-full bg-white text-black hover:bg-zinc-200 transition-colors shadow-sm').props('unelevated no-caps')

            with ui.column().classes('gap-1 w-full'):
                ui.label('MENU PRINCIPAL').classes('text-[10px] font-bold text-zinc-500 px-2 mt-2 tracking-wider')
                
                def nav_btn(label, icon, active=False):
                    classes = 'sidebar-item sidebar-item-active' if active else 'sidebar-item'
                    with ui.row().classes(f'w-full items-center gap-3 px-3 py-2 cursor-pointer {classes}'):
                        ui.icon(icon, size='xs')
                        ui.label(label).classes('text-sm font-medium')
                
                nav_btn('Playground', 'terminal', True)
                nav_btn('Meus Agentes', 'groups')
                nav_btn('Memória', 'folder_open')
                nav_btn('Automação', 'auto_fix_high')
                nav_btn('Configurações', 'settings')

            with ui.column().classes('flex-grow overflow-hidden w-full gap-1'):
                ui.label('CONVERSAS').classes('text-[10px] font-bold text-zinc-500 px-2 mt-4 tracking-wider')
                
                history_list_scroll = ui.scroll_area().classes('w-full flex-grow custom-scroll pr-2')
                with history_list_scroll:
                    history_list_container = ui.column().classes('w-full gap-1')

                def refresh_history_sidebar():
                    history_list_container.clear()
                    try:
                        files = sorted(HISTORY_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
                        
                        with history_list_container:
                            if not files:
                                ui.label('Nenhum histórico').classes('text-xs text-zinc-600 px-3 italic')
                                return

                            for file in files:
                                try:
                                    with open(file, 'r', encoding='utf-8') as f:
                                        data = json.load(f)
                                        c_id = data.get("id", file.stem)
                                        title = data.get("title", "Sem título")
                                    
                                    with ui.row().classes('w-full items-center gap-2 px-3 py-2 cursor-pointer hover:bg-zinc-800/50 rounded group transition-colors'):
                                        btn = ui.label(title).classes('text-xs text-zinc-400 group-hover:text-zinc-200 truncate flex-grow cursor-pointer')
                                        btn.on('click', lambda id=c_id: load_chat(id))
                                        
                                        def delete_chat(p=file):
                                            p.unlink()
                                            refresh_history_sidebar()
                                            
                                        ui.button(icon='close', on_click=delete_chat).props('flat dense size=xs color=zinc-700').classes('opacity-0 group-hover:opacity-100')
                                except: continue
                    except Exception as e:
                        ui.notify(f"Erro ao atualizar lista: {e}")

                ui.timer(0.1, refresh_history_sidebar, once=True)

            with ui.row().classes('w-full border-t border-zinc-800 pt-4 items-center gap-3 cursor-pointer hover:bg-zinc-800/30 p-2 rounded transition-colors'):
                ui.avatar('https://robohash.org/admin', size='sm').classes('bg-zinc-700 ring-2 ring-zinc-800')
                with ui.column().classes('gap-0'):
                    ui.label('Admin User').classes('text-sm font-medium text-white')
                    ui.label('Pro Plan').classes('text-[10px] text-zinc-500')
                ui.space()
                ui.icon('more_vert', size='xs', color='zinc-500')

        with ui.column().classes('flex-grow h-full relative bg-[#09090b] flex flex-col min-w-0'):
            
            with ui.row().classes('w-full h-14 border-b border-zinc-800 bg-[#09090b]/80 backdrop-blur items-center px-6 justify-between z-10 shrink-0'):
                with ui.row().classes('items-center gap-4'):
                    ui.label('Trebuchet').classes('font-semibold text-zinc-200 tracking-tight')
                    ui.badge('v4.0', color='zinc-800', text_color='zinc-400').props('rounded outline dense')
                
                with ui.row().classes('items-center gap-2'):
                    ui.button(icon='share').props('flat round size=sm color=zinc-400')
                    ui.button(icon='star_border').props('flat round size=sm color=zinc-400')
                    ui.separator().props('vertical spaced').classes('bg-zinc-700')
                    status_badge = ui.badge('IDLE', color='zinc-800', text_color='zinc-500').props('rounded')

            chat_scroll = ui.scroll_area().classes('w-full flex-grow p-6 md:p-12 pb-40 custom-scroll')
            with chat_scroll:
                with ui.column().classes('w-full max-w-3xl mx-auto gap-8'):
                    with ui.column().classes('w-full items-center justify-center py-10 gap-4 opacity-50'):
                        with ui.element('div').classes('p-4 bg-zinc-900 rounded-full'):
                            ui.icon('castle', size='3rem', color='zinc-600')
                        ui.label('Como posso ajudar hoje?').classes('text-zinc-500 font-medium')
                    
                    messages_container = ui.column().classes('w-full gap-6')

            with ui.column().classes('absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-[#09090b] via-[#09090b] to-transparent pointer-events-none z-20'):
                with ui.column().classes('w-full max-w-3xl mx-auto bg-[#18181b] border border-zinc-700 rounded-xl shadow-2xl overflow-hidden ring-1 ring-white/5 pointer-events-auto'):
                   
                    with ui.row().classes('w-full px-4 pt-2 gap-2 min-h-[0px]') as attachments_container:
                        pass
                    
                    input_text = ui.textarea(placeholder='Peça ao Trebuchet').props('borderless autogrow bg-transparent dark input-style="min-height: 48px; max-height: 200px;"').classes('w-full px-4 py-2 text-base text-zinc-100 placeholder-zinc-500').on('keydown.enter.prevent', lambda: run_chat())
                    
                    with ui.row().classes('w-full bg-[#18181b] border-t border-zinc-700/50 p-2 items-center justify-between'):
                        
                        with ui.row().classes('gap-1'):
                            ui.button(icon='add_circle').props('flat round size=sm color=zinc-400').tooltip('Adicionar Arquivo')
                            btn_mic = ui.button(icon='mic').props('flat round size=sm color=zinc-400').on('click', lambda: handle_mic())
                            
                        
                        with ui.row().classes('items-center gap-3'):
                            ui.label(f'{session["config"]["model"]}').classes('text-[10px] text-zinc-500 font-mono px-2 bg-zinc-900 rounded py-1')
                            btn_send = ui.button(icon='arrow_upward', on_click=lambda: run_chat()).props('unelevated round color=indigo-600 size=md shadow-lg shadow-indigo-500/20')

                ui.label('Trebuchet pode cometer erros. Verifique informações críticas.').classes('text-[10px] text-zinc-600 w-full text-center mt-2 font-mono')

        with ui.column().classes('w-96 h-full border-l border-zinc-800 bg-[#0c0c0e] flex-none flex flex-col'):
            
            with ui.row().classes('w-full h-12 border-b border-zinc-800 items-center px-4 gap-4 shrink-0'):
                ui.label('PAINEL DE CONTROLE').classes('text-xs font-bold text-zinc-400 tracking-wider')
                ui.space()
                ui.button(icon='dock', on_click=lambda: ui.notify('Dock layout')).props('flat round size=sm color=zinc-500')

            with ui.scroll_area().classes('flex-grow w-full p-4 gap-6 custom-scroll'):

                with ui.column().classes('w-full gap-3 mb-4'):
                    ui.label('FERRAMENTAS').classes('text-[10px] font-bold text-zinc-500 tracking-widest')
                    
                    with ui.column().classes('w-full bg-zinc-900/50 border border-zinc-800 rounded p-4 gap-4'):
                        for name, tool in tool_registry.tools.items():
                            if name not in session["config"]["tools"]:
                                session["config"]["tools"][name] = {"enabled": True, "settings": {}}
                            
                            tool_conf = session["config"]["tools"][name]
                            
                            with ui.row().classes('w-full justify-between items-center'):
                                with ui.row().classes('gap-2 items-center'):
                                    icon = getattr(tool, 'icon', 'extension') 
                                    ui.icon(icon, size='xs', color='zinc-400')
                                    ui.label(name.replace('_', ' ').title()).classes('text-xs text-zinc-300')
                                
                                with ui.row().classes('gap-1 items-center'):
                                    has_config = bool(getattr(tool, 'config_schema', {}).get('properties'))
                                    
                                    if has_config:
                                        ui.button(icon='settings', on_click=lambda n=name, t=tool: open_tool_settings(n, t)).props('flat dense size=xs color=zinc-600').tooltip('Configurações')
                                    
                                    ui.switch().bind_value(tool_conf, 'enabled').props('dense color=indigo size=xs')
                ui.separator().classes('bg-zinc-800')       

                with ui.column().classes('w-full h-1/3 flex-none flex flex-col bg-[#050505]/40 p-4'):
                    with ui.row().classes('w-full items-center justify-between mb-2'):
                        ui.label('LOGS DO SISTEMA').classes('text-[10px] font-bold text-zinc-500 tracking-widest')
                        with ui.row().classes('gap-1'):
                            ui.button(icon='download').props('flat round size=xs color=zinc-600')
                            ui.button(icon='delete_sweep', on_click=lambda: log_container.clear()).props('flat round size=xs color=zinc-600')
                    
                    log_scroll = ui.scroll_area().classes('w-full flex-grow bg-black/20 border border-zinc-800/50 rounded p-2 custom-scroll')
                    with log_scroll:
                        log_container = ui.column().classes('w-full gap-0.5')

    bridge_input = ui.input().props('id=data-bridge').classes('hidden').on('update:model-value', handle_bridge)

    async def handle_mic():
        status = await ui.run_javascript('return toggleRecording()', timeout=15.0)
        if status == "started":
            btn_mic.props('color=red icon=mic_off')
            ui.notify('Gravando áudio...', position='bottom', color='negative', icon='mic')
        else:
            btn_mic.props('color=zinc-400 icon=mic')

    def render_message(role, content):
        with messages_container:
            align = 'end' if role == 'user' else 'start'
            bg_class = 'msg-bubble-user' if role == 'user' else 'msg-bubble-bot'
            
            with ui.row().classes(f'w-full justify-{align} mb-4 animate-fade'):
                if role == 'assistant':
                    with ui.avatar('https://robohash.org/trebuchet?set=set4', size='md').classes('mt-1 mr-3 shadow-md border border-zinc-700'): pass
                
                with ui.column().classes(f'items-{align} max-w-3xl'):
                    if role == 'assistant':
                        ui.label('Trebuchet').classes('text-xs font-bold text-zinc-400 mb-1 ml-1')
                    
                    with ui.column().classes(f'{bg_class} p-4 shadow-lg {"bg-[#1e1e20]" if role=="assistant" else ""}'):
                        ui.markdown(content).classes('text-sm prose prose-invert')

    async def run_chat():
        await asyncio.sleep(0.1) 
        
        text = input_text.value.strip()
        if session["running"] or (not text and not session["attachments"]): return
        
        input_text.value = ''
        session["running"] = True
        input_text.disable()
        btn_send.disable()
        status_badge.props('color=amber-900 text_color=amber-500').set_text('TRABALHANDO')
        
        display_text = text if text else "*(Arquivo Anexado)*"
        agent_context = text
        files_display_names = [Path(p).name for p in session["attachments"]]
        if session["attachments"]:
            agent_context += "\n[FILES]:\n" + "\n".join(session["attachments"])
        
        with messages_container:
            with ui.row().classes('w-full justify-end mb-4 animate-fade'):
                with ui.column().classes('items-end'):
                    with ui.column().classes('msg-bubble-user p-4 max-w-2xl shadow-lg'):
                        ui.markdown(display_text).classes('text-sm prose prose-invert')
                    
                    if files_display_names:
                        with ui.row().classes('gap-2 mt-2 mr-1'):
                            for name in files_display_names:
                                ui.chip(name, icon='file_present').props('dense outline square color=zinc-600').classes('text-xs text-zinc-400')

        with messages_container:
            with ui.row().classes('w-full justify-start mb-8 animate-fade'):
                with ui.avatar('https://robohash.org/trebuchet?set=set4', size='md').classes('mt-1 mr-3 shadow-md border border-zinc-700'): pass
                
                with ui.column().classes('max-w-3xl w-full'):
                    ui.label('Trebuchet').classes('text-xs font-bold text-zinc-400 mb-1 ml-1')
                    
                    thought_expander = ui.expansion('Processo de Pensamento', icon='psychology').classes('w-full bg-zinc-900/30 border border-zinc-800 rounded-lg mb-3 text-zinc-500 text-xs').props('dense header-class="text-zinc-500 hover:text-zinc-300 transition-colors"')
                    with thought_expander:
                        thought_display = ui.markdown().classes('p-2 text-xs text-zinc-400')

                    response_card = ui.column().classes('msg-bubble-bot p-6 w-full bg-[#1e1e20] shadow-sm')
                    with response_card:
                        spinner = ui.spinner('dots', size='2rem', color='indigo-500')
                        response_text = ui.markdown().classes('prose prose-invert max-w-none text-sm leading-relaxed text-zinc-300')

        chat_scroll.scroll_to(percent=1.0)
        
        try:
            from agents.workflow import TrebuchetOrchestrator
            
            orch = TrebuchetOrchestrator()
            workflow = orch.build()
            agent_indicators = {}
            initial_state = {
                "objective": agent_context,
                "status": "architecting",
                "chat_history": session["history"],
                "completed_log": [],
                "current_mode": "task",
                "agent_config": session["config"]
            }

            system_log(f"Workflow iniciado: {session['config']['model']}", "info")
            
            final_answer = ""
            
            async for event in workflow.astream(initial_state):
                try:
                    await asyncio.sleep(0.001)
                    
                    for node, updates in event.items():
                        
                        system_log(f"Nó Ativo: {node.upper()}", "info")
                        
                        if "completed_log" in updates and updates["completed_log"]:
                            log_msg = updates["completed_log"][-1]
                            if "RESPOSTA:" in log_msg:
                                response_text.content = log_msg.split("RESPOSTA:")[1].strip()
                        
                        if "current_thought" in updates:
                            system_log(f"Thought: {updates['current_thought'][:50]}...", "warning")

                        for key, els in agent_indicators.items():
                            els['dot'].classes('bg-zinc-600 shadow-zinc-600', remove='bg-emerald-500 shadow-emerald-500 bg-amber-500 shadow-amber-500 animate-pulse')
                            els['spinner'].set_visibility(False)

                        active_key = None
                        if node in ['architect', 'planner']: active_key = 'thinking'
                        elif node in ['tools', 'coder', 'action']: active_key = 'executing'
                        elif node in ['reviewer', 'critic']: active_key = 'analyzing'
                        
                        if active_key and active_key in agent_indicators:
                            els = agent_indicators[active_key]
                            els['dot'].classes('bg-emerald-500 shadow-emerald-500 animate-pulse', remove='bg-zinc-600 shadow-zinc-600')
                            els['spinner'].set_visibility(True)

                        if "current_thought" in updates:
                            thought = updates["current_thought"]
                            if 'spinner' in locals(): 
                                spinner.set_visibility(False)

                            thought_display.content = f"**[{node.upper()}]**: {thought}"
                            thought_expander.value = True
                            
                        if "final_response" in updates:
                            if 'spinner' in locals(): 
                                try: spinner.set_visibility(False)
                                except: pass
                                
                            final_answer = updates["final_response"]
                            response_text.content = final_answer 
                            
                            chat_scroll.scroll_to(percent=1.0)

                except RuntimeError:
                    return

            if final_answer:
                session["history"].append({"role": "user", "content": text})
                session["history"].append({"role": "assistant", "content": final_answer})
                save_current_chat()
                system_log("Resposta gerada com sucesso.", "success")

        except RuntimeError:
            pass
        except Exception as e:
            try:
                ui.notify(f"Erro de Execução: {str(e)}", type='negative', position='top')
                with log_container:
                    ui.label(f"CRITICAL ERROR: {str(e)}").classes('text-red-500 font-bold log-font border-l-2 border-red-500 pl-2 my-2')
            except: pass
            
            if 'spinner' in locals(): 
                try: spinner.set_visibility(False)
                except: pass
        
        finally:
            session["running"] = False
            session["attachments"] = []
            
            try:
                status_badge.props('color=emerald-900 text_color=emerald-400').set_text('IDLE')
                attachments_container.clear()
                input_text.enable()
                btn_send.enable()
                input_text.run_method('focus')
            except:
                pass
                
    def system_log(message, type='info'):
        if not log_container.client.connected: return
        
        ts = time.strftime("%H:%M:%S")
        color_map = {
            'error': 'text-red-400 border-red-900/30',
            'success': 'text-emerald-400 border-emerald-900/30',
            'warning': 'text-amber-400 border-amber-900/30',
            'info': 'text-zinc-400 border-zinc-900/50'
        }
        color_class = color_map.get(type, color_map['info'])
        
        with log_container:
            ui.label(f"[{ts}] {str(message)}").classes(f'{color_class} log-font break-all border-b py-0.5')
        
        log_scroll.scroll_to(percent=1.0)
    def process_sys_queue():
        try:
            while not sys_log_queue.empty():
                msg, ltype = sys_log_queue.get_nowait()
                system_log(msg, type=ltype)
        except Exception:
            pass
    ui.timer(0.2, process_sys_queue)
            
            
def run_ui():
    ui.run(title='Trebuchet', dark=True, show=True, port=8080, favicon='', reload=True)

if __name__ in {"__main__", "__mp_main__"}:
    run_ui()