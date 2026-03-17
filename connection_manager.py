import os
import json
import asyncio
import logging
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
import aiohttp

from dataclasses import asdict
from app_registry import APP_REGISTRY, get_app_config, get_apps_by_category, get_all_apps

logger = logging.getLogger("foxxgent")

_connection_cache: Dict[str, Any] = {}


class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, Any] = {}
    
    def _encrypt_credentials(self, data: str) -> str:
        key = os.getenv("CREDENTIALS_KEY", "default_dev_key_change_in_production")
        encoded = base64.b64encode(f"{key}:{data}".encode()).decode()
        return encoded
    
    def _decrypt_credentials(self, encrypted: str) -> Optional[Dict]:
        try:
            key = os.getenv("CREDENTIALS_KEY", "default_dev_key_change_in_production")
            decoded = base64.b64decode(encrypted.encode()).decode()
            if decoded.startswith(f"{key}:"):
                return json.loads(decoded[len(key)+1:])
        except:
            pass
        return None
    
    async def connect(self, app_id: str, credentials: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
        app_config = get_app_config(app_id)
        if not app_config:
            return {"status": "error", "output": f"Unknown app: {app_id}"}
        
        try:
            if app_config.auth_type == "oauth":
                result = await self._handle_oauth_connect(app_config, credentials, config)
            elif app_config.auth_type == "bearer":
                result = await self._handle_bearer_connect(app_config, credentials, config)
            elif app_config.auth_type == "api_key":
                result = await self._handle_api_key_connect(app_config, credentials, config)
            elif app_config.auth_type == "basic":
                result = await self._handle_basic_connect(app_config, credentials, config)
            elif app_config.auth_type == "jwt":
                result = await self._handle_jwt_connect(app_config, credentials, config)
            elif app_config.auth_type == "aws":
                result = await self._handle_aws_connect(app_config, credentials, config)
            elif app_config.auth_type == "connection_string":
                result = await self._handle_connection_string_connect(app_config, credentials, config)
            else:
                return {"status": "error", "output": f"Unsupported auth type: {app_config.auth_type}"}
            
            if result.get("status") == "success":
                self.connections[app_id] = {
                    "config": app_config,
                    "credentials": credentials,
                    "config_extra": config,
                    "connected_at": datetime.utcnow()
                }
                
                from database import SessionLocal, save_app_connection
                db = SessionLocal()
                try:
                    save_app_connection(
                        db, app_id, app_config.name, app_config.category,
                        app_config.auth_type,
                        self._encrypt_credentials(json.dumps(credentials)),
                        json.dumps(config) if config else None
                    )
                finally:
                    db.close()
                
                await self._generate_skills_for_app(app_id, app_config)
            
            return result
            
        except Exception as e:
            logger.error(f"Connection failed for {app_id}: {e}")
            return {"status": "error", "output": str(e)}
    
    async def _handle_oauth_connect(self, app_config, credentials: Dict, config: Dict) -> Dict[str, Any]:
        creds_path = credentials.get("credentials_path", "")
        if not os.path.exists(creds_path):
            return {"status": "error", "output": f"Credentials file not found: {creds_path}"}
        
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(creds_path, app_config.scopes)
            if not creds or not creds.valid:
                return {"status": "error", "output": "Invalid OAuth credentials"}
            return {"status": "success", "output": "OAuth connection established"}
        except ImportError:
            return {"status": "error", "output": "google-auth library not installed"}
        except Exception as e:
            return {"status": "error", "output": f"OAuth error: {str(e)}"}
    
    async def _handle_bearer_connect(self, app_config, credentials: Dict, config: Dict) -> Dict[str, Any]:
        token = credentials.get("access_token") or credentials.get("api_key") or credentials.get("api_token") or credentials.get("token")
        if not token:
            return {"status": "error", "output": "Access token required"}
        
        if app_config.id == "notion":
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.notion.com/v1/users/me",
                    headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
                )
                if resp.status_code == 200:
                    return {"status": "success", "output": "Notion connected"}
                return {"status": "error", "output": f"Invalid token: {resp.text[:100]}"}
        
        return {"status": "success", "output": f"{app_config.name} connected with bearer token"}
    
    async def _handle_api_key_connect(self, app_config, credentials: Dict, config: Dict) -> Dict[str, Any]:
        api_key = credentials.get("api_key") or credentials.get("bot_token")
        if not api_key:
            return {"status": "error", "output": "API key required"}
        
        return {"status": "success", "output": f"{app_config.name} connected with API key"}
    
    async def _handle_basic_connect(self, app_config, credentials: Dict, config: Dict) -> Dict[str, Any]:
        if not credentials.get("email") or not credentials.get("api_token"):
            return {"status": "error", "output": "Email and API token required"}
        
        return {"status": "success", "output": f"{app_config.name} connected with basic auth"}
    
    async def _handle_jwt_connect(self, app_config, credentials: Dict, config: Dict) -> Dict[str, Any]:
        required = ["client_id", "client_secret"]
        for field in required:
            if not credentials.get(field):
                return {"status": "error", "output": f"{field} required"}
        
        return {"status": "success", "output": f"{app_config.name} connected with JWT auth"}
    
    async def _handle_aws_connect(self, app_config, credentials: Dict, config: Dict) -> Dict[str, Any]:
        required = ["access_key_id", "secret_access_key", "region"]
        for field in required:
            if not credentials.get(field):
                return {"status": "error", "output": f"{field} required"}
        
        return {"status": "success", "output": f"{app_config.name} connected to AWS {credentials.get('region')}"}
    
    async def _handle_connection_string_connect(self, app_config, credentials: Dict, config: Dict) -> Dict[str, Any]:
        conn_str = credentials.get("connection_string")
        if not conn_str:
            return {"status": "error", "output": "Connection string required"}
        
        return {"status": "success", "output": f"{app_config.name} connected"}
    
    async def disconnect(self, app_id: str) -> Dict[str, Any]:
        if app_id in self.connections:
            del self.connections[app_id]
        
        from database import SessionLocal, delete_app_connection
        db = SessionLocal()
        try:
            delete_app_connection(db, app_id)
        finally:
            db.close()
        
        return {"status": "success", "output": f"Disconnected from {app_id}"}
    
    def is_connected(self, app_id: str) -> bool:
        return app_id in self.connections
    
    def load_saved_connections(self):
        from database import SessionLocal, get_all_connections
        from app_registry import get_app_config as get_config
        db = SessionLocal()
        try:
            connections = get_all_connections(db)
            for conn in connections:
                if conn.status == "connected" and conn.enabled:
                    credentials = self._decrypt_credentials(conn.credentials_encrypted)
                    if credentials:
                        app_config = get_config(conn.app_id)
                        if app_config:
                            self.connections[conn.app_id] = {
                                "config": app_config,
                                "credentials": credentials,
                                "config_extra": json.loads(conn.config) if conn.config else {},
                                "connected_at": conn.connected_at
                            }
                            logger.info(f"Loaded saved connection: {conn.app_id}")
        finally:
            db.close()
    
    def get_connection(self, app_id: str) -> Optional[Dict]:
        return self.connections.get(app_id)
    
    def get_connected_apps(self) -> List[str]:
        return list(self.connections.keys())
    
    async def execute_action(self, app_id: str, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if app_id not in self.connections:
            return {"status": "error", "output": f"Not connected to {app_id}"}
        
        conn = self.connections[app_id]
        app_config = conn["config"]
        credentials = conn["credentials"]
        
        params = params or {}
        
        try:
            if app_id == "github":
                return await self._github_action(action, credentials, params)
            elif app_id == "notion":
                return await self._notion_action(action, credentials, params)
            elif app_id == "slack":
                return await self._slack_action(action, credentials, params)
            elif app_id == "trello":
                return await self._trello_action(action, credentials, params)
            elif app_id == "gmail":
                return await self._gmail_action(action, credentials, params)
            elif app_id == "google_calendar":
                return await self._calendar_action(action, credentials, params)
            elif app_id == "discord":
                return await self._discord_action(action, credentials, params)
            elif app_id == "telegram":
                return await self._telegram_action(action, credentials, params)
            elif app_id == "hubspot":
                return await self._hubspot_action(action, credentials, params)
            elif app_id == "openai":
                return await self._openai_action(action, credentials, params)
            elif app_id == "sendgrid":
                return await self._sendgrid_action(action, credentials, params)
            elif app_id == "stripe":
                return await self._stripe_action(action, credentials, params)
            elif app_id == "airtable":
                return await self._airtable_action(action, credentials, params)
            elif app_id == "jira":
                return await self._jira_action(action, credentials, params)
            elif app_id == "linear":
                return await self._linear_action(action, credentials, params)
            elif app_id == "asana":
                return await self._asana_action(action, credentials, params)
            elif app_id == "todoist":
                return await self._todoist_action(action, credentials, params)
            elif app_id == "clickup":
                return await self._clickup_action(action, credentials, params)
            elif app_id == "monday":
                return await self._monday_action(action, credentials, params)
            elif app_id == "shopify":
                return await self._shopify_action(action, credentials, params)
            elif app_id == "mailchimp":
                return await self._mailchimp_action(action, credentials, params)
            elif app_id == "sendgrid":
                return await self._sendgrid_action(action, credentials, params)
            elif app_id == "calendly":
                return await self._calendly_action(action, credentials, params)
            elif app_id == "gitlab":
                return await self._gitlab_action(action, credentials, params)
            elif app_id == "bitbucket":
                return await self._bitbucket_action(action, credentials, params)
            elif app_id == "vercel":
                return await self._vercel_action(action, credentials, params)
            elif app_id == "digitalocean":
                return await self._digitalocean_action(action, credentials, params)
            elif app_id == "heroku":
                return await self._heroku_action(action, credentials, params)
            elif app_id == "aws":
                return await self._aws_action(action, credentials, params)
            elif app_id == "datadog":
                return await self._datadog_action(action, credentials, params)
            elif app_id == "sentry":
                return await self._sentry_action(action, credentials, params)
            elif app_id == "mixpanel":
                return await self._mixpanel_action(action, credentials, params)
            elif app_id == "anthropic":
                return await self._anthropic_action(action, credentials, params)
            elif app_id == "huggingface":
                return await self._huggingface_action(action, credentials, params)
            elif app_id == "replicate":
                return await self._replicate_action(action, credentials, params)
            elif app_id == "google_drive":
                return await self._google_drive_action(action, credentials, params)
            elif app_id == "dropbox":
                return await self._dropbox_action(action, credentials, params)
            elif app_id == "onedrive":
                return await self._onedrive_action(action, credentials, params)
            elif app_id == "salesforce":
                return await self._salesforce_action(action, credentials, params)
            elif app_id == "pipedrive":
                return await self._pipedrive_action(action, credentials, params)
            elif app_id == "cal_com":
                return await self._cal_com_action(action, credentials, params)
            elif app_id == "webflow":
                return await self._webflow_action(action, credentials, params)
            elif app_id == "supabase":
                return await self._supabase_action(action, credentials, params)
            # Mail Apps
            elif app_id == "outlook":
                return await self._outlook_action(action, credentials, params)
            elif app_id == "proton_mail":
                return await self._proton_mail_action(action, credentials, params)
            elif app_id == "zoho_mail":
                return await self._zoho_mail_action(action, credentials, params)
            elif app_id == "fastmail":
                return await self._fastmail_action(action, credentials, params)
            elif app_id == "postmark":
                return await self._postmark_action(action, credentials, params)
            elif app_id == "mailgun":
                return await self._mailgun_action(action, credentials, params)
            elif app_id == "resend":
                return await self._resend_action(action, credentials, params)
            elif app_id == "brevo":
                return await self._brevo_action(action, credentials, params)
            else:
                return {"status": "error", "output": f"Action {action} not implemented for {app_id}"}
        except Exception as e:
            logger.error(f"Action {action} failed for {app_id}: {e}")
            return {"status": "error", "output": str(e)}
    
    async def _github_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
        
        if action == "list_repos":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.github.com/user/repos", headers=headers)
                repos = resp.json()
                return {"status": "success", "output": "\n".join([f"- {r['name']}" for r in repos[:10]])}
        
        elif action == "create_issue":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.github.com/repos/{params.get('owner')}/{params.get('repo')}/issues",
                    headers=headers,
                    json={"title": params.get("title"), "body": params.get("body", "")}
                )
                return {"status": "success", "output": f"Issue created: {resp.json().get('html_url')}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _notion_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("api_key")
        headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
        
        if action == "list_databases":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.notion.com/v1/databases", headers=headers)
                dbs = resp.json().get("results", [])
                return {"status": "success", "output": "\n".join([f"- {d.get('title', [{}])[0].get('plain_text', 'Untitled')}" for d in dbs])}
        
        elif action == "query_database":
            async with httpx.AsyncClient() as client:
                db_id = params.get("database_id") or creds.get("database_id")
                resp = await client.post(f"https://api.notion.com/v1/databases/{db_id}/query", headers=headers)
                pages = resp.json().get("results", [])
                return {"status": "success", "output": f"Found {len(pages)} pages"}
        
        elif action == "create_page":
            async with httpx.AsyncClient() as client:
                db_id = params.get("database_id") or creds.get("database_id")
                resp = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers=headers,
                    json={
                        "parent": {"database_id": db_id},
                        "properties": {"Name": {"title": [{"text": {"content": params.get("title", "Untitled")}}]}}
                    }
                )
                return {"status": "success", "output": f"Page created: {resp.json().get('id')}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _slack_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("bot_token") or creds.get("access_token")
        if not token:
            return {"status": "error", "output": "Slack token not found"}
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        if action == "send_message":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers=headers,
                    json={"channel": params.get("channel"), "text": params.get("message")}
                )
                result = resp.json()
                return {"status": "success", "output": "Message sent" if result.get("ok") else f"Failed: {result.get('error')}"}
        
        elif action == "list_channels":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://slack.com/api/conversations.list", headers=headers)
                result = resp.json()
                channels = result.get("channels", [])
                return {"status": "success", "output": "\n".join([f"- #{c.get('name')}" for c in channels[:10]])}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _trello_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        token = creds.get("token")
        
        if not api_key or not token:
            return {"status": "error", "output": "API key and token required"}
        
        if action == "list_boards":
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.trello.com/1/members/me/boards",
                    params={"key": api_key, "token": token}
                )
                boards = resp.json()
                return {"status": "success", "output": "\n".join([f"- {b.get('name')}" for b in boards[:10]])}
        
        elif action == "create_card":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.trello.com/1/cards",
                    params={"key": api_key, "token": token},
                    json={
                        "name": params.get("name"),
                        "idList": params.get("list_id"),
                        "desc": params.get("description", "")
                    }
                )
                return {"status": "success", "output": "Card created"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _gmail_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        creds_path = creds.get("credentials_path")
        if not creds_path or not os.path.exists(creds_path):
            return {"status": "error", "output": "Gmail credentials not configured"}
        
        try:
            creds_obj = Credentials.from_authorized_user_file(creds_path, ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"])
            service = build("gmail", "v1", credentials=creds_obj)
            
            if action == "list_emails":
                results = service.users().messages().list(userId="me", maxResults=10).execute()
                msgs = results.get("messages", [])
                return {"status": "success", "output": f"Found {len(msgs)} recent emails"}
            
            elif action == "send_email":
                from email.mime.text import MIMEText
                import base64
                
                msg = MIMEText(params.get("body", ""))
                msg["to"] = params.get("to")
                msg["subject"] = params.get("subject", "No Subject")
                
                encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                service.users().messages().send(userId="me", body={"raw": encoded}).execute()
                return {"status": "success", "output": "Email sent"}
        
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def _calendar_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        creds_path = creds.get("credentials_path")
        if not creds_path or not os.path.exists(creds_path):
            return {"status": "error", "output": "Calendar credentials not configured"}
        
        try:
            creds_obj = Credentials.from_authorized_user_file(creds_path, ["https://www.googleapis.com/auth/calendar.events"])
            service = build("calendar", "v3", credentials=creds_obj)
            
            if action == "list_events":
                now = datetime.utcnow().isoformat() + "Z"
                later = (datetime.utcnow().replace(hour=23, minute=59) + __import__('datetime').timedelta(days=7)).isoformat() + "Z"
                
                events = service.events().list(calendarId="primary", timeMin=now, timeMax=later, maxResults=10).execute()
                items = events.get("items", [])
                return {"status": "success", "output": f"Found {len(items)} upcoming events"}
            
            elif action == "create_event":
                event = {
                    "summary": params.get("title"),
                    "description": params.get("description", ""),
                    "start": {"dateTime": params.get("start_time"), "timeZone": "UTC"},
                    "end": {"dateTime": params.get("end_time"), "timeZone": "UTC"}
                }
                service.events().insert(calendarId="primary", body=event).execute()
                return {"status": "success", "output": "Event created"}
        
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def _discord_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("bot_token")
        if not token:
            return {"status": "error", "output": "Discord bot token required"}
        
        headers = {"Authorization": f"Bot {token}"}
        
        if action == "send_message":
            channel_id = params.get("channel_id")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers=headers,
                    json={"content": params.get("message")}
                )
                return {"status": "success", "output": "Message sent" if resp.status_code == 200 else f"Failed: {resp.status_code}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _telegram_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("bot_token")
        if not token:
            return {"status": "error", "output": "Telegram bot token required"}
        
        if action == "send_message":
            chat_id = params.get("chat_id")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": params.get("message")}
                )
                return {"status": "success", "output": "Message sent" if resp.json().get("ok") else "Failed"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _hubspot_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        if action == "list_contacts":
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.hubspot.com/crm/v3/objects/contacts",
                    headers=headers,
                    params={"limit": 10}
                )
                contacts = resp.json().get("results", [])
                return {"status": "success", "output": f"Found {len(contacts)} contacts"}
        
        elif action == "create_contact":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.hubspot.com/crm/v3/objects/contacts",
                    headers=headers,
                    json={"properties": {"email": params.get("email"), "firstname": params.get("first_name", ""), "lastname": params.get("last_name", "")}}
                )
                return {"status": "success", "output": f"Contact created: {resp.json().get('id')}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _openai_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        if not api_key:
            return {"status": "error", "output": "OpenAI API key required"}
        
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        if action == "complete":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.openai.com/v1/completions",
                    headers=headers,
                    json={"model": params.get("model", "text-davinci-003"), "prompt": params.get("prompt"), "max_tokens": params.get("max_tokens", 500)}
                )
                result = resp.json()
                return {"status": "success", "output": result.get("choices", [{}])[0].get("text", "").strip()}
        
        elif action == "chat":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json={"model": params.get("model", "gpt-3.5-turbo"), "messages": [{"role": "user", "content": params.get("message")}]}
                )
                result = resp.json()
                return {"status": "success", "output": result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _sendgrid_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        if not api_key:
            return {"status": "error", "output": "SendGrid API key required"}
        
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        if action == "send_email":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers=headers,
                    json={
                        "personalizations": [{"to": [{"email": params.get("to")}]}],
                        "from": {"email": params.get("from")},
                        "subject": params.get("subject"),
                        "content": [{"type": "text/plain", "value": params.get("body")}]
                    }
                )
                return {"status": "success", "output": "Email sent" if resp.status_code == 202 else f"Failed: {resp.status_code}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _stripe_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        if not api_key:
            return {"status": "error", "output": "Stripe API key required"}
        
        headers = {"Authorization": f"Bearer {api_key}"}
        
        if action == "list_customers":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.stripe.com/v1/customers", headers=headers)
                customers = resp.json().get("data", [])
                return {"status": "success", "output": f"Found {len(customers)} customers"}
        
        elif action == "create_charge":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.stripe.com/v1/charges",
                    headers=headers,
                    data={"amount": params.get("amount"), "currency": params.get("currency", "usd"), "source": params.get("token"), "description": params.get("description", "")}
                )
                return {"status": "success", "output": f"Charge created: {resp.json().get('id')}" if resp.status_code == 200 else f"Failed: {resp.text[:100]}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _airtable_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        base_id = params.get("base_id") or creds.get("base_id")
        if not api_key:
            return {"status": "error", "output": "Airtable API key required"}
        
        headers = {"Authorization": f"Bearer {api_key}"}
        
        if action == "list_records":
            if not base_id:
                return {"status": "error", "output": "Base ID required"}
            table_name = params.get("table", "Table 1")
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.airtable.com/v0/{base_id}/{table_name}", headers=headers, params={"maxRecords": 10})
                records = resp.json().get("records", [])
                return {"status": "success", "output": f"Found {len(records)} records"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _jira_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        domain = creds.get("domain")
        email = creds.get("email")
        token = creds.get("api_token")
        
        if not all([domain, email, token]):
            return {"status": "error", "output": "Jira domain, email and API token required"}
        
        auth = base64.b64encode(f"{email}:{token}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        if action == "list_issues":
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://{domain}.atlassian.net/rest/api/3/search",
                    headers=headers,
                    params={"maxResults": 10, "jql": "assignee=currentUser"}
                )
                issues = resp.json().get("issues", [])
                return {"status": "success", "output": f"Found {len(issues)} issues"}
        
        elif action == "create_issue":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://{domain}.atlassian.net/rest/api/3/issue",
                    headers=headers,
                    json={
                        "fields": {
                            "project": {"key": params.get("project_key", "PROJ")},
                            "summary": params.get("summary"),
                            "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": params.get("description", "")}]}]},
                            "issuetype": {"name": "Task"}
                        }
                    }
                )
                return {"status": "success", "output": f"Issue created: {resp.json().get('key')}" if resp.status_code == 201 else f"Failed: {resp.text[:100]}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _linear_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        if not api_key:
            return {"status": "error", "output": "Linear API key required"}
        
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        
        if action == "list_issues":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.linear.app/graphql",
                    headers=headers,
                    json={"query": "{ issues(first: 10) { nodes { id title state { name } } } }"}
                )
                issues = resp.json().get("data", {}).get("issues", {}).get("nodes", [])
                return {"status": "success", "output": f"Found {len(issues)} issues"}
        
        elif action == "create_issue":
            async with httpx.AsyncClient() as client:
                query = f'mutation {{ createIssue(input: {{ title: "{params.get('title')}", teamId: "{params.get('team_id')}" }}) {{ success issue {{ id title }} }} }}'
                resp = await client.post("https://api.linear.app/graphql", headers=headers, json={"query": query})
                return {"status": "success", "output": "Issue created" if resp.json().get("data", {}).get("createIssue", {}).get("success") else "Failed"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _asana_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("access_token")
        if not token:
            return {"status": "error", "output": "Asana access token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "list_projects":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://app.asana.com/api/1.0/projects", headers=headers)
                projects = resp.json().get("data", [])
                return {"status": "success", "output": "\n".join([f"- {p.get('name')}" for p in projects[:10]])}
        
        elif action == "create_task":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://app.asana.com/api/1.0/tasks",
                    headers=headers,
                    json={"data": {"name": params.get("name"), "notes": params.get("notes", ""), "projects": [params.get("project_id")]}}
                )
                return {"status": "success", "output": f"Task created: {resp.json().get('data', {}).get('gid')}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _todoist_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("api_token")
        if not token:
            return {"status": "error", "output": "Todoist API token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "list_tasks":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.todoist.com/rest/v2/tasks", headers=headers, params={"limit": 10})
                tasks = resp.json()
                return {"status": "success", "output": "\n".join([f"- {t.get('content')}" for t in tasks[:10]])}
        
        elif action == "create_task":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.todoist.com/rest/v2/tasks",
                    headers=headers,
                    json={"content": params.get("content"), "description": params.get("description", "")}
                )
                return {"status": "success", "output": f"Task created: {resp.json().get('id')}"}
        
        elif action == "complete_task":
            task_id = params.get("task_id")
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"https://api.todoist.com/rest/v2/tasks/{task_id}/close", headers=headers)
                return {"status": "success", "output": "Task completed" if resp.status_code == 204 else "Failed"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _clickup_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("api_token")
        if not token:
            return {"status": "error", "output": "ClickUp API token required"}
        
        headers = {"Authorization": token, "Content-Type": "application/json"}
        
        if action == "list_tasks":
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.clickup.com/api/v2/team",
                    headers=headers
                )
                data = resp.json()
                return {"status": "success", "output": f"ClickUp connected. Teams: {len(data.get('teams', []))}"}
        
        elif action == "create_task":
            async with httpx.AsyncClient() as client:
                list_id = params.get("list_id")
                resp = await client.post(
                    f"https://api.clickup.com/api/v2/list/{list_id}/task",
                    headers=headers,
                    json={"name": params.get("name"), "description": params.get("description", "")}
                )
                return {"status": "success", "output": f"Task created: {resp.json().get('id')}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _monday_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("api_token")
        if not token:
            return {"status": "error", "output": "Monday.com API token required"}
        
        headers = {"Authorization": token, "Content-Type": "application/json"}
        
        if action == "list_boards":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.monday.com/v2",
                    headers=headers,
                    json={"query": "{ boards(limit: 10) { id name } }"}
                )
                boards = resp.json().get("data", {}).get("boards", [])
                return {"status": "success", "output": "\n".join([f"- {b.get('name')}" for b in boards])}
        
        elif action == "create_item":
            async with httpx.AsyncClient() as client:
                query = f'mutation {{ create_item(board_id: {params.get("board_id")}, item_name: "{params.get("name")}") {{ id }} }}'
                resp = await client.post("https://api.monday.com/v2", headers=headers, json={"query": query})
                return {"status": "success", "output": f"Item created: {resp.json().get('data', {}).get('create_item', {}).get('id')}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _shopify_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        shop_name = creds.get("shop_name")
        token = creds.get("access_token")
        
        if not shop_name or not token:
            return {"status": "error", "output": "Shopify shop name and access token required"}
        
        headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
        
        if action == "list_products":
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://{shop_name}.myshopify.com/admin/api/2024-01/products.json", headers=headers)
                products = resp.json().get("products", [])
                return {"status": "success", "output": "\n".join([f"- {p.get('title')}" for p in products[:10]])}
        
        elif action == "create_order":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://{shop_name}.myshopify.com/admin/api/2024-01/orders.json",
                    headers=headers,
                    json={"order": {"line_items": [{"title": params.get("product"), "quantity": params.get("quantity", 1)}]}}
                )
                return {"status": "success", "output": f"Order created: {resp.json().get('order', {}).get('id')}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _mailchimp_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        server = creds.get("server_prefix")
        
        if not api_key or not server:
            return {"status": "error", "output": "Mailchimp API key and server prefix required"}
        
        auth = base64.b64encode(f"anystring:{api_key}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}
        
        if action == "list_subscribers":
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://{server}.api.mailchimp.com/3.0/lists", headers=headers)
                lists = resp.json().get("lists", [])
                return {"status": "success", "output": f"Found {len(lists)} lists"}
        
        elif action == "add_subscriber":
            list_id = params.get("list_id")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://{server}.api.mailchimp.com/3.0/lists/{list_id}/members",
                    headers=headers,
                    json={"email_address": params.get("email"), "status": "subscribed"}
                )
                return {"status": "success", "output": "Subscriber added" if resp.status_code == 200 else f"Failed: {resp.status_code}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _calendly_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("api_token")
        if not token:
            return {"status": "error", "output": "Calendly API token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "list_event_types":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.calendly.com/event_types", headers=headers)
                events = resp.json().get("collection", [])
                return {"status": "success", "output": "\n".join([f"- {e.get('name')}" for e in events[:10]])}
        
        elif action == "list_events":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.calendly.com/scheduled_events", headers=headers)
                events = resp.json().get("collection", [])
                return {"status": "success", "output": f"Found {len(events)} upcoming events"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _gitlab_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("access_token")
        gitlab_url = creds.get("gitlab_url", "https://gitlab.com")
        
        if not token:
            return {"status": "error", "output": "GitLab access token required"}
        
        headers = {"PRIVATE-TOKEN": token}
        
        if action == "list_projects":
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{gitlab_url}/api/v4/projects", headers=headers, params={"membership": True, "per_page": 10})
                projects = resp.json()
                return {"status": "success", "output": "\n".join([f"- {p.get('name')}" for p in projects[:10]])}
        
        elif action == "create_issue":
            project_id = params.get("project_id")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{gitlab_url}/api/v4/projects/{project_id}/issues",
                    headers=headers,
                    json={"title": params.get("title"), "description": params.get("description", "")}
                )
                return {"status": "success", "output": f"Issue created: {resp.json().get('iid')}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _bitbucket_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        username = creds.get("username")
        password = creds.get("app_password")
        
        if not username or not password:
            return {"status": "error", "output": "Bitbucket username and app password required"}
        
        auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}
        
        if action == "list_repos":
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.bitbucket.org/2.0/repositories/{username}", headers=headers)
                repos = resp.json().get("values", [])
                return {"status": "success", "output": "\n".join([f"- {r.get('name')}" for r in repos[:10]])}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _vercel_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("token")
        if not token:
            return {"status": "error", "output": "Vercel token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "list_deployments":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.vercel.com/v6/deployments", headers=headers, params={"limit": 10})
                deps = resp.json().get("deployments", [])
                return {"status": "success", "output": f"Found {len(deps)} deployments"}
        
        elif action == "create_deployment":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.vercel.com/v13/deployments",
                    headers=headers,
                    json={"name": params.get("name"), "files": [], "project": params.get("project_id")}
                )
                result = resp.json()
                if resp.status_code == 200:
                    return {"status": "success", "output": f"Deployment created: {result.get('uid')}"}
                return {"status": "error", "output": f"Failed: {resp.status_code}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _digitalocean_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("access_token")
        if not token:
            return {"status": "error", "output": "DigitalOcean access token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "list_droplets":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.digitalocean.com/v2/droplets", headers=headers)
                droplets = resp.json().get("droplets", [])
                return {"status": "success", "output": "\n".join([f"- {d.get('name')} ({d.get('status')})" for d in droplets[:10]])}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _heroku_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        if not api_key:
            return {"status": "error", "output": "Heroku API key required"}
        
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/vnd.heroku+json; version=3"}
        
        if action == "list_apps":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.heroku.com/apps", headers=headers)
                apps = resp.json()
                return {"status": "success", "output": "\n".join([f"- {a.get('name')}" for a in apps[:10]])}
        
        elif action == "view_logs":
            app_name = params.get("app_name")
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.heroku.com/apps/{app_name}/logs", headers=headers, params={"lines": 20})
                return {"status": "success", "output": f"Logs fetched (20 lines)"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _aws_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        import boto3
        
        access_key = creds.get("access_key_id")
        secret_key = creds.get("secret_access_key")
        region = creds.get("region")
        
        if not all([access_key, secret_key, region]):
            return {"status": "error", "output": "AWS access key, secret key and region required"}
        
        try:
            if action == "list_ec2":
                ec2 = boto3.client("ec2", aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region)
                instances = ec2.describe_instances()
                names = []
                for res in instances.get("Reservations", []):
                    for inst in res.get("Instances", []):
                        name = next((tag.get("Value") for tag in inst.get("Tags", []) if tag.get("Key") == "Name"), inst.get("InstanceId"))
                        names.append(f"- {name}")
                return {"status": "success", "output": "\n".join(names) if names else "No instances found"}
            
            elif action == "list_s3":
                s3 = boto3.client("s3", aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region)
                buckets = s3.list_buckets().get("Buckets", [])
                return {"status": "success", "output": "\n".join([f"- {b.get('Name')}" for b in buckets[:10]])}
            
            return {"status": "error", "output": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def _datadog_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        app_key = creds.get("app_key")
        
        if not api_key:
            return {"status": "error", "output": "Datadog API key required"}
        
        headers = {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key or ""}
        
        if action == "query_metrics":
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.datadoghq.com/api/v1/query",
                    headers=headers,
                    params={"from": "now-1h", "to": "now", "query": params.get("query", "system.cpu.usage")}
                )
                return {"status": "success", "output": f"Query executed"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _sentry_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("auth_token")
        org = creds.get("organization_slug")
        
        if not token or not org:
            return {"status": "error", "output": "Sentry auth token and organization required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "list_issues":
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://sentry.io/api/0/organizations/{org}/issues/", headers=headers, params={"limit": 10})
                issues = resp.json()
                return {"status": "success", "output": f"Found {len(issues)} issues"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _mixpanel_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        username = creds.get("service_account_username")
        secret = creds.get("service_account_secret")
        
        if not username or not secret:
            return {"status": "error", "output": "Mixpanel service account credentials required"}
        
        import hashlib
        import time
        import json
        
        creds_json = json.dumps({"username": username, "password": secret}).encode()
        signature = hashlib.md5(creds_json + str(int(time.time())).encode()).hexdigest()
        
        headers = {"Content-Type": "application/json"}
        
        if action == "track_event":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.mixpanel.com/track",
                    headers=headers,
                    params={"data": base64.b64encode(json.dumps({"event": params.get("event"), "properties": params.get("properties", {})}).encode()).decode(), "sig": signature}
                )
                return {"status": "success", "output": "Event tracked" if resp.status_code == 200 else f"Failed: {resp.status_code}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _anthropic_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        if not api_key:
            return {"status": "error", "output": "Anthropic API key required"}
        
        headers = {"x-api-key": api_key, "Content-Type": "application/json", "anthropic-version": "2023-06-01"}
        
        if action == "complete" or action == "message":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json={
                        "model": params.get("model", "claude-3-sonnet-20240229"),
                        "max_tokens": params.get("max_tokens", 1024),
                        "messages": [{"role": "user", "content": params.get("prompt") or params.get("message", "")}]
                    }
                )
                result = resp.json()
                return {"status": "success", "output": result.get("content", [{}])[0].get("text", "").strip()}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _huggingface_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("api_token")
        if not token:
            return {"status": "error", "output": "HuggingFace API token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "inference":
            async with httpx.AsyncClient() as client:
                model = params.get("model", "gpt2")
                resp = await client.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    headers=headers,
                    json={"inputs": params.get("prompt", "")}
                )
                return {"status": "success", "output": str(resp.json())[:500]}
        
        elif action == "list_models":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://huggingface.co/api/models", headers=headers, params={"search": params.get("search", "gpt"), "limit": 10})
                models = resp.json()
                return {"status": "success", "output": "\n".join([f"- {m.get('modelId')}" for m in models])}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _replicate_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("api_token")
        if not token:
            return {"status": "error", "output": "Replicate API token required"}
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        if action == "run_model":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.replicate.com/v1/predictions",
                    headers=headers,
                    json={
                        "version": params.get("version"),
                        "input": params.get("input", {})
                    }
                )
                return {"status": "success", "output": f"Prediction started: {resp.json().get('id')}"}
        
        elif action == "list_models":
            return {"status": "success", "output": "Use run_model action to run models from Replicate"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _google_drive_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        creds_path = creds.get("credentials_path")
        if not creds_path or not os.path.exists(creds_path):
            return {"status": "error", "output": "Google Drive credentials not configured"}
        
        try:
            creds_obj = Credentials.from_authorized_user_file(creds_path, ["https://www.googleapis.com/auth/drive"])
            service = build("drive", "v3", credentials=creds_obj)
            
            if action == "list_files":
                results = service.files().list(pageSize=10, fields="files(id, name, mimeType)").execute()
                files = results.get("files", [])
                return {"status": "success", "output": "\n".join([f"- {f.get('name')}" for f in files])}
            
            return {"status": "error", "output": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def _dropbox_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("access_token")
        if not token:
            return {"status": "error", "output": "Dropbox access token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "list_files":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.dropboxapi.com/2/files/list_folder",
                    headers=headers,
                    json={"path": ""}
                )
                entries = resp.json().get("entries", [])
                return {"status": "success", "output": "\n".join([f"- {e.get('name')}" for e in entries[:10]])}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _onedrive_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        return {"status": "error", "output": "OneDrive requires OAuth setup. Use Google Drive instead for simpler auth."}
    
    async def _salesforce_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        instance_url = creds.get("instance_url")
        token = creds.get("access_token")
        
        if not instance_url or not token:
            return {"status": "error", "output": "Salesforce instance URL and access token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "query_objects":
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{instance_url}/services/data/v58.0/query",
                    headers=headers,
                    params={"q": "SELECT Id, Name FROM Account LIMIT 10"}
                )
                records = resp.json().get("totalSize", 0)
                return {"status": "success", "output": f"Found {records} accounts"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _pipedrive_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("api_token")
        if not token:
            return {"status": "error", "output": "Pipedrive API token required"}
        
        headers = {"Authorization": token}
        
        if action == "list_deals":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.pipedrive.com/v1/deals", headers=headers, params={"limit": 10})
                deals = resp.json().get("data", [])
                return {"status": "success", "output": f"Found {len(deals)} deals"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _cal_com_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        base_url = creds.get("base_url")
        
        if not api_key or not base_url:
            return {"status": "error", "output": "Cal.com API key and base URL required"}
        
        headers = {"Authorization": f"Bearer {api_key}"}
        
        if action == "list_bookings":
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{base_url}/bookings", headers=headers)
                bookings = resp.json()
                return {"status": "success", "output": f"Found {len(bookings)} bookings"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _webflow_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("access_token")
        if not token:
            return {"status": "error", "output": "Webflow access token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "list_sites":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.webflow.com/sites", headers=headers)
                sites = resp.json()
                return {"status": "success", "output": "\n".join([f"- {s.get('displayName')}" for s in sites[:10]])}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _supabase_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        url = creds.get("url")
        key = creds.get("anon_key") or creds.get("service_key")
        
        if not url or not key:
            return {"status": "error", "output": "Supabase URL and key required"}
        
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        
        if action == "query_table":
            table = params.get("table")
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{url}/rest/v1/{table}", headers=headers, params={"limit": 10})
                records = resp.json()
                return {"status": "success", "output": f"Found {len(records)} records in {table}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _outlook_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        tenant_id = creds.get("tenant_id")
        
        if not all([client_id, client_secret, tenant_id]):
            return {"status": "error", "output": "Outlook: client_id, client_secret, and tenant_id required"}
        
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        scope = "https://graph.microsoft.com/.default"
        
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(token_url, data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope
            })
            
            if token_resp.status_code != 200:
                return {"status": "error", "output": "Failed to get access token"}
            
            access_token = token_resp.json().get("access_token")
            headers = {"Authorization": f"Bearer {access_token}"}
            
            if action == "list_emails":
                resp = await client.get("https://graph.microsoft.com/v1.0/me/messages", headers=headers, params={"$top": 10})
                messages = resp.json().get("value", [])
                return {"status": "success", "output": f"Found {len(messages)} emails"}
            
            elif action == "send_email":
                resp = await client.post(
                    "https://graph.microsoft.com/v1.0/me/sendMail",
                    headers=headers,
                    json={
                        "message": {
                            "subject": params.get("subject", "No Subject"),
                            "body": {"contentType": "Text", "content": params.get("body", "")},
                            "toRecipients": [{"emailAddress": {"address": params.get("to")}}]
                        }
                    }
                )
                return {"status": "success", "output": "Email sent" if resp.status_code == 202 else f"Failed: {resp.status_code}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _proton_mail_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("access_token")
        if not token:
            return {"status": "error", "output": "Proton Mail access token required"}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if action == "list_emails":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.protonmail.com/api/v4/messages", headers=headers, params={"limit": 10})
                messages = resp.json().get("Messages", [])
                return {"status": "success", "output": f"Found {len(messages)} emails"}
        
        elif action == "send_email":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.protonmail.com/api/v4/messages",
                    headers=headers,
                    json={
                        "subject": params.get("subject", ""),
                        "body": params.get("body", ""),
                        "to": [{"address": params.get("to")}]
                    }
                )
                return {"status": "success", "output": "Email sent" if resp.status_code == 201 else f"Failed: {resp.status_code}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _zoho_mail_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        org_id = creds.get("org_id")
        
        if not all([client_id, client_secret, org_id]):
            return {"status": "error", "output": "Zoho Mail: client_id, client_secret, and org_id required"}
        
        token_url = f"https://accounts.zoho.com/oauth/v2/token?grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}&scope=Zmailsg.Mail.message.READ,ZohoFiles.files.READ"
        
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(token_url)
            if token_resp.status_code != 200:
                return {"status": "error", "output": "Failed to get Zoho token"}
            
            access_token = token_resp.json().get("access_token")
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            
            if action == "list_emails":
                resp = await client.get(f"https://mail.zoho.com/api/accounts/{org_id}/messages", headers=headers, params={"limit": 10})
                messages = resp.json().get("data", [])
                return {"status": "success", "output": f"Found {len(messages)} emails"}
            
            elif action == "send_email":
                resp = await client.post(
                    f"https://mail.zoho.com/api/accounts/{org_id}/messages",
                    headers=headers,
                    json={
                        "subject": params.get("subject", ""),
                        "content": params.get("body", ""),
                        "to": params.get("to")
                    }
                )
                return {"status": "success", "output": "Email sent" if resp.status_code == 200 else f"Failed: {resp.status_code}"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _fastmail_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        email = creds.get("email")
        app_password = creds.get("app_password")
        
        if not email or not app_password:
            return {"status": "error", "output": "Fastmail email and app password required"}
        
        import base64
        auth = base64.b64encode(f"{email}:{app_password}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        if action == "list_emails":
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.fastmail.com/.well-known/jmap",
                    headers=headers
                )
                return {"status": "success", "output": "Fastmail connected - JMAP available"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _postmark_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        token = creds.get("server_api_token")
        if not token:
            return {"status": "error", "output": "Postmark server API token required"}
        
        headers = {"Accept": "application/json", "Content-Type": "application/json", "X-Postmark-Server-Token": token}
        
        if action == "send_email":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.postmarkapp.com/email",
                    headers=headers,
                    json={
                        "From": params.get("from", "noreply@example.com"),
                        "To": params.get("to"),
                        "Subject": params.get("subject", ""),
                        "HtmlBody": params.get("body", "")
                    }
                )
                if resp.status_code == 200:
                    return {"status": "success", "output": "Email sent"}
                return {"status": "error", "output": f"Failed: {resp.status_code}"}
        
        elif action == "get_bounces":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.postmarkapp.com/bounces", headers=headers)
                bounces = resp.json().get("Bounces", [])
                return {"status": "success", "output": f"Found {len(bounces)} bounces"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _mailgun_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        domain = creds.get("domain")
        
        if not api_key or not domain:
            return {"status": "error", "output": "Mailgun API key and domain required"}
        
        auth = ("api", api_key)
        
        if action == "send_email":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.mailgun.net/v3/{domain}/messages",
                    auth=auth,
                    data={
                        "from": params.get("from", f"noreply@{domain}"),
                        "to": params.get("to"),
                        "subject": params.get("subject", ""),
                        "html": params.get("body", "")
                    }
                )
                if resp.status_code == 200:
                    return {"status": "success", "output": "Email sent"}
                return {"status": "error", "output": f"Failed: {resp.status_code}"}
        
        elif action == "get_events":
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.mailgun.net/v3/{domain}/events", auth=auth)
                events = resp.json().get("items", [])
                return {"status": "success", "output": f"Found {len(events)} events"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _resend_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        if not api_key:
            return {"status": "error", "output": "Resend API key required"}
        
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        if action == "send_email":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers=headers,
                    json={
                        "from": params.get("from", "onboarding@resend.dev"),
                        "to": [params.get("to")],
                        "subject": params.get("subject", ""),
                        "html": params.get("body", "")
                    }
                )
                if resp.status_code == 200:
                    return {"status": "success", "output": f"Email sent: {resp.json().get('id')}"}
                return {"status": "error", "output": f"Failed: {resp.status_code}"}
        
        elif action == "list_domains":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.resend.com/domains", headers=headers)
                domains = resp.json().get("data", [])
                return {"status": "success", "output": f"Found {len(domains)} domains"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _brevo_action(self, action: str, creds: Dict, params: Dict) -> Dict[str, Any]:
        api_key = creds.get("api_key")
        if not api_key:
            return {"status": "error", "output": "Brevo API key required"}
        
        headers = {"Accept": "application/json", "Content-Type": "application/json", "Api-Key": api_key}
        
        if action == "send_email":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers=headers,
                    json={
                        "sender": {"email": params.get("from", "noreply@example.com")},
                        "to": [{"email": params.get("to")}],
                        "subject": params.get("subject", ""),
                        "htmlContent": params.get("body", "")
                    }
                )
                if resp.status_code == 201:
                    return {"status": "success", "output": f"Email sent: {resp.json().get('messageId')}"}
                return {"status": "error", "output": f"Failed: {resp.status_code}"}
        
        elif action == "list_contacts":
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.brevo.com/v3/contacts", headers=headers, params={"limit": 10})
                contacts = resp.json().get("contacts", [])
                return {"status": "success", "output": f"Found {len(contacts)} contacts"}
        
        return {"status": "error", "output": f"Unknown action: {action}"}
    
    async def _generate_skills_for_app(self, app_id: str, app_config):
        from database import SessionLocal, save_connection_skill
        
        db = SessionLocal()
        try:
            for cap in app_config.capabilities:
                skill_name = f"{app_id}_{cap}"
                description = f"{app_config.name}: {cap.replace('_', ' ')}"
                params_schema = json.dumps({"app_id": app_id, "action": cap, "params": {}})
                
                save_connection_skill(db, app_id, skill_name, description, params_schema)
        finally:
            db.close()
    
    def get_skills_for_connected_apps(self) -> List[Dict]:
        skills = []
        for app_id in self.connections:
            app_config = self.connections[app_id]["config"]
            for cap in app_config.capabilities:
                skills.append({
                    "app_id": app_id,
                    "app_name": app_config.name,
                    "capability": cap,
                    "skill_name": f"{app_id}_{cap}"
                })
        return skills


connection_manager = ConnectionManager()


async def execute_connection_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    parts = tool_name.split("_", 1)
    if len(parts) != 2:
        return {"status": "error", "output": f"Invalid tool format: {tool_name}"}
    
    app_id = parts[0]
    action = parts[1]
    
    return await connection_manager.execute_action(app_id, action, params)


async def connect_app(app_id: str, credentials: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
    return await connection_manager.connect(app_id, credentials, config)


async def disconnect_app(app_id: str) -> Dict[str, Any]:
    return await connection_manager.disconnect(app_id)


def get_connection_status() -> Dict[str, Any]:
    by_category_raw = get_apps_by_category()
    by_category = {}
    for category, apps in by_category_raw.items():
        by_category[category] = [asdict(app) for app in apps]
    
    all_apps = get_all_apps()
    available_apps = [asdict(app) for app in all_apps]
    
    return {
        "connected": connection_manager.get_connected_apps(),
        "count": len(connection_manager.connections),
        "by_category": by_category,
        "available_apps": available_apps
    }


def get_available_apps() -> Dict[str, Any]:
    return {
        "apps": get_all_apps(),
        "by_category": get_apps_by_category()
    }