import os
import asyncio
import json
import secrets
from typing import List, Dict
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [FoxxGent] %(levelname)s: %(message)s')
logger = logging.getLogger("foxxgent")

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from database import init_db, SessionLocal, get_chat_history, get_sub_agents, get_cron_tasks, create_sub_agent, delete_sub_agent, save_paired_device, get_paired_devices, update_paired_device, save_setting, get_setting, get_all_settings, PairedDevice, Settings
from agent_brain import agent_brain
from exec_tools import execute_tool, spawn_sub_agent, get_sub_agent_status, cron_list as exec_tools_cron_list

BOT_RUNNING = False
TELEGRAM_APP = None

PAIRING_CODE = secrets.token_hex(4).upper()
PAIRED_USERS = {}

print(f"\n{'='*50}")
print(f"  FoxxGent - AI Agent")
print(f"{'='*50}")
print(f"  🔐 Pairing Code: {PAIRING_CODE}")
print(f"  📱 Send this code via Telegram: pair {PAIRING_CODE}")
print(f"  🌐 Web UI: http://localhost:8000")
print(f"{'='*50}\n")

DEFAULT_CONFIG = {
    "model": "openai/gpt-oss-120b",
    "max_tokens": 100000,
    "temperature": 0.7,
    "auto_think": True,
    "max_tool_calls": 5,
    "tools": {
        "get_ip": True
    },
    "telegram_chat_id": "",
    "auto_pair": True,
    "theme": "win8",
    "mcp_servers": [],
    "notifications": {
        "telegram": True,
        "file": False,
        "file_path": "/tmp/foxxgent_notifications.txt"
    }
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global BOT_RUNNING, TELEGRAM_APP, PAIRED_USERS
    
    init_db()
    
    # Load paired users from database
    db = SessionLocal()
    try:
        devices = get_paired_devices(db)
        for device in devices:
            if device.enabled:
                PAIRED_USERS[device.chat_id] = {
                    "username": device.username,
                    "first_name": device.first_name
                }
        logger.info(f"Loaded {len(PAIRED_USERS)} paired users")
    except Exception as e:
        logger.error(f"Failed to load paired users: {e}")
    finally:
        db.close()
    
    # Load saved MCP servers
    db = SessionLocal()
    try:
        mcp_servers_json = get_setting(db, "mcp_servers")
        if mcp_servers_json:
            mcp_servers = json.loads(mcp_servers_json)
            from mcp_client import mcp_server
            for server in mcp_servers:
                await mcp_server.add_client(server.get("name"), server.get("command"), server.get("args"))
                logger.info(f"Loaded MCP server: {server.get('name')}")
    except Exception as e:
        logger.error(f"Failed to load MCP servers: {e}")
    finally:
        db.close()
    
    # Load saved connections
    try:
        from connection_manager import connection_manager
        connection_manager.load_saved_connections()
        logger.info("Loaded saved connections")
    except Exception as e:
        logger.error(f"Failed to load connections: {e}")
    
    bot_token = os.getenv("TELEGRAM_BOT_KEY")
    if bot_token:
        TELEGRAM_APP = Application.builder().token(bot_token).build()
        
        async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_chat_id = str(update.effective_user.id)
            
            if user_chat_id in PAIRED_USERS:
                await update.message.reply_text(
                    f"✅ You're already paired with FoxxGent!\n\n"
                    f"Type a message and I'll help you control your server."
                )
            else:
                await update.message.reply_text(
                    f"👋 Welcome to FoxxGent!\n\n"
                    f"To pair your account, ask the server admin for the pairing code.\n\n"
                    f"Then type: <code>pair YOUR_CODE</code>",
                    parse_mode="HTML"
                )
        
        async def compact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(
                "🔽 Compact mode: AI responses will be shorter and more concise.",
                parse_mode="HTML"
            )
        
        async def new_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(
                "🆕 New session started! Previous context cleared.",
                parse_mode="HTML"
            )
        
        async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            from exec_tools import get_system_stats
            stats = await get_system_stats()
            if stats.get('status') == 'success':
                s = stats.get('stats', {})
                output = f"✅ System OK\n\nCPU: {s.get('cpu_percent', 0)}%\nMemory: {s.get('memory_percent', 0)}%\nDisk: {s.get('disk_percent', 0)}%"
            else:
                output = f"❌ {stats.get('output', 'Unknown error')}"
            await update.message.reply_text(f"📊 System Status:\n\n{output}")
        
        async def pair_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            code = update.message.text.split()[1] if len(update.message.text.split()) > 1 else ""
            
            if code == PAIRING_CODE:
                user_chat_id = str(update.effective_user.id)
                PAIRED_USERS[user_chat_id] = {
                    "username": update.effective_user.username or "",
                    "first_name": update.effective_user.first_name or ""
                }
                
                db = SessionLocal()
                try:
                    save_paired_device(db, user_chat_id, update.effective_user.username or "unknown", update.effective_user.first_name or "User")
                finally:
                    db.close()
                
                await update.message.reply_text(
                    f"✅ Paired successfully!\n\n"
                    f"I can now help you control your server via Telegram.\n\n"
                    f"Commands:\n"
                    f"- /start - Show welcome\n"
                    f"- /compact - Shorter responses\n"
                    f"- /new_session - Clear context\n"
                    f"- /status - System stats\n"
                    f"- /unpair - Unpair device",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("❌ Invalid pairing code.")
        
        async def unpair_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_chat_id = str(update.effective_user.id)
            if user_chat_id in PAIRED_USERS:
                del PAIRED_USERS[user_chat_id]
                await update.message.reply_text("✅ Unpaired successfully!")
            else:
                await update.message.reply_text("You're not paired.")
        
        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_chat_id = str(update.effective_user.id)
            message = update.message.text
            
            if user_chat_id not in PAIRED_USERS:
                await update.message.reply_text("❌ Not paired. Use /start to begin.")
                return
            
            await update.message.chat.send_action("typing")
            
            response = await agent_brain.chat(user_chat_id, message)
            content = response.get("content", "No response")
            
            await update.message.reply_text(content, parse_mode="Markdown")
        
        TELEGRAM_APP.add_handler(CommandHandler("start", start_command))
        TELEGRAM_APP.add_handler(CommandHandler("pair", pair_command))
        TELEGRAM_APP.add_handler(CommandHandler("unpair", unpair_command))
        TELEGRAM_APP.add_handler(CommandHandler("compact", compact_command))
        TELEGRAM_APP.add_handler(CommandHandler("new_session", new_session_command))
        TELEGRAM_APP.add_handler(CommandHandler("status", status_command))
        TELEGRAM_APP.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        await TELEGRAM_APP.initialize()
        await TELEGRAM_APP.start()
        BOT_RUNNING = True
        asyncio.create_task(TELEGRAM_APP.updater.start_polling())
        logger.info("Telegram bot started")
    
    # Start proactive scheduler
    try:
        from proactive_scheduler import scheduler
        await scheduler.start()
        logger.info("Proactive scheduler started")
    except Exception as e:
        logger.error(f"Failed to start proactive scheduler: {e}")
    
    yield
    
    if TELEGRAM_APP:
        await TELEGRAM_APP.stop()

app = FastAPI(title="FoxxGent", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/health checks"""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "foxxgent"
    }

@app.get("/healthz")
async def healthz():
    """Kubernetes health check endpoint"""
    return {"status": "ok"}

@app.get("/chat")
async def chat_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "chat_only": True})

@app.get("/api/chat/history")
async def get_chat_history_api(user_id: str = "web"):
    db = SessionLocal()
    try:
        messages = get_chat_history(db, user_id)
        return JSONResponse([
            {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat() if msg.timestamp else None}
            for msg in messages
        ])
    finally:
        db.close()

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    user_id = data.get("user_id", "web")
    message = data.get("message", "")
    
    if not message:
        return JSONResponse({"error": "Message is required"}, status_code=400)
    
    # Handle slash commands
    if message.startswith("/"):
        command_parts = message.split()
        command = command_parts[0].lower()
        
        if command == "/status":
            from exec_tools import get_system_stats
            stats = await get_system_stats()
            if stats.get('status') == 'success':
                s = stats.get('stats', {})
                content = f"📊 System Status:\n\nCPU: {s.get('cpu_percent', 0)}%\nMemory: {s.get('memory_percent', 0)}%\nDisk: {s.get('disk_percent', 0)}%"
            else:
                content = f"❌ Error: {stats.get('output', 'Unknown')}"
        elif command == "/help":
            content = """📖 Available Commands:

/status - Show system status
/help - Show this help message
/new - Start a new conversation

Or just chat with me naturally!"""
        elif command == "/new":
            content = "🔄 New conversation started! How can I help you?"
        else:
            content = f"Unknown command: {command}\n\nType /help for available commands."
        
        return JSONResponse({"role": "assistant", "content": content})
    
    response = await agent_brain.chat(user_id, message)
    
    return JSONResponse({
        "role": "assistant",
        "content": response.get("content", "")
    })

@app.websocket("/api/chat/stream")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    user_id = "web"
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_input = message_data.get("message", "")
            logger.info(f"Received message: {user_input[:50]}...")
            
            await websocket.send_text(json.dumps({"type": "start"}))
            
            # Handle slash commands directly
            if user_input.startswith("/"):
                command_parts = user_input.split()
                command = command_parts[0].lower()
                args = command_parts[1:] if len(command_parts) > 1 else []
                
                response = ""
                if command == "/status":
                    from exec_tools import get_system_stats
                    stats = await get_system_stats()
                    if stats.get('status') == 'success':
                        s = stats.get('stats', {})
                        response = f"📊 System Status:\n\nCPU: {s.get('cpu_percent', 0)}%\nMemory: {s.get('memory_percent', 0)}%\nDisk: {s.get('disk_percent', 0)}%"
                    else:
                        response = f"❌ Error: {stats.get('output', 'Unknown')}"
                elif command == "/help":
                    response = """📖 Available Commands:

/status - Show system status
/help - Show this help message
/new - Start a new conversation

Or just chat with me naturally!"""
                elif command == "/new":
                    response = "🔄 New conversation started! How can I help you?"
                else:
                    response = f"Unknown command: {command}\n\nType /help for available commands."
                
                await websocket.send_text(json.dumps({"type": "content", "content": response, "delta": False}))
                await websocket.send_text(json.dumps({"type": "end"}))
                continue
            
            async for chunk in agent_brain.stream_chat(user_id, user_input):
                chunk_type = chunk.get("type")
                if chunk_type == "tool":
                    tool_name = chunk.get("tool")
                    params = chunk.get("params", {})
                    logger.info(f"Executing tool: {tool_name}")
                    tool_result = await execute_tool(tool_name, params)
                    logger.info(f"Tool result received")
                    await websocket.send_text(json.dumps({
                        "type": "tool",
                        "tool": tool_name,
                        "result": tool_result
                    }))
                elif chunk_type == "tool_result":
                    logger.info(f"Tool completed successfully")
                else:
                    await websocket.send_text(json.dumps({
                        "type": "content",
                        "content": chunk.get("content", ""),
                        "delta": chunk.get("delta", False)
                    }))
            
            await websocket.send_text(json.dumps({"type": "end"}))
            logger.info("Response complete")
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")

@app.get("/api/config")
async def get_full_config():
    db = SessionLocal()
    try:
        settings = get_all_settings(db)
        config = DEFAULT_CONFIG.copy()
        for key, value in settings.items():
            if key in config:
                if key in ("tools", "mcp_servers", "notifications"):
                    config[key] = json.loads(value) if value else config[key]
                else:
                    config[key] = value
        return JSONResponse(config)
    finally:
        db.close()

@app.post("/api/config")
async def update_full_config(request: Request):
    data = await request.json()
    db = SessionLocal()
    try:
        for key, value in data.items():
            if key in ("tools", "mcp_servers", "notifications"):
                save_setting(db, key, json.dumps(value))
            else:
                save_setting(db, key, str(value))
    finally:
        db.close()
    return JSONResponse({"status": "success"})

@app.post("/api/config/save")
async def save_config(request: Request):
    data = await request.json()
    return JSONResponse({"status": "success"})

async def notify_telegram_action(chat_id: str, tool_name: str, result: Dict[str, Any], user_message: str):
    """Send tool execution result to Telegram"""
    bot_token = os.getenv("TELEGRAM_BOT_KEY")
    if not bot_token:
        return
    
    import httpx
    status_icon = "✅" if result.get("status") == "success" else "❌"
    output = result.get("output", "Unknown")[:200]
    
    message = f"🦊 FoxxGent Action Report\n\n" \
               f"Tool: {tool_name}\n" \
               f"Request: {user_message[:50]}...\n" \
               f"Status: {status_icon}\n" \
               f"Result: {output}"
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message}
            )
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")

web_logs: list = []

def add_web_log(level: str, message: str):
    from datetime import datetime
    web_logs.append({
        "time": datetime.utcnow().isoformat(),
        "level": level,
        "message": message
    })
    if len(web_logs) > 100:
        web_logs.pop(0)

@app.get("/api/logs")
async def get_logs():
    return JSONResponse(web_logs[-50:])

@app.post("/api/pair")
async def pair_device(request: Request):
    data = await request.json()
    code = data.get("code", "")
    
    if code != PAIRING_CODE:
        return JSONResponse({"error": "Invalid code"}, status_code=400)
    
    user_id = data.get("user_id", "web")
    PAIRED_USERS[user_id] = {"paired": True}
    
    db = SessionLocal()
    try:
        save_paired_device(db, user_id, "web", "Web User")
    finally:
        db.close()
    
    return JSONResponse({"status": "paired"})

@app.get("/api/devices")
async def get_devices():
    db = SessionLocal()
    try:
        devices = get_paired_devices(db)
        return JSONResponse([
            {
                "chat_id": d.chat_id,
                "username": d.username,
                "first_name": d.first_name,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                "enabled": d.enabled
            }
            for d in devices
        ])
    finally:
        db.close()

@app.post("/api/devices/{chat_id}/toggle")
async def toggle_device(chat_id: str, request: Request):
    data = await request.json()
    enabled = data.get("enabled", True)
    
    db = SessionLocal()
    try:
        update_paired_device(db, chat_id, enabled)
    finally:
        db.close()
    
    return JSONResponse({"status": "success"})

@app.get("/api/sub-agents")
async def get_sub_agents_api():
    db = SessionLocal()
    try:
        agents = get_sub_agents(db)
        return JSONResponse([
            {
                "id": a.id,
                "name": a.name,
                "task": a.task,
                "status": a.status,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "result": a.result
            }
            for a in agents
        ])
    finally:
        db.close()

@app.post("/api/sub-agents")
async def create_sub_agent_api(request: Request):
    data = await request.json()
    name = data.get("name", "")
    prompt = data.get("prompt", "")
    
    db = SessionLocal()
    try:
        agent = create_sub_agent(db, name, prompt)
        return JSONResponse({"id": agent.id, "name": agent.name})
    finally:
        db.close()

@app.delete("/api/sub-agents/{agent_id}")
async def delete_sub_agent_api(agentId: int):
    db = SessionLocal()
    try:
        delete_sub_agent(db, agentId)
        return JSONResponse({"status": "deleted"})
    finally:
        db.close()

@app.post("/api/sub-agents/{agent_id}/run")
async def run_sub_agent(AgentId: int, request: Request):
    data = await request.json()
    task = data.get("task", "")
    
    result = await spawn_sub_agent(AgentId, task)
    return JSONResponse(result)

@app.get("/api/sub-agents/{agent_id}/status")
async def get_sub_agent_status_api(AgentId: int):
    status = get_sub_agent_status(AgentId)
    return JSONResponse(status)

@app.get("/api/cron")
async def get_cron_tasks():
    db = SessionLocal()
    try:
        tasks = get_cron_tasks(db)
        return JSONResponse([
            {
                "id": t.id,
                "name": t.name,
                "schedule": t.schedule,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "next_run": t.next_run.isoformat() if t.next_run else None,
                "status": t.status
            }
            for t in tasks
        ])
    finally:
        db.close()

@app.get("/api/stats")
async def get_stats():
    from exec_tools import get_system_stats
    stats = await get_system_stats()
    
    db = SessionLocal()
    try:
        from database import get_token_usage_summary, get_all_time_token_usage
        usage_30d = get_token_usage_summary(db, "global", 30)
        all_time = get_all_time_token_usage(db)
        stats["token_usage"] = {
            "last_30_days": usage_30d,
            "all_time": all_time
        }
    except Exception as e:
        stats["token_usage"] = {"error": str(e)}
    finally:
        db.close()
    
    return JSONResponse(stats)

@app.get("/api/tools")
async def get_tools():
    db = SessionLocal()
    try:
        tools = exec_tools_cron_list()
        return JSONResponse(tools)
    finally:
        db.close()

@app.get("/api/connections")
async def get_connections():
    from connection_manager import get_connection_status
    return JSONResponse(get_connection_status())

@app.post("/api/connect")
async def connect_app(request: Request):
    data = await request.json()
    app_id = data.get("app_id", "")
    credentials = data.get("credentials", {})
    config = data.get("config", {})
    
    from connection_manager import connection_manager
    result = await connection_manager.connect(app_id, credentials, config)
    return JSONResponse(result)

@app.post("/api/disconnect")
async def disconnect_app(request: Request):
    data = await request.json()
    app_id = data.get("app_id", "")
    
    from connection_manager import connection_manager
    result = await connection_manager.disconnect(app_id)
    return JSONResponse(result)

@app.get("/api/mcp")
async def get_mcp_servers():
    from mcp_client import mcp_server
    return JSONResponse({"servers": mcp_server.list_clients()})

@app.post("/api/mcp/add")
async def add_mcp_server(request: Request):
    from mcp_client import mcp_server
    data = await request.json()
    name = data.get("name", "")
    command = data.get("command", "")
    args = data.get("args", [])
    
    success = await mcp_server.add_client(name, command, args)
    if success:
        db = SessionLocal()
        try:
            mcp_servers = json.loads(get_setting(db, "mcp_servers") or "[]")
            mcp_servers.append({"name": name, "command": command, "args": args})
            save_setting(db, "mcp_servers", json.dumps(mcp_servers))
        finally:
            db.close()
    return JSONResponse({"status": "success" if success else "error"})

@app.post("/api/mcp/remove")
async def remove_mcp_server(request: Request):
    from mcp_client import mcp_server
    data = await request.json()
    name = data.get("name", "")
    await mcp_server.remove_client(name)
    
    db = SessionLocal()
    try:
        mcp_servers = json.loads(get_setting(db, "mcp_servers") or "[]")
        mcp_servers = [s for s in mcp_servers if s.get("name") != name]
        save_setting(db, "mcp_servers", json.dumps(mcp_servers))
    finally:
        db.close()
    
    return JSONResponse({"status": "success"})

@app.get("/api/omni/status")
async def omni_status():
    from omni_connector import omni_connector
    return JSONResponse(omni_connector.status())

@app.post("/api/omni/connect")
async def omni_connect():
    from omni_connector import omni_connector
    result = await omni_connector.connect_all()
    return JSONResponse({"status": "success", "connected": result})

@app.get("/api/omni/gmail/list")
async def gmail_list(request: Request):
    from omni_connector import omni_connector
    result = await omni_connector.gmail_list_messages(50)
    return JSONResponse(result)

@app.get("/api/omni/gmail/{message_id}")
async def gmail_get_message(message_id: str):
    from omni_connector import omni_connector
    result = await omni_connector.gmail_get_message(message_id)
    return JSONResponse(result)

@app.post("/api/omni/gmail/send")
async def gmail_send(request: Request):
    data = await request.json()
    to = data.get("to", "")
    subject = data.get("subject", "")
    body = data.get("body", "")
    
    from omni_connector import omni_connector
    result = await omni_connector.gmail_send_message(to, subject, body)
    return JSONResponse(result)

@app.get("/api/omni/calendar/events")
async def calendar_events(request: Request, days: int = 7):
    from omni_connector import omni_connector
    result = await omni_connector.calendar_list_events(days)
    return JSONResponse(result)

@app.post("/api/omni/calendar/create")
async def calendar_create(request: Request):
    data = await request.json()
    title = data.get("title", "")
    start_time = data.get("start_time", "")
    end_time = data.get("end_time", "")
    description = data.get("description", "")
    
    from omni_connector import omni_connector
    result = await omni_connector.calendar_create_event(title, start_time, end_time, description)
    return JSONResponse(result)

@app.get("/api/omni/github/repos")
async def github_repos():
    from omni_connector import omni_connector
    result = await omni_connector.github_list_repos()
    return JSONResponse(result)

@app.get("/api/omni/github/repo/{owner}/{repo}")
async def github_repo(owner: str, repo: str):
    from omni_connector import omni_connector
    result = await omni_connector.github_get_repo(owner, repo)
    return JSONResponse(result)

@app.post("/api/omni/github/repo/{owner}/{repo}/issue")
async def github_create_issue(owner: str, repo: str, request: Request):
    data = await request.json()
    title = data.get("title", "")
    body = data.get("body", "")
    
    from omni_connector import omni_connector
    result = await omni_connector.github_create_issue(owner, repo, title, body)
    return JSONResponse(result)

@app.get("/api/omni/github/repo/{owner}/{repo}/issues")
async def github_issues(owner: str, repo: str):
    from omni_connector import omni_connector
    result = await omni_connector.github_list_issues(owner, repo)
    return JSONResponse(result)

@app.get("/api/omni/notion/databases")
async def notion_databases():
    from omni_connector import omni_connector
    result = await omni_connector.notion_list_databases()
    return JSONResponse(result)

@app.post("/api/omni/notion/page")
async def notion_create_page(request: Request):
    data = await request.json()
    database_id = data.get("database_id", "")
    title = data.get("title", "")
    properties = data.get("properties", {})
    
    from omni_connector import omni_connector
    result = await omni_connector.notion_create_page(database_id, title, properties)
    return JSONResponse(result)

@app.get("/api/omni/slack/channels")
async def slack_channels():
    from omni_connector import omni_connector
    result = await omni_connector.slack_list_channels()
    return JSONResponse(result)

@app.post("/api/omni/slack/message")
async def slack_send(request: Request):
    data = await request.json()
    channel = data.get("channel", "")
    text = data.get("text", "")
    
    from omni_connector import omni_connector
    result = await omni_connector.slack_send_message(channel, text)
    return JSONResponse(result)

@app.post("/api/memory")
async def save_memory_endpoint(request: Request):
    data = await request.json()
    memory_type = data.get("type", "fact")
    key = data.get("key", "")
    value = data.get("value", "")
    user_id = data.get("user_id", "global")
    importance = data.get("importance", 1)
    
    if not key:
        return JSONResponse({"error": "Key is required"}, status_code=400)
    
    db = SessionLocal()
    try:
        from database import save_memory
        save_memory(db, memory_type, key, value, user_id, importance)
        return JSONResponse({"status": "success"})
    finally:
        db.close()

@app.get("/api/memory")
async def get_memory_endpoint(request: Request, key: str = None, type: str = None, user_id: str = "global"):
    db = SessionLocal()
    try:
        from database import get_memory, get_all_memory, get_memories_by_type
        if key:
            mem = get_memory(db, key, user_id)
            if mem:
                return JSONResponse({"key": mem.key, "value": mem.value, "type": mem.memory_type, "importance": mem.importance})
            return JSONResponse({"error": "Not found"}, status_code=404)
        elif type:
            mems = get_memories_by_type(db, type, user_id)
            return JSONResponse([{"key": m.key, "value": m.value, "type": m.memory_type, "importance": m.importance} for m in mems])
        else:
            mems = get_all_memory(db, user_id)
            return JSONResponse([{"key": m.key, "value": m.value, "type": m.memory_type, "importance": m.importance} for m in mems])
    finally:
        db.close()

@app.get("/api/memory/search")
async def search_memory_endpoint(request: Request, q: str, user_id: str = "global"):
    db = SessionLocal()
    try:
        from database import search_memory
        mems = search_memory(db, q, user_id)
        return JSONResponse([{"key": m.key, "value": m.value, "type": m.memory_type, "importance": m.importance} for m in mems])
    finally:
        db.close()

@app.delete("/api/memory")
async def delete_memory_endpoint(request: Request, key: str, user_id: str = "global"):
    db = SessionLocal()
    try:
        from database import delete_memory
        delete_memory(db, key, user_id)
        return JSONResponse({"status": "success"})
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# Additional endpoints needed by frontend

@app.get("/api/system")
async def get_system():
    from exec_tools import get_system_stats
    stats = await get_system_stats()
    
    db = SessionLocal()
    try:
        from database import get_token_usage_summary, get_all_time_token_usage
        usage_30d = get_token_usage_summary(db, "global", 30)
        all_time = get_all_time_token_usage(db)
        stats["token_usage"] = {
            "last_30_days": usage_30d,
            "all_time": all_time
        }
    except Exception as e:
        stats["token_usage"] = {"error": str(e)}
    finally:
        db.close()
    
    return JSONResponse(stats)

@app.get("/api/agents")
async def get_agents():
    db = SessionLocal()
    try:
        agents = get_sub_agents(db)
        return JSONResponse([
            {
                "id": a.id,
                "name": a.name,
                "task": a.task,
                "status": a.status,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "finished_at": a.finished_at.isoformat() if a.finished_at else None,
                "result": a.result
            }
            for a in agents
        ])
    finally:
        db.close()

@app.post("/api/agents/create")
async def create_agent(request: Request):
    data = await request.json()
    name = data.get("name", "")
    prompt = data.get("prompt", "")
    
    db = SessionLocal()
    try:
        agent = create_sub_agent(db, name, prompt)
        return JSONResponse({"id": agent.id, "name": agent.name})
    finally:
        db.close()

@app.post("/api/agents/delete")
async def delete_agent(request: Request):
    data = await request.json()
    agent_id = data.get("id", 0)
    
    db = SessionLocal()
    try:
        delete_sub_agent(db, agent_id)
        return JSONResponse({"status": "deleted"})
    finally:
        db.close()

@app.get("/api/bot/status")
async def bot_status():
    global BOT_RUNNING
    return JSONResponse({"running": BOT_RUNNING, "paired_users": len(PAIRED_USERS)})

@app.get("/api/pairing/code")
async def get_pairing_code():
    return JSONResponse({"code": PAIRING_CODE})

@app.get("/api/pairing/users")
async def get_pairing_users():
    return JSONResponse(list(PAIRED_USERS.keys()))

@app.post("/api/pairing/toggle")
async def pairing_toggle(request: Request):
    data = await request.json()
    chat_id = data.get("chat_id", "")
    enabled = data.get("enabled", True)
    
    if enabled:
        PAIRED_USERS[chat_id] = {"enabled": True}
    elif chat_id in PAIRED_USERS:
        del PAIRED_USERS[chat_id]
    
    return JSONResponse({"status": "success"})

@app.get("/api/skills")
async def get_skills():
    from connection_manager import connection_manager
    skills = []
    for app_id, conn in connection_manager.connections.items():
        if "skills" in conn:
            for skill in conn["skills"]:
                skill["app_id"] = app_id
                skills.append(skill)
    return JSONResponse(skills)

@app.post("/api/skills/add")
async def add_skill(request: Request):
    data = await request.json()
    app_id = data.get("app_id", "")
    skill_name = data.get("skill_name", "")
    description = data.get("description", "")
    parameters = data.get("parameters", "{}")
    
    if not app_id or not skill_name:
        return JSONResponse({"error": "app_id and skill_name are required"}, status_code=400)
    
    from database import SessionLocal, save_connection_skill
    db = SessionLocal()
    try:
        save_connection_skill(db, app_id, skill_name, description, parameters)
        return JSONResponse({"status": "success", "message": f"Skill {skill_name} added"})
    finally:
        db.close()

@app.post("/api/skills/toggle")
async def toggle_skill(request: Request):
    data = await request.json()
    app_id = data.get("app_id", "")
    skill_name = data.get("skill_name", "")
    enabled = data.get("enabled", True)
    
    if not app_id or not skill_name:
        return JSONResponse({"error": "app_id and skill_name are required"}, status_code=400)
    
    from database import SessionLocal, ConnectionSkill
    db = SessionLocal()
    try:
        skill = db.query(ConnectionSkill).filter_by(app_id=app_id, skill_name=skill_name).first()
        if skill:
            skill.enabled = enabled
            db.commit()
            return JSONResponse({"status": "success", "message": f"Skill {skill_name} {'enabled' if enabled else 'disabled'}"})
        return JSONResponse({"error": "Skill not found"}, status_code=404)
    finally:
        db.close()

@app.post("/api/skills/remove")
async def remove_skill(request: Request):
    data = await request.json()
    app_id = data.get("app_id", "")
    skill_name = data.get("skill_name", "")
    
    if not app_id or not skill_name:
        return JSONResponse({"error": "app_id and skill_name are required"}, status_code=400)
    
    from database import SessionLocal, ConnectionSkill
    db = SessionLocal()
    try:
        skill = db.query(ConnectionSkill).filter_by(app_id=app_id, skill_name=skill_name).first()
        if skill:
            db.delete(skill)
            db.commit()
            return JSONResponse({"status": "success", "message": f"Skill {skill_name} removed"})
        return JSONResponse({"error": "Skill not found"}, status_code=404)
    finally:
        db.close()

@app.get("/api/stream")
async def stream_events(request: Request):
    async def event_generator():
        import time
        while True:
            yield f"data: {time.time()}\n\n"
            await asyncio.sleep(5)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/logs/clear")
async def clear_logs():
    global web_logs
    web_logs.clear()
    return JSONResponse({"status": "success"})

@app.get("/api/connections/skills")
async def get_connection_skills():
    from connection_manager import connection_manager
    skills = []
    for app_id, conn in connection_manager.connections.items():
        if "skills" in conn:
            for skill in conn["skills"]:
                skill["app_id"] = app_id
                skills.append(skill)
    return JSONResponse(skills)

@app.get("/api/connections/{app_id}/config")
async def get_connection_config(app_id: str):
    from connection_manager import connection_manager
    from app_registry import get_app_config
    from dataclasses import asdict
    
    conn = connection_manager.get_connection(app_id)
    if conn:
        return JSONResponse({"status": "connected", "name": conn.get("name"), "config": conn.get("config_extra", {})})
    
    app = get_app_config(app_id)
    if app:
        return JSONResponse({
            "status": "available",
            "name": app.name,
            "category": app.category,
            "auth_type": app.auth_type,
            "auth_fields": app.auth_fields,
            "documentation": app.documentation
        })
    return JSONResponse({"error": "App not found"}, status_code=404)

@app.post("/api/connections/execute")
async def execute_connection_action(request: Request):
    data = await request.json()
    app_id = data.get("app_id", "")
    action = data.get("action", "")
    params = data.get("params", {})
    
    from connection_manager import connection_manager
    result = await connection_manager.execute_action(app_id, action, params)
    return JSONResponse(result)
