import os
import json
import base64
import hashlib
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

Base = declarative_base()

def get_encryption_key():
    key = os.getenv("FOXXGENT_SECRET_KEY") or os.getenv("SECRET_KEY")
    if not key:
        key = "foxxgent-default-key-change-in-production"
    return hashlib.sha256(key.encode()).digest()[:32]

def encrypt_credential(data: str) -> str:
    from cryptography.fernet import Fernet
    try:
        key = get_encryption_key()
        f = Fernet(base64.urlsafe_b64encode(key))
        return f.encrypt(data.encode()).decode()
    except ImportError:
        return base64.b64encode(data.encode()).decode()

def decrypt_credential(encrypted: str) -> str:
    from cryptography.fernet import Fernet
    try:
        key = get_encryption_key()
        f = Fernet(base64.urlsafe_b64encode(key))
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        try:
            return base64.b64decode(encrypted.encode()).decode()
        except:
            return encrypted

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True)
    source = Column(String(20))  # "web" or "telegram"
    user_id = Column(String(100))
    role = Column(String(20))  # "user" or "assistant"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True)
    key = Column(String(100))
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SubAgent(Base):
    __tablename__ = "sub_agents"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100))
    status = Column(String(20), default="idle")  # idle, running, completed, failed
    task = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    result = Column(Text)

class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    
    id = Column(Integer, primary_key=True)
    sub_agent_id = Column(String(50))
    command = Column(Text)
    output = Column(Text)
    exit_code = Column(Integer)
    executed_at = Column(DateTime, default=datetime.utcnow)

class CronTask(Base):
    __tablename__ = "cron_tasks"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    command = Column(Text)
    schedule = Column(String(100))  # cron expression
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class PairedDevice(Base):
    __tablename__ = "paired_devices"
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(String(50), unique=True)
    username = Column(String(100))
    first_name = Column(String(100))
    paired_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime)
    enabled = Column(Boolean, default=True)

class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlatformData(Base):
    __tablename__ = "platform_data"
    
    id = Column(Integer, primary_key=True)
    platform = Column(String(50))  # gmail, calendar, notion, telegram, etc.
    data_type = Column(String(50))  # email, event, page, message, etc.
    external_id = Column(String(200))  # External platform ID
    title = Column(Text)
    content = Column(Text)
    meta_json = Column(Text)  # JSON string for additional data
    synced_at = Column(DateTime, default=datetime.utcnow)
    indexed = Column(Boolean, default=False)


class CrossRefData(Base):
    __tablename__ = "cross_ref_data"
    
    id = Column(Integer, primary_key=True)
    query_hash = Column(String(64))  # Hash of search query for correlation
    source_platform = Column(String(50))
    source_id = Column(String(200))
    result_data = Column(Text)  # JSON string of correlated data
    created_at = Column(DateTime, default=datetime.utcnow)


class VibeProfile(Base):
    __tablename__ = "vibe_profiles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100))
    time_range_start = Column(Integer)  # Hour 0-23
    time_range_end = Column(Integer)
    response_length = Column(String(20))  # concise, normal, detailed
    tone = Column(String(20))  # formal, casual, neutral
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BackgroundTask(Base):
    __tablename__ = "background_tasks"
    
    id = Column(Integer, primary_key=True)
    task_type = Column(String(50))
    name = Column(String(100))
    schedule = Column(String(100))
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    status = Column(String(20))
    result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class AppConnection(Base):
    __tablename__ = "app_connections"
    
    id = Column(Integer, primary_key=True)
    app_id = Column(String(50), unique=True)
    app_name = Column(String(100))
    category = Column(String(50))
    status = Column(String(20), default="disconnected")  # connected, error, disconnected
    auth_type = Column(String(20))
    credentials_encrypted = Column(Text)  # Encrypted JSON credentials
    config = Column(Text)  # JSON config
    connected_at = Column(DateTime)
    last_used = Column(DateTime)
    error_message = Column(Text)
    enabled = Column(Boolean, default=True)


class ConnectionSkill(Base):
    __tablename__ = "connection_skills"
    
    id = Column(Integer, primary_key=True)
    app_id = Column(String(50))
    skill_name = Column(String(100))
    skill_description = Column(Text)
    parameters = Column(Text)  # JSON schema
    enabled = Column(Boolean, default=True)


