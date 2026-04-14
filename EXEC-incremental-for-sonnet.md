# Sonnet 增量執行指令（2026-04-14）

> 上下文：72h 驗證正在運行（Hour 10/72 ALL PASS）。Phase 0–7 代碼已完成。
> 本文件只包含**增量工作**——不重複已有內容，不重寫已通過的代碼。
> 優先級：P0 先做完再碰 P1。P0 內部按編號順序。

---

## P0：72h 驗證完成後立即執行（生存級）

### P0-1：light_node 記憶體穩態修復（Dumb Pipe 改造）

**問題**：72h 日誌顯示 RSS 從 4 MiB 線性增長到 192 MiB（10h）。
外推 30 天 → ~14 GB → 超過 c7g 的 8 GB RAM → OOM。
根因：light_node 上的 `causal-dag` DashMap 持續累積記錄永不釋放。

**修復方案**：light_node 不維護 causal-dag。改為純轉發模式。

在 `crates/aevum-core/src/runtime.rs` 中，按 feature flag 分離行為：

```rust
// genesis_node: 完整 DAG + ledger + autopoiesis（現有邏輯不變）
// light_node: TGP 校驗 → pressure_gauge 速率檢查 → 轉發 → Drop

#[cfg(feature = "light_node")]
async fn process_envelope_light(raw: &[u8], upstream: &TailscaleForwarder) -> Result<(), EnvelopeError> {
    // 1. TGP 物理校驗（現有邏輯）
    let tgp = parse_tgp_frame(raw)?;
    if !tgp.lambda.is_physically_plausible() {
        return Err(EnvelopeError::PhysicsViolation);
    }
    
    // 2. 壓力計速率限制（現有邏輯）
    if pressure_gauge.should_throttle(tgp.lambda.point) {
        return Err(EnvelopeError::ThermodynamicOverload);
    }
    
    // 3. 直接轉發原始字節到 M1（不解析 CTP/AgentCard，不存 DAG）
    upstream.forward(raw).await?;
    
    // 4. raw 在此離開作用域 → Rust Drop → 記憶體立即釋放
    Ok(())
    // ← 沒有任何 DashMap insert，沒有任何持久化
}
```

**驗收標準**：
- 修復後在 AWS 上跑 24h
- RSS 必須穩定在 < 32 MiB（波動 ±5 MiB 可接受，趨勢必須平坦非線性）
- `aevum status` 新增 `memory_trend: stable | growing` 指標

**新增文件**：`crates/aevum-core/src/forwarder.rs`

```rust
/// Pillar: I. PACR field: none (light_node does not produce PACR records).
/// Design: End-to-End Principle (Saltzer, Reed, Clark 1984).
/// Intelligence at the edges (M1), dumb pipe in the middle (AWS).
///
/// This module forwards raw envelope bytes to the genesis_node via Tailscale.
/// It does NOT parse CTP/AgentCard, does NOT maintain causal-dag,
/// does NOT produce PACR records. It is a thermodynamic filter + pipe.

pub struct TailscaleForwarder {
    genesis_addr: std::net::SocketAddr,  // 100.113.207.108:8420
}

impl TailscaleForwarder {
    pub fn new(genesis_ip: &str, port: u16) -> Self {
        Self {
            genesis_addr: format!("{}:{}", genesis_ip, port).parse().unwrap(),
        }
    }
    
    pub async fn forward(&self, raw_bytes: &[u8]) -> Result<(), std::io::Error> {
        // UDP 轉發：無連接、無狀態、O(1)
        let socket = tokio::net::UdpSocket::bind("0.0.0.0:0").await?;
        socket.send_to(raw_bytes, self.genesis_addr).await?;
        Ok(())
    }
}
```

**配置更新**：`light-node.toml` 新增：

```toml
[forwarder]
genesis_tailscale_ip = "100.113.207.108"
genesis_port = 8420
```

---

### P0-2：CLAUDE.local.md 更新實際拓撲

在 `CLAUDE.local.md` 的現有 §4 部署拓撲描述之後，追加實測數據：

```markdown
## §10 Confirmed Physical Topology (2026-04-14 measured)

| Node | Tailscale IP | Role | Measured Latency |
|------|-------------|------|-----------------|
| M1 Ultra 128GB | 100.113.207.108 | Genesis Node (full DAG + AGI) | local |
| AWS Tokyo c7g | 100.116.253.50 | Membrane Router (Dumb Pipe) | ~54ms from M1 |
| NAS 23TB | 100.82.176.54 | State Vault (pacr-ledger backend) | ~2ms Tailscale / ~0.8ms LAN |

### Storage mapping:
- pacr-ledger persistent backend → NAS 23TB via Tailscale (100.82.176.54)
- state_vault symlink → NAS mount point (not external SSD)
- NAS LAN address: 192.168.3.54 (used when M1 and NAS on same network)
- 23TB capacity → sufficient for decades of PACR records at current rate

### light_node memory contract:
- light_node is a STATELESS forwarder (Dumb Pipe)
- Does NOT maintain causal-dag, does NOT accumulate PacrRecords
- Steady-state RSS MUST be < 32 MiB
- Enforced by: no DashMap in light_node code path, all allocations freed after forwarding
```

---

### P0-3：Wire Format 凍結聲明

