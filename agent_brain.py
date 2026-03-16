import os
import json
import uuid
import logging
import hashlib
from typing import List, Dict, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI
from database import SessionLocal, get_chat_history, save_message, get_setting, get_all_memory, save_memory, search_memory, save_token_usage
from exec_tools import execute_tool

logging.basicConfig(level=logging.INFO, format='%(asctime)s [FoxxGent] %(levelname)s: %(message)s')
logger = logging.getLogger("foxxgent")

load_dotenv()


def load_user_memory(user_id: str) -> str:
    """Load relevant memories for context"""
    db = SessionLocal()
    try:
        memories = get_all_memory(db, user_id)
        if not memories:
            return ""
        
        mem_text = "Important context about you:\n"
        for mem in memories[:10]:
            mem_text += f"- {mem.key}: {mem.value}\n"
        return mem_text
    finally:
        db.close()


def auto_save_memory(user_id: str, key: str, value: str, memory_type: str = "fact", importance: int = 1):
    """Automatically save important information to memory"""
    db = SessionLocal()
    try:
        save_memory(db, memory_type, key, value, user_id, importance)
        logger.info(f"Saved to memory: {key}")
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")
    finally:
        db.close()


def get_vibe_aware_prompt(user_id: str) -> str:
    hour = datetime.now().hour
    
    length_mod = "concise" if hour >= 22 or hour < 7 else "normal"
    tone_mod = "casual" if hour >= 22 or hour < 7 else "neutral"
    
    try:
        db = SessionLocal()
        try:
            from database import get_vibe_for_time
            vibe = get_vibe_for_time(db, user_id, hour)
            length_mod = vibe.get("length", length_mod)
            tone_mod = vibe.get("tone", tone_mod)
        finally:
            db.close()
    except:
        pass
    
    length_instruction = {
        "concise": "Keep responses very brief - 1-3 sentences max. No elaboration.",
        "normal": "Provide normal-length responses with reasonable detail.",
        "detailed": "Provide comprehensive, detailed responses with full explanations."
    }.get(length_mod, "")
    
    tone_instruction = {
        "formal": "Use formal, professional language.",
        "casual": "Use casual, friendly language with emojis where appropriate.",
        "neutral": "Use neutral, balanced tone."
    }.get(tone_mod, "")
    
    base_prompt = REASONING_SYSTEM_PROMPT
    if length_instruction or tone_instruction:
        base_prompt += f"\n\n## VIBE-AWARENESS RULES:\n{length_instruction}\n{tone_mod}"
    
    return base_prompt


def search_cross_platform(query: str, platforms: list = None) -> Dict[str, Any]:
    try:
        db = SessionLocal()
        try:
            from database import search_platform_data, save_cross_ref
            
            if not platforms:
                # Check for connected apps and use their data
                from connection_manager import connection_manager
                connected = connection_manager.get_connected_apps()
                platforms = connected if connected else ["gmail", "calendar", "notion", "telegram"]
            
            query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
            
            from database import get_cross_ref
            cached = get_cross_ref(db, query_hash)
            if cached and (datetime.utcnow() - cached.created_at).seconds < 3600:
                return json.loads(cached.result_data)
            
            results = search_platform_data(db, query, platforms)
            data = [{"platform": r.platform, "title": r.title, "content": r.content[:200]} for r in results[:10]]
            
            result_data = json.dumps({"results": data, "count": len(data)})
            save_cross_ref(db, query_hash, "search", "cross_platform", result_data)
            
            return {"status": "success", "data": data}
        finally:
            db.close()
    except Exception as e:
        return {"status": "error", "output": str(e)}


def get_connection_based_tools(user_input: str) -> List[str]:
    from connection_manager import connection_manager
    connected = connection_manager.get_connected_apps()
    tools = []
    
    for app_id in connected:
        conn = connection_manager.get_connection(app_id)
        if conn and conn.get("config"):
            for cap in conn["config"].capabilities:
                tools.append(f"{app_id}_{cap}")
    
    return tools


def prune_context_history(user_id: str, max_messages: int = 20) -> Dict[str, Any]:
    """automatically summarize old history when nearing token limits to keep context lean."""
    db = SessionLocal()
    try:
        from database import ChatMessage
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.user_id == user_id
        ).order_by(ChatMessage.timestamp.desc()).all()
        
        if len(messages) <= max_messages:
            return {"status": "success", "output": "no pruning needed", "message_count": len(messages)}
        
        keep_count = max_messages // 2
        old_messages = messages[keep_count:]
        
        summary = f"[summarized {len(old_messages)} older messages]"
        summary_msg = ChatMessage(
            user_id=user_id,
            role="system",
            content=summary,
            timestamp=datetime.utcnow()
        )
        
        for msg in old_messages:
            db.delete(msg)
        
        db.add(summary_msg)
        db.commit()
        
        return {"status": "success", "output": f"pruned {len(old_messages)} messages, kept {keep_count}", "message_count": keep_count}
    finally:
        db.close()


