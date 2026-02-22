import json
import re
import datetime
import asyncio
from typing import Dict
from core.llm import LLMEngine
from memory.manager import MemoryManager
from tools.registry import ToolRegistry
from agents.state import AgentState

class TrebuchetNodes:
    def __init__(self):
        self.llm = LLMEngine() 
        self.memory = MemoryManager.get_instance()
        self.tools = ToolRegistry()

    async def pure_chat(self, state: AgentState) -> Dict:
        objective = state.get("objective")
        chat_history = state.get("chat_history", [])
        memory_context = self.memory.retrieve(objective, k=5)
        
        formatted_history = []
        for msg in chat_history[-10:]:
            formatted_history.append({"role": msg["role"], "content": msg["content"]})
        
        sys_prompt = f"""Você é o TREBUCHET v4.0. 
        Use o contexto abaixo se for relevante para a pergunta.
        CONTEXTO DE MEMÓRIA:
        {memory_context}
        """
        
        messages = [{"role": "system", "content": sys_prompt}] + formatted_history + [{"role": "user", "content": objective}]
        
        response = await self.llm.chat(messages=messages, temperature=0.7)
        
        return {
            "status": "finished",
            "final_response": response,
            "completed_log": [f"CHAT_RESPONSE: {response[:100]}..."]
        }
    
    async def orchestrator(self, state: AgentState) -> Dict:
        objective = state.get("objective")
        chat_history = state.get("chat_history", [])
        internal_log = state.get("completed_log", [])
        agent_config = state.get("agent_config", {}).get("tools", {})
        
        memory_context = self.memory.retrieve(objective, k=3)
        
        history_str = ""
        for msg in chat_history[-6:]:
            history_str += f"{msg['role'].upper()}: {msg['content']}\n"
        
        log_str = "\n".join(internal_log[-5:]) if internal_log else "Nenhuma ação tomada ainda."
        tools_list = self.tools.get_prompt_list(active_tools=agent_config)
        
        prompt = f"""
        OBJETIVO ATUAL: "{objective}"
        
        CONTEXTO RECUPERADO (RAG):
        {memory_context}
        
        HISTÓRICO DA CONVERSA:
        {history_str}
        
        LOG DE EXECUÇÃO ATUAL:
        {log_str}

        FERRAMENTAS: 
        {tools_list}
        
        RESPONDA APENAS JSON:
        {{
            "thought": "raciocínio",
            "tool_name": "tool ou 'finish' ou 'answer_user'",
            "args": {{ "arg": "val" }}
        }}
        """

        response = await self.llm.chat(messages=[{"role": "user", "content": prompt}], temperature=0.1)
        
    async def classifier(self, state: AgentState) -> Dict:
        last_msg = state.get("objective", "")
        prompt = f"Analise a intenção: '{last_msg}'. Responda em JSON: {{\"thought\": \"sua análise\", \"mode\": \"chat\" ou \"task\"}}"
        
        response = await self.llm.chat(messages=[{"role": "user", "content": prompt}], temperature=0.0)
        try:
            data = json.loads(re.search(r'\{.*\}', response, re.DOTALL).group(0))
            return {
                "current_mode": data.get("mode", "task"),
                "current_thought": data.get("thought", "Classificando intenção...")
            }
        except:
            return {"current_mode": "task", "current_thought": "Analisando complexidade da tarefa..."}
    
    async def tool_executor(self, state: AgentState) -> Dict:
        action = state.get("next_action", {})
        tool_name = action.get("tool_name")
        args = action.get("args", {})

        if tool_name in ["finish", "answer_user"]:
            return {"status": "finished", "final_response": args.get("message", "Tarefa concluída.")}

        result = self.tools.execute(tool_name, args)
        output = str(result.get("output", ""))[:500]
        
        return {
            "completed_log": [f"AÇÃO: {tool_name} | Saída: {output}"],
            "last_tool_output": output,
            "next_action": None
        }

    async def unified_agent(self, state: AgentState) -> Dict:
        print("\n[AGENTE] Raciocinando...")
        
        objective = state.get("objective")
        history = state.get("completed_log", [])
        agent_config = state.get("agent_config", {}).get("tools", {})
        history_str = "\n".join(history[-8:]) if history else "Início da tarefa."
        tools_list = self.tools.get_prompt_list(active_tools=agent_config)
        
        prompt = f"""
        OBJETIVO: "{objective}"
        HISTÓRICO RECENTE:
        {history_str}

        FERRAMENTAS DISPONÍVEIS: 
        {tools_list}
        
        RESPONDA ESTRITAMENTE EM JSON neste formato:
        {{
            "thought": "Seu raciocínio passo a passo aqui",
            "tool_name": "nome_da_tool",
            "args": {{ "arg1": "valor" }}
        }}
        
        Para finalizar, use tool_name: "finish".
        Para responder ao usuário sem finalizar, use tool_name: "answer_user".
        """

        response = await self.llm.chat(messages=[{"role": "user", "content": prompt}], temperature=0.1)

        try:
            tool_specific_config = agent_config.get(tool_name, {}).get("settings", {})
            result = self.tools.execute(tool_name, args, tool_config=tool_specific_config)
            clean_res = response.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', clean_res, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
            else:
                raise ValueError("JSON não encontrado")
        except Exception:

            data = {
                "thought": "Erro no formato JSON, tentando recuperar...", 
                "tool_name": "answer_user", 
                "args": {"message": response}
            }
            
        thought = data.get("thought", "Processando...")
        tool_name = data.get("tool_name")
        args = data.get("args", {})

        if tool_name in ["finish", "task_complete"]:
            return {
                "status": "finished",
                "final_response": thought,
                "completed_log": [f"FINALIZADO: {thought}"],
                "current_thought": thought
            }

        if tool_name == "answer_user":
            msg = args.get("message", thought)
            return {
                "completed_log": [f"RESPOSTA: {msg}"],
                "current_thought": thought,
                "status": "building"
            }


        try:

            result = self.tools.execute(tool_name, args)
            output = str(result.get("output", ""))[:500]
            success = result.get("success", False)
            
            log_entry = f"AÇÃO: {tool_name} | STATUS: {'✅' if success else '❌'}\n   Saída: {output}"
            
            return {
                "completed_log": [log_entry],
                "status": "building",
                "last_tool_output": output,
                "current_thought": thought,
                "current_micro_task": f"Analisar resultado de {tool_name}"
            }

        except Exception as e:
            return {
                "completed_log": [f"ERRO SYSTEMA: {str(e)}"],
                "status": "error_recovery",
                "last_error": str(e)
            }