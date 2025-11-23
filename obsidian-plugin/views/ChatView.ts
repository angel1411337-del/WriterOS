import { ItemView, WorkspaceLeaf, Notice, setIcon } from 'obsidian';
import { ApiClient } from '../api';

export const VIEW_TYPE_CHAT = 'writeros-chat-view';

export class ChatView extends ItemView {
    private apiClient: ApiClient;
    private messagesContainer: HTMLElement;
    private inputEl: HTMLTextAreaElement;
    private vaultId: string;

    constructor(leaf: WorkspaceLeaf, apiClient: ApiClient, vaultId: string) {
        super(leaf);
        this.apiClient = apiClient;
        this.vaultId = vaultId;
    }

    getViewType(): string {
        return VIEW_TYPE_CHAT;
    }

    getDisplayText(): string {
        return 'WriterOS Chat';
    }

    getIcon(): string {
        return 'message-square';
    }

    async onOpen() {
        const container = this.containerEl.children[1];
        container.empty();
        container.addClass('writeros-chat-container');

        // 1. Header
        const header = container.createEl('div', { cls: 'writeros-chat-header' });
        header.createEl('h4', { text: 'WriterOS Agent' });

        // 2. Messages Area
        this.messagesContainer = container.createEl('div', { cls: 'writeros-chat-messages' });

        // Welcome message
        this.addMessage('system', 'Hello! I am your WriterOS assistant. How can I help you with your story today?');

        // 3. Input Area
        const inputContainer = container.createEl('div', { cls: 'writeros-chat-input-container' });

        this.inputEl = inputContainer.createEl('textarea', {
            cls: 'writeros-chat-input',
            attr: { placeholder: 'Ask about your characters, plot, or world...' }
        });

        // Send on Enter (Shift+Enter for new line)
        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        const sendBtn = inputContainer.createEl('button', {
            cls: 'writeros-chat-send-btn',
            text: 'Send'
        });
        sendBtn.addEventListener('click', () => this.sendMessage());
    }

    private async sendMessage() {
        const message = this.inputEl.value.trim();
        if (!message) return;

        // Clear input
        this.inputEl.value = '';

        // Add User Message
        this.addMessage('user', message);

        // Add Assistant Placeholder
        const assistantMsgEl = this.addMessage('assistant', '');
        const contentEl = assistantMsgEl.querySelector('.writeros-message-content') as HTMLElement;
        contentEl.setText('Thinking...');

        let fullResponse = '';
        let isFirstChunk = true;

        await this.apiClient.streamChat(
            message,
            this.vaultId,
            (chunk) => {
                if (isFirstChunk) {
                    contentEl.setText('');
                    isFirstChunk = false;
                }
                fullResponse += chunk;
                contentEl.setText(fullResponse);
                this.scrollToBottom();
            },
            (error) => {
                new Notice(error);
                contentEl.setText(`Error: ${error}`);
            },
            () => {
                // Done
                console.log('Stream complete');
            }
        );
    }

    private addMessage(role: 'user' | 'assistant' | 'system', text: string): HTMLElement {
        const msgEl = this.messagesContainer.createEl('div', {
            cls: `writeros-message writeros-message-${role}`
        });

        const contentEl = msgEl.createEl('div', { cls: 'writeros-message-content' });
        contentEl.setText(text);

        this.scrollToBottom();
        return msgEl;
    }

    private scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    async onClose() {
        // Cleanup
    }
}
