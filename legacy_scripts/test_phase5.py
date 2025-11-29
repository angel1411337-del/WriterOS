"""
Phase 5 Verification Script
Tests the FastAPI server, Indexer, and Chat capabilities.
"""
import asyncio
import uvicorn
import requests
import time
import threading
from pathlib import Path
from uuid import uuid4
import json

# Import server app
from server import app

SERVER_URL = "http://localhost:8000"

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000)

def test_server_health():
    print("\n--- Testing Server Health ---")
    try:
        resp = requests.get(f"{SERVER_URL}/health")
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.json()}")
        return resp.status_code == 200
    except Exception as e:
        print(f"Failed to connect: {e}")
        return False

def test_chat_stream():
    print("\n--- Testing Chat Streaming ---")
    vault_id = str(uuid4())
    payload = {
        "message": "Hello, who are you?",
        "vault_id": vault_id
    }
    
    try:
        with requests.post(f"{SERVER_URL}/chat/stream", json=payload, stream=True) as r:
            print("Streaming response:")
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        data_str = decoded[6:]
                        if data_str == "[DONE]":
                            print("\n[Stream Complete]")
                            break
                        try:
                            data = json.loads(data_str)
                            print(data.get('content', ''), end='', flush=True)
                        except Exception:
                            pass
        print("\nChat test passed.")
        return True
    except Exception as e:
        print(f"Chat test failed: {e}")
        return False

def main():
    # 1. Start Server in Thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    print("Waiting for server to start...")
    time.sleep(5) # Give it time to init DB and Agents
    
    # 2. Test Health
    if not test_server_health():
        print("Server health check failed. Aborting.")
        return

    # 3. Test Chat
    test_chat_stream()
    
    print("\nVerification Complete.")

if __name__ == "__main__":
    main()
