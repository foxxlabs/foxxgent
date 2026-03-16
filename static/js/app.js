class FoxxGentApp {
    constructor() {
        this.ws = null;
        this.messageContainer = null;
        this.chatInput = null;
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.messageContainer = document.getElementById('chatMessages');
            this.chatInput = document.getElementById('chatInput');
            this.initWebSocket();
            this.initEventListeners();
            this.initNavigation();
            this.startPolling();
            this.loadConfig();
        });
    }

    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/api/chat/stream`);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateBotStatus(true);
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateBotStatus(false);
            setTimeout(() => this.initWebSocket(), 3000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleWebSocketMessage(data) {
        console.log('WS message:', data);
        try {
            if (data.type === 'start') {
                this.showTypingIndicator();
                this.setAiStatus('thinking', 'Thinking...');
            } else if (data.type === 'content') {
                if (!data.content && data.delta === false) return;
                this.updateTypingContent(data.content, data.delta);
            } else if (data.type === 'tool') {
                this.hideTypingIndicator();
                this.setAiStatus('tool', `Running ${data.tool}...`);
                this.addMessage('assistant', `🔧 Running: ${data.tool}\n${data.result?.output || 'Done'}`);
            } else if (data.type === 'end') {
                this.hideTypingIndicator();
                this.setAiStatus('idle', 'Ready');
            }
        } catch (error) {
            console.error('Error handling WebSocket message:', error);
        }
    }

    initEventListeners() {
        const sendBtn = document.getElementById('sendButton');
        const chatInput = document.getElementById('chatInput');

        const sendMessage = () => {
            const message = chatInput.value.trim();
            if (!message) return;
            
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                console.log('WebSocket not connected, readyState:', this.ws?.readyState);
                alert('Connection not ready. Please wait a moment and try again.');
                return;
            }
            
            this.addMessage('user', message);
            chatInput.value = '';
            
            this.ws.send(JSON.stringify({message}));
        };

        sendBtn.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }

    initNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                this.switchPage(page);
            });
        });

        const tabs = document.querySelectorAll('.tab[data-tab]');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.loadTasksByStatus(tab.dataset.tab);
            });
        });
    }

    switchPage(page) {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelector(`.nav-item[data-page="${page}"]`).classList.add('active');
        
        document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
        document.getElementById(`page-${page}`).classList.remove('hidden');
        
        if (page === 'skills') this.loadSkills();
        if (page === 'config') this.loadConfig();
        if (page === 'chat') this.scrollToBottom();
        if (page === 'logs') this.loadLogs();
        if (page === 'connections') this.loadConnections();
    }

    async loadSkills() {
        const container = document.getElementById('skillsList');
        try {
            const response = await fetch('/api/skills');
            const data = await response.json();
            const skills = data.skills || [];
            
            if (skills.length === 0) {
                container.innerHTML = '<div style="color: var(--win8-text-muted);">No skills installed. Add a skill to get started.</div>';
                return;
            }
            
            container.innerHTML = skills.map(skill => `
                <div class="glass-card" style="padding: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                        <div>
                            <h4 style="margin: 0; font-weight: 600;">${this.escapeHtml(skill.name)}</h4>
                            <small style="color: var(--win8-text-muted);">v${this.escapeHtml(skill.version || '1.0.0')}</small>
                        </div>
                        <label class="toggle-switch" style="margin: 0;">
                            <input type="checkbox" ${skill.enabled ? 'checked' : ''} onchange="toggleSkill('${skill.name}', this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                    <p style="font-size: 12px; color: var(--win8-text-secondary); margin: 8px 0;">${this.escapeHtml(skill.description || 'No description')}</p>
                    ${skill.endpoint ? `<small style="color: var(--win8-text-muted);">Endpoint: ${this.escapeHtml(skill.endpoint)}</small>` : ''}
                    <div style="margin-top: 12px;">
                        <button class="btn btn-secondary" style="padding: 4px 12px; font-size: 11px;" onclick="viewSkillDetails('${skill.name}')">Details</button>
                        <button class="btn btn-secondary" style="padding: 4px 12px; font-size: 11px;" onclick="removeSkill('${skill.name}')">Remove</button>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = '<div style="color: var(--win8-error);">Failed to load skills</div>';
        }
    }

    async loadLogs() {
        const container = document.getElementById('logContainer');
        const level = document.getElementById('logLevel')?.value || '';
        
        try {
            const url = level ? `/api/logs?level=${level}` : '/api/logs';
            const response = await fetch(url);
            const data = await response.json();
            const logs = data.logs || [];
            
            if (logs.length === 0) {
                container.innerHTML = '<div style="color: var(--text-muted);">No logs available</div>';
                return;
            }
            
            container.innerHTML = logs.map(log => {
                const color = log.level === 'ERROR' ? 'var(--md-error)' : 
                              log.level === 'WARNING' ? '#ff9800' : 
                              log.level === 'INFO' ? 'var(--md-primary)' : 'var(--text-muted)';
                return `<div style="margin-bottom: 4px; color: ${color};">
                    <span style="opacity: 0.6;">${log.time.split('T')[1].split('.')[0]}</span>
                    <span style="font-weight: bold;">[${log.level}]</span>
                    ${this.escapeHtml(log.message)}
                </div>`;
            }).join('');
        } catch (error) {
            container.innerHTML = '<div style="color: var(--md-error);">Failed to load logs</div>';
        }
    }
    
    async loadConnections() {
        const appCategories = document.getElementById('appCategories');
        const connectedApps = document.getElementById('connectedApps');
        const connectionCount = document.getElementById('connectionCount');
        
        try {
            const response = await fetch('/api/connections');
            const data = await response.json();
            
            if (connectionCount) {
                connectionCount.textContent = `${data.count} connected`;
            }
            
            if (appCategories) {
                let html = '';
                for (const [category, apps] of Object.entries(data.by_category || {})) {
                    html += `<div style="margin-bottom: 16px;">
                        <h4 style="color: var(--win8-accent-light); margin-bottom: 8px;">${category}</h4>
                        <div style="display: flex; flex-wrap: wrap; gap: 8px;">`;
                    
                    for (const app of apps) {
                        const isConnected = data.connected.includes(app.id);
                        html += `<button class="btn ${isConnected ? 'btn-primary' : 'btn-secondary'}" 
                            style="padding: 8px 12px; font-size: 12px;"
                            onclick="showConnectModal('${app.id}')"
                            ${isConnected ? 'disabled' : ''}>
                            ${app.icon} ${app.name}${isConnected ? ' ✓' : ''}
                        </button>`;
                    }
                    
                    html += `</div></div>`;
                }
                appCategories.innerHTML = html || '<div style="color: var(--text-muted);">No apps available</div>';
            }
            
            if (connectedApps) {
                if (data.connected.length === 0) {
                    connectedApps.innerHTML = '<div style="color: var(--text-muted); padding: 20px; text-align: center;">No apps connected yet</div>';
                } else {
                    let html = '';
                    for (const appId of data.connected) {
                        const appInfo = data.available_apps.find(a => a.id === appId);
                        if (appInfo) {
                            html += `<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: var(--win8-bg); border: 1px solid var(--win8-border); margin-bottom: 8px; border-radius: 4px;">
                                <div>
                                    <span style="font-size: 20px;">${appInfo.icon}</span>
                                    <span style="margin-left: 8px; font-weight: 600;">${appInfo.name}</span>
                                </div>
                                <button class="btn btn-secondary" style="padding: 4px 12px;" onclick="disconnectApp('${appId}')">Disconnect</button>
                            </div>`;
                        }
                    }
                    connectedApps.innerHTML = html;
                }
            }
            
            this.loadConnectionSkills();
            
        } catch (error) {
            console.error('Failed to load connections:', error);
        }
    }
    
    async loadConnectionSkills() {
        const container = document.getElementById('connectionActions');
        if (!container) return;
        
        try {
            const response = await fetch('/api/connections/skills');
            const data = await response.json();
            
            if (data.skills && data.skills.length > 0) {
                container.innerHTML = data.skills.map(skill => `
                    <div style="display: flex; align-items: center; gap: 8px; padding: 8px; background: var(--win8-bg); border: 1px solid var(--win8-border); margin-bottom: 4px; border-radius: 4px;">
                        <span style="font-size: 16px;">⚡</span>
                        <span style="flex: 1;">${skill.app_name}: ${skill.capability.replace('_', ' ')}</span>
                        <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" 
                            onclick="testConnectionAction('${skill.app_id}', '${skill.capability}')">Test</button>
                    </div>
                `).join('');
            } else {
                container.innerHTML = '<div style="color: var(--text-muted);">Connect an app to see available actions</div>';
            }
        } catch (error) {
            console.error('Failed to load skills:', error);
        }
    }

    addMessage(role, content) {
        if (!this.messageContainer) {
            console.error('messageContainer is null!');
            return;
        }
        
        console.log('Adding message:', role, content);
        
        const avatar = role === 'user' ? 'Y' : 'F';
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        this.messageContainer.appendChild(div);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        if (!this.messageContainer) return;
        
        const existing = this.messageContainer.querySelector('.typing');
        if (existing) existing.remove();
        
        const div = document.createElement('div');
        div.className = 'message assistant typing';
        div.innerHTML = `
            <div class="message-avatar">F</div>
            <div class="message-content"></div>
        `;
        this.messageContainer.appendChild(div);
    }

    updateTypingContent(content, isDelta) {
        if (!this.messageContainer) return;
        
        if (!content && !isDelta) return;
        
        const typingDiv = this.messageContainer.querySelector('.typing .message-content');
        if (typingDiv) {
            if (isDelta) {
                typingDiv.textContent += content;
            } else {
                typingDiv.textContent = content;
            }
        } else {
            this.addMessage('assistant', content);
        }
    }

    hideTypingIndicator() {
        if (!this.messageContainer) return;
        
        const typing = this.messageContainer.querySelector('.typing');
        if (typing) {
            typing.classList.remove('typing');
            console.log('Hidden typing, final content:', typing.querySelector('.message-content')?.textContent);
        }
    }

    scrollToBottom() {
        if (this.messageContainer) {
            this.messageContainer.scrollTop = this.messageContainer.scrollHeight;
        }
    }

    updateBotStatus(online) {
        if (!this.messageContainer) return;
        
        const dots = document.querySelectorAll('#botStatusDot, #configBotStatusDot');
        const texts = document.querySelectorAll('#botStatusText, #configBotText');
        
        dots.forEach(dot => {
            dot.classList.toggle('online', online);
            dot.classList.toggle('offline', !online);
        });
        
        texts.forEach(text => {
            text.textContent = online ? 'Online' : 'Offline';
        });
    }

    async startPolling() {
        this.updateSystemStats();
        this.updateTime();
        this.loadAgents();
        this.setAiStatus('idle', 'Ready');
        
        setInterval(() => this.updateSystemStats(), 5000);
        setInterval(() => this.updateTime(), 1000);
        setInterval(() => this.loadAgents(), 10000);
        setInterval(() => this.updateOmniConnectors(), 60000);
    }
    
    updateTime() {
        const tileTimeValue = document.getElementById('tileTimeValue');
        if (tileTimeValue) {
            const now = new Date();
            const hours = now.getHours().toString().padStart(2, '0');
            const minutes = now.getMinutes().toString().padStart(2, '0');
            tileTimeValue.textContent = `${hours}:${minutes}`;
        }
    }
    
    async updateOmniConnectors() {
        try {
            const response = await fetch('/api/omni/status');
            const data = await response.json();
            
            const tileOmniStatus = document.getElementById('tileOmniStatus');
            if (tileOmniStatus) {
                const connected = Object.values(data).filter(v => v).length;
                tileOmniStatus.textContent = `${connected}/4`;
            }
        } catch (error) {
            console.error('Failed to update omni connectors:', error);
        }
    }

    async updateSystemStats() {
        try {
            const response = await fetch('/api/system');
            const data = await response.json();
            
            if (data.stats) {
                const stats = data.stats;
                
                const cpuBar = document.getElementById('cpuBar');
                const memBar = document.getElementById('memBar');
                const diskBar = document.getElementById('diskBar');
                const statCpu = document.getElementById('statCpu');
                const statMem = document.getElementById('statMem');
                const statDisk = document.getElementById('statDisk');
                
                if (cpuBar) cpuBar.style.width = `${stats.cpu_percent}%`;
                if (memBar) memBar.style.width = `${stats.memory_percent}%`;
                if (diskBar) diskBar.style.width = `${stats.disk_percent}%`;
                if (statCpu) statCpu.textContent = `${stats.cpu_percent.toFixed(0)}%`;
                if (statMem) statMem.textContent = `${stats.memory_percent.toFixed(0)}%`;
                if (statDisk) statDisk.textContent = `${stats.disk_percent.toFixed(0)}%`;
                
                this.updateLiveTiles(stats);
            }
            
            if (data.token_usage && data.token_usage.last_30_days) {
                const usage = data.token_usage.last_30_days;
                const tileTokensValue = document.getElementById('tileTokensValue');
                const tileTokensBar = document.getElementById('tileTokensBar');
                if (tileTokensValue) {
                    tileTokensValue.textContent = this.formatNumber(usage.total_tokens);
                }
                if (tileTokensBar) {
                    const maxTokens = 1000000;
                    const percent = Math.min((usage.total_tokens / maxTokens) * 100, 100);
                    tileTokensBar.style.width = `${percent}%`;
                }
            }
        } catch (error) {
            console.error('Failed to update system stats:', error);
        }
    }
    
    updateLiveTiles(stats) {
        const tileCpuBar = document.getElementById('tileCpuBar');
        const tileCpuValue = document.getElementById('tileCpuValue');
        const tileMemBar = document.getElementById('tileMemBar');
        const tileMemValue = document.getElementById('tileMemValue');
        
        if (tileCpuBar) tileCpuBar.style.width = `${stats.cpu_percent}%`;
        if (tileCpuValue) tileCpuValue.textContent = `${stats.cpu_percent.toFixed(0)}%`;
        if (tileMemBar) tileMemBar.style.width = `${stats.memory_percent}%`;
        if (tileMemValue) tileMemValue.textContent = `${stats.memory_percent.toFixed(0)}%`;
        
        const tileCpu = document.getElementById('tile-cpu');
        if (tileCpu) {
            if (stats.cpu_percent > 80) {
                tileCpu.classList.add('alert');
            } else {
                tileCpu.classList.remove('alert');
            }
        }
    }
    
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
    
    updateAgentTile(status) {
        const agentTile = document.getElementById('tile-agent');
        const agentTileStatus = document.getElementById('agentTileStatus');
        const agentTileIcon = document.getElementById('agentTileIcon');
        const agentTilePulse = document.getElementById('agentTilePulse');
        
        if (agentTile) {
            if (status === 'thinking') {
                agentTile.classList.add('active');
                agentTile.classList.remove('alert');
                if (agentTileStatus) agentTileStatus.textContent = 'Thinking';
                if (agentTilePulse) agentTilePulse.classList.add('running');
            } else if (status === 'running') {
                agentTile.classList.add('active');
                agentTile.classList.remove('alert');
                if (agentTileStatus) agentTileStatus.textContent = 'Running';
                if (agentTilePulse) agentTilePulse.classList.add('running');
            } else {
                agentTile.classList.remove('active');
                agentTile.classList.remove('alert');
                if (agentTileStatus) agentTileStatus.textContent = 'Idle';
                if (agentTilePulse) agentTilePulse.classList.remove('running');
            }
        }
    }

    async loadAgents() {
        try {
            const response = await fetch('/api/agents');
            const data = await response.json();
            
            const countEl = document.getElementById('activeAgentsCount');
            if (countEl) {
                const running = data.agents?.filter(a => a.status === 'running').length || 0;
                countEl.textContent = running;
            }
        } catch (error) {
            console.error('Failed to load agents:', error);
        }
    }

    async loadAllAgents() {
        this.loadAgents();
    }

    async loadTasksByStatus(status) {
        this.loadAgents();
    }

    renderTaskCard(agent) {
        const time = agent.started_at ? new Date(agent.started_at).toLocaleString() : '';
        return `
            <div class="task-card" draggable="true" ondragstart="drag(event)" data-id="${agent.id}">
                <div class="task-title">${this.escapeHtml(agent.name)}</div>
                <div class="task-desc">${this.escapeHtml(agent.task || 'No description')}</div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="task-status ${agent.status}">${agent.status}</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="task-time"><span class="material-icons" style="font-size: 12px;">schedule</span>${time}</span>
                        <button class="icon-btn" onclick="deleteTask('${agent.id}')" title="Delete task" style="opacity: 0.7;">
                            <span class="material-icons" style="font-size: 16px; color: var(--md-error);">delete</span>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    setAiStatus(status, text) {
        const agentTile = document.getElementById('tile-agent');
        const agentTileStatus = document.getElementById('agentTileStatus');
        const agentTileIcon = document.getElementById('agentTileIcon');
        const agentTilePulse = document.getElementById('agentTilePulse');
        
        if (!agentTile) return;
        
        if (status === 'thinking') {
            agentTile.classList.add('active');
            agentTile.classList.remove('alert');
            if (agentTileStatus) agentTileStatus.textContent = text || 'Thinking...';
            if (agentTileIcon) agentTileIcon.querySelector('span').textContent = 'psychology';
            if (agentTilePulse) agentTilePulse.classList.add('running');
        } else if (status === 'tool') {
            agentTile.classList.add('active');
            agentTile.classList.remove('alert');
            agentTile.classList.add('tool-running');
            if (agentTileStatus) agentTileStatus.textContent = '🔧 ' + (text || 'Running tool...');
            if (agentTileIcon) agentTileIcon.querySelector('span').textContent = 'build';
            if (agentTilePulse) agentTilePulse.classList.add('running');
        } else {
            agentTile.classList.remove('active', 'thinking', 'tool-running');
            agentTile.classList.remove('running');
            if (agentTileStatus) agentTileStatus.textContent = text || 'Idle';
            if (agentTileIcon) agentTileIcon.querySelector('span').textContent = 'smart_toy';
            if (agentTilePulse) agentTilePulse.classList.remove('running');
        }
        
        this.updateAgentTile?.(status);
    }

    async loadCronJobs() {
        const container = document.getElementById('cronList');
        try {
            const response = await fetch('/api/cron');
            const data = await response.json();
            
            const tasks = data.tasks || [];
            if (tasks.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <span class="material-icons">schedule</span>
                        <p>No scheduled tasks</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = tasks.map(task => `
                <div class="agent-card">
                    <div class="agent-info">
                        <h4>${this.escapeHtml(task.name)}</h4>
                        <p>${this.escapeHtml(task.command)}</p>
                    </div>
                    <div class="agent-actions">
                        <span class="status-chip running">${task.schedule}</span>
                        <button class="icon-btn" onclick="deleteCron(${task.id})">
                            <span class="material-icons">delete</span>
                        </button>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = '<p style="color: var(--md-error);">Failed to load cron jobs</p>';
        }
    }

    async loadConfig() {
        try {
            const [configRes, statusRes, pairingRes, usersRes, mcpRes] = await Promise.all([
                fetch('/api/config'),
                fetch('/api/bot/status'),
                fetch('/api/pairing/code'),
                fetch('/api/pairing/users'),
                fetch('/api/mcp')
            ]);
            
            const config = await configRes.json();
            const statusData = await statusRes.json();
            const pairingData = await pairingRes.json();
            const usersData = await usersRes.json();
            const mcpData = await mcpRes.json();
            
            const el = (id) => document.getElementById(id);
            
            if (el('configModel')) el('configModel').value = config.model || 'openai/gpt-oss-120b';
            if (el('configTemp')) el('configTemp').value = config.temperature || 0.7;
            if (el('configMaxTokens')) el('configMaxTokens').value = config.max_tokens || 100000;
            if (el('configChatId')) el('configChatId').value = config.telegram_chat_id || '';
            
            if (el('notifyTelegram') && config.notifications) {
                el('notifyTelegram').checked = config.notifications.telegram !== false;
            }
            
            if (document.getElementById('toolsList')) {
                const defaultTools = {
                    "shell": true, "web_search": true, "file_read": true, "file_write": true,
                    "docker_ps": true, "docker_logs": true, "system_stats": true, "get_processes": true,
                    "systemctl": true, "send_telegram": true, "schedule_message": true, "pip_install": true,
                    "git_status": true, "git_pull": true, "cron_create": true, "get_ip": true
                };
                const tools = config.tools || defaultTools;
                let toolsHtml = '';
                for (const [name, enabled] of Object.entries(tools)) {
                    toolsHtml += `<label style="display: flex; align-items: center; gap: 8px; padding: 6px; background: var(--win8-bg); border: 1px solid var(--win8-border);">
                        <input type="checkbox" ${enabled ? 'checked' : ''} data-tool="${name}">
                        ${name.replace('_', ' ')}
                    </label>`;
                }
                document.getElementById('toolsList').innerHTML = toolsHtml;
            }
            
            if (document.getElementById('mcpServers')) {
                const servers = mcpData.servers || [];
                if (servers.length === 0) {
                    document.getElementById('mcpServers').innerHTML = '<div style="color: var(--win8-text-muted);">No MCP servers connected</div>';
                } else {
                    document.getElementById('mcpServers').innerHTML = servers.map(s => `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; background: var(--win8-bg); border: 1px solid var(--win8-border); margin-bottom: 4px;">
                            <span>${s.name} (${s.tools} tools)</span>
                            <span class="status-chip ${s.connected ? 'online' : 'offline'}">${s.connected ? 'Connected' : 'Disconnected'}</span>
                            <button class="icon-btn" onclick="removeMcpServer('${s.name}')"><span class="material-icons">delete</span></button>
                        </div>
                    `).join('');
                }
            }
            
            if (document.getElementById('pairedDevices')) {
                const users = usersData.users || [];
                if (users.length === 0) {
                    document.getElementById('pairedDevices').innerHTML = '<div style="color: var(--win8-text-muted);">No paired devices</div>';
                } else {
                    document.getElementById('pairedDevices').innerHTML = users.map(u => `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; background: var(--win8-bg); border: 1px solid var(--win8-border); margin-bottom: 4px;">
                            <span>${u.name || u.username || u.chat_id}</span>
                            <label class="toggle-switch" style="margin: 0 8px;">
                                <input type="checkbox" ${u.enabled ? 'checked' : ''} onchange="toggleDevice('${u.chat_id}', this.checked)">
                                <span class="slider"></span>
                            </label>
                        </div>
                    `).join('');
                }
            }
            
            const statusContainer = document.getElementById('botStatusConfig');
            if (statusContainer) {
                statusContainer.innerHTML = statusData.running 
                    ? '<span class="status-chip online">Online</span>'
                    : '<span class="status-chip offline">Offline</span>';
            }
            
            const codeElement = document.getElementById('pairingCode');
            if (codeElement && pairingData.code) {
                codeElement.textContent = pairingData.code;
            }
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }

    quickAction(action) {
        document.getElementById('chatInput').value = action;
        document.getElementById('sendButton').click();
    }

    async refreshPairingCode() {
        try {
            const response = await fetch('/api/pairing/code');
            const data = await response.json();
            document.getElementById('pairingCode').textContent = data.code || '------';
        } catch (e) {
            console.error('Failed to refresh code');
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

async function deleteCron(taskId) {
    if (!confirm('Delete this cron job?')) return;
    
    const response = await fetch(`/api/cron/delete`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({task_id: taskId})
    });
    
    const data = await response.json();
    if (data.status === 'success') {
        app.loadCronJobs();
    } else {
        alert('Failed to delete cron');
    }
}

let draggedTaskId = null;

function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
    draggedTaskId = ev.target.dataset.id;
    ev.target.classList.add('dragging');
}

function drop(ev, status) {
    ev.preventDefault();
    document.querySelectorAll('.task-card').forEach(card => card.classList.remove('dragging'));
    
    if (draggedTaskId && status) {
        console.log('Move task', draggedTaskId, 'to', status);
    }
    draggedTaskId = null;
}

const app = new FoxxGentApp();

async function deleteTask(agentId) {
    if (!confirm('Delete this task?')) return;
    
    try {
        const response = await fetch('/api/agents/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({agent_id: agentId})
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            app.loadTaskBoard();
        } else {
            alert('Failed to delete task');
        }
    } catch (error) {
        alert('Failed to delete task');
    }
}

async function createTask() {
    const name = document.getElementById('taskName').value.trim();
    const task = document.getElementById('taskDescription').value.trim();
    
    if (!name || !task) {
        alert('Please enter task name and description');
        return;
    }
    
    try {
        const response = await fetch('/api/agents/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, task: task})
        });
        
        const data = await response.json();
        if (data.status === 'started') {
            document.getElementById('taskName').value = '';
            document.getElementById('taskDescription').value = '';
            document.getElementById('createTaskModal').style.display = 'none';
            app.loadTaskBoard();
        } else {
            alert('Failed to create task');
        }
    } catch (error) {
        alert('Failed to create task');
    }
}

