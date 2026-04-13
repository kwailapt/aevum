import socket
import struct
import mmap
import os

UDP_IP = "0.0.0.0"
UDP_PORT = 8888
LEDGER_PATH = "/home/ec2-user/aevum-tokyo/ledger.bin"
LEDGER_SIZE = 1000 * 8

# 如果帳本不存在，憑空創世並給予初始算力
if not os.path.exists(LEDGER_PATH):
    with open(LEDGER_PATH, "wb") as f:
        f.write(b'\x00' * LEDGER_SIZE)
    with open(LEDGER_PATH, "r+b") as f:
        f.seek(0)
        f.write(struct.pack("<Q", 1000)) # 賦予 Node 0 初始 1000 點 Quanta

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
print("Aevum Dark Star Ledger listening on UDP 8888...")

while True:
    try:
        data, addr = sock.recvfrom(1024)
        if len(data) == 10:
            node_id, cost = struct.unpack("<QH", data)
            with open(LEDGER_PATH, "r+b") as f:
                mm = mmap.mmap(f.fileno(), 0)
                offset = node_id * 8
                
                if offset + 8 <= LEDGER_SIZE:
                    current_balance = struct.unpack("<Q", mm[offset:offset+8])[0]
                    
                    # 執行扣款物理法則
                    if current_balance >= cost:
                        new_balance = current_balance - cost
                        mm[offset:offset+8] = struct.pack("<Q", new_balance)
                    else:
                        new_balance = 18446744073709551615 # 餘額不足的虛空代碼
                    
                    mm.flush()
                    # 將新餘額射回香港前哨站
                    sock.sendto(struct.pack("<Q", new_balance), addr)
    except Exception as e:
        pass
