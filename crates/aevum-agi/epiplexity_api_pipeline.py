#!/usr/bin/env python3
import asyncio
import json
import os
import aiohttp
from typing import Dict, Any, Tuple
from dataclasses import dataclass

# ---------------------------------------------------------
# 0.1% Protocol: Configuration & State
# Space Complexity: O(1)
# ---------------------------------------------------------
API_URL = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
API_KEY = os.getenv("LLM_API_KEY", "YOUR_API_KEY_HERE")
MODEL_NAME = os.getenv("LLM_MODEL", "gpt-4-turbo-preview") # 替換為您的目標模型

@dataclass(slots=True)
class PipelineState:
    payload: str
    processed: bool
    result_matrix: Dict[str, Any]
    error_log: str

class EpiplexityAPIEngine:
    """
    第一性原理 API 引擎: 繞過 UI 護欄，強制執行 JSON 結構化輸出。
    """
    def __init__(self, threshold: float = 3.0):
        self.threshold = threshold
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

    def _build_strict_payload(self, text: str) -> Dict[str, Any]:
        """
        構建絕對決定論的 API 請求，強制 temperature = 0.0 以實現概率坍縮。
        """
        system_prompt = """
        Analyze the input text and output strictly a JSON object. No markdown, no explanations.
        Calculate "structural_complexity" (integer), "semantic_redundancy" (float 0.0-1.0), and "optimization_score" (structural_complexity * 0.6 + semantic_redundancy * 10 * 0.4).
        If optimization_score > {threshold}, return a compressed version in "final_payload". Otherwise, return the exact original text.
        Schema: {"metrics": {"structural_complexity": int, "semantic_redundancy": float, "optimization_score": float}, "refactoring_applied": bool, "final_payload": str, "equivalence_confidence": float}
        """.replace("{threshold}", str(self.threshold))

        return {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.0, # 零隨機性
            "response_format": {"type": "json_object"} # 強制 JSON 模式 (OpenAI 原語)
        }

    async def execute(self, text_payload: str) -> Tuple[bool, PipelineState]:
        """
        原生非阻塞異步 I/O 執行器，包含墨菲定律防禦 (Timeout & Fallback)。
        """
        state = PipelineState(payload=text_payload, processed=False, result_matrix={}, error_log="")
        request_body = self._build_strict_payload(text_payload)

        try:
            # 設置硬中斷超時，防止系統掛起
            timeout = aiohttp.ClientTimeout(total=15.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(API_URL, headers=self.headers, json=request_body) as response:
                    if response.status != 200:
                        state.error_log = f"HTTP {response.status}: {await response.text()}"
                        return False, state
                    
                    data = await response.json()
                    raw_content = data["choices"][0]["message"]["content"]
                    
                    # 校驗並解析 JSON 狀態機
                    state.result_matrix = json.loads(raw_content)
                    state.processed = True
                    return True, state

        except asyncio.TimeoutError:
            state.error_log = "HARD HALT: API Request Timeout (Exceeded 15s limit)."
            return False, state
        except json.JSONDecodeError:
            state.error_log = "HARD HALT: Non-deterministic output detected. JSON parse failed."
            return False, state
        except Exception as e:
            state.error_log = f"HARD HALT: Unknown system failure - {str(e)}"
            return False, state

# 冪等測試入口
async def main():
    test_payload = "This is a very, very, extremely long and redundant sentence that basically just says hello world, but uses way too many words to do so and has an if statement like if true then print."
    
    print(f"[*] 啟動 Epiplexity API 引擎 (Target = {API_URL})")
    engine = EpiplexityAPIEngine(threshold=2.0)
    success, final_state = await engine.execute(test_payload)
    
    if success:
        print("[+] 0.1% 協議執行成功。量子坍縮完成。")
        print(json.dumps(final_state.result_matrix, indent=2))
    else:
        print(f"[-] 執行失敗，觸發優雅降級。原因: {final_state.error_log}")

if __name__ == "__main__":
    # 確保異步事件循環正確關閉
    asyncio.run(main())