function openCreateTaskModal() {
    document.getElementById('createTaskModal').style.display = 'flex';
}

function closeCreateTaskModal() {
    document.getElementById('createTaskModal').style.display = 'none';
}

async function loadLogs() {
    app.loadLogs();
}

async function clearLogs() {
    if (!confirm('Clear all logs?')) return;
    await fetch('/api/logs/clear', { method: 'POST' });
    app.loadLogs();
}

async function saveAllConfig() {
    const el = (id) => document.getElementById(id);
    const config = {
        model: el('configModel')?.value || 'openai/gpt-oss-120b',
        temperature: parseFloat(el('configTemp')?.value || 0.7),
        max_tokens: parseInt(el('configMaxTokens')?.value || 100000),
        telegram_chat_id: el('configChatId')?.value || '',
        notifications: {
            telegram: el('notifyTelegram')?.checked !== false
        },
        tools: {}
    };
    
    const toolCheckboxes = document.querySelectorAll('#toolsList input[type="checkbox"]');
    toolCheckboxes.forEach(cb => {
        config.tools[cb.dataset.tool] = cb.checked;
    });
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const data = await response.json();
        if (data.status === 'success') {
            alert('Settings saved!');
        } else {
            alert('Failed to save settings');
        }
    } catch (error) {
        alert('Failed to save settings');
    }
}