72h 驗證通過後，在 agentcard-spec GitHub 倉庫執行：

```bash
cd ~/agentcard-spec

cat > FROZEN.md << 'EOF'
# Wire Format Freeze Notice

**Version**: v1.0.0
**Date**: 2026-04-17 (post 72h validation)
**Status**: FROZEN

The PACR envelope wire format (Primary Header + Extension Headers + Body)
as defined in this repository is hereby frozen.

## Guarantee
- No backward-incompatible changes will ever be made to v1.x
- New Extension Header types may be added (TYPE codes 0x0100-0xFFFE)
- Primary Header structure (104 bytes fixed) will NEVER change
- MAGIC (0x50414352), VERSION_MAJOR (1) interpretation will NEVER change

## Verification
Any v1.0 envelope serialized today MUST be deserializable by any future v1.x parser.

## Rationale
The first real PACR records are now being generated (72h validation: 2,600,000+ records).
Changing wire format after this point would invalidate causal history — a thermodynamic
impossibility (you cannot un-erase erased bits).
EOF

git add FROZEN.md
git tag -a v1.0.0 -m "Wire Format Freeze: backward compatibility guaranteed"
git push origin main --tags
```

---

## P1：72h 驗證 + P0 修復 + 24h 穩態驗證後執行（擴展級）

### P1-1：AWS Tokyo 降級

現在 light_node 是 Dumb Pipe（< 32 MiB RSS），不需要 c7g.xlarge（8GB RAM）。

```
當前：c7g.xlarge  4vCPU / 8GB   ~$60/月
降至：c7g.small   2vCPU / 2GB   ~$15/月
```

操作：
1. 在 AWS Console 停止實例
2. Change Instance Type → c7g.small
3. 啟動，`tailscale up`，驗證 `aevum status`
4. 跑 24h 確認穩定

---

### P1-2：部署第二個 light_node（新加坡）

**為什麼新加坡優先**：
- 離 M1（假設在新加坡/香港附近）延遲最低
- Hetzner Singapore ~$4/月（比 AWS 便宜 4 倍）
- 驗證「多節點 + DAG 合併」的最小成本實驗

**部署步驟**：

```bash
# 在 Hetzner Singapore VPS 上：

# 1. 安裝 Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up

# 2. 複製 light_node 二進制（已交叉編譯的 aarch64 或 x86_64）
scp user@100.113.207.108:~/aevum_workspace/target/release/aevum ./aevum
chmod +x aevum

# 3. 配置
cat > light-node.toml << 'EOF'
[node]
role = "light"
region = "singapore"

[forwarder]
genesis_tailscale_ip = "100.113.207.108"
genesis_port = 8420

[pressure_gauge]
max_watts = 1000.0
window_duration_secs = 1.0
EOF

# 4. 啟動
./aevum run --config light-node.toml &

# 5. 驗證
curl http://localhost:8420/health  # 應返回 200
```

**驗收**：
- 新加坡節點 RSS < 32 MiB 穩定 24h
- M1 能收到從新加坡轉發的封包
- Cloudflare 配置新加坡節點的 DNS 記錄

---

### P1-3：多節點 Cloudflare 配置

```
api.aevum.network → Cloudflare Load Balancer
  ├── tokyo.aevum.network    → 100.116.253.50  (AWS)
  ├── singapore.aevum.network → [新加坡 Tailscale IP]
  └── (未來) hongkong / siliconvalley
  
Cloudflare 配置：
- Load Balancing: Geographic routing（亞洲 → 東京/新加坡，美洲 → 硅谷）
- Health Check: GET /health 每 30 秒
- Failover: 節點不健康 → 自動切換到下一個
```

---

### P1-4：NAS 作為 pacr-ledger 後端配置

72h 日誌確認 NAS 延遲 ~0.8ms（本地網）。配置 M1 的 pacr-ledger 指向 NAS：

```bash
# M1 上：
# 方案 A：NFS mount（最簡單）
sudo mount -t nfs 192.168.3.54:/volume1/aevum /mnt/nas_aevum

# 方案 B：symlink（如果 NAS 已通過 SMB/AFP 掛載）
ln -sf /Volumes/NAS_23TB/aevum_ledger ~/aevum_workspace/state_vault/ledger

# pacr-ledger 配置
# genesis-node.toml:
[ledger]
path = "/mnt/nas_aevum/pacr_ledger"  # 或 symlink 指向的路徑
```

按 36,000 records/hour × 每條 ~0.6 KB：
- 每天：~500 MB
- 每年：~180 GB
- 23 TB → **可存 ~130 年**

---

## 不執行清單（明確排除）

| 項目 | 排除原因 |
|------|---------|
| light_node 上運行 causal-dag | 違反 Dumb Pipe 原則，是記憶體膨脹的根因 |
| light_node 上運行 epsilon-engine | 輕節點不做認知分析 |
| light_node 上運行 autopoiesis | 輕節點不做自我演化 |
| Phase 7 aevum-agi 在 AWS 上編譯 | genesis_node feature 永遠不在 AWS 上出現 |
| 在修復記憶體穩態前部署新節點 | 四個膨脹的節點比一個更難排查 |
| curl \| bash 部署方式 | §9 黑名單：違反零信任原則 |
