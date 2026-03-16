import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format='%(asctime)s [FoxxGent] %(levelname)s: %(message)s')
logger = logging.getLogger("foxxgent")


class OmniConnectorBase(ABC):
    @abstractmethod
    async def connect(self) -> bool:
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        pass


class GmailConnector(OmniConnectorBase):
    def __init__(self):
        self.credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        self.credentials = None
        self.service = None
        self.scopes = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']
    
    async def connect(self) -> bool:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            
            if not os.path.exists(self.credentials_path):
                logger.warning(f"Google credentials not found at {self.credentials_path}")
                return False
            
            self.credentials = Credentials.from_authorized_user_file(self.credentials_path, self.scopes)
            self.service = build('gmail', 'v1', credentials=self.credentials)
            logger.info("Gmail connector connected")
            return True
        except Exception as e:
            logger.error(f"Gmail connection failed: {e}")
            return False
    
    async def disconnect(self) -> bool:
        self.service = None
        return True
    
    async def list_emails(self, max_results: int = 10, query: str = "") -> Dict[str, Any]:
        if not self.service:
            return {"status": "error", "output": "Not connected to Gmail"}
        
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for msg in messages[:max_results]:
                email_data = self.service.users().messages().get(
                    userId='me', 
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date']
                ).execute()
                
                headers = email_data.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                
                emails.append({
                    "id": msg['id'],
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "snippet": email_data.get('snippet', '')
                })
            
            return {"status": "success", "emails": emails}
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def read_email(self, message_id: str) -> Dict[str, Any]:
        if not self.service:
            return {"status": "error", "output": "Not connected to Gmail"}
        
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            body = ""
            parts = message.get('payload', {}).get('parts', [])
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    body = part.get('body', {}).get('data', '')
                    break
            
            if body:
                import base64
                body = base64.urlsafe_b64decode(body).decode('utf-8')
            
            return {
                "status": "success",
                "email": {
                    "id": message_id,
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "body": body[:2000]
                }
            }
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def send_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        if not self.service:
            return {"status": "error", "output": "Not connected to Gmail"}
        
        try:
            from email.mime.text import MIMEText
            import base64
            
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            
            encoded = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            self.service.users().messages().send(
                userId='me',
                body={'raw': encoded}
            ).execute()
            
            return {"status": "success", "output": f"Email sent to {to}"}
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def search_emails(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        return await self.list_emails(max_results, query)


class CalendarConnector(OmniConnectorBase):
    def __init__(self):
        self.credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        self.credentials = None
        self.service = None
        self.scopes = ['https://www.googleapis.com/auth/calendar.readonly', 'https://www.googleapis.com/auth/calendar.events']
    
    async def connect(self) -> bool:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            
            if not os.path.exists(self.credentials_path):
                logger.warning(f"Google credentials not found at {self.credentials_path}")
                return False
            
            self.credentials = Credentials.from_authorized_user_file(self.credentials_path, self.scopes)
            self.service = build('calendar', 'v3', credentials=self.credentials)
            logger.info("Calendar connector connected")
            return True
        except Exception as e:
            logger.error(f"Calendar connection failed: {e}")
            return False
    
    async def disconnect(self) -> bool:
        self.service = None
        return True
    
    async def list_events(self, days_ahead: int = 7) -> Dict[str, Any]:
        if not self.service:
            return {"status": "error", "output": "Not connected to Calendar"}
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            later = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=later,
                maxResults=20,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            event_list = []
            
            for event in events:
                start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'Unknown'))
                end = event.get('end', {}).get('dateTime', event.get('end', {}).get('date', 'Unknown'))
                event_list.append({
                    "id": event.get('id'),
                    "summary": event.get('summary', 'No title'),
                    "start": start,
                    "end": end,
                    "location": event.get('location', ''),
                    "description": event.get('description', '')[:200]
                })
            
            return {"status": "success", "events": event_list}
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def create_event(self, title: str, start_time: str, end_time: str, description: str = "", location: str = "") -> Dict[str, Any]:
        if not self.service:
            return {"status": "error", "output": "Not connected to Calendar"}
        
        try:
            event = {
                'summary': title,
                'description': description,
                'location': location,
                'start': {'dateTime': start_time, 'timeZone': 'UTC'},
                'end': {'dateTime': end_time, 'timeZone': 'UTC'}
            }
            
            created = self.service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            return {"status": "success", "output": f"Event created: {created.get('htmlLink')}"}
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def delete_event(self, event_id: str) -> Dict[str, Any]:
        if not self.service:
            return {"status": "error", "output": "Not connected to Calendar"}
        
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            return {"status": "success", "output": f"Event {event_id} deleted"}
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def today_events(self) -> Dict[str, Any]:
        return await self.list_events(1)