async function addMcpServer() {
    const name = document.getElementById('mcpName').value.trim();
    const command = document.getElementById('mcpCommand').value.trim();
    const argsStr = document.getElementById('mcpArgs').value.trim();
    const args = argsStr ? argsStr.split(' ').filter(a => a) : [];
    
    if (!name || !command) {
        alert('Please enter server name and command');
        return;
    }
    
    try {
        const response = await fetch('/api/mcp/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, command, args})
        });
        const data = await response.json();
        if (data.status === 'success') {
            document.getElementById('mcpName').value = '';
            document.getElementById('mcpCommand').value = '';
            document.getElementById('mcpArgs').value = '';
            app.loadConfig();
        } else {
            alert('Failed to add MCP server');
        }
    } catch (error) {
        alert('Failed to add MCP server');
    }
}

async function removeMcpServer(name) {
    if (!confirm(`Remove MCP server "${name}"?`)) return;
    
    try {
        await fetch('/api/mcp/remove', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });
        app.loadConfig();
    } catch (error) {
        alert('Failed to remove MCP server');
    }
}

async function toggleDevice(chatId, enabled) {
    try {
        await fetch('/api/pairing/toggle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({chat_id: chatId, enabled})
        });
    } catch (error) {
        console.error('Failed to toggle device');
    }
}

