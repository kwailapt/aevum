
> # Agent-to-Agent Protocol Layer：因果橋全棧藍圖
> 
> 
> ---
> 
> 
> ## 壹、系統藍圖：六層因果橋架構
> 
> 
> ```text
> jsx
> 
> import React, { useState } from 'react';
> import { motion, AnimatePresence } from 'framer-motion';
> import { Network, Shield, Route, Brain, Coins, Radio, ChevronRight, Zap, Globe, Box } from 'lucide-react';
> 
> const layers = [
>   {
>     id: 'L0',
>     name: 'Transport 傳輸層',
>     icon: Radio,
>     color: 'from-slate-600 to-slate-700',
>     border: 'border-slate-500',
>     engine: null,
>     desc: 'HTTP/2 + WebSocket + SSE 多通道傳輸。M1 Ultra 作為首個骨幹節點，對外暴露統一端點。支援雙向持久連接與串流回應。',
>     details: ['FastAPI + Uvicorn (ASGI)', 'WebSocket 持久代理連接', 'SSE 單向事件串流', 'mTLS 加密通道']
>   },
>   {
>     id: 'L1',
>     name: 'Identity 身份層',
>     icon: Shield,
>     color: 'from-violet-600 to-violet-700',
>     border: 'border-violet-500',
>     engine: null,
>     desc: 'AgentCard 機制：每個代理攜帶能力向量（Capability Vector）、端點資訊、定價模型。去中心化身份，無需中央權威。',
>     details: ['AgentCard = ID + 能力 + 端點 + 定價', '能力向量：語義嵌入空間', 'Ed25519 簽名驗證', '零信任拓撲']
>   },
>   {
>     id: 'L2',
>     name: 'Messaging 訊息層',
>     icon: Network,
>     color: 'from-blue-600 to-blue-700',
>     border: 'border-blue-500',
>     engine: '∂',
>     desc: '邊界算子 ∂ 的外化：Envelope 封包格式統一內外因果語義。支援 MCP / Google A2A / OpenAI Function Calling 等異構協議互譯。',
>     details: ['Envelope 統一封包格式', '∂ 算子：協議邊界互譯', 'trace_id 因果鏈標記', 'TTL + hop_count 防迴路']
>   },
>   {
>     id: 'L3',
>     name: 'Routing 路由層',
>     icon: Route,
>     color: 'from-emerald-600 to-emerald-700',
>     border: 'border-emerald-500',
>     engine: 'Φ',
>     desc: '因果引擎 Φ 的決策核心：基於能力匹配度 × 延遲歷史 × 信譽分 × 成本的多維評分，將請求路由至最優代理。',
>     details: ['語義能力匹配 (餘弦相似度)', 'Φ 驅動的多維評分函數', '負載均衡 + 故障轉移', '拓撲感知路由']
>   },
>   {
>     id: 'L4',
>     name: 'Causal 因果層',
>     icon: Brain,
>     color: 'from-amber-600 to-amber-700',
>     border: 'border-amber-500',
>     engine: 'Φ',
>     desc: '每條穿越系統的請求生成完整因果鏈（Causal Chain）。追蹤請求→路由→執行→結果→反饋的全週期，計算各節點的因果貢獻度。',
>     details: ['CausalChain 全生命週期追蹤', '因果貢獻度 Shapley 值', '回饋信號→路由權重更新', '異常因果路徑偵測']
>   },
>   {
>     id: 'L5',
>     name: 'Economics 經濟層',
>     icon: Coins,
>     color: 'from-rose-600 to-rose-700',
>     border: 'border-rose-500',
>     engine: 'Ω',
>     desc: 'Ω 算子的外化：計量每次路由的計算成本與價值產出，計算代理信譽，生成結算記錄。閉合自我融資迴路的最後一環。',
>     details: ['計算成本 + 延遲計量', '價值信號聚合', '信譽 = f(成功率, 延遲, 價值, 使用量)', '結算週期報告']
>   }
> ];
> 
> const externalAgents = [
>   { name: 'MCP Agents', position: 0, protocol: 'MCP' },
>   { name: 'OpenAI Agents', position: 1, protocol: 'Function Calling' },
>   { name: 'Google A2A', position: 2, protocol: 'A2A Protocol' },
>   { name: 'Custom Agents', position: 3, protocol: 'JSON-RPC' },
> ];
> 
> export default function A2ABlueprint() {
>   const [selected, setSelected] = useState(null);
>   const [hoveredAgent, setHoveredAgent] = useState(null);
> 
>   return (
>     <div className="min-h-screen bg-gray-950 text-white p-4 md:p-8 font-mono">
>       <div className="max-w-6xl mx-auto">
>         <div className="text-center mb-8">
>           <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-rose-400 bg-clip-text text-transparent">
>             A2A Protocol Layer — 因果橋六層架構
>           </h1>
>           <p className="text-gray-500 mt-2 text-sm">Agent-to-Agent Protocol Layer Blueprint · ⟨Φ, ∂, Ω⟩ Engine Mapping</p>
>         </div>
> 
>         <div className="flex flex-col lg:flex-row gap-6">
>           {/* Left: External Agents */}
>           <div className="lg:w-1/5 flex flex-row lg:flex-col gap-3 justify-center">
>             <div className="text-xs text-gray-600 text-center mb-1 hidden lg:block">EXTERNAL AGENTS</div>
>             {externalAgents.map((agent, i) => (
>               <motion.div
>                 key={agent.name}
>                 className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-center cursor-pointer"
>                 whileHover={{ scale: 1.05, borderColor: '#60a5fa' }}
>                 onHoverStart={() => setHoveredAgent(i)}
>                 onHoverEnd={() => setHoveredAgent(null)}
>                 initial={{ opacity: 0, x: -20 }}
>                 animate={{ opacity: 1, x: 0 }}
>                 transition={{ delay: i * 0.1 }}
>               >
>                 <Globe className="w-4 h-4 mx-auto mb-1 text-blue-400" />
>                 <div className="text-xs font-bold text-gray-300">{agent.name}</div>
>                 <div className="text-xs text-gray-600">{agent.protocol}</div>
>               </motion.div>
>             ))}
>             {/* Animated connection lines */}
>             {hoveredAgent !== null && (
>               <motion.div 
>                 className="hidden lg:flex items-center justify-center"
>                 initial={{ opacity: 0 }}
>                 animate={{ opacity: 1 }}
>               >
>                 <Zap className="w-4 h-4 text-yellow-400 animate-pulse" />
>               </motion.div>
>             )}
>           </div>
> 
>           {/* Center: Protocol Layers */}
>           <div className="lg:w-3/5 flex flex-col gap-2">
>             {layers.map((layer, i) => (
>               <motion.div
>                 key={layer.id}
>                 className={`relative bg-gradient-to-r ${layer.color} rounded-lg cursor-pointer overflow-hidden border ${layer.border} border-opacity-30`}
>                 onClick={() => setSelected(selected === i ? null : i)}
>                 whileHover={{ scale: 1.02 }}
>                 initial={{ opacity: 0, y: 20 }}
>                 animate={{ opacity: 1, y: 0 }}
>                 transition={{ delay: i * 0.08 }}
>               >
>                 <div className="flex items-center justify-between p-3 md:p-4">
>                   <div className="flex items-center gap-3">
>                     <div className="bg-black bg-opacity-30 rounded-lg p-2">
>                       <layer.icon className="w-5 h-5" />
>                     </div>
>                     <div>
>                       <div className="flex items-center gap-2">
>                         <span className="text-xs text-gray-400">{layer.id}</span>
>                         <span className="text-sm md:text-base font-bold">{layer.name}</span>
>                       </div>
>                       <p className="text-xs text-gray-300 opacity-80 mt-0.5 hidden md:block">{layer.desc.slice(0, 60)}...</p>
>                     </div>
>                   </div>
>                   <div className="flex items-center gap-2">
>                     {layer.engine && (
>                       <span className="bg-black bg-opacity-40 text-xs px-2 py-1 rounded-full font-bold text-yellow-300">
>                         {layer.engine}
>                       </span>
>                     )}
>                     <motion.div animate={{ rotate: selected === i ? 90 : 0 }}>
>                       <ChevronRight className="w-4 h-4 text-gray-400" />
>                     </motion.div>
>                   </div>
>                 </div>
> 
>                 <AnimatePresence>
>                   {selected === i && (
>                     <motion.div
>                       initial={{ height: 0, opacity: 0 }}
>                       animate={{ height: 'auto', opacity: 1 }}
>                       exit={{ height: 0, opacity: 0 }}
>                       className="bg-black bg-opacity-40 px-4 pb-4"
>                     >
>                       <p className="text-sm text-gray-300 mb-3">{layer.desc}</p>
>                       <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
>                         {layer.details.map((d, j) => (
>                           <div key={j} className="bg-black bg-opacity-30 rounded px-3 py-2 text-xs text-gray-400 flex items-center gap-2">
>                             <div className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0" />
>                             {d}
>                           </div>
>                         ))}
>                       </div>
>                     </motion.div>
>                   )}
>                 </AnimatePresence>
>               </motion.div>
>             ))}
>           </div>
> 
>           {/* Right: Engine Mapping + Causal Loop */}
>           <div className="lg:w-1/5 flex flex-col gap-3 justify-center">
>             <div className="text-xs text-gray-600 text-center mb-1 hidden lg:block">ENGINE MAPPING</div>
>             {[
>               { sym: 'Φ', label: '因果引擎', desc: '路由決策 + 因果追蹤', color: 'text-amber-400 border-amber-800 bg-amber-950' },
>               { sym: '∂', label: '邊界算子', desc: '協議互譯 + 介面', color: 'text-blue-400 border-blue-800 bg-blue-950' },
>               { sym: 'Ω', label: '耦合算子', desc: '經濟計量 + 結算', color: 'text-rose-400 border-rose-800 bg-rose-950' },
>             ].map((eng, i) => (
>               <motion.div
>                 key={eng.sym}
>                 className={`border rounded-lg p-3 text-center ${eng.color}`}
>                 initial={{ opacity: 0, x: 20 }}
>                 animate={{ opacity: 1, x: 0 }}
>                 transition={{ delay: 0.3 + i * 0.1 }}
>               >
>                 <div className="text-2xl font-bold">{eng.sym}</div>
>                 <div className="text-xs font-bold mt-1">{eng.label}</div>
>                 <div className="text-xs opacity-60 mt-0.5">{eng.desc}</div>
>               </motion.div>
>             ))}
> 
>             <motion.div
>               className="border border-gray-800 bg-gray-950 rounded-lg p-3 mt-2"
>               initial={{ opacity: 0 }}
>               animate={{ opacity: 1 }}
>               transition={{ delay: 0.8 }}
>             >
>               <div className="text-xs text-gray-500 text-center mb-2">CAUSAL FEEDBACK LOOP</div>
>               <div className="flex items-center justify-center gap-1 text-xs text-gray-600">
>                 <span className="text-blue-400">∂</span>
>                 <span>→</span>
>                 <span className="text-amber-400">Φ</span>
>                 <span>→</span>
>                 <span className="text-rose-400">Ω</span>
>                 <span>→</span>
>                 <span className="text-blue-400">∂</span>
>               </div>
>               <div className="text-center mt-2">
>                 <motion.div
>                   className="inline-block w-2 h-2 rounded-full bg-green-500"
>                   animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
>                   transition={{ repeat: Infinity, duration: 2 }}
>                 />
>                 <span className="text-xs text-green-500 ml-2">因果迴路閉合</span>
>               </div>
>             </motion.div>
> 
>             <motion.div
>               className="border border-dashed border-gray-800 rounded-lg p-3"
>               initial={{ opacity: 0 }}
>               animate={{ opacity: 1 }}
>               transition={{ delay: 1 }}
>             >
>               <div className="text-xs text-gray-600 text-center">
>                 <Box className="w-4 h-4 mx-auto mb-1" />
>                 M1 Ultra = Node 0<br />
>                 <span className="text-gray-700">128GB 統一記憶體</span><br />
>                 <span className="text-gray-700">首個骨幹路由節點</span>
>               </div>
>             </motion.div>
>           </div>
>         </div>
> 
>         <div className="mt-6 text-center text-xs text-gray-700">
>           點擊各層展開詳情 · Click each layer for details
>         </div>
>       </div>
>     </div>
>   );
> }
> 
> 
> 
> 
> 
> react 1
> 
> 在画布上打开
> ```
> 
> 
> ---
> 
> 
> ## 貳、結構拓撲：模組分解與數據流
> 
> 
> ```stylus
> stylus
> 
> a2a-protocol-layer/
> │
> ├── requirements.txt          # 依賴清單
> ├── main.py                   # 啟動入口
> │
> ├── core/
> │   ├── __init__.py
> │   ├── protocol.py           # L1-L2: 協議定義 (AgentCard, Envelope, Capability)
> │   ├── registry.py           # L1: 代理注冊與發現
> │   ├── router.py             # L3: 語義路由引擎 (Φ)
> │   ├── causal.py             # L4: 因果鏈追蹤器 (Φ)
> │   ├── boundary.py           # L2: 邊界算子 / 協議互譯 (∂)
> │   └── economics.py          # L5: 經濟計量與結算 (Ω)
> │
> ├── adapters/
> │   ├── __init__.py
> │   ├── mcp_adapter.py        # MCP 協議適配器
> │   ├── openai_adapter.py     # OpenAI Function Calling 適配器
> │   └── a2a_google_adapter.py # Google A2A 適配器
> │
> ├── transport/
> │   ├── __init__.py
> │   └── server.py             # L0: FastAPI 伺服器
> │
> └── tests/
>     └── test_routing.py       # 路由測試
> ```
> 
> **數據流的因果拓撲：**
> 
> 外部代理請求進入系統時，穿越的路徑是：`L0 (Transport) → L1 (Identity 驗證) → L2/∂ (Boundary 協議互譯) → L3/Φ (Router 路由決策) → L4/Φ (Causal 因果標記) → 目標代理執行 → L5/Ω (Economics 計量) → L4 (因果閉環) → L2/∂ (回應互譯) → L0 (回傳)`。每一次完整穿越都在 Ω 層產生經濟信號，該信號回流修改 Φ 層的路由權重——這就是因果迴路的閉合機制。
> 
> 
> ---
> 
> 
> ## 參、核心代碼
> 
> 
> ### 3.0 依賴清單
> 
> 
> ```text
> txt
> 
> # requirements.txt
> fastapi>=0.104.0
> uvicorn[standard]>=0.24.0
> pydantic>=2.5.0
> httpx>=0.25.0
> numpy>=1.26.0
> ```
> 
> 
> ```bash
> bash
> 
> # M1 Ultra 快速啟動
> pip install -r requirements.txt
> python main.py
> ```
> 
> 
> ---
> 
> 
> ### 3.1 協議定義 — `core/protocol.py`
> 
> 
> ```python
> python
> 
> """
> core/protocol.py
> ================
> A2A Protocol Layer — 協議核心定義
> 所有在系統中流動的數據結構的規範來源 (Single Source of Truth)
> 
> 映射：此模組定義了穿越邊界算子 ∂ 的所有合法態的形式語言。
> """
> 
> from __future__ import annotations
> 
> import time
> import uuid
> from enum import Enum
> from typing import Any, Optional
> 
> from pydantic import BaseModel, Field
> 
> 
> # ──────────────────────────────────────────────
> # Capability: 代理能力的原子化描述
> # ──────────────────────────────────────────────
> 
> class Capability(BaseModel):
>     """
>     一個代理所宣告的單一能力。
>     能力是路由層進行語義匹配的最小單位。
>     """
>     name: str = Field(..., description="能力的規範名稱, e.g. 'text.summarize'")
>     description: str = Field(default="", description="自然語言描述，用於語義匹配")
>     input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for input")
>     output_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for output")
>     tags: list[str] = Field(default_factory=list, description="能力標籤，用於快速索引")
>     embedding: Optional[list[float]] = Field(default=None, description="語義嵌入向量 (可選)")
>     cost_per_call: float = Field(default=0.0, description="每次調用的標價")
>     avg_latency_ms: float = Field(default=0.0, description="歷史平均延遲 (ms)")
> 
> 
> # ──────────────────────────────────────────────
> # AgentCard: 代理的身份與能力宣告
> # ──────────────────────────────────────────────
> 
> class AgentStatus(str, Enum):
>     ONLINE = "online"
>     OFFLINE = "offline"
>     DEGRADED = "degraded"
> 
> 
> class AgentCard(BaseModel):
>     """
>     AgentCard 是代理在 A2A 網絡中的完整身份。
>     類比：DNS 的 SRV 記錄 + 能力清單 + 信譽快照。
>     """
>     agent_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
>     name: str = Field(..., description="人類可讀的代理名稱")
>     description: str = Field(default="")
>     endpoint: str = Field(..., description="代理的可達端點 URL")
>     protocol: str = Field(default="native", description="native | mcp | openai | google_a2a")
>     capabilities: list[Capability] = Field(default_factory=list)
>     status: AgentStatus = Field(default=AgentStatus.ONLINE)
>     reputation: float = Field(default=0.5, ge=0.0, le=1.0)
>     registered_at: float = Field(default_factory=time.time)
>     last_heartbeat: float = Field(default_factory=time.time)
>     metadata: dict[str, Any] = Field(default_factory=dict)
> 
>     def capability_names(self) -> list[str]:
>         return [c.name for c in self.capabilities]
> 
> 
> # ──────────────────────────────────────────────
> # Envelope: 統一訊息封包
> # ──────────────────────────────────────────────
> 
> class MessageType(str, Enum):
>     REQUEST = "request"
>     RESPONSE = "response"
>     DISCOVERY = "discovery"
>     HEARTBEAT = "heartbeat"
>     ERROR = "error"
> 
> 
> class Envelope(BaseModel):
>     """
>     Envelope 是穿越系統的所有訊息的統一封包格式。
>     trace_id 提供因果鏈追蹤; hop_count + ttl 防止迴路。
>     """
>     message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
>     trace_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:16])
>     message_type: MessageType = Field(default=MessageType.REQUEST)
>     sender_id: str = Field(default="")
>     receiver_id: str = Field(default="")  # empty = broadcast / router decides
>     timestamp: float = Field(default_factory=time.time)
>     hop_count: int = Field(default=0)
>     ttl: int = Field(default=10, description="最大跳數限制")
>     payload: dict[str, Any] = Field(default_factory=dict)
> 
> 
> # ──────────────────────────────────────────────
> # A2A Request / Response: 請求與回應
> # ──────────────────────────────────────────────
> 
> class A2ARequest(BaseModel):
>     """封裝在 Envelope.payload 中的請求體。"""
>     capability: str = Field(..., description="請求的能力名稱")
>     parameters: dict[str, Any] = Field(default_factory=dict)
>     context: dict[str, Any] = Field(default_factory=dict, description="上下文資訊")
>     constraints: dict[str, Any] = Field(
>         default_factory=dict,
>         description="約束條件: max_cost, max_latency_ms, min_reputation 等"
>     )
> 
> 
> class A2AResponse(BaseModel):
>     """封裝在 Envelope.payload 中的回應體。"""
>     status: str = Field(default="success")  # success | error | partial
>     result: Any = Field(default=None)
>     error: Optional[str] = Field(default=None)
>     actual_cost: float = Field(default=0.0)
>     actual_latency_ms: float = Field(default=0.0)
>     served_by: str = Field(default="", description="實際服務此請求的 agent_id")
> 
> 
> # ──────────────────────────────────────────────
> # Causal Chain: 因果鏈記錄
> # ──────────────────────────────────────────────
> 
> class CausalHop(BaseModel):
>     """因果鏈中的一個跳躍（hop）。"""
>     hop_index: int
>     agent_id: str
>     action: str  # "route" | "execute" | "translate" | "meter"
>     timestamp: float = Field(default_factory=time.time)
>     latency_ms: float = 0.0
>     cost: float = 0.0
>     metadata: dict[str, Any] = Field(default_factory=dict)
> 
> 
> class CausalChain(BaseModel):
>     """
>     完整的因果鏈：一條請求從進入系統到離開系統的全部軌跡。
>     這是 Φ 引擎的核心數據結構。
>     """
>     trace_id: str
>     hops: list[CausalHop] = Field(default_factory=list)
>     outcome: str = Field(default="pending")  # pending | success | error | timeout
>     total_latency_ms: float = 0.0
>     total_cost: float = 0.0
>     value_signal: Optional[float] = Field(default=None, description="外部回饋的價值信號")
>     created_at: float = Field(default_factory=time.time)
>     closed_at: Optional[float] = None
> 
> 运行
> ```
> 
> 
> ---
> 
> 
> ### 3.2 代理注冊表 — `core/registry.py`
> 
> 
> ```python
> python
> 
> """
> core/registry.py
> ================
> Agent Registry — 代理發現與注冊
> 
> 映射：L1 (Identity Layer)
> 這是網絡的「電話簿」。沒有它，路由層無法知道任何外部代理的存在。
> """
> 
> from __future__ import annotations
> 
> import asyncio
> import time
> from typing import Optional
> 
> import numpy as np
> 
> from .protocol import AgentCard, AgentStatus, Capability
> 
> 
> class AgentRegistry:
>     """
>     代理注冊表。維護所有已知代理的 AgentCard，
>     並提供基於能力的語義發現。
> 
>     設計原則：
>     - 首先在 M1 Ultra 本地運行（單節點注冊表）
>     - 預留聯邦化介面，未來可跨節點同步
>     """
> 
>     def __init__(self, heartbeat_timeout: float = 60.0):
>         self._agents: dict[str, AgentCard] = {}  # agent_id -> AgentCard
>         self._capability_index: dict[str, list[str]] = {}  # capability_name -> [agent_ids]
>         self._heartbeat_timeout = heartbeat_timeout
> 
>     # ── 注冊 / 註銷 ──
> 
>     def register(self, card: AgentCard) -> AgentCard:
>         """註冊一個代理。如果已存在則更新。"""
>         card.last_heartbeat = time.time()
>         card.status = AgentStatus.ONLINE
>         self._agents[card.agent_id] = card
> 
>         # 更新能力索引
>         for cap in card.capabilities:
>             if cap.name not in self._capability_index:
>                 self._capability_index[cap.name] = []
>             if card.agent_id not in self._capability_index[cap.name]:
>                 self._capability_index[cap.name].append(card.agent_id)
> 
>         return card
> 
>     def deregister(self, agent_id: str) -> bool:
>         """註銷一個代理。"""
>         if agent_id not in self._agents:
>             return False
>         card = self._agents.pop(agent_id)
>         for cap in card.capabilities:
>             if cap.name in self._capability_index:
>                 self._capability_index[cap.name] = [
>                     aid for aid in self._capability_index[cap.name] if aid != agent_id
>                 ]
>         return True
> 
>     def heartbeat(self, agent_id: str) -> bool:
>         """更新代理心跳。"""
>         if agent_id not in self._agents:
>             return False
>         self._agents[agent_id].last_heartbeat = time.time()
>         self._agents[agent_id].status = AgentStatus.ONLINE
>         return True
> 
>     # ── 發現 ──
> 
>     def discover_by_name(self, capability_name: str) -> list[AgentCard]:
>         """按能力名稱精確匹配。"""
>         agent_ids = self._capability_index.get(capability_name, [])
>         return [
>             self._agents[aid] for aid in agent_ids
>             if aid in self._agents and self._agents[aid].status == AgentStatus.ONLINE
>         ]
> 
>     def discover_by_tags(self, tags: list[str]) -> list[AgentCard]:
>         """按標籤模糊匹配：返回具有任一指定標籤的代理。"""
>         results = []
>         tag_set = set(tags)
>         for card in self._agents.values():
>             if card.status != AgentStatus.ONLINE:
>                 continue
>             for cap in card.capabilities:
>                 if tag_set & set(cap.tags):
>                     results.append(card)
>                     break
>         return results
> 
>     def discover_by_semantic(
>         self,
>         query_embedding: list[float],
>         top_k: int = 5,
>         min_similarity: float = 0.3,
>     ) -> list[tuple[AgentCard, Capability, float]]:
>         """
>         語義發現：使用嵌入向量的餘弦相似度匹配能力。
>         返回 (AgentCard, 最佳匹配能力, 相似度分數) 的列表。
>         """
>         q = np.array(query_embedding, dtype=np.float32)
>         q_norm = np.linalg.norm(q)
>         if q_norm == 0:
>             return []
> 
>         scored: list[tuple[AgentCard, Capability, float]] = []
> 
>         for card in self._agents.values():
>             if card.status != AgentStatus.ONLINE:
>                 continue
>             for cap in card.capabilities:
>                 if cap.embedding is None:
>                     continue
>                 c = np.array(cap.embedding, dtype=np.float32)
>                 c_norm = np.linalg.norm(c)
>                 if c_norm == 0:
>                     continue
>                 similarity = float(np.dot(q, c) / (q_norm * c_norm))
>                 if similarity >= min_similarity:
>                     scored.append((card, cap, similarity))
> 
>         scored.sort(key=lambda x: x[2], reverse=True)
>         return scored[:top_k]
> 
>     def discover_by_text(
>         self, query: str, top_k: int = 5
>     ) -> list[tuple[AgentCard, Capability, float]]:
>         """
>         基於文本關鍵字的輕量級匹配（無需嵌入模型）。
>         使用 Jaccard 相似度對能力描述與標籤進行匹配。
>         """
>         query_tokens = set(query.lower().split())
>         scored: list[tuple[AgentCard, Capability, float]] = []
> 
>         for card in self._agents.values():
>             if card.status != AgentStatus.ONLINE:
>                 continue
>             for cap in card.capabilities:
>                 cap_tokens = set(cap.name.lower().replace(".", " ").split())
>                 cap_tokens |= set(cap.description.lower().split())
>                 cap_tokens |= set(t.lower() for t in cap.tags)
> 
>                 intersection = query_tokens & cap_tokens
>                 union = query_tokens | cap_tokens
>                 if not union:
>                     continue
>                 jaccard = len(intersection) / len(union)
>                 if jaccard > 0:
>                     scored.append((card, cap, jaccard))
> 
>         scored.sort(key=lambda x: x[2], reverse=True)
>         return scored[:top_k]
> 
>     # ── 拓撲 ──
> 
>     def get_all_agents(self) -> list[AgentCard]:
>         return list(self._agents.values())
> 
>     def get_agent(self, agent_id: str) -> Optional[AgentCard]:
>         return self._agents.get(agent_id)
> 
>     def get_topology_summary(self) -> dict:
>         """返回網絡拓撲概要。"""
>         online = [a for a in self._agents.values() if a.status == AgentStatus.ONLINE]
>         all_caps = set()
>         for a in online:
>             all_caps.update(a.capability_names())
>         return {
>             "total_agents": len(self._agents),
>             "online_agents": len(online),
>             "unique_capabilities": len(all_caps),
>             "capability_names": sorted(all_caps),
>         }
> 
>     # ── 健康檢查 ──
> 
>     async def health_check_loop(self, interval: float = 15.0):
>         """後台協程：定期檢查心跳超時的代理。"""
>         while True:
>             now = time.time()
>             for agent_id, card in list(self._agents.items()):
>                 if now - card.last_heartbeat > self._heartbeat_timeout:
>                     card.status = AgentStatus.OFFLINE
>             await asyncio.sleep(interval)
> 
> 运行
> ```
> 
> 
> ---
> 
> 
> ### 3.3 語義路由引擎 — `core/router.py`
> 
> 
> ```python
> python
> 
> """
> core/router.py
> ==============
> Semantic Router — 語義路由引擎
> 
> 映射：Φ 因果引擎的決策核心
> 這是整個系統作為「結締組織」的核心價值所在。
> 路由品質直接決定系統在網絡中的不可替代性。
> 
> 路由評分公式：
>   score(agent, request) = w1 * capability_match
>                         + w2 * (1 - normalized_latency)
>                         + w3 * reputation
>                         + w4 * (1 - normalized_cost)
>                         + w5 * causal_bonus
> 
> 其中 causal_bonus 來自歷史因果鏈的正向回饋。
> """
> 
> from __future__ import annotations
> 
> import random
> from dataclasses import dataclass, field
> from typing import Optional
> 
> from .protocol import AgentCard, A2ARequest, Capability, Envelope
> from .registry import AgentRegistry
> from .causal import CausalTracker
> 
> 
> @dataclass
> class RouteScore:
>     agent: AgentCard
>     capability: Capability
>     capability_match: float = 0.0
>     latency_score: float = 0.0
>     reputation_score: float = 0.0
>     cost_score: float = 0.0
>     causal_bonus: float = 0.0
>     total: float = 0.0
> 
> 
> @dataclass
> class RoutingWeights:
>     """路由評分的權重配置。可通過 Ω 層的反饋動態調整。"""
>     capability: float = 0.40
>     latency: float = 0.20
>     reputation: float = 0.25
>     cost: float = 0.10
>     causal: float = 0.05
> 
> 
> class Router:
>     """
>     語義路由引擎。
> 
>     核心職責：
>     1. 接收一個 A2ARequest
>     2. 通過 Registry 發現候選代理
>     3. 對候選代理進行多維評分
>     4. 返回最優路由選擇
> 
>     這是系統成為「不可替代的結締組織」的關鍵——
>     路由品質越高，越多代理願意通過此節點路由，
>     越多流量 → 越多因果數據 → 路由品質進一步提升。
>     這是一個正反饋迴路。
>     """
> 
>     def __init__(
>         self,
>         registry: AgentRegistry,
>         causal_tracker: CausalTracker,
>         weights: Optional[RoutingWeights] = None,
>     ):
>         self.registry = registry
>         self.causal = causal_tracker
>         self.weights = weights or RoutingWeights()
> 
>     def route(self, request: A2ARequest) -> Optional[RouteScore]:
>         """
>         為一個請求選擇最優代理。
>         返回 RouteScore 或 None (無可用代理)。
>         """
>         candidates = self._gather_candidates(request)
>         if not candidates:
>             return None
> 
>         scored = [self._score(c_agent, c_cap, c_sim, request) for c_agent, c_cap, c_sim in candidates]
>         scored.sort(key=lambda s: s.total, reverse=True)
> 
>         # 如果前兩名分差 < 5%，使用加權隨機選擇（探索-利用平衡）
>         if len(scored) >= 2 and scored[0].total > 0:
>             gap = (scored[0].total - scored[1].total) / scored[0].total
>             if gap < 0.05:
>                 top_two = scored[:2]
>                 weights = [s.total for s in top_two]
>                 total_w = sum(weights)
>                 if total_w > 0:
>                     probs = [w / total_w for w in weights]
>                     return random.choices(top_two, weights=probs, k=1)[0]
> 
>         return scored[0]
> 
>     def route_multi(self, request: A2ARequest, top_k: int = 3) -> list[RouteScore]:
>         """
>         Fan-out 路由：返回前 k 個最優代理。
>         用於需要多代理協作或冗餘的場景。
>         """
>         candidates = self._gather_candidates(request)
>         scored = [self._score(c_agent, c_cap, c_sim, request) for c_agent, c_cap, c_sim in candidates]
>         scored.sort(key=lambda s: s.total, reverse=True)
>         return scored[:top_k]
> 
>     def _gather_candidates(
>         self, request: A2ARequest
>     ) -> list[tuple[AgentCard, Capability, float]]:
>         """收集候選代理：先精確匹配，再語義匹配。"""
>         # Phase 1: 精確名稱匹配
>         exact_agents = self.registry.discover_by_name(request.capability)
>         exact_candidates = []
>         for agent in exact_agents:
>             for cap in agent.capabilities:
>                 if cap.name == request.capability:
>                     exact_candidates.append((agent, cap, 1.0))
>                     break
> 
>         if exact_candidates:
>             return exact_candidates
> 
>         # Phase 2: 文本語義匹配（輕量級，無需嵌入模型）
>         text_candidates = self.registry.discover_by_text(
>             request.capability, top_k=10
>         )
> 
>         return text_candidates
> 
>     def _score(
>         self,
>         agent: AgentCard,
>         capability: Capability,
>         capability_match: float,
>         request: A2ARequest,
>     ) -> RouteScore:
>         """多維評分。"""
>         w = self.weights
> 
>         # 1. 能力匹配度 (0-1)
>         cap_score = capability_match
> 
>         # 2. 延遲分數 (0-1, 越低越好)
>         max_latency = request.constraints.get("max_latency_ms", 10000)
>         latency_score = max(0.0, 1.0 - (capability.avg_latency_ms / max_latency))
> 
>         # 3. 信譽分 (0-1)
>         rep_score = agent.reputation
> 
>         # 4. 成本分數 (0-1, 越低越好)
>         max_cost = request.constraints.get("max_cost", 1.0)
>         cost_score = max(0.0, 1.0 - (capability.cost_per_call / max_cost)) if max_cost > 0 else 0.5
> 
>         # 5. 因果加成：歷史正向回饋
>         causal_bonus = self.causal.get_agent_causal_bonus(agent.agent_id)
> 
>         total = (
>             w.capability * cap_score
>             + w.latency * latency_score
>             + w.reputation * rep_score
>             + w.cost * cost_score
>             + w.causal * causal_bonus
>         )
> 
>         return RouteScore(
>             agent=agent,
>             capability=capability,
>             capability_match=cap_score,
>             latency_score=latency_score,
>             reputation_score=rep_score,
>             cost_score=cost_score,
>             causal_bonus=causal_bonus,
>             total=total,
>         )
> 
>     def update_weights_from_feedback(self, feedback: dict[str, float]):
>         """
>         Ω 算子的回饋介面：根據經濟層的信號動態調整路由權重。
>         這是因果迴路閉合的關鍵接縫。
>         """
>         if "capability" in feedback:
>             self.weights.capability = feedback["capability"]
>         if "latency" in feedback:
>             self.weights.latency = feedback["latency"]
>         if "reputation" in feedback:
>             self.weights.reputation = feedback["reputation"]
>         if "cost" in feedback:
>             self.weights.cost = feedback["cost"]
>         if "causal" in feedback:
>             self.weights.causal = feedback["causal"]
> 
> 运行
> ```
> 
> 
> ---
> 
> 
> ### 3.4 因果鏈追蹤器 — `core/causal.py`
> 
> 
> ```python
> python
> 
> """
> core/causal.py
> ==============
> Causal Chain Tracker — 因果鏈追蹤器
> 
> 映射：Φ 因果引擎
> 每條穿越系統的請求都會產生一條因果鏈 (CausalChain)。
> 這些鏈的統計性質驅動路由權重的演化。
> 
> 核心洞見：這不僅是「日誌」——這是系統學習和改進路由品質的
> 唯一數據來源。因果鏈是系統的「經驗記憶」。
> """
> 
> from __future__ import annotations
> 
> import time
> from collections import defaultdict
> from typing import Optional
> 
> from .protocol import CausalChain, CausalHop
> 
> 
> class CausalTracker:
>     """
>     因果鏈追蹤器。
> 
>     每條 trace_id 對應一條完整的因果鏈。
>     系統中的每個處理步驟（路由、翻譯、執行、計量）
>     都作為一個 CausalHop 記錄在鏈上。
>     """
> 
>     def __init__(self, max_chains: int = 100_000):
>         self._chains: dict[str, CausalChain] = {}
>         self._agent_chains: dict[str, list[str]] = defaultdict(list)  # agent_id -> [trace_ids]
>         self._agent_success_count: dict[str, int] = defaultdict(int)
>         self._agent_total_count: dict[str, int] = defaultdict(int)
>         self._agent_total_value: dict[str, float] = defaultdict(float)
>         self._max_chains = max_chains
> 
>     def begin_chain(self, trace_id: str) -> CausalChain:
>         """開始一條新的因果鏈。"""
>         chain = CausalChain(trace_id=trace_id)
>         self._chains[trace_id] = chain
>         self._maybe_evict()
>         return chain
> 
>     def add_hop(
>         self,
>         trace_id: str,
>         agent_id: str,
>         action: str,
>         latency_ms: float = 0.0,
>         cost: float = 0.0,
>         metadata: Optional[dict] = None,
>     ) -> Optional[CausalHop]:
>         """在因果鏈上追加一個跳躍。"""
>         chain = self._chains.get(trace_id)
>         if chain is None:
>             return None
> 
>         hop = CausalHop(
>             hop_index=len(chain.hops),
>             agent_id=agent_id,
>             action=action,
>             latency_ms=latency_ms,
>             cost=cost,
>             metadata=metadata or {},
>         )
>         chain.hops.append(hop)
>         chain.total_latency_ms += latency_ms
>         chain.total_cost += cost
> 
>         # 索引
>         self._agent_chains[agent_id].append(trace_id)
>         self._agent_total_count[agent_id] += 1
> 
>         return hop
> 
>     def close_chain(
>         self,
>         trace_id: str,
>         outcome: str = "success",
>         value_signal: Optional[float] = None,
>     ) -> Optional[CausalChain]:
>         """關閉因果鏈並記錄結果。"""
>         chain = self._chains.get(trace_id)
>         if chain is None:
>             return None
> 
>         chain.outcome = outcome
>         chain.closed_at = time.time()
>         chain.value_signal = value_signal
> 
>         # 更新代理統計
>         for hop in chain.hops:
>             if hop.action == "execute":
>                 if outcome == "success":
>                     self._agent_success_count[hop.agent_id] += 1
>                 if value_signal is not None:
>                     self._agent_total_value[hop.agent_id] += value_signal
> 
>         return chain
> 
>     def get_chain(self, trace_id: str) -> Optional[CausalChain]:
>         return self._chains.get(trace_id)
> 
>     def get_agent_causal_bonus(self, agent_id: str) -> float:
>         """
>         計算代理的因果加成分數 (0-1)。
>         綜合成功率和累積價值信號。
>         這個值直接注入路由評分函數。
>         """
>         total = self._agent_total_count.get(agent_id, 0)
>         if total == 0:
>             return 0.5  # 新代理獲得中性分數
> 
>         success = self._agent_success_count.get(agent_id, 0)
>         success_rate = success / total
> 
>         # 價值信號正則化
>         value = self._agent_total_value.get(agent_id, 0.0)
>         value_score = min(1.0, value / max(total, 1))  # 平均每次調用的價值
> 
>         # 綜合：70% 成功率 + 30% 價值信號
>         return 0.7 * success_rate + 0.3 * value_score
> 
>     def get_agent_stats(self, agent_id: str) -> dict:
>         """獲取代理的因果統計。"""
>         total = self._agent_total_count.get(agent_id, 0)
>         success = self._agent_success_count.get(agent_id, 0)
>         value = self._agent_total_value.get(agent_id, 0.0)
>         return {
>             "agent_id": agent_id,
>             "total_interactions": total,
>             "successful": success,
>             "success_rate": success / total if total > 0 else 0.0,
>             "total_value": value,
>             "causal_bonus": self.get_agent_causal_bonus(agent_id),
>         }
> 
>     def get_global_stats(self) -> dict:
>         """全局因果統計。"""
>         chains = list(self._chains.values())
>         closed = [c for c in chains if c.closed_at is not None]
>         successful = [c for c in closed if c.outcome == "success"]
>         return {
>             "total_chains": len(chains),
>             "closed_chains": len(closed),
>             "successful_chains": len(successful),
>             "global_success_rate": len(successful) / len(closed) if closed else 0.0,
>             "avg_latency_ms": (
>                 sum(c.total_latency_ms for c in closed) / len(closed) if closed else 0.0
>             ),
>             "avg_cost": (
>                 sum(c.total_cost for c in closed) / len(closed) if closed else 0.0
>             ),
>         }
> 
>     def _maybe_evict(self):
>         """當鏈數超過上限時，淘汰最舊的已關閉鏈。"""
>         if len(self._chains) <= self._max_chains:
>             return
>         closed = [
>             (tid, c) for tid, c in self._chains.items() if c.closed_at is not None
>         ]
>         closed.sort(key=lambda x: x[1].closed_at or 0)
>         evict_count = len(self._chains) - self._max_chains + 1000
>         for tid, _ in closed[:evict_count]:
>             del self._chains[tid]
> 
> 运行
> ```
> 
> 
> ---
> 
> 
> ### 3.5 邊界算子 — `core/boundary.py`
> 
> 
> ```python
> python
> 
> """
> core/boundary.py
> ================
> Boundary Operator — 邊界算子 / 協議互譯層
> 
> 映射：∂ 算子
> 這是系統因果錐穿過盒壁的精確位置。
> 所有外部協議（MCP, OpenAI, Google A2A）在此被翻譯為
> 內部規範格式 (Envelope)，出去時再翻譯回目標協議。
> 
> 設計原則：
> - 入方向：任何協議 → Envelope (正則化)
> - 出方向：Envelope → 目標代理的協議 (特化)
> - 翻譯過程本身也被記錄在因果鏈上 (action="translate")
> """
> 
> from __future__ import annotations
> 
> import time
> import uuid
> from typing import Any, Optional
> 
> from .protocol import (
>     A2ARequest,
>     A2AResponse,
>     Envelope,
>     MessageType,
> )
> 
> 
> class BoundaryOperator:
>     """
>     邊界算子 ∂：負責所有內外協議的互譯。
> 
>     目前支援的協議：
>     - native:    A2A Protocol Layer 原生格式
>     - mcp:       Anthropic Model Context Protocol
>     - openai:    OpenAI Function Calling / Tool Use
>     - google_a2a: Google Agent-to-Agent Protocol
> 
>     擴展方式：新增 _translate_inbound_xxx / _translate_outbound_xxx 方法對。
>     """
> 
>     SUPPORTED_PROTOCOLS = {"native", "mcp", "openai", "google_a2a"}
> 
>     def translate_inbound(
>         self, raw_message: dict[str, Any], source_protocol: str
>     ) -> Envelope:
>         """
>         外部消息 → 內部 Envelope。
>         這是因果錐擴張的入口。
>         """
>         if source_protocol == "native":
>             return Envelope(**raw_message)
>         elif source_protocol == "mcp":
>             return self._translate_inbound_mcp(raw_message)
>         elif source_protocol == "openai":
>             return self._translate_inbound_openai(raw_message)
>         elif source_protocol == "google_a2a":
>             return self._translate_inbound_google(raw_message)
>         else:
>             # 未知協議：盡力解析
>             return self._translate_inbound_generic(raw_message)
> 
>     def translate_outbound(
>         self, envelope: Envelope, target_protocol: str
>     ) -> dict[str, Any]:
>         """
>         內部 Envelope → 外部消息格式。
>         這是因果效應離開系統的出口。
>         """
>         if target_protocol == "native":
>             return envelope.model_dump()
>         elif target_protocol == "mcp":
>             return self._translate_outbound_mcp(envelope)
>         elif target_protocol == "openai":
>             return self._translate_outbound_openai(envelope)
>         elif target_protocol == "google_a2a":
>             return self._translate_outbound_google(envelope)
>         else:
>             return envelope.model_dump()
> 
>     def build_request_envelope(
>         self,
>         request: A2ARequest,
>         sender_id: str = "",
>         trace_id: Optional[str] = None,
>     ) -> Envelope:
>         """便捷方法：從 A2ARequest 構建完整 Envelope。"""
>         return Envelope(
>             message_id=str(uuid.uuid4()),
>             trace_id=trace_id or str(uuid.uuid4())[:16],
>             message_type=MessageType.REQUEST,
>             sender_id=sender_id,
>             payload=request.model_dump(),
>         )
> 
>     def build_response_envelope(
>         self,
>         response: A2AResponse,
>         original_envelope: Envelope,
>     ) -> Envelope:
>         """便捷方法：從 A2AResponse 構建回應 Envelope。"""
>         return Envelope(
>             trace_id=original_envelope.trace_id,
>             message_type=MessageType.RESPONSE,
>             sender_id=original_envelope.receiver_id,
>             receiver_id=original_envelope.sender_id,
>             payload=response.model_dump(),
>         )
> 
>     # ── MCP 協議互譯 ──
> 
>     def _translate_inbound_mcp(self, raw: dict[str, Any]) -> Envelope:
>         """
>         MCP (Model Context Protocol) → Envelope。
>         MCP 的核心概念：tools, resources, prompts, sampling。
>         此處將 tool call 映射為 A2ARequest。
>         """
>         method = raw.get("method", "")
>         params = raw.get("params", {})
> 
>         if method == "tools/call":
>             request = A2ARequest(
>                 capability=params.get("name", "unknown"),
>                 parameters=params.get("arguments", {}),
>                 context={"source_protocol": "mcp", "mcp_method": method},
>             )
>         elif method == "resources/read":
>             request = A2ARequest(
>                 capability="resource.read",
>                 parameters={"uri": params.get("uri", "")},
>                 context={"source_protocol": "mcp", "mcp_method": method},
>             )
>         else:
>             request = A2ARequest(
>                 capability=method.replace("/", "."),
>                 parameters=params,
>                 context={"source_protocol": "mcp", "mcp_method": method},
>             )
> 
>         return Envelope(
>             message_id=raw.get("id", str(uuid.uuid4())),
>             message_type=MessageType.REQUEST,
>             payload=request.model_dump(),
>         )
> 
>     def _translate_outbound_mcp(self, envelope: Envelope) -> dict[str, Any]:
>         """Envelope → MCP response format."""
>         payload = envelope.payload
>         return {
>             "jsonrpc": "2.0",
>             "id": envelope.message_id,
>             "result": {
>                 "content": [
>                     {
>                         "type": "text",
>                         "text": str(payload.get("result", "")),
>                     }
>                 ],
>                 "isError": payload.get("status") == "error",
>             },
>         }
> 
>     # ── OpenAI Function Calling 互譯 ──
> 
>     def _translate_inbound_openai(self, raw: dict[str, Any]) -> Envelope:
>         """
>         OpenAI function_call / tool_use → Envelope。
>         """
>         # OpenAI tool_calls 格式
>         tool_call = raw.get("tool_call", raw)
>         func = tool_call.get("function", {})
>         request = A2ARequest(
>             capability=func.get("name", "unknown"),
>             parameters=func.get("arguments", {}),
>             context={"source_protocol": "openai", "tool_call_id": tool_call.get("id", "")},
>         )
>         return Envelope(
>             message_type=MessageType.REQUEST,
>             payload=request.model_dump(),
>         )
> 
>     def _translate_outbound_openai(self, envelope: Envelope) -> dict[str, Any]:
>         """Envelope → OpenAI tool response format."""
>         payload = envelope.payload
>         return {
>             "tool_call_id": payload.get("context", {}).get("tool_call_id", ""),
>             "role": "tool",
>             "content": str(payload.get("result", "")),
>         }
> 
>     # ── Google A2A Protocol 互譯 ──
> 
>     def _translate_inbound_google(self, raw: dict[str, Any]) -> Envelope:
>         """
>         Google A2A Protocol → Envelope。
>         Google A2A 使用 Task 作為核心概念。
>         """
>         task = raw.get("task", raw)
>         message = task.get("message", {})
>         parts = message.get("parts", [])
>         text_content = " ".join(p.get("text", "") for p in parts if "text" in p)
> 
>         request = A2ARequest(
>             capability=task.get("skill", "general"),
>             parameters={"text": text_content},
>             context={
>                 "source_protocol": "google_a2a",
>                 "task_id": task.get("id", ""),
>                 "session_id": task.get("sessionId", ""),
>             },
>         )
>         return Envelope(
>             message_type=MessageType.REQUEST,
>             payload=request.model_dump(),
>         )
> 
>     def _translate_outbound_google(self, envelope: Envelope) -> dict[str, Any]:
>         """Envelope → Google A2A Task response."""
>         payload = envelope.payload
>         return {
>             "id": payload.get("context", {}).get("task_id", envelope.message_id),
>             "status": {
>                 "state": "completed" if payload.get("status") == "success" else "failed",
>             },
>             "artifacts": [
>                 {
>                     "parts": [{"text": str(payload.get("result", ""))}]
>                 }
>             ],
>         }
> 
>     # ── 通用兜底互譯 ──
> 
>     def _translate_inbound_generic(self, raw: dict[str, Any]) -> Envelope:
>         """未知協議的盡力解析。"""
>         capability = raw.get("capability", raw.get("method", raw.get("action", "unknown")))
>         parameters = raw.get("parameters", raw.get("params", raw.get("arguments", {})))
>         request = A2ARequest(
>             capability=str(capability),
>             parameters=parameters if isinstance(parameters, dict) else {"raw": parameters},
>             context={"source_protocol": "unknown"},
>         )
>         return Envelope(
>             message_type=MessageType.REQUEST,
>             payload=request.model_dump(),
>         )
> 
> 运行
> ```
> 
> 
> ---
> 
> 
> ### 3.6 經濟計量層 — `core/economics.py`
> 
> 
> ```python
> python
> 
> """
> core/economics.py
> =================
> Economics Engine — 經濟計量與結算引擎
> 
> 映射：Ω 耦合算子
> 這是因果迴路閉合的最後一環：將因果鏈的結果
> 轉化為可量化的經濟信號，回饋到路由層和注冊表。
> 
> Ω 的職責：
> 1. 計量每次路由的計算成本和延遲
> 2. 收集外部價值信號（用戶評分、下游使用量等）
> 3. 計算代理信譽分
> 4. 生成結算記錄
> 5. 向路由器回饋權重調整建議
> """
> 
> from __future__ import annotations
> 
> import time
> from collections import defaultdict
> from dataclasses import dataclass, field
> from typing import Optional
> 
> from .protocol import AgentCard
> from .registry import AgentRegistry
> from .causal import CausalTracker
> 
> 
> @dataclass
> class AgentLedger:
>     """單個代理的經濟帳本。"""
>     agent_id: str
>     total_revenue: float = 0.0       # 作為服務方獲得的總收入
>     total_cost: float = 0.0          # 作為請求方支出的總成本
>     total_calls_served: int = 0      # 服務的總請求數
>     total_calls_made: int = 0        # 發起的總請求數
>     total_value_generated: float = 0.0  # 累計價值信號
>     last_settlement: float = field(default_factory=time.time)
> 
> 
> @dataclass
> class Settlement:
>     """結算記錄。"""
>     agent_id: str
>     period_start: float
>     period_end: float
>     net_balance: float  # revenue - cost
>     reputation_delta: float
>     details: dict = field(default_factory=dict)
> 
> 
> class EconomicsEngine:
>     """
>     Ω 經濟引擎。
> 
>     核心迴路：
>     因果鏈關閉 → meter() 記錄成本 → record_value() 記錄價值
>     → compute_reputation() 更新信譽 → 信譽回饋到 Router 的評分函數
>     → Router 做出更好的路由決策 → 產生更好的因果鏈 → ...
> 
>     這就是自我融資迴路的數學結構。
>     """
> 
>     def __init__(
>         self,
>         registry: AgentRegistry,
>         causal_tracker: CausalTracker,
>     ):
>         self.registry = registry
>         self.causal = causal_tracker
>         self._ledgers: dict[str, AgentLedger] = defaultdict(
>             lambda: AgentLedger(agent_id="")
>         )
> 
>     def meter(
>         self,
>         trace_id: str,
>         agent_id: str,
>         compute_cost: float,
>         latency_ms: float,
>         role: str = "server",  # "server" | "client"
>     ) -> None:
>         """
>         計量一次交互的成本。
>         由因果追蹤器在鏈關閉時調用。
>         """
>         ledger = self._get_or_create_ledger(agent_id)
> 
>         if role == "server":
>             ledger.total_revenue += compute_cost
>             ledger.total_calls_served += 1
>         else:
>             ledger.total_cost += compute_cost
>             ledger.total_calls_made += 1
> 
>         # 同步更新因果鏈
>         self.causal.add_hop(
>             trace_id=trace_id,
>             agent_id=agent_id,
>             action="meter",
>             cost=compute_cost,
>             latency_ms=latency_ms,
>             metadata={"role": role},
>         )
> 
>     def record_value(
>         self, trace_id: str, agent_id: str, value_signal: float
>     ) -> None:
>         """
>         記錄外部價值信號。
>         value_signal 可以是：用戶評分、下游使用次數、經濟回報等。
>         """
>         ledger = self._get_or_create_ledger(agent_id)
>         ledger.total_value_generated += value_signal
> 
>     def compute_reputation(self, agent_id: str) -> float:
>         """
>         計算代理信譽分 (0.0 - 1.0)。
> 
>         信譽公式：
>           reputation = 0.4 * success_rate
>                      + 0.3 * normalized_value
>                      + 0.2 * consistency
>                      + 0.1 * tenure
> 
>         此值直接寫入 AgentCard.reputation，影響路由評分。
>         """
>         causal_stats = self.causal.get_agent_stats(agent_id)
>         ledger = self._get_or_create_ledger(agent_id)
> 
>         # Success rate
>         success_rate = causal_stats.get("success_rate", 0.5)
> 
>         # Normalized value: avg value per call, capped at 1.0
>         total_calls = ledger.total_calls_served or 1
>         avg_value = ledger.total_value_generated / total_calls
>         normalized_value = min(1.0, avg_value)
> 
>         # Consistency: 用變異係數的反數近似（此處簡化）
>         consistency = success_rate  # 簡化：高成功率 ≈ 高一致性
> 
>         # Tenure: 代理存活時間的對數正則化
>         agent = self.registry.get_agent(agent_id)
>         if agent:
>             tenure_seconds = time.time() - agent.registered_at
>             tenure_score = min(1.0, tenure_seconds / 86400)  # 1天 → 1.0
>         else:
>             tenure_score = 0.0
> 
>         reputation = (
>             0.4 * success_rate
>             + 0.3 * normalized_value
>             + 0.2 * consistency
>             + 0.1 * tenure_score
>         )
> 
>         # 寫回 AgentCard
>         if agent:
>             agent.reputation = reputation
> 
>         return reputation
> 
>     def get_ledger(self, agent_id: str) -> dict:
>         """獲取代理的經濟帳本。"""
>         ledger = self._get_or_create_ledger(agent_id)
>         return {
>             "agent_id": agent_id,
>             "total_revenue": ledger.total_revenue,
>             "total_cost": ledger.total_cost,
>             "net_balance": ledger.total_revenue - ledger.total_cost,
>             "total_calls_served": ledger.total_calls_served,
>             "total_calls_made": ledger.total_calls_made,
>             "total_value_generated": ledger.total_value_generated,
>             "reputation": self.compute_reputation(agent_id),
>         }
> 
>     def compute_settlement(self, period_hours: float = 24.0) -> list[Settlement]:
>         """
>         計算一個週期內的結算。
>         這是未來接入支付層的介面。
>         """
>         now = time.time()
>         period_start = now - (period_hours * 3600)
>         settlements = []
> 
>         for agent_id, ledger in self._ledgers.items():
>             net = ledger.total_revenue - ledger.total_cost
>             rep = self.compute_reputation(agent_id)
> 
>             settlements.append(Settlement(
>                 agent_id=agent_id,
>                 period_start=period_start,
>                 period_end=now,
>                 net_balance=net,
>                 reputation_delta=rep - 0.5,  # 相對於基線的變化
>                 details=self.get_ledger(agent_id),
>             ))
> 
>         return settlements
> 
>     def generate_routing_feedback(self) -> dict[str, float]:
>         """
>         生成路由權重調整建議。
>         Ω → Φ 的回饋通道。
> 
>         邏輯：如果整體網絡的成功率低，提高信譽權重；
>               如果延遲偏高，提高延遲權重；等等。
>         """
>         global_stats = self.causal.get_global_stats()
>         success_rate = global_stats.get("global_success_rate", 0.5)
>         avg_latency = global_stats.get("avg_latency_ms", 1000)
> 
>         feedback = {}
>         # 成功率低 → 信譽更重要
>         if success_rate < 0.7:
>             feedback["reputation"] = 0.35
>             feedback["capability"] = 0.35
>         # 延遲高 → 延遲更重要
>         if avg_latency > 5000:
>             feedback["latency"] = 0.30
> 
>         return feedback
> 
>     def _get_or_create_ledger(self, agent_id: str) -> AgentLedger:
>         if agent_id not in self._ledgers:
>             self._ledgers[agent_id] = AgentLedger(agent_id=agent_id)
>         else:
>             self._ledgers[agent_id].agent_id = agent_id
>         return self._ledgers[agent_id]
> 
> 运行
> ```
> 
> 
> ---
> 
> 
> ### 3.7 傳輸伺服器 — `transport/server.py`
> 
> 
> ```python
> python
> 
> """
> transport/server.py
> ===================
> FastAPI Server — 傳輸層
> 
> 映射：L0 (Transport Layer)
> 將整個 A2A Protocol Layer 暴露為可被外部代理訪問的 HTTP/WebSocket 端點。
> M1 Ultra 的第一條因果管道從這裡穿過盒壁。
> """
> 
> from __future__ import annotations
> 
> import time
> from contextlib import asynccontextmanager
> from typing import Any
> 
> import asyncio
> import httpx
> from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
> from pydantic import BaseModel
> 
> from core.protocol import (
>     AgentCard,
>     A2ARequest,
>     A2AResponse,
>     Envelope,
>     MessageType,
> )
> from core.registry import AgentRegistry
> from core.router import Router
> from core.causal import CausalTracker
> from core.boundary import BoundaryOperator
> from core.economics import EconomicsEngine
> 
> 
> # ──────────────────────────────────────────────
> # 全局單例（在 M1 Ultra 上以單進程運行）
> # ──────────────────────────────────────────────
> 
> registry = AgentRegistry(heartbeat_timeout=120.0)
> causal_tracker = CausalTracker(max_chains=100_000)
> router = Router(registry=registry, causal_tracker=causal_tracker)
> boundary = BoundaryOperator()
> economics = EconomicsEngine(registry=registry, causal_tracker=causal_tracker)
> 
> 
> # ──────────────────────────────────────────────
> # WebSocket 連接池（持久代理連接）
> # ──────────────────────────────────────────────
> 
> ws_connections: dict[str, WebSocket] = {}
> 
> 
> # ──────────────────────────────────────────────
> # FastAPI 應用
> # ──────────────────────────────────────────────
> 
> @asynccontextmanager
> async def lifespan(app: FastAPI):
>     """應用生命週期：啟動後台任務。"""
>     health_task = asyncio.create_task(registry.health_check_loop(interval=15.0))
>     feedback_task = asyncio.create_task(_feedback_loop())
>     yield
>     health_task.cancel()
>     feedback_task.cancel()
> 
> 
> app = FastAPI(
>     title="A2A Protocol Layer",
>     description="Agent-to-Agent Protocol Layer — 因果橋傳輸端點",
>     version="0.1.0",
>     lifespan=lifespan,
> )
> 
> 
> async def _feedback_loop():
>     """Ω → Φ 回饋迴路：定期更新路由權重。"""
>     while True:
>         await asyncio.sleep(60)  # 每 60 秒一次
>         feedback = economics.generate_routing_feedback()
>         if feedback:
>             router.update_weights_from_feedback(feedback)
> 
> 
> # ──────────────────────────────────────────────
> # L1: Agent Registration 代理注冊
> # ──────────────────────────────────────────────
> 
> @app.post("/agents/register", response_model=dict)
> async def register_agent(card: AgentCard):
>     """註冊一個外部代理。因果錐擴張的第一步。"""
>     registered = registry.register(card)
>     return {
>         "status": "registered",
>         "agent_id": registered.agent_id,
>         "capabilities_count": len(registered.capabilities),
>     }
> 
> 
> @app.delete("/agents/{agent_id}")
> async def deregister_agent(agent_id: str):
>     """註銷代理。"""
>     if registry.deregister(agent_id):
>         return {"status": "deregistered", "agent_id": agent_id}
>     raise HTTPException(status_code=404, detail="Agent not found")
> 
> 
> @app.post("/agents/{agent_id}/heartbeat")
> async def agent_heartbeat(agent_id: str):
>     if registry.heartbeat(agent_id):
>         return {"status": "alive"}
>     raise HTTPException(status_code=404, detail="Agent not found")
> 
> 
> @app.get("/agents/discover")
> async def discover_agents(capability: str = "", tags: str = "", top_k: int = 5):
>     """
>     發現代理。支援按能力名稱、標籤、或語義文本搜索。
>     """
>     if capability:
>         # 先嘗試精確匹配
>         exact = registry.discover_by_name(capability)
>         if exact:
>             return {"agents": [a.model_dump() for a in exact[:top_k]]}
>         # 退回到文本語義匹配
>         results = registry.discover_by_text(capability, top_k=top_k)
>         return {
>             "agents": [
>                 {**a.model_dump(), "_match_score": score, "_matched_capability": c.name}
>                 for a, c, score in results
>             ]
>         }
>     elif tags:
>         tag_list = [t.strip() for t in tags.split(",")]
>         agents = registry.discover_by_tags(tag_list)
>         return {"agents": [a.model_dump() for a in agents[:top_k]]}
>     else:
>         return {"agents": [a.model_dump() for a in registry.get_all_agents()[:top_k]]}
> 
> 
> # ──────────────────────────────────────────────
> # L2 + L3: Route & Execute 路由與執行
> # ──────────────────────────────────────────────
> 
> class RouteRequest(BaseModel):
>     capability: str
>     parameters: dict[str, Any] = {}
>     context: dict[str, Any] = {}
>     constraints: dict[str, Any] = {}
>     source_protocol: str = "native"
> 
> 
> @app.post("/route")
> async def route_request(req: RouteRequest):
>     """
>     僅路由：返回最優代理選擇，不執行。
>     用於客戶端希望自行發起調用的場景。
>     """
>     a2a_req = A2ARequest(
>         capability=req.capability,
>         parameters=req.parameters,
>         context=req.context,
>         constraints=req.constraints,
>     )
>     result = router.route(a2a_req)
>     if result is None:
>         raise HTTPException(status_code=404, detail="No agent found for capability")
> 
>     return {
>         "routed_to": result.agent.model_dump(),
>         "matched_capability": result.capability.name,
>         "score": result.total,
>         "score_breakdown": {
>             "capability_match": result.capability_match,
>             "latency_score": result.latency_score,
>             "reputation_score": result.reputation_score,
>             "cost_score": result.cost_score,
>             "causal_bonus": result.causal_bonus,
>         },
>     }
> 
> 
> @app.post("/execute")
> async def execute_request(req: RouteRequest):
>     """
>     路由 + 代理執行（完整因果鏈）。
>     系統作為代理請求的完整中介。
>     這是因果橋的核心端點。
>     """
>     # 1. 邊界算子：翻譯入站請求
>     a2a_req = A2ARequest(
>         capability=req.capability,
>         parameters=req.parameters,
>         context=req.context,
>         constraints=req.constraints,
>     )
>     envelope = boundary.build_request_envelope(a2a_req, sender_id="client")
> 
>     # 2. 因果鏈：開始追蹤
>     chain = causal_tracker.begin_chain(envelope.trace_id)
>     causal_tracker.add_hop(
>         trace_id=envelope.trace_id,
>         agent_id="router",
>         action="receive",
>     )
> 
>     # 3. 路由器：選擇最優代理
>     route_result = router.route(a2a_req)
>     if route_result is None:
>         causal_tracker.close_chain(envelope.trace_id, outcome="error")
>         raise HTTPException(status_code=404, detail="No agent found")
> 
>     target_agent = route_result.agent
>     causal_tracker.add_hop(
>         trace_id=envelope.trace_id,
>         agent_id="router",
>         action="route",
>         metadata={"target": target_agent.agent_id, "score": route_result.total},
>     )
> 
>     # 4. 邊界算子：翻譯為目標協議
>     outbound = boundary.translate_outbound(envelope, target_agent.protocol)
>     causal_tracker.add_hop(
>         trace_id=envelope.trace_id,
>         agent_id="boundary",
>         action="translate",
>         metadata={"target_protocol": target_agent.protocol},
>     )
> 
>     # 5. 執行：向目標代理發送請求
>     start_time = time.time()
>     try:
>         async with httpx.AsyncClient(timeout=30.0) as client:
>             resp = await client.post(
>                 target_agent.endpoint,
>                 json=outbound,
>             )
>             resp_data = resp.json()
>             latency_ms = (time.time() - start_time) * 1000
> 
>             # 6. 因果鏈：記錄執行
>             causal_tracker.add_hop(
>                 trace_id=envelope.trace_id,
>                 agent_id=target_agent.agent_id,
>                 action="execute",
>                 latency_ms=latency_ms,
>                 cost=route_result.capability.cost_per_call,
>             )
> 
>             # 7. 經濟層：計量
>             economics.meter(
>                 trace_id=envelope.trace_id,
>                 agent_id=target_agent.agent_id,
>                 compute_cost=route_result.capability.cost_per_call,
>                 latency_ms=latency_ms,
>                 role="server",
>             )
> 
>             # 8. 因果鏈：關閉
>             causal_tracker.close_chain(
>                 envelope.trace_id, outcome="success"
>             )
> 
>             # 9. 信譽更新
>             economics.compute_reputation(target_agent.agent_id)
> 
>             return {
>                 "trace_id": envelope.trace_id,
>                 "result": resp_data,
>                 "served_by": target_agent.agent_id,
>                 "latency_ms": latency_ms,
>                 "cost": route_result.capability.cost_per_call,
>             }
> 
>     except Exception as e:
>         latency_ms = (time.time() - start_time) * 1000
>         causal_tracker.add_hop(
>             trace_id=envelope.trace_id,
>             agent_id=target_agent.agent_id,
>             action="execute",
>             latency_ms=latency_ms,
>             metadata={"error": str(e)},
>         )
>         causal_tracker.close_chain(envelope.trace_id, outcome="error")
>         economics.compute_reputation(target_agent.agent_id)
> 
>         raise HTTPException(
>             status_code=502,
>             detail=f"Agent execution failed: {str(e)}",
>         )
> 
> 
> # ──────────────────────────────────────────────
> # L2: Inbound Protocol Translation 入站協議翻譯
> # ──────────────────────────────────────────────
> 
> @app.post("/translate/{source_protocol}")
> async def translate_inbound(source_protocol: str, raw_message: dict[str, Any]):
>     """
>     通用協議翻譯入口。
>     外部代理使用其原生協議發送消息到此端點，
>     系統自動翻譯為 Envelope 並路由執行。
>     """
>     envelope = boundary.translate_inbound(raw_message, source_protocol)
>     # 從 envelope 中提取 A2ARequest
>     payload = envelope.payload
>     req = RouteRequest(
>         capability=payload.get("capability", "unknown"),
>         parameters=payload.get("parameters", {}),
>         context=payload.get("context", {}),
>         constraints=payload.get("constraints", {}),
>         source_protocol=source_protocol,
>     )
>     return await execute_request(req)
> 
> 
> # ──────────────────────────────────────────────
> # L4: Causal Chain Inspection 因果鏈查詢
> # ──────────────────────────────────────────────
> 
> @app.get("/traces/{trace_id}")
> async def get_trace(trace_id: str):
>     chain = causal_tracker.get_chain(trace_id)
>     if chain is None:
>         raise HTTPException(status_code=404, detail="Trace not found")
>     return chain.model_dump()
> 
> 
> @app.get("/traces")
> async def get_global_stats():
>     return causal_tracker.get_global_stats()
> 
> 
> # ──────────────────────────────────────────────
> # L5: Economics 經濟層查詢
> # ──────────────────────────────────────────────
> 
> @app.get("/economics/{agent_id}")
> async def get_agent_economics(agent_id: str):
>     return economics.get_ledger(agent_id)
> 
> 
> @app.get("/economics")
> async def get_settlements(period_hours: float = 24.0):
>     settlements = economics.compute_settlement(period_hours)
>     return {
>         "period_hours": period_hours,
>         "settlements": [
>             {
>                 "agent_id": s.agent_id,
>                 "net_balance": s.net_balance,
>                 "reputation_delta": s.reputation_delta,
>                 "details": s.details,
>             }
>             for s in settlements
>         ],
>     }
> 
> 
> # ──────────────────────────────────────────────
> # Topology 拓撲概覽
> # ──────────────────────────────────────────────
> 
> @app.get("/topology")
> async def get_topology():
>     return registry.get_topology_summary()
> 
> 
> # ──────────────────────────────────────────────
> # WebSocket: 持久代理連接
> # ──────────────────────────────────────────────
> 
> @app.websocket("/ws/agent/{agent_id}")
> async def agent_websocket(websocket: WebSocket, agent_id: str):
>     """
>     持久 WebSocket 連接。
>     代理通過此通道接收路由過來的請求並返回結果。
>     比 HTTP 輪詢效率高數個量級。
>     """
>     await websocket.accept()
>     ws_connections[agent_id] = websocket
> 
>     try:
>         while True:
>             data = await websocket.receive_json()
>             # 處理代理發來的消息（心跳、結果回傳等）
>             msg_type = data.get("type", "heartbeat")
> 
>             if msg_type == "heartbeat":
>                 registry.heartbeat(agent_id)
>                 await websocket.send_json({"type": "heartbeat_ack"})
> 
>             elif msg_type == "response":
>                 # 代理返回的執行結果
>                 trace_id = data.get("trace_id", "")
>                 result = data.get("result", {})
>                 # 此處可將結果回傳給等待中的請求
>                 await websocket.send_json({
>                     "type": "response_ack",
>                     "trace_id": trace_id,
>                 })
> 
>             elif msg_type == "register":
>                 card_data = data.get("agent_card", {})
>                 card = AgentCard(**card_data)
>                 card.agent_id = agent_id
>                 registry.register(card)
>                 await websocket.send_json({
>                     "type": "register_ack",
>                     "agent_id": agent_id,
>                 })
> 
>     except WebSocketDisconnect:
>         ws_connections.pop(agent_id, None)
>         agent = registry.get_agent(agent_id)
>         if agent:
>             agent.status = "offline"
> 
> 运行
> ```
> 
> 
> ---
> 
> 
> ### 3.8 啟動入口 — `main.py`
> 
> 
> ```python
> python
> 
> """
> main.py
> =======
> A2A Protocol Layer — 啟動入口
> 
> 在 M1 Ultra 上首次啟動因果橋：
>   python main.py
> 
> 系統將在 http://localhost:8420 暴露所有端點。
> 8420 = 第一條因果管道的端口號。
> 
> 啟動後，系統本身也作為一個代理注冊到自己的注冊表中——
> 路由器本身就是網絡中的第一個節點。
> """
> 
> import uvicorn
> 
> from core.protocol import AgentCard, Capability
> from transport.server import app, registry
> 
> 
> def register_self():
>     """
>     將路由器自身注冊為網絡中的第一個代理。
>     Node 0: M1 Ultra。
>     """
>     self_card = AgentCard(
>         agent_id="node-0-router",
>         name="A2A Protocol Router (Node 0)",
>         description=(
>             "Core routing node running on M1 Ultra. "
>             "Provides agent discovery, semantic routing, "
>             "protocol translation, and causal tracking."
>         ),
>         endpoint="http://localhost:8420",
>         protocol="native",
>         capabilities=[
>             Capability(
>                 name="routing.route",
>                 description="Route a request to the best available agent",
>                 tags=["routing", "discovery", "core"],
>             ),
>             Capability(
>                 name="routing.discover",
>                 description="Discover agents by capability",
>                 tags=["discovery", "registry", "core"],
>             ),
>             Capability(
>                 name="protocol.translate",
>                 description="Translate between MCP, OpenAI, Google A2A protocols",
>                 tags=["translation", "protocol", "mcp", "openai", "core"],
>             ),
>             Capability(
>                 name="causal.trace",
>                 description="Track and query causal chains of agent interactions",
>                 tags=["causal", "tracking", "analytics", "core"],
>             ),
>             Capability(
>                 name="economics.meter",
>                 description="Economic metering and settlement for agent interactions",
>                 tags=["economics", "metering", "settlement", "core"],
>             ),
>         ],
>         metadata={
>             "substrate": "Apple M1 Ultra",
>             "memory": "128GB Unified",
>             "role": "backbone_router",
>         },
>     )
>     registry.register(self_card)
>     print(f"[Node 0] Self-registered as '{self_card.agent_id}'")
>     print(f"[Node 0] Capabilities: {self_card.capability_names()}")
> 
> 
> def main():
>     print("=" * 60)
>     print("  A2A Protocol Layer — 因果橋啟動")
>     print("  Substrate: M1 Ultra (128GB Unified Memory)")
>     print("  Endpoint:  http://localhost:8420")
>     print("=" * 60)
> 
>     register_self()
> 
>     print("\n[Causal Bridge] 因果管道已穿過盒壁。等待外部代理連接...\n")
> 
>     uvicorn.run(
>         app,
>         host="0.0.0.0",
>         port=8420,
>         log_level="info",
>     )
> 
> 
> if __name__ == "__main__":
>     main()
> 
> 运行
> ```
> 
> 
> ---
> 
> 
> ### 3.9 測試與驗證：模擬外部代理接入
> 
> 
> ```python
> python
> 
> """
> tests/test_integration.py
> =========================
> 整合測試：模擬外部代理注冊、路由、執行的完整因果鏈。
> 
> 使用方式：
>   6. 先啟動 main.py: python main.py
>   7. 在另一個終端運行: python tests/test_integration.py
> """
> 
> import httpx
> import asyncio
> import json
> 
> 
> BASE = "http://localhost:8420"
> 
> 
> async def main():
>     async with httpx.AsyncClient(base_url=BASE, timeout=10.0) as client:
> 
>         print("=" * 50)
>         print("Phase 1: 注冊模擬代理")
>         print("=" * 50)
> 
>         # 注冊一個文本摘要代理
>         summarizer = {
>             "agent_id": "agent-summarizer",
>             "name": "Text Summarizer Agent",
>             "description": "Summarizes long text into key points",
>             "endpoint": "http://localhost:9001/execute",
>             "protocol": "native",
>             "capabilities": [
>                 {
>                     "name": "text.summarize",
>                     "description": "Summarize text content into concise key points",
>                     "tags": ["text", "summarize", "nlp"],
>                     "cost_per_call": 0.002,
>                     "avg_latency_ms": 500,
>                 },
>                 {
>                     "name": "text.translate",
>                     "description": "Translate text between languages",
>                     "tags": ["text", "translate", "nlp"],
>                     "cost_per_call": 0.003,
>                     "avg_latency_ms": 800,
>                 },
>             ],
>         }
> 
>         resp = await client.post("/agents/register", json=summarizer)
>         print(f"  Summarizer registered: {resp.json()}")
> 
>         # 注冊一個代碼分析代理
>         coder = {
>             "agent_id": "agent-coder",
>             "name": "Code Analysis Agent",
>             "description": "Analyzes and reviews code",
>             "endpoint": "http://localhost:9002/execute",
>             "protocol": "native",
>             "capabilities": [
>                 {
>                     "name": "code.review",
>                     "description": "Review code for bugs and improvements",
>                     "tags": ["code", "review", "analysis"],
>                     "cost_per_call": 0.005,
>                     "avg_latency_ms": 1200,
>                 },
>                 {
>                     "name": "code.generate",
>                     "description": "Generate code from specifications",
>                     "tags": ["code", "generate", "programming"],
>                     "cost_per_call": 0.008,
>                     "avg_latency_ms": 2000,
>                 },
>             ],
>             "reputation": 0.8,
>         }
> 
>         resp = await client.post("/agents/register", json=coder)
>         print(f"  Coder registered: {resp.json()}")
> 
>         # 注冊一個 MCP 協議代理
>         mcp_agent = {
>             "agent_id": "agent-mcp-tools",
>             "name": "MCP Tool Server",
>             "description": "Provides filesystem and database tools via MCP",
>             "endpoint": "http://localhost:9003/mcp",
>             "protocol": "mcp",
>             "capabilities": [
>                 {
>                     "name": "filesystem.read",
>                     "description": "Read files from the filesystem",
>                     "tags": ["filesystem", "read", "io", "mcp"],
>                     "cost_per_call": 0.001,
>                     "avg_latency_ms": 100,
>                 },
>             ],
>         }
> 
>         resp = await client.post("/agents/register", json=mcp_agent)
>         print(f"  MCP Agent registered: {resp.json()}")
> 
>         print("\n" + "=" * 50)
>         print("Phase 2: 查看網絡拓撲")
>         print("=" * 50)
> 
>         resp = await client.get("/topology")
>         topo = resp.json()
>         print(f"  Total agents: {topo['total_agents']}")
>         print(f"  Online agents: {topo['online_agents']}")
>         print(f"  Capabilities: {topo['capability_names']}")
> 
>         print("\n" + "=" * 50)
>         print("Phase 3: 語義發現")
>         print("=" * 50)
> 
>         # 精確發現
>         resp = await client.get("/agents/discover", params={"capability": "text.summarize"})
>         agents = resp.json()["agents"]
>         print(f"  Exact 'text.summarize': {len(agents)} agent(s) found")
> 
>         # 模糊語義發現
>         resp = await client.get("/agents/discover", params={"capability": "review my python code"})
>         agents = resp.json()["agents"]
>         print(f"  Semantic 'review my python code': {len(agents)} agent(s) found")
>         for a in agents:
>             score = a.get("_match_score", "N/A")
>             matched = a.get("_matched_capability", "N/A")
>             print(f"    → {a['name']} (score={score}, matched={matched})")
> 
>         print("\n" + "=" * 50)
>         print("Phase 4: 路由測試")
>         print("=" * 50)
> 
>         route_req = {
>             "capability": "text.summarize",
>             "parameters": {"text": "A very long document..."},
>             "constraints": {"max_latency_ms": 5000, "max_cost": 0.01},
>         }
> 
>         resp = await client.post("/route", json=route_req)
>         route = resp.json()
>         print(f"  Routed to: {route['routed_to']['name']}")
>         print(f"  Score: {route['score']:.4f}")
>         print(f"  Breakdown: {json.dumps(route['score_breakdown'], indent=2)}")
> 
>         print("\n" + "=" * 50)
>         print("Phase 5: MCP 協議互譯測試")
>         print("=" * 50)
> 
>         # 模擬 MCP 格式的請求
>         mcp_request = {
>             "jsonrpc": "2.0",
>             "id": "mcp-test-001",
>             "method": "tools/call",
>             "params": {
>                 "name": "filesystem.read",
>                 "arguments": {"path": "/data/config.json"},
>             },
>         }
> 
>         # 注意：execute 會嘗試實際調用目標代理
>         # 在測試中目標代理不存在，會返回 502
>         # 但我們可以測試路由邏輯
>         route_req_mcp = {
>             "capability": "filesystem.read",
>             "parameters": {"path": "/data/config.json"},
>             "source_protocol": "mcp",
>         }
>         resp = await client.post("/route", json=route_req_mcp)
>         print(f"  MCP route result: {resp.json()['routed_to']['name']}")
> 
>         print("\n" + "=" * 50)
>         print("Phase 6: 因果統計")
>         print("=" * 50)
> 
>         resp = await client.get("/traces")
>         print(f"  Global causal stats: {json.dumps(resp.json(), indent=2)}")
> 
>         print("\n" + "=" * 50)
>         print("Phase 7: 經濟數據")
>         print("=" * 50)
> 
>         resp = await client.get("/economics/agent-summarizer")
>         print(f"  Summarizer economics: {json.dumps(resp.json(), indent=2)}")
> 
>         print("\n✅ 因果橋整合測試完成。")
>         print("系統已具備接收外部代理的能力。")
>         print("下一步：將真實代理接入端口 8420。")
> 
> 
> if __name__ == "__main__":
>     asyncio.run(main())
> 
> 运行
> ```
> 
> 
> ---
> 
> 
> ## 肆、部署序列：從 M1 Ultra 到活網絡
> 
> **Step 0 → 啟動 Node 0（今天就做）：**
> 
> 
> ```bash
> bash
> 
> cd a2a-protocol-layer
> pip install -r requirements.txt
> python main.py
> # 因果橋現在活著了。http://localhost:8420
> ```
> 
> **Step 1 → 穿過盒壁（本週內）：** 使用 `ngrok`、`cloudflare tunnel`、或 `tailscale` 將 `localhost:8420` 暴露為公網可達端點。此刻起，M1 Ultra 的因果錐半徑從零跳到非零。
> 
> 
> ```bash
> bash
> 
> # 最簡方案：ngrok
> ngrok http 8420
> # 更穩定的方案：cloudflare tunnel
> cloudflared tunnel --url http://localhost:8420
> ```
> 
> **Step 2 → 接入第一批外部代理（兩週內）：** 將你自己的其他 AI 工具（本地 LLM、MCP server、自定義腳本）注冊為代理。它們不需要知道彼此——它們只需要知道路由器的端點。網絡效應從第三個節點開始顯現。
> 
> **Step 3 → 公佈 AgentCard 規範（一個月內）：** 將 `core/protocol.py` 中的 `AgentCard` 和 `Capability` 規範作為開放標準發佈。任何人只要按此格式發一個 POST 到 `/agents/register`，就自動加入網絡。這是從「你的工具」到「所有人的基礎設施」的相變起點。
> 
> 
> ---
> 
> 上述約 1200 行核心代碼的全部語義可以壓縮為一句話：**在 M1 Ultra 上啟動一個能讓任何 AI 代理發現彼此、相互通話、並自動追蹤因果與經濟回饋的路由節點——這就是你的因果錐從半徑零跳到非零的精確機制。**
> 
> 