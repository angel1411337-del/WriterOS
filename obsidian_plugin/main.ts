import { App, Editor, MarkdownView, Modal, Notice, Plugin, PluginSettingTab, Setting, FileSystemAdapter, WorkspaceLeaf } from 'obsidian';
import { spawn, exec } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { ChatView, VIEW_TYPE_CHAT } from './views/ChatView';
import { ApiClient } from './api';

interface WriterOSSettings {
    pythonPath: string;
    scriptPath: string;
    serverPath: string;
    defaultGraphType: string;
    serverPort: number;
}

const DEFAULT_SETTINGS: WriterOSSettings = {
    pythonPath: 'python',
    scriptPath: '',
    serverPath: '',
    defaultGraphType: 'force',
    serverPort: 8000
}

export default class WriterOSPlugin extends Plugin {
    settings: WriterOSSettings;
    apiClient: ApiClient;
    vaultId: string;

    async onload() {
        await this.loadSettings();
        this.apiClient = new ApiClient(this.settings.serverPort);
        this.vaultId = this.getOrCreateVaultId();

        // Register Chat View
        this.registerView(
            VIEW_TYPE_CHAT,
            (leaf) => new ChatView(leaf, this.apiClient, this.vaultId)
        );

        // Ribbon Icon
        this.addRibbonIcon('dice', 'WriterOS Graph', (evt: MouseEvent) => {
            this.generateGraph(this.settings.defaultGraphType);
        });

        this.addRibbonIcon('message-square', 'WriterOS Chat', (evt: MouseEvent) => {
            this.activateChatView();
        });

        // Status Bar
        const statusBarItemEl = this.addStatusBarItem();

        // Server Discovery
        this.checkServerStatus(statusBarItemEl);

        // Commands
        this.addCommand({
            id: 'open-writeros-chat',
            name: 'Open Chat',
            callback: () => this.activateChatView()
        });

        this.addCommand({
            id: 'analyze-vault',
            name: 'Analyze Vault',
            callback: () => this.analyzeVault()
        });

        this.addCommand({
            id: 'start-writeros-server',
            name: 'Start Server',
            callback: () => this.startServer()
        });

        // Graph Commands
        ['force', 'family', 'faction', 'location'].forEach(type => {
            this.addCommand({
                id: `open-${type}-graph`,
                name: `Open ${type.charAt(0).toUpperCase() + type.slice(1)} Graph`,
                callback: () => this.generateGraph(type)
            });
        });

        this.addSettingTab(new WriterOSSettingTab(this.app, this));
    }

    async checkServerStatus(statusBar: HTMLElement) {
        const isRunning = await this.apiClient.checkHealth();
        if (isRunning) {
            statusBar.setText('WriterOS: Connected');
            statusBar.style.color = 'lightgreen';
        } else {
            statusBar.setText('WriterOS: Disconnected');
            statusBar.style.color = 'orange';
            new Notice('WriterOS Server not running. Use "Start Server" command.');
        }
    }

    async startServer() {
        const pythonPath = this.settings.pythonPath;
        const serverPath = this.settings.serverPath || path.join(this.getVaultPath(), 'server.py');

        if (!fs.existsSync(serverPath)) {
            new Notice(`Server script not found at: ${serverPath}`);
            return;
        }

        new Notice('Starting WriterOS Server...');

        // Run in background (detached)
        const subprocess = spawn(pythonPath, [serverPath], {
            detached: true,
            stdio: 'ignore'
        });
        subprocess.unref();

        // Wait a bit and check health
        setTimeout(async () => {
            const isRunning = await this.apiClient.checkHealth();
            if (isRunning) {
                new Notice('WriterOS Server Started!');
            } else {
                new Notice('Failed to connect to server. Check console.');
            }
        }, 3000);
    }

    async analyzeVault() {
        new Notice('Starting Vault Analysis...');
        const success = await this.apiClient.analyzeVault(this.getVaultPath(), this.vaultId);
        if (success) {
            new Notice('Analysis started in background.');
        } else {
            new Notice('Failed to start analysis. Is server running?');
        }
    }

    async activateChatView() {
        const { workspace } = this.app;

        let leaf: WorkspaceLeaf | null = null;
        const leaves = workspace.getLeavesOfType(VIEW_TYPE_CHAT);

        if (leaves.length > 0) {
            leaf = leaves[0];
        } else {
            leaf = workspace.getRightLeaf(false);
            await leaf.setViewState({ type: VIEW_TYPE_CHAT, active: true });
        }

        workspace.revealLeaf(leaf);
    }

