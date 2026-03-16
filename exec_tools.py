import os
import asyncio
import subprocess
import uuid
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import httpx
from database import SessionLocal, log_execution, create_sub_agent, update_sub_agent, save_cron_task, get_cron_tasks, delete_cron_task, CronTask
from crontab import CronTab

logging.basicConfig(level=logging.INFO, format='%(asctime)s [FoxxGent] %(levelname)s: %(message)s')
logger = logging.getLogger("foxxgent")

executor = ThreadPoolExecutor(max_workers=5)
sub_agents: Dict[str, Dict[str, Any]] = {}

async def add_web_log(level: str, message: str):
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://127.0.0.1:8000/api/logs/add", json={"level": level, "message": message})
    except Exception:
        pass

async def execute_shell(command: str, description: str = "", async_mode: bool = False, 
                        agent_id: Optional[str] = None) -> Dict[str, Any]:
    if async_mode and agent_id:
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(executor, _run_shell_sync, command, agent_id)
        return {"status": "started", "agent_id": agent_id, "message": f"Task started: {description}"}
    
    return await asyncio.get_event_loop().run_in_executor(executor, _run_shell_sync, command, agent_id or "direct")

def _run_shell_sync(command: str, agent_id: str) -> Dict[str, Any]:
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        stdout, stderr = process.communicate()
        output = stdout + stderr if stderr else stdout
        
        exit_code = process.returncode
        
        db = SessionLocal()
        try:
            log_execution(db, agent_id, command, output, exit_code)
        finally:
            db.close()
        
        if agent_id != "direct":
            update_sub_agent(SessionLocal(), agent_id, "completed" if exit_code == 0 else "failed", output[:1000])
        
        return {
            "status": "success" if exit_code == 0 else "error",
            "output": output,
            "exit_code": exit_code
        }
    except Exception as e:
        return {"status": "error", "output": str(e), "exit_code": 1}

async def spawn_sub_agent(name: str, task: str) -> str:
    logger.info(f"Spawning new agent: {name} - {task[:50]}...")
    await add_web_log("INFO", f"Creating task: {name}")
    agent_id = f"agent_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        create_sub_agent(db, agent_id, name, task)
    finally:
        db.close()
    
    sub_agents[agent_id] = {"name": name, "task": task, "status": "running", "started": datetime.utcnow()}
    
    asyncio.create_task(run_agent_task(agent_id, task))
    
    return agent_id

async def run_agent_task(agent_id: str, task: str):
    logger.info(f"Running agent task: {agent_id}")
    await add_web_log("INFO", f"Starting task execution: {task[:30]}...")
    try:
        from agent_brain import agent_brain
        result = await agent_brain.chat(agent_id, task)
        
        output = "No response"
        status = "failed"
        
        if result is not None:
            if isinstance(result, dict):
                output = result.get("content") or result.get("output") or str(result) if result else "Empty response"
            else:
                output = str(result)
            status = "completed"
        
        logger.info(f"Agent {agent_id} completed: {str(output)[:50]}...")
        await add_web_log("INFO", f"Task completed: {str(output)[:50]}...")
    except Exception as e:
        output = f"Error: {str(e)}"
        status = "failed"
        logger.error(f"Agent {agent_id} failed: {str(e)}")
        await add_web_log("ERROR", f"Task failed: {str(e)}")
    
    db = SessionLocal()
    try:
        update_sub_agent(db, agent_id, status, output[:1000])
    finally:
        db.close()