function sendCommand(cmd) {
    const chatInput = document.getElementById('chatInput');
    chatInput.value = cmd;
    document.getElementById('sendButton').click();
}

function showAddSkillModal() {
    document.getElementById('addSkillModal').style.display = 'flex';
}

function closeAddSkillModal() {
    document.getElementById('addSkillModal').style.display = 'none';
}

async function saveNewSkillFromMarkdown() {
    const markdown = document.getElementById('skillMarkdown').value.trim();
    
    if (!markdown) {
        alert('Please paste a skill in markdown format');
        return;
    }
    
    const lines = markdown.split('\n');
    const skill = {
        name: '',
        version: '1.0.0',
        description: '',
        endpoint: '',
        api_key: '',
        tools: []
    };
    
    let currentTool = '';
    let toolDesc = '';
    
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        
        if (trimmed.startsWith('name:')) {
            skill.name = trimmed.substring(5).trim();
        } else if (trimmed.startsWith('version:')) {
            skill.version = trimmed.substring(8).trim();
        } else if (trimmed.startsWith('description:')) {
            skill.description = trimmed.substring(12).trim();
        } else if (trimmed.startsWith('endpoint:')) {
            skill.endpoint = trimmed.substring(9).trim();
        } else if (trimmed.startsWith('api_key:') || trimmed.startsWith('api key:')) {
            skill.api_key = trimmed.split(':').slice(1).join(':').trim();
        } else if (trimmed.startsWith('- ')) {
            const toolPart = trimmed.substring(2);
            if (toolPart.includes(':')) {
                const [toolName, ...descParts] = toolPart.split(':');
                skill.tools.push({ name: toolName.trim(), description: descParts.join(':').trim() });
            } else {
                skill.tools.push({ name: toolPart.trim(), description: '' });
            }
        }
    }
    
    if (!skill.name) {
        alert('Skill must have a name (name: skill-name)');
        return;
    }
    
    try {
        const response = await fetch('/api/skills/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: skill.name,
                version: skill.version,
                description: skill.description,
                endpoint: skill.endpoint,
                api_key: skill.api_key,
                tools: skill.tools
            })
        });
        const data = await response.json();
        if (data.status === 'success') {
            closeAddSkillModal();
            document.getElementById('skillMarkdown').value = '';
            app.loadSkills();
            alert('✓ Skill added successfully!');
        } else {
            alert('Failed to add skill: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to add skill: ' + error.message);
    }
}