class AIMemory(Base):
    __tablename__ = "ai_memory"
    
    id = Column(Integer, primary_key=True)
    memory_type = Column(String(50))  # "fact", "preference", "important", "context"
    key = Column(String(200))
    value = Column(Text)
    user_id = Column(String(100), default="global")
    importance = Column(Integer, default=1)  # 1-5
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TokenUsage(Base):
    __tablename__ = "token_usage"
    
    id = Column(Integer, primary_key=True)
    model = Column(String(100))
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    user_id = Column(String(100), default="global")
    timestamp = Column(DateTime, default=datetime.utcnow)


def save_memory(db: Session, memory_type: str, key: str, value: str, user_id: str = "global", importance: int = 1):
    existing = db.query(AIMemory).filter_by(key=key, user_id=user_id).first()
    if existing:
        existing.value = value
        existing.memory_type = memory_type
        existing.importance = importance
        existing.updated_at = datetime.utcnow()
    else:
        mem = AIMemory(
            memory_type=memory_type,
            key=key,
            value=value,
            user_id=user_id,
            importance=importance
        )
        db.add(mem)
    db.commit()


def get_memory(db: Session, key: str, user_id: str = "global") -> Optional[AIMemory]:
    return db.query(AIMemory).filter_by(key=key, user_id=user_id).first()


def get_all_memory(db: Session, user_id: str = "global") -> list:
    return db.query(AIMemory).filter_by(user_id=user_id).order_by(AIMemory.importance.desc(), AIMemory.updated_at.desc()).all()


def get_memories_by_type(db: Session, memory_type: str, user_id: str = "global") -> list:
    return db.query(AIMemory).filter_by(memory_type=memory_type, user_id=user_id).order_by(AIMemory.importance.desc()).all()


def search_memory(db: Session, query: str, user_id: str = "global") -> list:
    return db.query(AIMemory).filter(
        AIMemory.user_id == user_id,
        (AIMemory.key.ilike(f"%{query}%")) | (AIMemory.value.ilike(f"%{query}%"))
    ).order_by(AIMemory.importance.desc()).all()


def delete_memory(db: Session, key: str, user_id: str = "global") -> bool:
    mem = db.query(AIMemory).filter_by(key=key, user_id=user_id).first()
    if mem:
        db.delete(mem)
        db.commit()
        return True
    return False


