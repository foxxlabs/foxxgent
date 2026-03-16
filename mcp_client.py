import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from database import SessionLocal, Base

logger = logging.getLogger("foxxgent")

class MCPClient:
    def __init__(self):
        self.connected = False
        self.tools: Dict[str, Any] = {}
    
    async def connect(self, command: str, args: List[str] = None):
        try:
            self.process = await asyncio.create_subprocess_exec(
                command, *(args or []),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.connected = True
            logger.info(f"MCP client connected: {command}")
            await self.initialize()
            return True
        except Exception as e:
            logger.error(f"MCP connection failed: {e}")
            return False
    
    async def initialize(self):
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "FoxxGent", "version": "1.0.0"}
            }
        }
        response = await self.send_request(init_request)
        if response:
            await self.send_notification({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        return response
    
    async def send_request(self, request: Dict) -> Optional[Dict]:
        if not self.connected:
            return None
        try:
            data = json.dumps(request) + "\n"
            self.process.stdin.write(data.encode())
            await self.process.stdin.drain()
            
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                response = json.loads(line.decode())
                if "id" in response and response["id"] == request.get("id"):
                    if "error" in response:
                        logger.error(f"MCP error: {response['error']}")
                        return None
                    return response.get("result")
        except Exception as e:
            logger.error(f"MCP request failed: {e}")
        return None
    
    async def send_notification(self, notification: Dict):
        if not self.connected:
            return
        try:
            data = json.dumps(notification) + "\n"
            self.process.stdin.write(data.encode())
            await self.process.stdin.drain()
        except Exception as e:
            logger.error(f"MCP notification failed: {e}")
    
    async def list_tools(self) -> List[Dict]:
        if not self.connected:
            return []
        
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        result = await self.send_request(request)
        if result and "tools" in result:
            self.tools = {t["name"]: t for t in result["tools"]}
            return result["tools"]
        return []
    
    async def call_tool(self, name: str, arguments: Dict) -> Dict:
        if not self.connected:
            return {"status": "error", "output": "MCP not connected"}
        
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }
        
        result = await self.send_request(request)
        if result:
            content = result.get("content", [])
            output = ""
            for item in content:
                if item.get("type") == "text":
                    output += item.get("text", "")
            return {"status": "success", "output": output}
        return {"status": "error", "output": "Tool call failed"}
    
    async def disconnect(self):
        if self.connected:
            self.process.terminate()
            await self.process.wait()
            self.connected = False
            logger.info("MCP client disconnected")

class MCPServer:
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
    
    async def add_client(self, name: str, command: str, args: List[str] = None) -> bool:
        client = MCPClient()
        success = await client.connect(command, args)
        if success:
            self.clients[name] = client
            await client.list_tools()
            logger.info(f"Added MCP client: {name}")
        return success
    
    async def remove_client(self, name: str):
        if name in self.clients:
            await self.clients[name].disconnect()
            del self.clients[name]
    
    def get_client(self, name: str) -> Optional[MCPClient]:
        return self.clients.get(name)
    
    def list_clients(self) -> List[Dict]:
        return [
            {"name": name, "connected": client.connected, "tools": len(client.tools)}
            for name, client in self.clients.items()
        ]
    
    async def call_tool(self, client_name: str, tool_name: str, arguments: Dict) -> Dict:
        client = self.clients.get(client_name)
        if not client:
            return {"status": "error", "output": f"MCP client '{client_name}' not found"}
        return await client.call_tool(tool_name, arguments)

mcp_server = MCPServer()

async def get_mcp_tools() -> Dict[str, Any]:
    tools = {}
    for name, client in mcp_server.clients.items():
        for tool_name, tool in client.tools.items():
            tools[f"mcp_{name}_{tool_name}"] = {
                "client": name,
                "original_name": tool_name,
                "description": tool.get("description", "")
            }
    return tools