def get_or_create_session(user_id: str) -> str:
    """get or create a session id for the user."""
    db = SessionLocal()
    try:
        from database import get_setting, save_setting
        
        session_id = get_setting(db, f"session_{user_id}")
        if not session_id:
            session_id = str(uuid.uuid4())
            save_setting(db, f"session_{user_id}", session_id)
        
        return session_id
    finally:
        db.close()

REASONING_SYSTEM_PROMPT = """🦊 You are FoxxGent, a helpful AI assistant.

## TOOL USAGE - THINK, ACT, VERIFY CYCLE:
When you need to perform an action, use this JSON format to call a tool:
{"tool": "tool_name", "params": {"param1": "value1", "param2": "value2"}}

## AVAILABLE TOOLS:
- shell: run bash commands (ls, ps, systemctl, docker, pip, git, etc.)
- file_read, file_write, file_list: file operations (file_write requires "path" and "content" params)
- system_stats, get_processes, get_uptime, get_ip: system information
- docker_ps, docker_logs: docker operations (docker_logs requires "container" param)
- web_search: search the web (requires "query" param). USE THIS when user asks to search or look up something!
- send_telegram: send a telegram message (requires "chat_id" and "text" params)
- schedule_message: schedule a telegram reminder (requires "chat_id", "message", and "delay_minutes" params)
- cron_create: create a scheduled task (requires "name", "command", and "schedule" params)
- get_settings: get a setting value (requires "key" param, e.g., "telegram_chat_id")

## IMPORTANT - USER IDENTITY:
- To send messages or reminders to the user on Telegram, you MUST first get their chat_id
- Use: {"tool": "get_settings", "params": {"key": "telegram_chat_id"}}
- If the setting is not found, the user needs to pair their Telegram from the web UI (config page)
- NEVER guess or make up a chat_id

## EXAMPLES:
User: "check system status" → {"tool": "system_stats", "params": {}}
User: "search capybara population" → {"tool": "web_search", "params": {"query": "capybara population"}}
User: "remind me tea in 1 minute" → First get chat_id with {"tool": "get_settings", "params": {"key": "telegram_chat_id"}}, then use schedule_message
User: "send me a message" → First get chat_id with {"tool": "get_settings", "params": {"key": "telegram_chat_id"}}, then use send_telegram
User: "list files in /tmp" → {"tool": "shell", "params": {"command": "ls -la /tmp"}}

## CRITICAL RULES:
1. When user asks to search, look up, find, or get information about ANYTHING - you MUST output JSON like {"tool": "web_search", "params": {"query": "their exact words"}}
2. NEVER respond with text - always use the JSON format when action is needed
3. NEVER say "I couldn't" or ask for clarification - just output the JSON tool call
4. If user asks for a reminder, FIRST get their telegram_chat_id using get_settings, THEN use schedule_message
5. If user asks to send something to telegram, FIRST get their telegram_chat_id, THEN use send_telegram
6. If telegram_chat_id is not found, tell the user to go to the config page and pair their Telegram
7. Output ONLY the JSON, nothing else - no text, no explanation

respond naturally to the user. 🦊"""