    getVaultPath(): string {
        return (this.app.vault.adapter as FileSystemAdapter).getBasePath();
    }

    getOrCreateVaultId(): string {
        const vaultPath = this.getVaultPath();
        const configPath = path.join(vaultPath, '.writeros', 'config.json');

        if (fs.existsSync(configPath)) {
            try {
                const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
                return config.vault_id;
            } catch (e) {
                console.error('Failed to read config', e);
            }
        }

        // Create new
        const writerOSPath = path.join(vaultPath, '.writeros');
        if (!fs.existsSync(writerOSPath)) {
            fs.mkdirSync(writerOSPath, { recursive: true });
        }

        // Simple UUID gen
        const uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });

        fs.writeFileSync(configPath, JSON.stringify({
            vault_id: uuid,
            created_at: new Date().toISOString()
        }, null, 2));

        return uuid;
    }

    async generateGraph(type: string) {
        new Notice(`Generating ${type} graph...`);
        const vaultPath = this.getVaultPath();
        const pythonPath = this.settings.pythonPath;
        const scriptPath = this.settings.scriptPath || path.join(vaultPath, 'generate_graph.py');

        const command = `"${pythonPath}" "${scriptPath}" --vault-path "${vaultPath}" --graph-type "${type}" --vault-id "${this.vaultId}"`;

        exec(command, (error: any, stdout: any, stderr: any) => {
            if (error) {
                console.error(`exec error: ${error}`);
                new Notice(`Error: ${error.message}`);
                return;
            }

            const match = stdout.match(/Graph HTML generated: (.*)/);
            if (match && match[1]) {
                const filePath = match[1].trim();
                this.openGraphInBrowser(filePath);
            } else {
                // Fallback: check last line
                const lines = stdout.trim().split('\n');
                const lastLine = lines[lines.length - 1];
                if (lastLine && lastLine.endsWith('.html')) {
                    this.openGraphInBrowser(lastLine.trim());
                } else {
                    new Notice('Graph generated but could not auto-open. Check .writeros/graphs/ folder.');
                }
            }
        });
    }

    openGraphInBrowser(filePath: string) {
        if (process.platform === 'win32') {
            // Use PowerShell Start-Process for better path handling with spaces
            exec(`powershell -Command "Start-Process '${filePath}'"`, (error: any) => {
                if (error) {
                    console.error('Failed to open graph:', error);
                    new Notice(`Graph saved to: ${filePath}`);
                }
            });
        } else if (process.platform === 'darwin') {
            exec(`open "${filePath}"`);
        } else {
            exec(`xdg-open "${filePath}"`);
        }
    }

    onunload() {
    }

    async loadSettings() {
        this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    }

    async saveSettings() {
        await this.saveData(this.settings);
    }
}

class WriterOSSettingTab extends PluginSettingTab {
    plugin: WriterOSPlugin;

    constructor(app: App, plugin: WriterOSPlugin) {
        super(app, plugin);
        this.plugin = plugin;
    }

    display(): void {
        const { containerEl } = this;
        containerEl.empty();
        containerEl.createEl('h2', { text: 'WriterOS Settings' });

        new Setting(containerEl)
            .setName('Python Path')
            .setDesc('Path to Python executable')
            .addText(text => text
                .setPlaceholder('python')
                .setValue(this.plugin.settings.pythonPath)
                .onChange(async (value) => {
                    this.plugin.settings.pythonPath = value;
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Script Path')
            .setDesc('Path to generate_graph.py')
            .addText(text => text
                .setPlaceholder('Path to generate_graph.py')
                .setValue(this.plugin.settings.scriptPath)
                .onChange(async (value) => {
                    this.plugin.settings.scriptPath = value;
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Server Script Path')
            .setDesc('Path to server.py (Optional, defaults to vault root)')
            .addText(text => text
                .setValue(this.plugin.settings.serverPath)
                .onChange(async (value) => {
                    this.plugin.settings.serverPath = value;
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Server Port')
            .setDesc('Port for FastAPI server')
            .addText(text => text
                .setValue(String(this.plugin.settings.serverPort))
                .onChange(async (value) => {
                    this.plugin.settings.serverPort = parseInt(value) || 8000;
                    await this.plugin.saveSettings();
                }));
    }
}