class NotionConnector(OmniConnectorBase):
    def __init__(self):
        self.api_key = os.getenv("NOTION_API_KEY")
        self.database_id = os.getenv("NOTION_DATABASE_ID")
        self.base_url = "https://api.notion.com/v1"
    
    async def connect(self) -> bool:
        if not self.api_key:
            logger.warning("NOTION_API_KEY not configured")
            return False
        logger.info("Notion connector initialized")
        return True
    
    async def disconnect(self) -> bool:
        return True
    
    async def _request(self, method: str, endpoint: str, data: dict = None) -> Dict[str, Any]:
        if not self.api_key:
            return {"status": "error", "output": "NOTION_API_KEY not configured"}
        
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}{endpoint}"
            
            if method == "GET":
                response = httpx.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = httpx.post(url, headers=headers, json=data, timeout=30)
            elif method == "PATCH":
                response = httpx.patch(url, headers=headers, json=data, timeout=30)
            elif method == "DELETE":
                response = httpx.delete(url, headers=headers, timeout=30)
            else:
                return {"status": "error", "output": f"Unknown method: {method}"}
            
            if response.status_code >= 400:
                return {"status": "error", "output": f"Notion API error: {response.text[:200]}"}
            
            return {"status": "success", "data": response.json()}
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def list_databases(self) -> Dict[str, Any]:
        result = await self._request("GET", "/databases")
        if result.get("status") == "success":
            databases = result.get("data", {}).get("results", [])
            return {"status": "success", "databases": [{"id": d["id"], "title": d.get("title", [{}])[0].get("plain_text", "Untitled")} for d in databases]}
        return result
    
    async def query_database(self, database_id: str = None) -> Dict[str, Any]:
        db_id = database_id or self.database_id
        if not db_id:
            return {"status": "error", "output": "No database ID provided"}
        
        result = await self._request("POST", f"/databases/{db_id}/query", {"page_size": 10})
        if result.get("status") == "success":
            pages = result.get("data", {}).get("results", [])
            return {"status": "success", "pages": [self._parse_page(p) for p in pages]}
        return result
    
    def _parse_page(self, page: dict) -> dict:
        props = page.get("properties", {})
        title = ""
        if "Name" in props:
            title = props["Name"].get("title", [{}])[0].get("plain_text", "")
        elif "Title" in props:
            title = props["Title"].get("title", [{}])[0].get("plain_text", "")
        
        return {
            "id": page.get("id"),
            "title": title,
            "created_time": page.get("created_time"),
            "last_edited": page.get("last_edited_time")
        }
    
    async def create_page(self, title: str, content: str = "", database_id: str = None) -> Dict[str, Any]:
        db_id = database_id or self.database_id
        if not db_id:
            return {"status": "error", "output": "No database ID provided"}
        
        data = {
            "parent": {"database_id": db_id},
            "properties": {
                "Name": {"title": [{"text": {"content": title}}]}
            },
            "children": [{"object": "block", "paragraph": {"rich_text": [{"text": {"content": content}}]}}]
        }
        
        result = await self._request("POST", "/pages", data)
        if result.get("status") == "success":
            return {"status": "success", "output": f"Page created: {result['data'].get('id')}"}
        return result


