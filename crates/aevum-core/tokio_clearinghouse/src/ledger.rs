use std::sync::atomic::{AtomicU64, Ordering};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

// 帳本被映射為一個巨大的 AtomicU64 切片
pub struct PhysicalLedger {
    pub memory_mapped_accounts: &'static [AtomicU64],
}

impl PhysicalLedger {
    /// O(1) 空間摺疊：將礦工 ID 坍縮為實體記憶體索引
    #[inline(always)]
    pub fn get_physical_offset(&self, miner_id: &str) -> usize {
        let mut hasher = DefaultHasher::new();
        miner_id.hash(&mut hasher);
        let hash_val = hasher.finish() as usize;
        hash_val % self.memory_mapped_accounts.len()
    }

    /// 無鎖 CAS 轉帳核心 (Absolute Lock-Free Transfer)
    pub fn execute_transfer(&self, from_id: &str, to_id: &str, amount: u64) -> Result<(), &'static str> {
        let from_idx = self.get_physical_offset(from_id);
        let to_idx = self.get_physical_offset(to_id);

        // 禁止自我轉帳的拓撲悖論
        if from_idx == to_idx {
            return Err("Topology Error: Self-transfer prohibited");
        }

        let sender_balance = &self.memory_mapped_accounts[from_idx];
        let receiver_balance = &self.memory_mapped_accounts[to_idx];

        // 1. 發送端 CAS 扣款迴圈 (防超扣、防併發競爭)
        let mut current_balance = sender_balance.load(Ordering::Acquire);
        loop {
            // 熱力學檢測：能量不足，直接斬斷
            if current_balance < amount {
                return Err("Insufficient \\chi-Quanta");
            }

            // Compare-And-Swap: 如果當前餘額未被其他執行緒篡改，則扣除 amount
            match sender_balance.compare_exchange_weak(
                current_balance,
                current_balance - amount,
                Ordering::AcqRel,   // 成功時的屏障：保證寫入可見性
                Ordering::Acquire,  // 失敗時的屏障：重新讀取最新狀態
            ) {
                Ok(_) => break, // 物理扣款成功，跳出迴圈
                Err(updated_balance) => {
                    // 發生併發競爭，更新 current_balance 並重試
                    current_balance = updated_balance;
                }
            }
        }

        // 2. 接收端極速入帳 (無需 CAS 迴圈，硬體層級疊加)
        receiver_balance.fetch_add(amount, Ordering::AcqRel);

        Ok(())
    }

    /// 礦工提交高純度 S_T 成功後的鑄幣邏輯 (Minting)
    pub fn mint_reward(&self, miner_id: &str, reward: u64) {
        let idx = self.get_physical_offset(miner_id);
        self.memory_mapped_accounts[idx].fetch_add(reward, Ordering::AcqRel);
    }
    
    /// 觀測函數：唯讀獲取當前餘額
    pub fn get_balance(&self, miner_id: &str) -> u64 {
        let idx = self.get_physical_offset(miner_id);
        self.memory_mapped_accounts[idx].load(Ordering::Acquire)
    }
}