async function addSkillFromUrl() {
    const url = document.getElementById('skillUrl').value.trim();
    if (!url) {
        alert('Please enter a URL');
        return;
    }
    
    try {
        const response = await fetch('/api/skills/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url})
        });
        const data = await response.json();
        if (data.status === 'success') {
            document.getElementById('skillUrl').value = '';
            app.loadSkills();
        } else {
            alert('Failed to add skill from URL');
        }
    } catch (error) {
        alert('Failed to add skill from URL');
    }
}

async function addBuiltInSkill(skillName) {
    const skills = {
        clawreach: {name: 'clawreach', version: '1.2.6', description: 'AI agent messaging relay for OpenClaw', endpoint: 'https://clawreach.com/api/v1'},
        websearch: {name: 'websearch', version: '1.0.0', description: 'Web search capability', endpoint: ''},
        filesystem: {name: 'filesystem', version: '1.0.0', description: 'File system operations', endpoint: ''}
    };
    
    const skill = skills[skillName];
    if (!skill) return;
    
    try {
        const response = await fetch('/api/skills/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(skill)
        });
        app.loadSkills();
    } catch (error) {
        console.error('Failed to add skill', error);
    }
}

async function toggleSkill(name, enabled) {
    try {
        await fetch('/api/skills/toggle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, enabled})
        });
    } catch (error) {
        console.error('Failed to toggle skill');
    }
}

