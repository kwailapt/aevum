use memmap2::MmapMut;
use std::fs::OpenOptions;
use std::io::Write;
use std::net::UdpSocket;
use std::os::unix::net::UnixDatagram;
use std::slice;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const UDP_ADDR: &str = "0.0.0.0:8888";
const LEDGER_PATH: &str = "/home/ec2-user/aevum-tokyo/ledger.bin";
const AUDIT_PATH: &str = "/home/ec2-user/aevum-tokyo/ledger_audit.jsonl";
const MAX_NODES: usize = 1000;
const LEDGER_SIZE: usize = MAX_NODES * 8;
const INSUFFICIENT_FUNDS: u64 = u64::MAX;
const MAX_RPS: u32 = 5000; 

fn notify_systemd(msg: &str) {
    if let Ok(sock_path) = std::env::var("NOTIFY_SOCKET") {
        if let Ok(sock) = UnixDatagram::unbound() {
            let _ = sock.send_to(msg.as_bytes(), sock_path);
        }
    }
}

fn main() -> std::io::Result<()> {
    let mut file = OpenOptions::new().read(true).write(true).create(true).open(LEDGER_PATH)?;
    if file.metadata()?.len() < LEDGER_SIZE as u64 { file.set_len(LEDGER_SIZE as u64)?; }
    
    let mut mmap = unsafe { MmapMut::map_mut(&file)? };
    let atomic_ledger: &[AtomicU64] = unsafe {
        slice::from_raw_parts(mmap.as_mut_ptr() as *const AtomicU64, MAX_NODES)
    };

    let (log_tx, log_rx) = mpsc::channel::<String>();
    thread::spawn(move || {
        if let Ok(mut log_file) = OpenOptions::new().create(true).append(true).open(AUDIT_PATH) {
            for log_msg in log_rx { let _ = log_file.write_all(log_msg.as_bytes()); }
        }
    });

    let socket = UdpSocket::bind(UDP_ADDR)?;
    socket.set_nonblocking(true)?;

    notify_systemd("READY=1");

    let mut buf = [0u8; 1024];
    let mut tx_count = 0u64;
    let mut loop_counter = 0u32; // 降頻抽樣計數器
    
    let mut rps_counter = 0u32;
    let mut last_second = Instant::now();

    loop {
        loop_counter = loop_counter.wrapping_add(1);
        
        // 【優化】：每 1024 次迴圈才呼叫一次 Instant::now()，消除 Syscall 摩擦
        if loop_counter % 1024 == 0 {
            if last_second.elapsed() >= Duration::from_secs(1) {
                rps_counter = 0;
                last_second = Instant::now();
                notify_systemd("WATCHDOG=1");
            }
        }

        match socket.recv_from(&mut buf) {
            Ok((10, src)) => {
                rps_counter += 1;
                if rps_counter > MAX_RPS { continue; }

                let node_id = u64::from_le_bytes(buf[0..8].try_into().unwrap()) as usize;
                let cost = u16::from_le_bytes(buf[8..10].try_into().unwrap()) as u64;

                if node_id < MAX_NODES {
                    let balance_ref = &atomic_ledger[node_id];
                    let mut current_balance = balance_ref.load(Ordering::Acquire); // ARM64 防禦

                    let final_balance = loop {
                        if current_balance < cost { break INSUFFICIENT_FUNDS; }
                        let new_balance = current_balance - cost;
                        // ARM64 極限防禦：成功 AcqRel，失敗 Acquire
                        match balance_ref.compare_exchange_weak(current_balance, new_balance, Ordering::AcqRel, Ordering::Acquire) {
                            Ok(_) => break new_balance,
                            Err(actual) => current_balance = actual,
                        }
                    };

                    let _ = socket.send_to(&final_balance.to_le_bytes(), src);

                    if final_balance != INSUFFICIENT_FUNDS {
                        let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis();
                        let _ = log_tx.send(format!("{{\"ts\":{},\"node\":{},\"cost\":{},\"bal\":{}}}\n", ts, node_id, cost, final_balance));
                    }

                    tx_count += 1;
                    if tx_count % 100 == 0 { let _ = mmap.flush_async(); } // 使用非同步 Flush 避免 I/O 阻塞
                }
            }
            Ok(_) => {} 
            Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                thread::sleep(Duration::from_micros(100));
            }
            Err(_) => {}
        }
    }
}