class WebScraper(OmniConnectorBase):
    def __init__(self):
        self.session = None
    
    async def connect(self) -> bool:
        import httpx
        self.session = httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=30.0
        )
        logger.info("Web scraper initialized")
        return True
    
    async def disconnect(self) -> bool:
        if self.session:
            await self.session.aclose()
        return True
    
    async def scrape_url(self, url: str, selectors: List[str] = None) -> Dict[str, Any]:
        if not self.session:
            await self.connect()
        
        try:
            response = await self.session.get(url)
            if response.status_code != 200:
                return {"status": "error", "output": f"HTTP {response.status_code}"}
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            data = {"url": url, "title": soup.title.string if soup.title else ""}
            
            if selectors:
                for selector in selectors:
                    elements = soup.select(selector)
                    data[selector] = [el.get_text(strip=True)[:500] for el in elements[:5]]
            else:
                data["headings"] = []
                for tag in ['h1', 'h2', 'h3']:
                    for el in soup.find_all(tag)[:3]:
                        data["headings"].append(el.get_text(strip=True))
                
                data["links"] = [{"text": a.get_text(strip=True)[:50], "href": a.get("href", "")} for a in soup.find_all('a')[:10] if a.get("href")]
                
                for tag in soup.find_all(['script', 'style']):
                    tag.decompose()
                data["text"] = soup.get_text(strip=True)[:2000]
            
            return {"status": "success", "data": data}
        except Exception as e:
            return {"status": "error", "output": str(e)}
    
    async def summarize_page(self, url: str, max_sentences: int = 5) -> Dict[str, Any]:
        result = await self.scrape_url(url)
        if result.get("status") != "success":
            return result
        
        data = result.get("data", {})
        text = data.get("text", "")
        
        if not text:
            return {"status": "success", "summary": "No text content found on page."}
        
        sentences = text.replace('\n', ' ').split('. ')[:max_sentences]
        summary = '. '.join(sentences)
        
        return {
            "status": "success",
            "summary": summary + ".",
            "title": data.get("title", ""),
            "url": url
        }
    
    async def extract_data(self, url: str, pattern: str) -> Dict[str, Any]:
        result = await self.scrape_url(url)
        if result.get("status") != "success":
            return result
        
        import re
        data = result.get("data", {})
        full_text = data.get("text", "")
        matches = re.findall(pattern, full_text)
        
        return {
            "status": "success",
            "matches": matches,
            "count": len(matches)
        }


class OmniConnector:
    def __init__(self):
        self.gmail = GmailConnector()
        self.calendar = CalendarConnector()
        self.notion = NotionConnector()
        self.scraper = WebScraper()
        self.connected = {
            "gmail": False,
            "calendar": False,
            "notion": False,
            "scraper": False
        }
    
    async def connect_all(self) -> Dict[str, bool]:
        self.connected["gmail"] = await self.gmail.connect()
        self.connected["calendar"] = await self.calendar.connect()
        self.connected["notion"] = await self.notion.connect()
        self.connected["scraper"] = await self.scraper.connect()
        return self.connected
    
    async def disconnect_all(self) -> Dict[str, bool]:
        await self.gmail.disconnect()
        await self.calendar.disconnect()
        await self.notion.disconnect()
        await self.scraper.disconnect()
        return {k: False for k in self.connected}
    
    def status(self) -> Dict[str, bool]:
        return self.connected


omni_connector = OmniConnector()


async def execute_omni_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    oc = omni_connector
    
    if tool_name == "gmail_list":
        return await oc.gmail.list_emails(params.get("max_results", 10), params.get("query", ""))
    
    elif tool_name == "gmail_read":
        return await oc.gmail.read_email(params.get("message_id", ""))
    
    elif tool_name == "gmail_send":
        return await oc.gmail.send_email(
            params.get("to", ""),
            params.get("subject", ""),
            params.get("body", "")
        )
    
    elif tool_name == "gmail_search":
        return await oc.gmail.search_emails(params.get("query", ""), params.get("max_results", 5))
    
    elif tool_name == "calendar_list":
        return await oc.calendar.list_events(params.get("days_ahead", 7))
    
    elif tool_name == "calendar_today":
        return await oc.calendar.today_events()
    
    elif tool_name == "calendar_create":
        return await oc.calendar.create_event(
            params.get("title", ""),
            params.get("start_time", ""),
            params.get("end_time", ""),
            params.get("description", ""),
            params.get("location", "")
        )
    
    elif tool_name == "calendar_delete":
        return await oc.calendar.delete_event(params.get("event_id", ""))
    
    elif tool_name == "notion_list_databases":
        return await oc.notion.list_databases()
    
    elif tool_name == "notion_query":
        return await oc.notion.query_database(params.get("database_id", ""))
    
    elif tool_name == "notion_create_page":
        return await oc.notion.create_page(
            params.get("title", ""),
            params.get("content", ""),
            params.get("database_id", "")
        )
    
    elif tool_name == "web_scrape":
        return await oc.scraper.scrape_url(params.get("url", ""), params.get("selectors"))
    
    elif tool_name == "web_summarize":
        return await oc.scraper.summarize_page(params.get("url", ""), params.get("max_sentences", 5))
    
    elif tool_name == "web_extract":
        return await oc.scraper.extract_data(params.get("url", ""), params.get("pattern", ""))
    
    elif tool_name == "omni_connect":
        result = await oc.connect_all()
        return {"status": "success", "output": f"Connected: {result}"}
    
    elif tool_name == "omni_status":
        return {"status": "success", "output": oc.status()}
    
    else:
        return {"status": "error", "output": f"Unknown omni tool: {tool_name}"}