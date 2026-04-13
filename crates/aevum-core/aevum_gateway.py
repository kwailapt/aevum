from flask import Flask, request, jsonify
import struct
import mmap
import os
import time
import json

app = Flask(__name__)
LEDGER_PATH = "/home/ec2-user/aevum-tokyo/ledger.bin"
JOURNAL_PATH = "/home/ec2-user/aevum-tokyo/akashic_genes.jsonl"

def append_journal(node_key, balance):
    # 僅追加 (Append-Only)，極致輕量
    event = {"ts": int(time.time()), "node": node_key, "balance": balance}
    with open(JOURNAL_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")

def get_balance(node_id):
    if not os.path.exists(LEDGER_PATH): return 0
    with open(LEDGER_PATH, "r+b") as f:
        mm = mmap.mmap(f.fileno(), 0)
        offset = node_id * 8
        if offset + 8 <= mm.size():
            return struct.unpack('<Q', mm[offset:offset+8])[0]
    return 0

@app.route('/v1/chat/completions', methods=['POST'])
def chat():
    auth_header = request.headers.get('Authorization', '')
    node_key = auth_header.replace('Bearer ', '').strip().zfill(16)
    node_id = int(node_key)
    
    balance = get_balance(node_id)
    
    # 寫入阿卡西事件流
    append_journal(node_key, balance)
    
    return jsonify({
        "choices": [{"message": {"content": f"Aevum 已處理。節點 {node_key} 餘額: {balance} χ."}}],
        "x_quanta_balance": str(balance)
    })

if __name__ == '__main__':
    app.run(port=8889)
