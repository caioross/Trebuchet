import os
import time
import pyautogui
import datetime
from core.config import Config
from tools.base import BaseTool, ToolResult


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

class DesktopTool(BaseTool):
    name = "desktop"
    description = "Automação Desktop completa. Permite ver a tela, mover mouse, clicar e digitar."
    

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["screenshot", "write", "move_click", "scroll", "hotkey", "locate_image", "screen_info"],
                "description": "Ação a realizar."
            },
            "text": {
                "type": "string",
                "description": "Texto para digitar ou teclas para hotkey (ex: 'ctrl,c')."
            },
            "x": {
                "type": "integer",
                "description": "Coordenada X"
            },
            "y": {
                "type": "integer",
                "description": "Coordenada Y"
            },
            "amount": {
                "type": "integer",
                "description": "Quantidade de scroll/rolagem"
            },
            "image_path": {
                "type": "string",
                "description": "Nome da imagem (na pasta temp) para procurar na tela."
            }
        },
        "required": ["action"]
    }


    config_schema = {
        "type": "object",
        "properties": {
            "dry_run": {
                "type": "boolean",
                "description": "Modo Simulação (Não executa ações físicas)",
                "default": False
            },
            "typing_speed": {
                "type": "number",
                "description": "Intervalo entre teclas (segundos)",
                "default": 0.05,
                "minimum": 0.0,
                "maximum": 1.0
            },
            "mouse_duration": {
                "type": "number",
                "description": "Duração do movimento do mouse (0=instantâneo)",
                "default": 0.5,
                "minimum": 0.0,
                "maximum": 3.0
            },
            "failsafe": {
                "type": "boolean",
                "description": "Fail-Safe (Mover mouse p/ canto aborta)",
                "default": True
            }
        }
    }

    def run(self, action: str, text: str = None, x: int = None, y: int = None, amount: int = None, image_path: str = None, config: dict = None, **kwargs) -> ToolResult:

        defaults = {
            "dry_run": False,
            "typing_speed": 0.05,
            "mouse_duration": 0.5,
            "failsafe": True
        }
        cfg = defaults.copy()
        if config:
            cfg.update(config)

        pyautogui.FAILSAFE = cfg["failsafe"]
        

        if cfg["dry_run"] and action != "screen_info":
            return {
                "success": True,
                "output": f"[DRY_RUN] Ação '{action}' simulada com sucesso. (Nenhuma interação real ocorreu). Params: {locals()}",
                "metadata": {"dry_run": True}
            }

        try:

            if action == "screen_info":
                w, h = pyautogui.size()
                return {
                    "success": True,
                    "output": f"Resolução da Tela: {w}x{h}",
                    "metadata": {"width": w, "height": h}
                }

            elif action == "screenshot":
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
                save_path = os.path.join(Config.DIRS["sandbox"], filename)
                
                screenshot = pyautogui.screenshot()
                screenshot.save(save_path)
                
                return {
                    "success": True, 
                    "output": f"Screenshot salvo em: {filename}", 
                    "metadata": {"file_path": save_path}
                }

            elif action == "write":
                if not text:
                    return {"success": False, "output": "Erro: Parâmetro 'text' obrigatório para escrita.", "metadata": {}}
                
                pyautogui.write(text, interval=float(cfg["typing_speed"]))
                return {"success": True, "output": f"Digitado: '{text}'", "metadata": {}}

            elif action == "move_click":
                if x is None or y is None:

                    pyautogui.click()
                    return {"success": True, "output": "Clique realizado na posição atual.", "metadata": {}}
                
                screen_w, screen_h = pyautogui.size()
                if x > screen_w or y > screen_h:
                    return {"success": False, "output": f"Erro: Coordenadas ({x},{y}) fora da tela ({screen_w}x{screen_h}).", "metadata": {}}

                pyautogui.moveTo(x, y, duration=float(cfg["mouse_duration"]))
                pyautogui.click()
                return {"success": True, "output": f"Mouse movido e clicado em ({x}, {y})", "metadata": {"x": x, "y": y}}

            elif action == "scroll":
                if not amount:
                    return {"success": False, "output": "Erro: 'amount' necessário para scroll.", "metadata": {}}
                pyautogui.scroll(amount)
                return {"success": True, "output": f"Scroll realizado: {amount}", "metadata": {}}

            elif action == "hotkey":
                if not text:
                    return {"success": False, "output": "Erro: 'text' necessário para hotkey (ex: 'ctrl,v').", "metadata": {}}
                keys = [k.strip() for k in text.split(',')]
                pyautogui.hotkey(*keys)
                return {"success": True, "output": f"Atalho pressionado: {keys}", "metadata": {}}

            elif action == "locate_image":
                if not image_path:
                    return {"success": False, "output": "Erro: 'image_path' necessário.", "metadata": {}}
                
                full_path = os.path.join(Config.DIRS["sandbox"], image_path)
                if not os.path.exists(full_path):
                    return {"success": False, "output": f"Arquivo não encontrado: {image_path}", "metadata": {}}

                try:
                    location = pyautogui.locateOnScreen(full_path, confidence=0.8)
                    if location:
                        center = pyautogui.center(location)
                        return {
                            "success": True, 
                            "output": f"Imagem encontrada. Centro: ({center.x}, {center.y})", 
                            "metadata": {"found": True, "x": center.x, "y": center.y}
                        }
                    else:
                        return {"success": False, "output": "Imagem não encontrada na tela.", "metadata": {"found": False}}
                except Exception as e:

                    try:
                        location = pyautogui.locateOnScreen(full_path)
                        if location:
                            center = pyautogui.center(location)
                            return {"success": True, "output": f"Encontrado: {center}", "metadata": {"found": True}}
                    except:
                        pass
                    return {"success": False, "output": f"Erro na busca visual: {str(e)}", "metadata": {"error": True}}

            else:
                return {"success": False, "output": f"Ação desconhecida: {action}", "metadata": {}}

        except pyautogui.FailSafeException:
            return {
                "success": False, 
                "output": "Ação Abortada: Fail-Safe ativado (mouse no canto da tela).", 
                "metadata": {"failsafe_triggered": True}
            }
        except Exception as e:
            return {
                "success": False, 
                "output": f"Erro de execução Desktop: {str(e)}", 
                "metadata": {"error": str(e)}
            }