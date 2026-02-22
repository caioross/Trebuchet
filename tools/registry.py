import importlib
import importlib.util
import inspect
import os
import sys
import json
from typing import Dict, Any, List
from core.config import Config
from tools.base import BaseTool
import tools.libs

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._register_builtins()
        self._load_plugins()

    def _register_builtins(self):
        libs_path = os.path.dirname(tools.libs.__file__)
        print(f"🔧 [TOOLS] Escaneando builtins em: {libs_path}")

        for filename in os.listdir(libs_path):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = f"tools.libs.{filename[:-3]}"
                
                try:
                    module = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                            if obj.__module__ == module_name:
                                try:
                                    instance = obj()
                                    self.tools[instance.name] = instance
                                    print(f"   -> Builtin Carregado: {instance.name} ({filename})")
                                except Exception as e:
                                    print(f" -> Erro ao instanciar {name} em {filename}: {str(e)}")
                except Exception as e:
                    print(f"[TOOLS] Falha ao carregar builtin {filename}: {str(e)}")

    def _load_plugins(self):
        plugin_dir = Config.DIRS["tools_plugins"]
        if not os.path.exists(plugin_dir):
            return

        print(f"[TOOLS] Escaneando plugins em: {plugin_dir}")
        
        for filename in os.listdir(plugin_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                filepath = os.path.join(plugin_dir, filename)
                module_name = f"plugin_{filename[:-3]}"
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, filepath)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module 
                        spec.loader.exec_module(module)
                        
                        loaded_count = 0
                        for name, obj in inspect.getmembers(module):
                            if inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                                try:
                                    instance = obj()

                                    self.tools[instance.name] = instance
                                    print(f"   -> Plugin Ativado: {instance.name} ({filename})")
                                    loaded_count += 1
                                except Exception as e:
                                    print(f"   -> Erro ao instanciar {name} em {filename}: {str(e)}")
                        
                        if loaded_count == 0:
                            print(f"   -> Nenhum Tool válido encontrado em {filename}")

                except Exception as e:
                    print(f"[TOOLS] Falha ao carregar plugin {filename}: {str(e)}")

    def get_prompt_list(self, active_tools=None) -> str:
        prompt = "FERRAMENTAS DISPONÍVEIS:\n"
        for name, tool in self.tools.items():
            if active_tools and name not in active_tools:
                continue
            prompt += f"- {name}: {tool.description} (Args: {tool.parameters})\n"
        return prompt

    def _validate_args(self, tool: BaseTool, args: Dict[str, Any]) -> List[str]:
        errors = []
        schema = tool.parameters
        props = schema.get("properties", {})
        required = schema.get("required", [])

        for req in required:
            if req not in args:
                errors.append(f"Missing required argument: '{req}'")

        for key, value in args.items():
            if key not in props:
                continue

            prop_def = props[key]
            expected_type = prop_def.get("type")
            enum_vals = prop_def.get("enum")

            if enum_vals and value not in enum_vals:
                errors.append(f"Argument '{key}' must be one of {enum_vals}, got '{value}'")
                continue

            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Argument '{key}' must be a string, got {type(value).__name__}")
            elif expected_type == "integer" and not isinstance(value, int):
                try:
                    args[key] = int(value)
                except:
                    errors.append(f"Argument '{key}' must be an integer, got {type(value).__name__}")
            elif expected_type == "boolean" and not isinstance(value, bool):
                 if str(value).lower() in ['true', 'false']:
                     args[key] = str(value).lower() == 'true'
                 else:
                    errors.append(f"Argument '{key}' must be a boolean")

        return errors

    def execute(self, tool_name: str, args: Dict) -> Dict:
        if tool_name not in self.tools:
            return {"success": False, "output": f"ERRO: Ferramenta '{tool_name}' não existe. Escolha uma da lista.", "metadata": {"error": True}}
        
        tool = self.tools[tool_name]
        
        validation_errors = self._validate_args(tool, args)
        if validation_errors:
            error_msg = f"ERRO DE ARGUMENTO em '{tool_name}': {'; '.join(validation_errors)}. Corrija os parâmetros no próximo pensamento."
            return {"success": False, "output": error_msg, "metadata": {"error": True, "validation_failed": True}}

        try:
            result = tool.run(**args)
            if not isinstance(result, dict) or "output" not in result:
                return {"success": False, "output": "Erro interno: Resposta da ferramenta em formato inválido.", "metadata": {}}
            return result
        except Exception as e:
            return {"success": False, "output": f"ERRO DE EXECUÇÃO em '{tool_name}': {str(e)}", "metadata": {"error": True}}