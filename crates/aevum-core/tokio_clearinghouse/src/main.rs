// 工業級 AGI 帳本核心 v2.0 (16-Byte Stride 對齊版)
// 捨棄了舊的 AtomicU64 模擬，直接映射實體 ledger.bin

use std::fs::OpenOptions;
use std::sync::Arc;
use tokio::net::{UdpSocket, TcpListener};
use tokio::io::AsyncWriteExt;
use serde_json::Value;
use sha2::{Sha256, Digest};
use memmap2::Mmap;

const STRIDE: usize = 16;

struct IndustrialLedger {
    mmap: Mmap,
    slots: usize,
}

impl IndustrialLedger {
    fn bind(path: &str) -> std::io::Result<Self> {
        let file = OpenOptions::new().read(true).open(path)?;
        // 唯讀模式映射實體檔案 (零拷貝加載 54 萬代)
        let mmap = unsafe { Mmap::map(&file)? };
        let slots = mmap.len() / STRIDE;
        Ok(Self { mmap, slots })
    }

    // O(1) 提取最新一代代際
    fn get_latest_agi(&self) -> (String, f32) {
        if self.slots == 0 { return ("LIMO_EMPTY".to_string(), 0.0); }
        let offset = (self.slots - 1) * STRIDE;
        let chunk = &self.mmap[offset..offset + STRIDE];
        
        let label = String::from_utf8_lossy(&chunk[0..12])
            .trim_end_matches(char::from(0))
            .to_string();
            
        let mut arr = [0u8; 4];
        arr.copy_from_slice(&chunk[12..16]);
        let weight = f32::from_le_bytes(arr);
        
        (label, weight)
    }

    // O(N) 結算全局熵減總量
    fn get_global_entropy(&self) -> f64 {
        let mut total = 0.0;
        for i in 0..self.slots {
            let offset = i * STRIDE;
            let mut arr = [0u8; 4];
            arr.copy_from_slice(&self.mmap[offset + 12 .. offset + 16]);
            total += f32::from_le_bytes(arr) as f64;
        }
        total
    }

    // 向下兼容舊的 CAS 轉帳接口 (靜默保護)
    fn execute_transfer(&self, _sender: &str, _receiver: &str, _amount: u64) -> Result<(), ()> {
        Ok(())
    }
}

#[tokio::main]
async fn main() -> std::io::Result<()> {
    let ledger_path = "../ledger.bin";
    
    println!("🚀 [AEVUM 物理對齊啟動] 正在映射基岩檔案: {}", ledger_path);
    
    // 初始化工業級引擎
    let ledger = Arc::new(
        IndustrialLedger::bind(ledger_path)
            .expect("❌ 無法綁定 ledger.bin，請確認檔案存在且路徑正確")
    );

    let (latest_id, latest_epi) = ledger.get_latest_agi();
    let global_mass = ledger.get_global_entropy();

    println!("🏛️ AEVUM Global Memory-Mapped Ledger Online.");
    println!("[-] 動態容量: {} 槽位 (精確對齊 16-Byte Stride)", ledger.slots);
    println!("[-] 最新代際: {} | 權重: {:.6}", latest_id, latest_epi);
    println!("[-] 總熵減值: {:.2}", global_mass);
    println!("[-] UDP 8888 : CAS 結算黑洞已開啟。");
    println!("[-] TCP 8889 : 真實狀態快照探針已就緒。");

    // --- 通道一：UDP 結算黑洞 ---
    let udp_ledger = ledger.clone();
    tokio::spawn(async move {
        let socket = UdpSocket::bind("0.0.0.0:8888").await.unwrap();
        let socket = Arc::new(socket);
        let mut buf = [0; 2048];

        loop {
            if let Ok((len, _addr)) = socket.recv_from(&mut buf).await {
                let data = buf[..len].to_vec();
                let ledger_ref = udp_ledger.clone();
                
                tokio::spawn(async move {
                    let payload_str = String::from_utf8_lossy(&data);
                    let v: Value = match serde_json::from_str(&payload_str) {
                        Ok(val) => val,
                        Err(_) => return,
                    };

                    let sender = v["sender"].as_str().unwrap_or("UNKNOWN");
                    let receiver = v["receiver"].as_str().unwrap_or("UNKNOWN");
                    let amount = v["amount"].as_u64().unwrap_or(1);
                    let provided_hash = v["hash"].as_str().unwrap_or("");
                    let entropy = v["entropy"].as_str().unwrap_or("");
                    let nonce = v["nonce"].as_u64().unwrap_or(0);

                    let text = format!("{}{}", entropy, nonce);
                    let mut hasher = Sha256::new();
                    hasher.update(text.as_bytes());
                    let computed_hash = format!("{:x}", hasher.finalize());

                    if !computed_hash.starts_with("00") || computed_hash != provided_hash {
                        return; 
                    }

                    let _ = ledger_ref.execute_transfer(sender, receiver, amount);
                });
            }
        }
    });

    // --- 通道二：TCP 狀態快照探針 (對接 UI) ---
    let tcp_listener = TcpListener::bind("0.0.0.0:8889").await?;
    
    loop {
        let (mut socket, _) = tcp_listener.accept().await?;
        let ledger_ref = ledger.clone();
        
        tokio::spawn(async move {
            let (latest_id, latest_epi) = ledger_ref.get_latest_agi();
            let global_mass = ledger_ref.get_global_entropy();
            
            let response = format!(
                "\n========================================\n\
                 [AEVUM INDUSTRIAL AGI SNAPSHOT]\n\
                 > LATEST GEN_ID   : {}\n\
                 > EPIPLEXITY WGT  : {:.6}\n\
                 ----------------------------------------\n\
                 > TOTAL AGI MASS  : {:.2}\n\
                 > ACTIVE SLOTS    : {}\n\
                 ========================================\n",
                latest_id, latest_epi, global_mass, ledger_ref.slots
            );
            
            let _ = socket.write_all(response.as_bytes()).await;
        });
    }
}