DB_PATH = os.getenv("DB_PATH", "foxxgent.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_message(db: Session, source: str, user_id: str, role: str, content: str):
    msg = ChatMessage(source=source, user_id=user_id, role=role, content=content)
    db.add(msg)
    db.commit()

def get_chat_history(db: Session, user_id: str, limit: int = 50):
    return db.query(ChatMessage).filter(
        ChatMessage.user_id == user_id
    ).order_by(ChatMessage.timestamp.desc()).limit(limit).all()[::-1]

def save_preference(db: Session, user_id: str, key: str, value: str):
    pref = db.query(UserPreference).filter_by(user_id=user_id, key=key).first()
    if pref:
        pref.value = value
    else:
        pref = UserPreference(user_id=user_id, key=key, value=value)
        db.add(pref)
    db.commit()

def get_preference(db: Session, user_id: str, key: str) -> Optional[str]:
    pref = db.query(UserPreference).filter_by(user_id=user_id, key=key).first()
    return pref.value if pref else None

def create_sub_agent(db: Session, agent_id: str, name: str, task: str):
    agent = SubAgent(
        id=agent_id,
        name=name,
        task=task,
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(agent)
    db.commit()
    return agent

def update_sub_agent(db: Session, agent_id: str, status: str, result: Optional[str] = None):
    agent = db.query(SubAgent).filter_by(id=agent_id).first()
    if agent:
        agent.status = status
        if result:
            agent.result = result
        if status in ("completed", "failed"):
            agent.finished_at = datetime.utcnow()
        db.commit()

def get_sub_agents(db: Session):
    return db.query(SubAgent).order_by(SubAgent.started_at.desc()).all()

def log_execution(db: Session, sub_agent_id: str, command: str, output: str, exit_code: int):
    log = ExecutionLog(
        sub_agent_id=sub_agent_id,
        command=command,
        output=output,
        exit_code=exit_code
    )
    db.add(log)
    db.commit()

def save_cron_task(db: Session, name: str, command: str, schedule: str):
    task = CronTask(name=name, command=command, schedule=schedule)
    db.add(task)
    db.commit()
    return task

def get_cron_tasks(db: Session):
    return db.query(CronTask).all()

def delete_cron_task(db: Session, task_id: int):
    task = db.query(CronTask).filter_by(id=task_id).first()
    if task:
        db.delete(task)
        db.commit()

def delete_sub_agent(agent_id):
    db = SessionLocal()
    try:
        agent = db.query(SubAgent).filter_by(id=str(agent_id)).first()
        if agent:
            db.delete(agent)
            db.commit()
            return True
        return False
    finally:
        db.close()

def save_paired_device(db: Session, chat_id: str, username: str, first_name: str):
    device = db.query(PairedDevice).filter_by(chat_id=chat_id).first()
    if device:
        device.username = username
        device.first_name = first_name
        device.last_seen = datetime.utcnow()
    else:
        device = PairedDevice(chat_id=chat_id, username=username, first_name=first_name)
        db.add(device)
    db.commit()

def get_paired_devices(db: Session):
    return db.query(PairedDevice).all()

def update_paired_device(db: Session, chat_id: str, enabled: bool):
    device = db.query(PairedDevice).filter_by(chat_id=chat_id).first()
    if device:
        device.enabled = enabled
        db.commit()

def save_setting(db: Session, key: str, value: str):
    setting = db.query(Settings).filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = Settings(key=key, value=value)
        db.add(setting)
    db.commit()

def get_setting(db: Session, key: str) -> Optional[str]:
    setting = db.query(Settings).filter_by(key=key).first()
    return setting.value if setting else None

def get_all_settings(db: Session):
    settings = db.query(Settings).all()
    return {s.key: s.value for s in settings}


def save_platform_data(db: Session, platform: str, data_type: str, external_id: str, title: str, content: str, metadata: str = None):
    data = PlatformData(
        platform=platform,
        data_type=data_type,
        external_id=external_id,
        title=title,
        content=content,
        metadata=metadata
    )
    db.add(data)
    db.commit()
    return data


def search_platform_data(db: Session, query: str, platforms: list = None, limit: int = 20):
    q = db.query(PlatformData)
    if platforms:
        q = q.filter(PlatformData.platform.in_(platforms))
    q = q.filter(
        (PlatformData.title.contains(query)) |
        (PlatformData.content.contains(query))
    ).limit(limit)
    return q.all()


def get_platform_data_by_id(db: Session, platform: str, external_id: str):
    return db.query(PlatformData).filter_by(platform=platform, external_id=external_id).first()


def save_cross_ref(db: Session, query_hash: str, source_platform: str, source_id: str, result_data: str):
    ref = CrossRefData(
        query_hash=query_hash,
        source_platform=source_platform,
        source_id=source_id,
        result_data=result_data
    )
    db.add(ref)
    db.commit()
    return ref


def get_cross_ref(db: Session, query_hash: str):
    return db.query(CrossRefData).filter_by(query_hash=query_hash).order_by(CrossRefData.created_at.desc()).first()


def delete_old_cross_refs(db: Session, hours: int = 24):
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    deleted = db.query(CrossRefData).filter(CrossRefData.created_at < cutoff).delete()
    db.commit()
    return deleted


def get_cross_refs_by_platform(db: Session, source_platform: str, limit: int = 50):
    return db.query(CrossRefData).filter_by(source_platform=source_platform).order_by(CrossRefData.created_at.desc()).limit(limit).all()


def save_vibe_profile(db: Session, user_id: str, time_start: int, time_end: int, response_length: str, tone: str):
    profile = VibeProfile(
        user_id=user_id,
        time_range_start=time_start,
        time_range_end=time_end,
        response_length=response_length,
        tone=tone
    )
    db.add(profile)
    db.commit()
    return profile


def get_vibe_for_time(db: Session, user_id: str, hour: int):
    profiles = db.query(VibeProfile).filter_by(user_id=user_id, enabled=True).all()
    for p in profiles:
        if p.time_range_start <= hour < p.time_range_end:
            return {"length": p.response_length, "tone": p.tone}
    return {"length": "normal", "tone": "neutral"}


def save_background_task(db: Session, task_type: str, name: str, schedule: str):
    from croniter import croniter
    task = BackgroundTask(
        task_type=task_type,
        name=name,
        schedule=schedule,
        status="pending"
    )
    base = datetime.utcnow()
    cron = croniter(schedule, base)
    task.next_run = cron.get_next(datetime)
    db.add(task)
    db.commit()
    return task


def get_background_tasks(db: Session):
    return db.query(BackgroundTask).order_by(BackgroundTask.next_run.asc()).all()


def update_background_task(db: Session, task_id: int, status: str, result: str = None):
    task = db.query(BackgroundTask).filter_by(id=task_id).first()
    if task:
        task.status = status
        task.last_run = datetime.utcnow()
        if result:
            task.result = result
        if status == "completed" or status == "failed":
            from croniter import croniter
            cron = croniter(task.schedule, datetime.utcnow())
            task.next_run = cron.get_next(datetime)
        db.commit()
    return task


def save_app_connection(db: Session, app_id: str, app_name: str, category: str, auth_type: str, credentials: str, config: str = None):
    encrypted = encrypt_credential(credentials)
    existing = db.query(AppConnection).filter_by(app_id=app_id).first()
    if existing:
        existing.credentials_encrypted = encrypted
        existing.config = config
        existing.status = "connected"
        existing.connected_at = datetime.utcnow()
        existing.error_message = None
    else:
        conn = AppConnection(
            app_id=app_id,
            app_name=app_name,
            category=category,
            auth_type=auth_type,
            credentials_encrypted=encrypted,
            config=config,
            status="connected",
            connected_at=datetime.utcnow()
        )
        db.add(conn)
    db.commit()


def get_app_connection_credentials(db: Session, app_id: str) -> Optional[str]:
    conn = db.query(AppConnection).filter_by(app_id=app_id).first()
    if conn and conn.credentials_encrypted:
        return decrypt_credential(conn.credentials_encrypted)
    return None


def get_app_connection(db: Session, app_id: str):
    return db.query(AppConnection).filter_by(app_id=app_id).first()


def get_all_connections(db: Session):
    return db.query(AppConnection).all()


def delete_app_connection(db: Session, app_id: str):
    conn = db.query(AppConnection).filter_by(app_id=app_id).first()
    if conn:
        db.delete(conn)
        db.commit()
        return True
    return False


def update_connection_status(db: Session, app_id: str, status: str, error: str = None):
    conn = db.query(AppConnection).filter_by(app_id=app_id).first()
    if conn:
        conn.status = status
        conn.error_message = error
        if status == "connected":
            conn.last_used = datetime.utcnow()
        db.commit()


def save_connection_skill(db: Session, app_id: str, skill_name: str, description: str, parameters: str):
    skill = db.query(ConnectionSkill).filter_by(app_id=app_id, skill_name=skill_name).first()
    if skill:
        skill.skill_description = description
        skill.parameters = parameters
    else:
        skill = ConnectionSkill(
            app_id=app_id,
            skill_name=skill_name,
            skill_description=description,
            parameters=parameters
        )
        db.add(skill)
    db.commit()


def get_connection_skills(db: Session, app_id: str = None):
    if app_id:
        return db.query(ConnectionSkill).filter_by(app_id=app_id, enabled=True).all()
    return db.query(ConnectionSkill).filter_by(enabled=True).all()


def save_token_usage(db: Session, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int, user_id: str = "global", cost_usd: float = 0.0):
    usage = TokenUsage(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        user_id=user_id
    )
    db.add(usage)
    db.commit()
    return usage


def get_token_usage_summary(db: Session, user_id: str = "global", days: int = 30):
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)
    usages = db.query(TokenUsage).filter(
        TokenUsage.user_id == user_id,
        TokenUsage.timestamp >= since
    ).all()
    
    total_prompt = sum(u.prompt_tokens for u in usages)
    total_completion = sum(u.completion_tokens for u in usages)
    total = sum(u.total_tokens for u in usages)
    total_cost = sum(u.cost_usd for u in usages)
    request_count = len(usages)
    
    return {
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total,
        "total_cost_usd": round(total_cost, 6),
        "request_count": request_count,
        "period_days": days
    }


def get_all_time_token_usage(db: Session):
    usages = db.query(TokenUsage).all()
    total_prompt = sum(u.prompt_tokens for u in usages)
    total_completion = sum(u.completion_tokens for u in usages)
    total = sum(u.total_tokens for u in usages)
    total_cost = sum(u.cost_usd for u in usages)
    request_count = len(usages)
    
    return {
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total,
        "total_cost_usd": round(total_cost, 6),
        "request_count": request_count
    }