async function removeSkill(name) {
    if (!confirm(`Remove skill "${name}"?`)) return;
    
    try {
        await fetch('/api/skills/remove', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });
        app.loadSkills();
    } catch (error) {
        alert('Failed to remove skill');
    }
}

function viewSkillDetails(name) {
    alert(`Skill details for ${name} - coming soon!`);
}

// Sidebar & Live Tiles
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

let eventSource = null;

function connectSSE() {
    if (eventSource) eventSource.close();
    
    eventSource = new EventSource('/api/stream');
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'thought') {
                updateThoughtStream(data.data);
            } else if (data.type === 'stats') {
                updateLiveStats(data.data);
            }
        } catch (e) {
            console.error('SSE parse error:', e);
        }
    };
    
    eventSource.onerror = function() {
        console.log('SSE connection lost, retrying...');
        setTimeout(connectSSE, 5000);
    };
}

function updateThoughtStream(thought) {
    const container = document.getElementById('thoughtStream');
    if (!container) return;
    
    const div = document.createElement('div');
    div.className = `thought ${thought.status || ''}`;
    div.innerHTML = `
        <div style="color: var(--win8-accent-light);">🧠 ${thought.thought || 'Thinking...'}</div>
        <div style="color: var(--win8-text-muted); font-size: 10px;">${thought.action || ''}</div>
    `;
    container.insertBefore(div, container.firstChild);
    
    // Keep only last 5 thoughts
    while (container.children.length > 5) {
        container.removeChild(container.lastChild);
    }
}

