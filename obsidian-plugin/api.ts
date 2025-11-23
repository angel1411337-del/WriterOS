import { Notice } from 'obsidian';

export class ApiClient {
    private baseUrl: string;

    constructor(port: number = 8000) {
        this.baseUrl = `http://localhost:${port}`;
    }

    async checkHealth(): Promise<boolean> {
        try {
            const response = await fetch(`${this.baseUrl}/health`);
            return response.ok;
        } catch (e) {
            return false;
        }
    }

    async analyzeVault(vaultPath: string, vaultId: string): Promise<boolean> {
        try {
            const response = await fetch(`${this.baseUrl}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vault_path: vaultPath, vault_id: vaultId })
            });
            return response.ok;
        } catch (e) {
            console.error("Analysis failed", e);
            return false;
        }
    }

    async streamChat(
        message: string,
        vaultId: string,
        onChunk: (text: string) => void,
        onError: (err: string) => void,
        onDone: () => void
    ) {
        try {
            const response = await fetch(`${this.baseUrl}/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, vault_id: vaultId })
            });

            if (!response.ok) {
                onError(`Server error: ${response.statusText}`);
                return;
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) {
                onError("Failed to read response stream");
                return;
            }

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6);
                        if (dataStr === '[DONE]') {
                            onDone();
                            return;
                        }

                        try {
                            const data = JSON.parse(dataStr);
                            if (data.content) {
                                onChunk(data.content);
                            } else if (data.error) {
                                onError(data.error);
                            }
                        } catch (e) {
                            console.warn("Failed to parse SSE data", e);
                        }
                    }
                }
            }
        } catch (e) {
            onError(String(e));
        }
    }
}
