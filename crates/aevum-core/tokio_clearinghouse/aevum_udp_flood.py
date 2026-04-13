import socket
import json
import time
import hashlib
import random
import string
import threading
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# 物理常數與目標座標 (AWS 東京 Tailscale 座標)
# ==============================================================================
TARGET_IP = "100.116.253.50"  
TARGET_PORT = 8888
DIFFICULTY = 2                # 測試難度：2 個前導零 (00)
MAGAZINE_SIZE = 5000          # 彈匣容量：5000 發實體封包
CONCURRENCY = 100             # 齊射管線：100 條執行緒同時開火

SENDER_ID = "GENESIS_ACCOUNT"
RECEIVER_ID = "MINER_EDGE_01"
TRANSFER_AMOUNT = 1

def generate_entropy(length=16):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def mine_payload():
    """鍛造單發子彈：計算 PoW 並打包轉帳 JSON"""
    entropy = generate_entropy()
    nonce = 0
    prefix = '0' * DIFFICULTY
    while True:
        text = f"{entropy}{nonce}"
        hash_result = hashlib.sha256(text.encode('utf-8')).hexdigest()
        if hash_result.startswith(prefix):
            payload = {
                "sender": SENDER_ID,
                "receiver": RECEIVER_ID,
                "amount": TRANSFER_AMOUNT,
                "entropy": entropy,
                "nonce": nonce,
                "hash": hash_result,
                "timestamp": time.time()
            }
            return json.dumps(payload).encode('utf-8')
        nonce += 1

def fire_udp_burst(payloads, batch_id):
    """打開閥門：單一執行緒以極限速度將陣列內的 UDP 封包打出"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
    for packet in payloads:
        sock.sendto(packet, (TARGET_IP, TARGET_PORT))
    sock.close()

def execute_flood_strike():
    print(f"🌌 [階段一] 啟動彈匣預填裝... 目標容量: {MAGAZINE_SIZE} 發")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=12) as miner_pool:
        results = miner_pool.map(lambda _: mine_payload(), range(MAGAZINE_SIZE))
        magazine = list(results)
        
    print(f"[+] 彈匣填裝完畢！耗時: {time.time() - start_time:.2f}s")
    print(f"🔥 [階段二] 準備解除限制器，進行 UDP 齊射...")
    time.sleep(2) 
    
    batch_size = MAGAZINE_SIZE // CONCURRENCY
    batches = [magazine[i:i + batch_size] for i in range(0, MAGAZINE_SIZE, batch_size)]
    
    print(f"🚀 [開火] {CONCURRENCY} 條管線同時向 {TARGET_IP}:{TARGET_PORT} 傾瀉火力！")
    strike_start = time.time()
    
    threads = []
    for i, batch in enumerate(batches):
        t = threading.Thread(target=fire_udp_burst, args=(batch, i))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    strike_end = time.time()
    print(f"🏁 [打擊結束] {MAGAZINE_SIZE} 發 UDP 封包已在 {strike_end - strike_start:.4f} 秒內全數發射！")
    try:
        tps = MAGAZINE_SIZE / (strike_end - strike_start)
        print(f"⚡ 瞬間吞吐率: {tps:.0f} TPS")
    except ZeroDivisionError:
        print(f"⚡ 瞬間吞吐率: 極限溢出 (O(1) 瞬發)")

if __name__ == "__main__":
    execute_flood_strike()