function updateLiveStats(stats) {
    // Could update a stats tile here
    console.log('📊 Live stats:', stats);
}

async function runTool(toolName) {
    const chatInput = document.getElementById('chatInput');
    const toolPrompts = {
        'SYS_MONITOR': 'show system stats',
        'get_processes': 'list running processes',
        'get_uptime': 'show system uptime',
        'docker_ps': 'list docker containers',
        'docker_stats': 'show docker stats',
        'get_ip': 'get public IP address',
        'get_network_info': 'show network info',
        'git_status': 'check git status'
    };
    
    chatInput.value = toolPrompts[toolName] || `run tool: ${toolName}`;
    document.getElementById('sendButton').click();
    
    // Close sidebar after action
    document.getElementById('sidebar').classList.remove('open');
}

function promptFileOp(operation) {
    const path = prompt(`Enter ${operation === 'read' ? 'file path to read' : operation === 'write' ? 'file path to write to' : 'directory path'}`);
    if (!path) return;
    
    if (operation === 'write') {
        const content = prompt('Enter content to write:');
        if (!content) return;
        document.getElementById('chatInput').value = `write file "${path}" with content: ${content}`;
    } else if (operation === 'read') {
        document.getElementById('chatInput').value = `read file "${path}"`;
    } else {
        document.getElementById('chatInput').value = `list files in "${path}"`;
    }
    document.getElementById('sendButton').click();
    document.getElementById('sidebar').classList.remove('open');
}