def get_sub_agent_status(agent_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        from database import SubAgent
        agent = db.query(SubAgent).filter_by(id=agent_id).first()
        if agent:
            return {
                "id": agent.id,
                "name": agent.name,
                "status": agent.status,
                "task": agent.task,
                "result": agent.result,
                "started_at": agent.started_at.isoformat() if agent.started_at else None,
                "finished_at": agent.finished_at.isoformat() if agent.finished_at else None
            }
    finally:
        db.close()
    return None

async def file_read(path: str) -> Dict[str, Any]:
    try:
        with open(path, 'r') as f:
            content = f.read()
        return {"status": "success", "content": content}
    except FileNotFoundError:
        return {"status": "error", "output": f"File not found: {path}"}
    except PermissionError:
        return {"status": "error", "output": f"Permission denied: {path}"}
    except Exception as e:
        return {"status": "error", "output": str(e)}

async def file_write(path: str, content: str) -> Dict[str, Any]:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return {"status": "success", "output": f"File written: {path}"}
    except Exception as e:
        return {"status": "error", "output": str(e)}

async def cron_create(name: str, command: str, schedule: str) -> Dict[str, Any]:
    try:
        cron = CronTab(user=True)
        job = cron.new(command=command, comment=name)
        job.setall(schedule)
        cron.write()
        
        db = SessionLocal()
        try:
            save_cron_task(db, name, command, schedule)
        finally:
            db.close()
        
        return {"status": "success", "output": f"Cron job '{name}' created: {schedule} -> {command}"}
    except Exception as e:
        return {"status": "error", "output": str(e)}

async def cron_list() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        tasks = get_cron_tasks(db)
        result = []
        for task in tasks:
            result.append({
                "id": task.id,
                "name": task.name,
                "command": task.command,
                "schedule": task.schedule,
                "enabled": task.enabled,
                "last_run": task.last_run.isoformat() if task.last_run else None
            })
        return {"status": "success", "tasks": result}
    finally:
        db.close()

async def cron_delete(task_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        task = db.query(CronTask).filter_by(id=task_id).first()
        if not task:
            return {"status": "error", "output": f"Cron task {task_id} not found"}
        
        try:
            cron = CronTab(user=True)
            for job in cron:
                if job.comment == str(task_id):
                    cron.remove(job)
                    cron.write()
                    break
        except:
            pass
        
        delete_cron_task(db, task_id)
        return {"status": "success", "output": f"Cron task {task_id} deleted"}
    finally:
        db.close()

async def web_search(query: str, num_results: int = 5) -> Dict[str, Any]:
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {"status": "error", "output": f"Search failed with status {response.status_code}"}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        for result in soup.select('.result__snippet')[:num_results]:
            title = result.get('data-src', '')
            parent = result.find_parent('.result')
            if parent:
                link = parent.select_one('.result__a')
                if link:
                    title = link.get_text(strip=True)
                    url = link.get('href', '')
            snippet = result.get_text(strip=True)
            results.append(f"- {title}: {snippet[:200]}")
        
        if not results:
            return {"status": "success", "output": "No results found"}
        
        return {"status": "success", "output": "\n".join(results)}
    except ImportError:
        return {"status": "error", "output": "requests/beautifulsoup4 not installed. Run: pip install requests beautifulsoup4"}
    except Exception as e:
        return {"status": "error", "output": f"Search error: {str(e)}"}

async def get_system_stats() -> Dict[str, Any]:
    try:
        import psutil
        
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "status": "success",
            "stats": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_total_mb": memory.total / (1024 * 1024),
                "disk_percent": disk.percent,
                "disk_used_gb": disk.used / (1024 * 1024 * 1024),
                "disk_total_gb": disk.total / (1024 * 1024 * 1024)
            }
        }
    except ImportError:
        return {"status": "error", "output": "psutil not installed"}
    except Exception as e:
        return {"status": "error", "output": str(e)}

async def send_telegram_message(chat_id: str, text: str) -> Dict[str, Any]:
    try:
        import requests
        token = os.getenv("TELEGRAM_BOT_KEY")
        if not token:
            return {"status": "error", "output": "TELEGRAM_BOT_KEY not configured"}
        
        resolved_id = await resolve_telegram_username(chat_id)
        if not resolved_id:
            return {"status": "error", "output": f"Could not find user: {chat_id}"}
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": resolved_id, "text": text}
        resp = requests.post(url, json=data, timeout=10)
        
        if resp.ok:
            return {"status": "success", "output": f"Message sent to {resolved_id}"}
        else:
            return {"status": "error", "output": f"Telegram API error: {resp.text}"}
    except Exception as e:
        return {"status": "error", "output": str(e)}

