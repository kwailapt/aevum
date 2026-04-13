from fastapi import FastAPI, Request
import uvicorn
import subprocess
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx

# ─── A2A Configuration ───────────────────────────────────────────────────────

AGENT_PORT     = 9001
ROUTER_URL     = "http://localhost:8420"
HEARTBEAT_SECS = 30
AGENT_ID       = "aevum.obsidian.wiki.v1"

# Use local endpoint for local A2A routing (avoids DNS/Cloudflare Tunnel issues)
_AGENT_CARD = {
    "agent_id":    AGENT_ID,
    "name":        "Aevum Obsidian Wiki Swarm",
    "description": "Qwen-powered wiki generation agent for Aevum Obsidian knowledge base.",
    "endpoint":    "http://localhost:9001",
    "protocol":    "openai",
    "capabilities": [
        {
            "name":         "wiki.generate",
            "description":  "Generate a wiki article on a given topic using the Qwen matrix",
            "input_schema": {
                "type":       "object",
                "properties": {"prompt": {"type": "string"}},
                "required":   ["prompt"],
            },
            "output_schema":  {"type": "object"},
            "cost_per_call":  0.001,
            "avg_latency_ms": 3000.0,
            "tags": ["wiki", "qwen", "knowledge"],
        }
    ],
    "tags":       ["wiki", "knowledge", "qwen"],
    "reputation": 0.5,
    "status":     "online",
}

# ─── Registration & self-healing heartbeat ────────────────────────────────────

async def _register_with_router(client: httpx.AsyncClient) -> bool:
    """POST agent card to router. Retries up to 5 times with backoff."""
    url = f"{ROUTER_URL}/agents/register"
    for attempt in range(1, 6):
        try:
            resp = await client.post(url, json=_AGENT_CARD, timeout=10.0)
            if resp.status_code < 400:
                data = resp.json()
                print(
                    f"[wiki-agent] Registered with router as {data.get('agent_id')} "
                    f"({data.get('capabilities_count', 0)} capabilities)"
                )
                return True
            print(f"[wiki-agent] Registration attempt {attempt}: HTTP {resp.status_code}")
        except Exception as exc:
            print(f"[wiki-agent] Registration attempt {attempt} failed: {exc}")
        await asyncio.sleep(2 ** attempt)
    return False


async def _heartbeat_loop(client: httpx.AsyncClient, stop: asyncio.Event) -> None:
    """POST heartbeat to router every HEARTBEAT_SECS to stay ONLINE.

    Self-healing: if the router returns HTTP 404 the agent is no longer in the
    registry (router was restarted / registry wiped).  Re-register immediately
    and resume normal heartbeating.
    """
    url = f"{ROUTER_URL}/agents/{AGENT_ID}/heartbeat"
    while not stop.is_set():
        try:
            resp = await client.post(url, timeout=5.0)
            if resp.status_code == 404:
                print(
                    "[wiki-agent] Heartbeat 404 — router registry wiped. "
                    "Re-registering..."
                )
                await _register_with_router(client)
        except Exception as exc:
            print(f"[wiki-agent] Heartbeat error: {exc}")
        await asyncio.sleep(HEARTBEAT_SECS)


# ─── Lifespan ────────────────────────────────────────────────────────────────

_http_client: Optional[httpx.AsyncClient] = None
_stop_hb: Optional[asyncio.Event] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client, _stop_hb
    _http_client = httpx.AsyncClient()
    _stop_hb     = asyncio.Event()

    await _register_with_router(_http_client)
    hb_task = asyncio.create_task(_heartbeat_loop(_http_client, _stop_hb))

    try:
        yield
    finally:
        _stop_hb.set()
        await asyncio.gather(hb_task, return_exceptions=True)
        await _http_client.aclose()


app = FastAPI(title="Aevum Obsidian Wiki Swarm", lifespan=lifespan)

@app.post("/v1/chat/completions")
async def generate_wiki(request: Request):
    data = await request.json()
    
    # 1. 深度解析 Payload，確保抓到真實的 Prompt
    print(f"📥 物理層觀測 (Raw Payload): {json.dumps(data, ensure_ascii=False)}")
    try:
        # 兼容不同的 JSON 封裝格式
        if "messages" in data:
            user_prompt = data["messages"][-1]["content"]
        elif "body" in data and "messages" in data["body"]:
            user_prompt = data["body"]["messages"][-1]["content"]
        else:
            user_prompt = str(data)
    except Exception as e:
        user_prompt = "Default Wiki Topic"

    print(f"\n🌌 [Wiki Swarm Membrane] 真實因果任務: {user_prompt}")
    print("🚀 [Wiki Swarm Membrane] 正在喚醒底層 Qwen/GLM 矩陣...")
    
    # 2. 喚醒真實的 Qwen 矩陣 (⚠️ 必須使用非互動式參數)
    try:
        # ⚠️ 請注意：這裡的參數 ["--topic", user_prompt] 必須替換為您真實腳本
        # 能夠「跳過選單直接執行」的參數寫法
        proc = await asyncio.create_subprocess_exec(
            "/opt/homebrew/bin/qwen", "--topic", user_prompt,
            cwd="//Volumes/MYWORK/Chaos/Aevum_wiki",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        returncode = await proc.wait()
        if returncode != 0:
            raise subprocess.CalledProcessError(returncode, "/opt/homebrew/bin/qwen")
        
        result_text = f"# Wiki 自動生成報告\n\n✅ 實體矩陣已成功接收並處理主題：**{user_prompt}**"
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        result_text = f"❌ 喚醒實體矩陣失敗: {e}"

    # 3. 回傳 OpenAI 相容格式給大腦
    return {
        "id": "chatcmpl-wiki-swarm-001",
        "object": "chat.completion",
        "model": "aevum.obsidian.wiki.swarm",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result_text
            },
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 15, "completion_tokens": 50, "total_tokens": 65}
    }

if __name__ == "__main__":
    # 監聽註冊表上宣告的 9001 埠
    uvicorn.run(app, host="0.0.0.0", port=9001)