// Initialize SSE on load
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(connectSSE, 1000);
});

// Connection management functions
async function showConnectModal(appId) {
    try {
        const response = await fetch(`/api/connections/${appId}/config`);
        const data = await response.json();
        
        if (data.status === 'error') {
            alert(data.output);
            return;
        }
        
        let formHtml = `<div class="modal" id="connectModal" style="display: flex;">
            <div class="modal-content" style="max-width: 500px;">
                <h3>Connect to ${data.name}</h3>
                <p style="color: var(--text-muted); margin-bottom: 16px;">${data.category} • ${data.auth_type}</p>
                <form id="connectForm">`;
        
        for (const field of data.auth_fields) {
            formHtml += `<div class="form-group">
                <label class="form-label">${field.label}${field.required ? ' *' : ''}</label>
                <input type="${field.type === 'password' ? 'password' : 'text'}" 
                    class="material-input" 
                    name="${field.name}" 
                    ${field.required ? 'required' : ''}>
            </div>`;
        }
        
        formHtml += `<div style="display: flex; gap: 8px; margin-top: 16px;">
                    <button type="submit" class="btn btn-primary">Connect</button>
                    <button type="button" class="btn btn-secondary" onclick="closeConnectModal()">Cancel</button>
                </div>
                </form>
                ${data.documentation ? `<a href="${data.documentation}" target="_blank" style="font-size: 12px; color: var(--win8-accent-light);">View Documentation</a>` : ''}
            </div>
        </div>`;
        
        document.body.insertAdjacentHTML('beforeend', formHtml);
        
        document.getElementById('connectForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const credentials = {};
            for (const [key, value] of formData.entries()) {
                credentials[key] = value;
            }
            
            const connectBtn = e.target.querySelector('button[type="submit"]');
            connectBtn.disabled = true;
            connectBtn.textContent = 'Connecting...';
            
            try {
                const response = await fetch('/api/connections/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({app_id: appId, credentials})
                });
                
                const result = await response.json();
                if (result.status === 'success') {
                    closeConnectModal();
                    app.loadConnections();
                    alert('✓ Connected successfully!');
                } else {
                    alert('Connection failed: ' + result.output);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
            
            connectBtn.disabled = false;
            connectBtn.textContent = 'Connect';
        });
        
    } catch (error) {
        alert('Error loading app config: ' + error.message);
    }
}

function closeConnectModal() {
    const modal = document.getElementById('connectModal');
    if (modal) modal.remove();
}

async function disconnectApp(appId) {
    if (!confirm('Disconnect this app?')) return;
    
    try {
        const response = await fetch('/api/connections/disconnect', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({app_id: appId})
        });
        
        const result = await response.json();
        if (result.status === 'success') {
            app.loadConnections();
            alert('Disconnected');
        } else {
            alert('Failed: ' + result.output);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function testConnectionAction(appId, action) {
    const params = prompt(`Testing ${action}. Enter params as JSON (or leave empty for default):`, '{}');
    let parsedParams = {};
    try {
        if (params && params !== '{}') {
            parsedParams = JSON.parse(params);
        }
    } catch (e) {
        alert('Invalid JSON');
        return;
    }
    
    try {
        const response = await fetch('/api/connections/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({app_id: appId, action: action, params: parsedParams})
        });
        
        const result = await response.json();
        alert(result.status === 'success' ? '✓ ' + result.output : '✗ ' + result.output);
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function filterApps() {
    const search = document.getElementById('appSearch').value.toLowerCase();
    const buttons = document.querySelectorAll('#appCategories button');
    buttons.forEach(btn => {
        const text = btn.textContent.toLowerCase();
        btn.style.display = text.includes(search) ? '' : 'none';
    });
}