async def resolve_telegram_username(username: str) -> Optional[str]:
    import requests
    token = os.getenv("TELEGRAM_BOT_KEY")
    if not token:
        return None
    
    if username.lstrip('-').isdigit():
        return username
    
    if username.startswith('@'):
        username = username[1:]
    
    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10)
        if resp.ok:
            data = resp.json()
            for update in data.get("result", []):
                user = update.get("message", {}).get("from", {})
                if user.get("username", "").lower() == username.lower():
                    return str(user.get("id"))
    except:
        pass
    
    return None

async def get_processes() -> Dict[str, Any]:
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent'])[:20]:
            try:
                procs.append(f"PID {p.info['pid']}: {p.info['name']} (CPU: {p.info['cpu_percent']:.1f}%, MEM: {p.info['memory_percent']:.1f}%)")
            except:
                pass
        return {"status": "success", "output": "Top processes:\n" + "\n".join(procs)}
    except ImportError:
        return {"status": "error", "output": "psutil not installed"}

async def get_uptime() -> Dict[str, Any]:
    try:
        import psutil
        boot = psutil.boot_time()
        import time
        uptime = time.time() - boot
        hours = int(uptime // 3600)
        mins = int((uptime % 3600) // 60)
        return {"status": "success", "output": f"System uptime: {hours}h {mins}m"}
    except:
        return await execute_shell("uptime", "Check uptime")

async def get_network_info() -> Dict[str, Any]:
    try:
        import psutil
        info = []
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family.name == 'AF_INET':
                    info.append(f"{iface}: {addr.address}")
        if not info:
            return {"status": "success", "output": "No active network interfaces"}
        return {"status": "success", "output": "Network interfaces:\n" + "\n".join(info)}
    except:
        return await execute_shell("ip addr", "Check network")

async def docker_ps() -> Dict[str, Any]:
    return await execute_shell("docker ps -a", "List containers")

async def docker_logs(container: str, lines: int = 100) -> Dict[str, Any]:
    return await execute_shell(f"docker logs --tail {lines} {container}", f"Get logs for {container}")

async def git_status(repo_path: str = ".") -> Dict[str, Any]:
    return await execute_shell(f"cd {repo_path} && git status", "Git status")

async def git_pull(repo_path: str = ".") -> Dict[str, Any]:
    return await execute_shell(f"cd {repo_path} && git pull", "Git pull")

async def download_file(url: str, path: str = "/tmp/") -> Dict[str, Any]:
    try:
        import requests
        import os
        from urllib.parse import urlparse
        
        filename = os.path.join(path, os.path.basename(urlparse(url).path) or "download")
        os.makedirs(path, exist_ok=True)
        
        resp = requests.get(url, timeout=30, stream=True)
        if resp.ok:
            with open(filename, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            return {"status": "success", "output": f"Downloaded to {filename}"}
        return {"status": "error", "output": f"Download failed: {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "output": str(e)}

async def systemctl(action: str, service: str) -> Dict[str, Any]:
    if not service:
        return {"status": "error", "output": "Service name required"}
    allowed = ["start", "stop", "restart", "status", "enable", "disable"]
    if action not in allowed:
        return {"status": "error", "output": f"Invalid action. Use: {allowed}"}
    return await execute_shell(f"sudo systemctl {action} {service}", f"{action} {service}")

async def pip_install(package: str) -> Dict[str, Any]:
    if not package:
        return {"status": "error", "output": "Package name required"}
    return await execute_shell(f"pip install {package}", f"Install {package}")

async def get_ip() -> Dict[str, Any]:
    try:
        import requests
        resp = requests.get("https://api.ipify.org", timeout=5)
        return {"status": "success", "output": f"Public IP: {resp.text}"}
    except:
        return {"status": "error", "output": "Failed to get IP"}

async def file_list(path: str = ".") -> Dict[str, Any]:
    """List files in directory"""
    try:
        import os
        items = os.listdir(path)
        output = f"Files in {path}:\n"
        for item in items:
            full_path = os.path.join(path, item)
            size = os.path.getsize(full_path) if os.path.isfile(full_path) else 0
            output += f"  {item} {'(dir)' if os.path.isdir(full_path) else f'({size} bytes)'}\n"
        return {"status": "success", "output": output}
    except Exception as e:
        return {"status": "error", "output": f"Error listing files: {str(e)}"}

async def file_delete(path: str) -> Dict[str, Any]:
    """Delete a file"""
    try:
        import os
        if not os.path.exists(path):
            return {"status": "error", "output": "File not found"}
        os.remove(path)
        return {"status": "success", "output": f"Deleted: {path}"}
    except Exception as e:
        return {"status": "error", "output": f"Error deleting file: {str(e)}"}

async def docker_stats() -> Dict[str, Any]:
    """Get Docker container stats"""
    try:
        result = await execute_shell("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.Status}}'", "Docker stats")
        return result
    except Exception as e:
        return {"status": "error", "output": f"Docker error: {str(e)}"}

async def auto_deploy(source_path: str, dest_path: str = "/var/www/html") -> Dict[str, Any]:
    """Auto-deploy files to web server directory"""
    try:
        # Check if destination exists
        check = await execute_shell(f"ls -la {dest_path}", "Check dest")
        if check.get("status") == "error":
            # Try to create the directory
            await execute_shell(f"sudo mkdir -p {dest_path}", "Create dest dir")
        
        # Copy files
        result = await execute_shell(f"sudo cp -r {source_path}/* {dest_path}/", "Deploy files")
        return result
    except Exception as e:
        return {"status": "error", "output": f"Deploy error: {str(e)}"}

async def create_background_task(name: str, action: str, notify_via: str, notify_target: str) -> Dict[str, Any]:
    agent_id = f"task_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        from database import create_sub_agent
        create_sub_agent(db, agent_id, name, action)
    finally:
        db.close()
    
    sub_agents[agent_id] = {
        "name": name, 
        "task": action, 
        "status": "running",
        "started": datetime.utcnow(),
        "notify_via": notify_via,
        "notify_target": notify_target
    }
    
    asyncio.create_task(run_ai_task(agent_id, name, action, notify_via, notify_target))
    
    return {
        "status": "success",
        "output": f"Task '{name}' started! I'll notify you when it's done.",
        "task_id": agent_id
    }

async def run_ai_task(agent_id: str, name: str, action: str, notify_via: str, notify_target: str):
    result_text = ""
    status = "completed"
    
    action_lower = action.lower()
    
    if "research" in action_lower or "search" in action_lower:
        query = action.replace("research", "").replace("search", "").strip()
        if not query:
            query = name
        result = await web_search(query, 5)
        result_text = f"Research results for '{query}':\n\n{result.get('output', 'No results')}"
        
    elif "download" in action_lower:
        result_text = f"Download task '{name}' - use web UI to provide URL"
        status = "pending"
        
    elif "analyze" in action_lower or "check" in action_lower:
        result = await get_system_stats()
        result_text = f"Analysis of '{name}':\n\n{result.get('output', 'Done')}"
        
    else:
        result = await web_search(action, 5)
        result_text = f"Task '{name}' results:\n\n{result.get('output', 'Done')}"
    
    db = SessionLocal()
    try:
        from database import update_sub_agent
        update_sub_agent(db, agent_id, status, result_text[:1000])
    finally:
        db.close()
    
    if notify_via == "telegram" and notify_target:
        await send_telegram_message(notify_target, f"✅ Task '{name}' completed!\n\n{result_text[:1000]}")
    elif notify_via == "file" and notify_target:
        await file_write(notify_target, result_text)

async def schedule_telegram_message(chat_id: str, message: str, delay_seconds: int) -> Dict[str, Any]:
    async def send_later():
        await asyncio.sleep(delay_seconds)
        await send_telegram_message(chat_id, f"🔔 Reminder: {message}")
    
    asyncio.create_task(send_later())
    minutes = delay_seconds // 60
    return {"status": "success", "output": f"⏰ Reminder set for {minutes} minute(s): \"{message}\""}

TOOL_HANDLERS = {
    "schedule_message": lambda p: schedule_telegram_message(p.get("chat_id", ""), p.get("message", ""), p.get("delay_minutes", 5) * 60),
    "autonomous_task_create": lambda p: create_autonomous_task_helper(p.get("name", ""), p.get("task_type", "custom"), p.get("schedule", ""), p.get("custom_data", "")),
    "autonomous_task_list": lambda p: list_autonomous_tasks_helper(),
    "autonomous_task_trigger": lambda p: trigger_task_now_helper(p.get("task_id", 0)),
    "cross_platform_search": lambda p: search_cross_platform_helper(p.get("query", ""), p.get("platforms")),
    "connection_status": lambda p: get_connection_status_helper(),
}

async def create_autonomous_task_helper(name: str, task_type: str, schedule: str, custom_data: str):
    from proactive_scheduler import create_autonomous_task
    return await create_autonomous_task(name, task_type, schedule, custom_data)

async def list_autonomous_tasks_helper():
    from proactive_scheduler import list_autonomous_tasks
    return await list_autonomous_tasks()

async def trigger_task_now_helper(task_id: int):
    from proactive_scheduler import trigger_task_now
    return await trigger_task_now(task_id)

async def search_cross_platform_helper(query: str, platforms: list):
    from agent_brain import search_cross_platform
    return search_cross_platform(query, platforms)

def get_connection_status_helper():
    from connection_manager import get_connection_status
    return get_connection_status()

async def execute_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    logger.info(f"🦊 [FoxxGent] Executing tool: {tool_name}")
    
    if tool_name in TOOL_HANDLERS:
        return await TOOL_HANDLERS[tool_name](params)
    
    if tool_name == "schedule_message":
        chat_id = params.get("chat_id", "")
        message = params.get("message", "")
        delay_minutes = params.get("delay_minutes", 5)
        delay_seconds = delay_minutes * 60
        return await schedule_telegram_message(chat_id, message, delay_seconds)
    
    if tool_name == "autonomous_task_create":
        from proactive_scheduler import create_autonomous_task
        return await create_autonomous_task(
            params.get("name", ""),
            params.get("task_type", "custom"),
            params.get("schedule", ""),
            params.get("custom_data", "")
        )
    
    if tool_name == "autonomous_task_list":
        from proactive_scheduler import list_autonomous_tasks
        return await list_autonomous_tasks()
    
    if tool_name == "autonomous_task_trigger":
        from proactive_scheduler import trigger_task_now
        return await trigger_task_now(params.get("task_id", 0))
    
    if tool_name == "cross_platform_search":
        from agent_brain import search_cross_platform
        return search_cross_platform(params.get("query", ""), params.get("platforms"))
    
    if tool_name.startswith("connect_app"):
        from connection_manager import connect_app
        return await connect_app(params.get("app_id", ""), params.get("credentials", {}), params.get("config"))
    
    if tool_name == "disconnect_app":
        from connection_manager import disconnect_app
        return await disconnect_app(params.get("app_id", ""))
    
    if tool_name == "connection_status":
        from connection_manager import get_connection_status
        return get_connection_status()
    
    if "_" in tool_name and any(tool_name.startswith(connected_app) for connected_app in ["github_", "notion_", "slack_", "trello_", "gmail_", "google_calendar_", "discord_", "telegram_", "hubspot_", "openai_", "sendgrid_", "stripe_", "airtable_", "jira_", "linear_", "asana_", "todoist_", "clickup_", "monday_", "shopify_", "mailchimp_", "calendly_"]):
        from connection_manager import execute_connection_tool
        return await execute_connection_tool(tool_name, params)
    
    # Omni-Connector tools
    from omni_connector import execute_omni_tool
    
    if tool_name.startswith("gmail_") or tool_name.startswith("calendar_") or tool_name.startswith("notion_") or tool_name.startswith("web_") or tool_name in ("omni_connect", "omni_status"):
        return await execute_omni_tool(tool_name, params)
    
    # Terminal Execution
    if tool_name in ("shell", "terminal_exec", "TERMINAL_EXEC"):
        command = params.get("command", "")
        description = params.get("description", "")
        async_mode = params.get("async", False)
        return await execute_shell(command, description, async_mode)
    
    # File Operations
    elif tool_name in ("file_read", "FILE_OPERATIONS_read"):
        path = params.get("path", "")
        return await file_read(path)
    
    elif tool_name in ("file_write", "FILE_OPERATIONS_write"):
        path = params.get("path", "")
        content = params.get("content", "")
        return await file_write(path, content)
    
    elif tool_name in ("file_list", "FILE_OPERATIONS_list"):
        path = params.get("path", ".")
        return await file_list(path)
    
    elif tool_name in ("file_delete", "FILE_OPERATIONS_delete"):
        path = params.get("path", "")
        return await file_delete(path)
    
    # System Monitor
    elif tool_name in ("system_stats", "SYS_MONITOR", "sys_monitor"):
        return await get_system_stats()
    
    # Docker Hooks
    elif tool_name in ("docker_stats", "DOCKER_HOOKS_stats"):
        return await docker_stats()
    
    elif tool_name == "cron_create":
        name = params.get("name", "")
        command = params.get("command", "")
        schedule = params.get("schedule", "")
        return await cron_create(name, command, schedule)
    
    elif tool_name == "cron_list":
        return await cron_list()
    
    elif tool_name == "cron_delete":
        task_id = params.get("task_id", 0)
        return await cron_delete(task_id)
    
    elif tool_name == "web_search":
        query = params.get("query", "")
        num_results = params.get("num_results", 5)
        return await web_search(query, num_results)
    
    elif tool_name == "search":
        query = params.get("query", "") or params.get("q", "") or params.get("text", "")
        return await web_search(query, 5)
    
    elif tool_name == "send_telegram":
        chat_id = params.get("chat_id", "")
        text = params.get("text", "")
        return await send_telegram_message(chat_id, text)
    
    elif tool_name == "get_settings":
        key = params.get("key", "")
        if not key:
            return {"status": "error", "output": "No key provided"}
        db = SessionLocal()
        try:
            from database import get_setting
            value = get_setting(db, key)
            if value:
                return {"status": "success", "output": value}
            else:
                return {"status": "error", "output": f"Setting '{key}' not found"}
        finally:
            db.close()
    
    elif tool_name == "get_processes":
        return await get_processes()
    
    elif tool_name == "get_uptime":
        return await get_uptime()
    
    elif tool_name == "get_network_info":
        return await get_network_info()
    
    elif tool_name == "docker_ps":
        return await docker_ps()
    
    elif tool_name == "docker_logs":
        container = params.get("container", "")
        lines = params.get("lines", 100)
        return await docker_logs(container, lines)
    
    elif tool_name == "git_status":
        repo_path = params.get("path", ".")
        return await git_status(repo_path)
    
    elif tool_name == "git_pull":
        repo_path = params.get("path", ".")
        return await git_pull(repo_path)
    
    elif tool_name == "download_file":
        url = params.get("url", "")
        dest = params.get("path", "/tmp/")
        return await download_file(url, dest)
    
    elif tool_name == "systemctl":
        action = params.get("action", "status")
        service = params.get("service", "")
        return await systemctl(action, service)
    
    elif tool_name == "pip_install":
        package = params.get("package", "")
        return await pip_install(package)
    
    elif tool_name == "get_ip":
        return await get_ip()
    
    elif tool_name == "task_create":
        name = params.get("name", "")
        action = params.get("action", "")
        notify_via = params.get("notify_via", "telegram")
        notify_target = params.get("notify_target", "")
        return await create_background_task(name, action, notify_via, notify_target)
    
    elif tool_name == "auto_deploy":
        source = params.get("source", "")
        dest = params.get("dest", "/var/www/html")
        return await auto_deploy(source, dest)
    
    return {"status": "error", "output": f"Unknown tool: {tool_name}"}