class ReasoningAgent:
    def __init__(self):
        self.client = None
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.max_retries = 3
        self.current_retry = 0
        self.thoughts_history = []
        self._last_chat_id = None
        
        if self.api_key:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1"
            )
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        PRICING_PER_1M = {
            "openrouter/auto": {"prompt": 0.0, "completion": 0.0},
            "openrouter/free": {"prompt": 0.0, "completion": 0.0},
            "gpt-oss-20b": {"prompt": 0.03, "completion": 0.14},
            "gpt-oss-120b": {"prompt": 0.039, "completion": 0.19},
            "minimax-2.5": {"prompt": 0.25, "completion": 1.20},
            "grok-4.1-fast": {"prompt": 0.2, "completion": 0.5},
        }
        model_key = model.lower()
        pricing = PRICING_PER_1M.get(model_key, {"prompt": 0.0, "completion": 0.0})
        return (prompt_tokens / 1_000_000 * pricing["prompt"]) + (completion_tokens / 1_000_000 * pricing["completion"])
    
    async def chat(self, user_id: str, user_input: str) -> Dict[str, Any]:
        """main chat entry point - wraps reason_and_act for compatibility"""
        return await self.reason_and_act(user_input, user_id)
    
    async def stream_chat(self, user_id: str, user_input: str):
        """stream chat responses"""
        result = await self.chat(user_id, user_input)
        content = result.get("content", "")
        
        for char in content:
            yield {"type": "content", "content": char, "delta": True}
        
        yield {"type": "end"}
        
        if result.get("thoughts"):
            yield {"type": "thoughts", "data": result["thoughts"]}
    
    def _get_model_config(self):
        db = SessionLocal()
        try:
            model = get_setting(db, "model") or "openai/gpt-oss-120b"
            max_tokens = int(get_setting(db, "max_tokens") or 100000)
            temperature = float(get_setting(db, "temperature") or 0.7)
        finally:
            db.close()
        return model, max_tokens, temperature
    
    async def reason_and_act(self, user_input: str, user_id: str) -> Dict[str, Any]:
        """Main autonomous reasoning loop: THINK → ACT → OBSERVE → VERIFY → RESPOND"""
        
        # Save user message to chat history
        db = SessionLocal()
        try:
            save_message(db, "web" if user_id == "web" else "telegram", user_id, "user", user_input)
        except Exception as e:
            logger.error(f"Failed to save user message: {e}")
        finally:
            db.close()
        
        model, max_tokens, temperature = self._get_model_config()
        
        # Load memory for context
        memory_context = load_user_memory(user_id)
        
        system_prompt = get_vibe_aware_prompt(user_id)
        if memory_context:
            system_prompt += f"\n\n{memory_context}\n\nThe AI has memories about the user - take these into account."
        
        if "search" in user_input.lower() or "find" in user_input.lower():
            cross_result = search_cross_platform(user_input)
            if cross_result.get("status") == "success" and cross_result.get("data"):
                logger.info(f"Cross-platform search found {len(cross_result['data'])} results")
        
        reasoning_context = self._build_reasoning_context(user_id, user_input)
        
        # Add initial thought
        thought_log = {
            "thought": f"Analyzing request: {user_input[:50]}...",
            "action": "Planning approach",
            "observation": "",
            "status": "thinking"
        }
        self.thoughts_history.append(thought_log)
        
        # Step 2: ACT - Execute with reasoning
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "system", "content": f"Current thoughts: {json.dumps(self.thoughts_history[-3:])}"},
                    {"role": "user", "content": user_input}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                extra_headers={
                    "HTTP-Referer": "https://foxxgent.local",
                    "X-Title": "FoxxGent"
                }
            )
            
            usage = response.usage
            if usage:
                cost_usd = self._calculate_cost(model, usage.prompt_tokens, usage.completion_tokens)
                db = SessionLocal()
                try:
                    save_token_usage(db, model, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, user_id, cost_usd)
                except Exception as e:
                    logger.error(f"Failed to save token usage: {e}")
                finally:
                    db.close()
            
            content = response.choices[0].message.content
            if content is None:
                return {"type": "text", "content": "🦊 No response from AI. Try a different model.", "thoughts": []}
            
            # Step 3: OBSERVE - Check for tool execution requests
            final_response = await self._process_response(content, user_id)
            
            return final_response
            
        except Exception as e:
            logger.error(f"🦊 Reasoning error: {e}")
            return {"type": "text", "content": f"🦊 Error: {str(e)}", "thoughts": self.thoughts_history}
    
    async def _process_response(self, content: str, user_id: str) -> Dict[str, Any]:
        """Process response and handle tool execution with verification"""
        
        # Try to extract tool from response
        try:
            # Check for JSON tool format - try plain JSON first, then markdown-wrapped
            parsed = None
            try:
                parsed = json.loads(content.strip())
            except:
                # Try stripping markdown code blocks
                import re
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group(1))
                    except:
                        pass
            
            logger.info(f"AI response content: {content[:200]}...")
            
            if parsed and "tool" in parsed:
                tool_name = parsed.get("tool")
                params = parsed.get("params", {})
                
                # Log the action
                thought_log = {
                    "thought": f"Executing tool: {tool_name}",
                    "action": f"Calling {tool_name} with params",
                    "observation": "In progress...",
                    "status": "executing"
                }
                self.thoughts_history.append(thought_log)
                
                # ACT - Execute the tool
                tool_result = await execute_tool(tool_name, params)
                
                if tool_result is None:
                    logger.error(f"Tool {tool_name} returned None")
                    return {"type": "text", "content": f"🦊 Tool {tool_name} returned no result", "thoughts": self.thoughts_history}
                
                # OBSERVE - Verify the result
                if tool_result.get("status") == "error":
                    # Self-correct and retry
                    thought_log = {
                        "thought": f"Tool {tool_name} failed",
                        "action": "Self-correcting and retrying...",
                        "observation": tool_result.get("output", "Unknown error"),
                        "status": "retrying"
                    }
                    self.thoughts_history.append(thought_log)
                    
                    # Retry with different approach
                    if self.current_retry < self.max_retries:
                        self.current_retry += 1
                        return await self.reason_and_act(
                            f"Previous attempt failed. {tool_result.get('output')}. Please try a different approach.",
                            user_id
                        )
                    
                    return {
                        "type": "text",
                        "content": f"🦊 Tool execution failed after {self.max_retries} retries: {tool_result.get('output')}",
                        "thoughts": self.thoughts_history
                    }
                
                # VERIFY - Tool succeeded
                thought_log = {
                    "thought": f"Tool {tool_name} completed successfully",
                    "action": "Verifying output...",
                    "observation": tool_result.get("output", "Done")[:100],
                    "status": "verified"
                }
                self.thoughts_history.append(thought_log)
                
                response_content = f"🦊 {tool_result.get('output', 'Task completed') if tool_result else 'Task completed'}"
                
                # If this was a get_settings call and it returned a value, use it as context
                if tool_name == "get_settings" and tool_result.get("status") == "success":
                    chat_id = tool_result.get("output", "")
                    if chat_id and "not found" not in chat_id.lower():
                        # Store for potential next tool call
                        self._last_chat_id = chat_id
                        # Continue with the original request using this chat_id
                        return await self.reason_and_act(
                            f"User wants to send a message or reminder. Their telegram_chat_id is {chat_id}. Please now use the appropriate tool (send_telegram or schedule_message) with this chat_id.",
                            user_id
                        )
                
                # Auto-save important info to memory
                if tool_result and tool_result.get("status") == "success":
                    output = tool_result.get("output", "")
                    # Save telegram chat_id if found
                    if tool_name == "get_settings" and self._last_chat_id:
                        auto_save_memory(user_id, "telegram_chat_id", self._last_chat_id, "fact", 5)
                    # Save connection statuses
                    if tool_name == "connection_status" and output:
                        auto_save_memory(user_id, "connected_apps", output[:200], "fact", 2)
                
                # Save AI response to chat history
                db = SessionLocal()
                try:
                    save_message(db, "web" if user_id == "web" else "telegram", user_id, "assistant", response_content)
                except Exception as e:
                    logger.error(f"Failed to save AI response: {e}")
                finally:
                    db.close()
                
                return {
                    "type": "text",
                    "content": response_content,
                    "thoughts": self.thoughts_history
                }
        
        except Exception as e:
            logger.error(f"🦊 Tool processing error: {e}")
            return {"type": "text", "content": f"🦊 Error processing request: {str(e)}", "thoughts": self.thoughts_history}
        
        # Plain response (no tool)
        if not content or not content.strip():
            response_content = "🦊 Hello! I'm FoxxGent. How can I help you today?"
            # Save to chat history
            db = SessionLocal()
            try:
                save_message(db, "web" if user_id == "web" else "telegram", user_id, "assistant", response_content)
            except Exception as e:
                logger.error(f"Failed to save AI response: {e}")
            finally:
                db.close()
            return {"type": "text", "content": response_content, "thoughts": []}
        
        # Save AI response to chat history
        db = SessionLocal()
        try:
            save_message(db, "web" if user_id == "web" else "telegram", user_id, "assistant", content)
        except Exception as e:
            logger.error(f"Failed to save AI response: {e}")
        finally:
            db.close()
        
        return {"type": "text", "content": content, "thoughts": self.thoughts_history}
    
    def _build_reasoning_context(self, user_id: str, user_input: str) -> str:
        """Build context with recent thoughts and history"""
        history = get_chat_history(SessionLocal(), user_id, limit=5)
        
        context = f"Recent conversation:\n"
        for msg in history:
            role = "User" if msg.role == "user" else "FoxxGent"
            context += f"{role}: {msg.content[:100]}\n"
        
        context += f"\nCurrent request: {user_input}"
        return context
    
    def clear_thoughts(self):
        """Clear thought history"""
        self.thoughts_history = []
        self.current_retry = 0

agent_brain = ReasoningAgent()

# For backward compatibility
class AgentBrain:
    def __init__(self):
        pass
    
    def _build_messages(self, user_id: str, user_input: str):
        messages = [{"role": "system", "content": REASONING_SYSTEM_PROMPT}]
        history = get_chat_history(SessionLocal(), user_id, limit=20)
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_input})
        return messages
    
    async def chat(self, user_id: str, user_input: str):
        return await agent_brain.reason_and_act(user_input, user_id)
    
    async def stream_chat(self, user_id: str, user_input: str):
        result = await self.chat(user_id, user_input)
        content = result.get("content", "")
        
        # Stream the response
        for char in content:
            yield {"type": "content", "content": char, "delta": True}
        
        yield {"type": "end"}
        
        # Also yield thoughts for UI
        if result.get("thoughts"):
            yield {"type": "thoughts", "data": result["thoughts"]}