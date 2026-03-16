import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from croniter import croniter

logger = logging.getLogger("foxxgent")

task_handlers = {}


class ProactiveScheduler:
    def __init__(self):
        self.running = False
        self.check_interval = 60
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
    
    async def start(self):
        self.running = True
        asyncio.create_task(self._scheduler_loop())
        logger.info("Proactive scheduler started")
    
    async def stop(self):
        self.running = False
        logger.info("Proactive scheduler stopped")
    
    async def _scheduler_loop(self):
        while self.running:
            try:
                await self._check_and_run_tasks()
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            await asyncio.sleep(self.check_interval)
    
    async def _check_and_run_tasks(self):
        from database import SessionLocal, get_background_tasks, update_background_task
        
        db = SessionLocal()
        try:
            tasks = get_background_tasks(db)
            now = datetime.utcnow()
            
            for task in tasks:
                if task.next_run and task.next_run <= now and task.status != "running":
                    logger.info(f"Triggering autonomous task: {task.name}")
                    update_background_task(db, task.id, "running")
                    
                    asyncio.create_task(self._run_task(task))
        finally:
            db.close()
    
    async def _run_task(self, task):
        from database import SessionLocal, update_background_task
        
        db = SessionLocal()
        try:
            result = f"Task {task.name} executed"
            
            if task.task_type == "morning_briefing":
                result = await self._morning_briefing()
            elif task.task_type == "system_check":
                result = await self._system_check()
            elif task.task_type == "email_sync":
                result = await self._email_sync()
            elif task.task_type == "calendar_check":
                result = await self._calendar_check()
            elif task.task_type == "custom":
                result = await self._run_custom_task(task.name, task.result)
            else:
                result = f"Unknown task type: {task.task_type}"
            
            update_background_task(db, task.id, "completed", result[:500])
            await self._broadcast_task_status(task.name, "completed", result)
            
        except Exception as e:
            logger.error(f"Task {task.name} failed: {e}")
            update_background_task(db, task.id, "failed", str(e)[:500])
            await self._broadcast_task_status(task.name, "failed", str(e))
        finally:
            db.close()
    
    async def _morning_briefing(self) -> str:
        lines = ["☀️ Morning Briefing"]
        
        from exec_tools import get_system_stats
        stats = await get_system_stats()
        if stats.get("status") == "success":
            s = stats.get("stats", {})
            lines.append(f"CPU: {s.get('cpu_percent', 0):.1f}%")
            lines.append(f"RAM: {s.get('memory_percent', 0):.1f}%")
        
        from omni_connector import omni_connector
        if omni_connector.connected.get("calendar"):
            result = await omni_connector.calendar.today_events()
            if result.get("status") == "success":
                events = result.get("events", [])
                if events:
                    lines.append(f"📅 {len(events)} events today")
                else:
                    lines.append("📅 No events today")
        
        return "\n".join(lines)
    
    async def _system_check(self) -> str:
        from exec_tools import get_system_stats, get_processes
        stats = await get_system_stats()
        procs = await get_processes()
        return f"System check complete. Stats: {stats.get('status')}"
    
    async def _email_sync(self) -> str:
        from omni_connector import omni_connector
        if omni_connector.connected.get("gmail"):
            result = await omni_connector.gmail.list_emails(5)
            return f"Synced {len(result.get('emails', []))} emails"
        return "Gmail not connected"
    
    async def _calendar_check(self) -> str:
        from omni_connector import omni_connector
        if omni_connector.connected.get("calendar"):
            result = await omni_connector.calendar.today_events()
            events = result.get("events", [])
            return f"Found {len(events)} events"
        return "Calendar not connected"
    
    async def _run_custom_task(self, name: str, command: str) -> str:
        from exec_tools import execute_shell
        result = await execute_shell(command, f"Scheduled task: {name}")
        return result.get("output", "Done")
    
    async def _broadcast_task_status(self, task_name: str, status: str, result: str):
        try:
            import httpx
            await httpx.AsyncClient().post(
                "http://127.0.0.1:8000/api/logs/add",
                json={"level": "INFO", "message": f"Auto-task {task_name}: {status}"}
            )
        except:
            pass
    
    def register_handler(self, task_type: str, handler):
        task_handlers[task_type] = handler
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        return list(self.active_tasks.values())
    
    def get_task_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "active_tasks": len(self.active_tasks),
            "tasks": list(self.active_tasks.values())
        }


scheduler = ProactiveScheduler()


async def create_autonomous_task(name: str, task_type: str, schedule: str, custom_data: str = "") -> Dict[str, Any]:
    from database import SessionLocal, save_background_task
    from croniter import croniter
    
    db = SessionLocal()
    try:
        task = save_background_task(db, task_type, name, schedule)
        
        return {
            "status": "success",
            "output": f"Autonomous task '{name}' created. Next run: {task.next_run}",
            "task_id": task.id,
            "next_run": task.next_run.isoformat()
        }
    finally:
        db.close()


async def list_autonomous_tasks() -> Dict[str, Any]:
    from database import SessionLocal, get_background_tasks
    
    db = SessionLocal()
    try:
        tasks = get_background_tasks(db)
        return {
            "status": "success",
            "tasks": [{
                "id": t.id,
                "name": t.name,
                "type": t.task_type,
                "schedule": t.schedule,
                "status": t.status,
                "next_run": t.next_run.isoformat() if t.next_run else None,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "result": t.result
            } for t in tasks]
        }
    finally:
        db.close()


async def delete_autonomous_task(task_id: int) -> Dict[str, Any]:
    from database import SessionLocal, BackgroundTask
    
    db = SessionLocal()
    try:
        task = db.query(BackgroundTask).filter_by(id=task_id).first()
        if task:
            db.delete(task)
            db.commit()
            return {"status": "success", "output": f"Task {task_id} deleted"}
        return {"status": "error", "output": "Task not found"}
    finally:
        db.close()


async def trigger_task_now(task_id: int) -> Dict[str, Any]:
    from database import SessionLocal, BackgroundTask, update_background_task
    
    db = SessionLocal()
    try:
        task = db.query(BackgroundTask).filter_by(id=task_id).first()
        if task:
            update_background_task(db, task.id, "running")
            asyncio.create_task(scheduler._run_task(task))
            return {"status": "success", "output": f"Task {task.name} triggered"}
        return {"status": "error", "output": "Task not found"}
    finally:
        db.close()