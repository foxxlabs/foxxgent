[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2.svg)](https://discord.gg/placeholder)

# FoxxGent - AI System Controller

> Control your server through natural language with autonomous AI reasoning

## Quick Install (One-Line)

Run this command to install FoxxGent with interactive setup:

```bash
curl -fsSL https://raw.githubusercontent.com/foxxlabs/foxxgent/main/install.sh | bash
```

Or to clone the repository first and then install:

```bash
curl -fsSL https://raw.githubusercontent.com/foxxlabs/foxxgent/main/install-bootstrap.sh | bash
```

> **Note:** Replace `foxxlabs/foxxgent` with your actual GitHub repository.

## Table of Contents
- [Quick Install](#quick-install-one-line)
- [Quick Start](#quick-start)
- [Features](#features)
- [Security](#security)
- [Installation](#installation)
  - [Docker (Recommended)](#docker-recommended)
  - [pip](#pip)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Telegram Setup](#telegram-setup)
- [Web UI Guide](#web-ui-guide)
- [API Endpoints](#api-endpoints)
- [Available Tools](#available-tools)
- [Omni-Connector](#omni-connector)
- [Autonomous Tasks](#autonomous-tasks)
- [MCP Server Support](#mcp-server-support)
- [Connection Manager](#connection-manager)
- [Memory System](#memory-system)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)

---

## Quick Start

```bash
# Docker (recommended)
docker-compose up -d

# Or with pip
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Visit **http://localhost:8000** to access the Web UI.

For detailed setup, see [Configuration](#configuration) and [Telegram Setup](#telegram-setup).

---

## Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI-Powered Chat** | Control your server using natural language with autonomous reasoning |
| 📱 **Telegram Integration** | Control your server from Telegram with secure pairing |
| 🔐 **Secure Pairing** | Unique pairing codes for device authentication |
| 📊 **System Monitoring** | Real-time CPU, Memory, Disk, and process stats |
| ⚡ **Task Management** | Run commands in background with sub-agents |
| 💾 **Persistent Memory** | AI remembers user preferences and important facts |
| 🌐 **Omni-Connector** | Gmail, Google Calendar, Notion, web scraping |
| 🕐 **Proactive Scheduler** | Cron-style autonomous task triggers |
| 🔍 **Cross-Platform Search** | Unified search across connected apps |
| 🌙 **Vibe-Awareness** | Time-based response style adjustment |
| 🔌 **MCP Support** | Model Context Protocol server integration |
| 📡 **WebSocket Streaming** | Real-time chat response streaming |

---

## Security

> ⚠️ **Important Security Notes**

- **Do not expose to public internet** without proper authentication (e.g., reverse proxy with authentication)
- **Change default secrets** before production use: update `SECRET_KEY` and `FOXXGENT_SECRET_KEY`
- **Run in Docker** for process isolation and easier security management
- **Never commit API keys** to version control
- Each server restart generates a new pairing code for Telegram authentication

---

## Installation

### Docker (Recommended)

```bash
docker-compose up -d
```

The Web UI will be available at `http://localhost:8000`.

### pip

```bash
pip install -r requirements.txt
```

---

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your API keys. See [`.env.example`](.env.example) for all available options.

### Required Variables
```bash
OPENROUTER_API_KEY=your_openrouter_key  # Get from https://openrouter.ai
```

### Optional Variables
```bash
# Telegram Bot
TELEGRAM_BOT_KEY=your_telegram_bot_token

# Google Services (for Gmail/Calendar)
GOOGLE_CREDENTIALS_PATH=./credentials.json

# Notion
NOTION_API_KEY=your_notion_token
NOTION_DATABASE_ID=your_database_id

# Security (CHANGE IN PRODUCTION!)
SECRET_KEY=your_secret_key
FOXXGENT_SECRET_KEY=production_secret_key
```

---

## Deployment

### Docker

The recommended way to run FoxxGent in production:

```bash
docker-compose up -d
```

Volume mounts:
- `foxxgent.db` - SQLite database (persists between restarts)
- `.env` - Environment variables (read-only)
- `credentials.json` - Google API credentials (read-only)

### Production Considerations

- Use a reverse proxy (nginx, Caddy) with authentication
- Enable HTTPS with valid certificates
- Change default secrets in `.env`
- Consider using Docker networks for additional isolation

---

## Telegram Setup

### Step 1: Create a Bot
1. Open Telegram and search for @BotFather
2. Send `/newbot` command
3. Follow the prompts to name your bot
4. Copy the bot token

### Step 2: Configure FoxxGent
Add the token to your `.env`:
```bash
TELEGRAM_BOT_KEY=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### Step 3: Pair Your Account
1. Start the server: `python main.py` or `docker-compose up`
2. Note the **Pairing Code** shown in the console
3. Open Telegram and message your bot:
   ```
   pair ABC1234
   ```
4. If successful, you'll see a welcome message

### Telegram Commands
| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and help |
| `/pair <code>` | Pair your Telegram account |
| `/unpair` | Unpair your account |
| `/compact` | Enable compact response mode |
| `/new_session` | Clear conversation context |
| `/status` | Show system statistics |

---

## Web UI Guide

### Chat Tab
- Type natural language commands
- AI automatically decides which tools to use
- Responses stream in real-time via WebSocket

### Tasks Tab
- View running sub-agents
- Monitor task progress
- View task results and history

### Settings Tab
- Configure AI model (default: openai/gpt-oss-120b)
- Set max tokens and temperature
- Configure Telegram pairing
- View system statistics

### Connections Tab
- Connect to 80+ third-party services
- Manage API credentials
- View connection status

---

## API Endpoints

### Chat API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chat/history` | Get chat history |
| POST | `/api/chat` | Send chat message |
| WS | `/api/chat/stream` | WebSocket streaming chat |

### Configuration API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Get full configuration |
| POST | `/api/config` | Update configuration |
| GET | `/api/stats` | Get system stats |

### Device Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | List paired devices |
| POST | `/api/devices/{chat_id}/toggle` | Enable/disable device |
| GET | `/api/pairing/code` | Get current pairing code |

### Sub-Agents
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sub-agents` | List sub-agents |
| POST | `/api/sub-agents` | Create sub-agent |
| DELETE | `/api/sub-agents/{id}` | Delete sub-agent |
| POST | `/api/sub-agents/{id}/run` | Run sub-agent task |

### Cron Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cron` | List cron tasks |

### Connections
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/connections` | List connections |
| POST | `/api/connect` | Connect to app |
| POST | `/api/disconnect` | Disconnect app |
| GET | `/api/skills` | List available skills |

### MCP Servers
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mcp` | List MCP servers |
| POST | `/api/mcp/add` | Add MCP server |
| POST | `/api/mcp/remove` | Remove MCP server |

### Omni-Connector
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/omni/status` | Connection status |
| POST | `/api/omni/connect` | Connect all services |
| GET | `/api/omni/gmail/list` | List emails |
| POST | `/api/omni/gmail/send` | Send email |
| GET | `/api/omni/calendar/events` | List calendar events |
| POST | `/api/omni/calendar/create` | Create calendar event |

### Memory
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/memory` | Get all memories |
| POST | `/api/memory` | Save memory |
| GET | `/api/memory/search` | Search memories |
| DELETE | `/api/memory` | Delete memory |

---

## Available Tools

### System Tools
| Tool | Description | Example |
|------|-------------|---------|
| `shell` | Run bash commands | `{"tool": "shell", "params": {"command": "ls -la"}}` |
| `system_stats` | Get CPU/Memory/Disk stats | `{"tool": "system_stats", "params": {}}` |
| `get_processes` | List running processes | `{"tool": "get_processes", "params": {}}` |
| `get_uptime` | Get system uptime | `{"tool": "get_uptime", "params": {}}` |
| `get_ip` | Get public IP | `{"tool": "get_ip", "params": {}}` |

### Docker Tools
| Tool | Description | Example |
|------|-------------|---------|
| `docker_ps` | List containers | `{"tool": "docker_ps", "params": {}}` |
| `docker_logs` | Get container logs | `{"tool": "docker_logs", "params": {"container": "web", "lines": 100}}` |
| `docker_stats` | Container statistics | `{"tool": "docker_stats", "params": {}}` |

### File Operations
| Tool | Description | Example |
|------|-------------|---------|
| `file_read` | Read file contents | `{"tool": "file_read", "params": {"path": "/etc/hostname"}}` |
| `file_write` | Write to file | `{"tool": "file_write", "params": {"path": "/tmp/test.txt", "content": "Hello"}}` |
| `file_list` | List directory | `{"tool": "file_list", "params": {"path": "/tmp"}}` |
| `file_delete` | Delete file | `{"tool": "file_delete", "params": {"path": "/tmp/test.txt"}}` |

### Cron & Scheduling
| Tool | Description | Example |
|------|-------------|---------|
| `cron_create` | Create cron job | `{"tool": "cron_create", "params": {"name": "backup", "command": "tar -czf backup.tar.gz /data", "schedule": "0 2 * * *"}}` |
| `cron_list` | List cron jobs | `{"tool": "cron_list", "params": {}}` |
| `cron_delete` | Delete cron job | `{"tool": "cron_delete", "params": {"task_id": 1}}` |

### Communication
| Tool | Description | Example |
|------|-------------|---------|
| `send_telegram` | Send Telegram message | `{"tool": "send_telegram", "params": {"chat_id": "123456", "text": "Hello!"}}` |
| `schedule_message` | Schedule reminder | `{"tool": "schedule_message", "params": {"chat_id": "123456", "message": "Check server", "delay_minutes": 30}}` |

### Web & Search
| Tool | Description | Example |
|------|-------------|---------|
| `web_search` | Search the web | `{"tool": "web_search", "params": {"query": "python fastapi tutorial"}}` |
| `download_file` | Download file from URL | `{"tool": "download_file", "params": {"url": "https://example.com/file.zip", "path": "/tmp/"}}` |

### Git Operations
| Tool | Description | Example |
|------|-------------|---------|
| `git_status` | Get git status | `{"tool": "git_status", "params": {"path": "/var/www/app"}}` |
| `git_pull` | Pull latest changes | `{"tool": "git_pull", "params": {"path": "/var/www/app"}}` |

### System Administration
| Tool | Description | Example |
|------|-------------|---------|
| `systemctl` | Control services | `{"tool": "systemctl", "params": {"action": "restart", "service": "nginx"}}` |
| `pip_install` | Install Python package | `{"tool": "pip_install", "params": {"package": "requests"}}` |
| `get_settings` | Get setting value | `{"tool": "get_settings", "params": {"key": "telegram_chat_id"}}` |

---

## Omni-Connector

The Omni-Connector provides integrated access to:

### Gmail
- List/search emails
- Read email content
- Send emails
- Manage labels

### Google Calendar
- List events
- Create events
- Delete events
- View today's schedule

### Notion
- List databases
- Query databases
- Create pages
- Update content

### Web Scraper
- Scrape URLs
- Extract data patterns
- Summarize pages

---

## Autonomous Tasks

Create scheduled tasks that run automatically:

### Task Types
- **morning_briefing**: System stats + calendar events
- **system_check**: Periodic health checks
- **email_sync**: Gmail synchronization
- **calendar_check**: Calendar event checks
- **custom**: User-defined shell commands

### Creating Tasks
Use the chat interface:
```
Create a task to check disk space every day at 8am
```

Or via API:
```bash
curl -X POST http://localhost:8000/api/autonomous/create \
  -H "Content-Type: application/json" \
  -d '{"name": "disk_check", "task_type": "system_check", "schedule": "0 8 * * *"}'
```

---

## MCP Server Support

FoxxGent supports Model Context Protocol (MCP) servers for extended capabilities.

### Adding an MCP Server
```bash
curl -X POST http://localhost:8000/api/mcp/add \
  -H "Content-Type: application/json" \
  -d '{"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]}'
```

### Using MCP Tools
MCP tools are automatically available to the AI and can be invoked via natural language.

---

## Connection Manager

FoxxGent supports 80+ third-party integrations:

### Communication
- Gmail, Google Calendar, Slack, Discord, Telegram, WhatsApp, Microsoft Teams, Zoom

### Productivity
- Notion, Trello, Asana, Todoist, Airtable, ClickUp, Monday.com

### Developer Tools
- GitHub, GitLab, Bitbucket, Jira, Linear

### Cloud & DevOps
- AWS, Google Drive, DigitalOcean, Heroku, Vercel, Cloudflare

### CRM & Marketing
- Salesforce, HubSpot, Pipedrive, Mailchimp, SendGrid, Stripe

### AI & ML
- OpenAI, Anthropic, Hugging Face, Replicate

---

## Memory System

FoxxGent has a persistent memory system for storing:

### Memory Types
- **fact**: Factual information about the user
- **preference**: User preferences and settings
- **important**: Important reminders
- **context**: Conversation context

### Using Memory
```python
# Save a memory
{"tool": "save_memory", "params": {"key": "server_ip", "value": "192.168.1.100", "type": "fact"}}

# Retrieve memories
# Just chat naturally - the AI automatically loads relevant memories
```

---

## Troubleshooting

### Bot Not Starting
```bash
# Check Python version (requires 3.10+)
python --version

# Install missing dependencies
pip install -r requirements.txt
```

### Telegram Pairing Issues
1. Ensure the bot token is correct in `.env`
2. Check the pairing code hasn't expired (regenerates on restart)
3. Verify the bot is started properly

### Connection Errors
```bash
# Check API keys are set
echo $OPENROUTER_API_KEY
echo $TELEGRAM_BOT_KEY

# View server logs
python main.py 2>&1 | tee logs.txt
```

### Database Issues
```bash
# Backup and reset database
cp foxxgent.db foxxgent.db.bak
rm foxxgent.db
python main.py  # Recreates database
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FoxxGent                              │
├─────────────────────────────────────────────────────────────┤
│  Web UI (HTML/CSS/JS)  │  Telegram Bot  │  REST API       │
├─────────────────────────────────────────────────────────────┤
│                     FastAPI Server                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │Agent Brain │  │  Database   │  │ Connection Manager│   │
│  │  (AI)      │  │  (SQLite)   │  │   (80+ apps)     │   │
│  └─────────────┘  └─────────────┘  └──────────────────┘   │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │Exec Tools   │  │Omni Connector│  │Proactive Sched. │   │
│  └─────────────┘  └─────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## License

MIT
