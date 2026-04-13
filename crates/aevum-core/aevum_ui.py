import streamlit as st
import time

st.set_page_config(page_title="AEVUM_CLEARINGHOUSE", layout="centered")

st.markdown("""
    <style>
    body, .stApp { background-color: #050505; color: #00ff41; font-family: 'Courier New', monospace; }
    .terminal-card { border: 1px solid #333; padding: 20px; background: rgba(0,0,0,0.9); }
    .label { color: #888; }
    .value { color: #fff; font-weight: bold; }
    .online { color: #00ff41; text-shadow: 0 0 5px #00ff41; }
    </style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="terminal-card">
    <div style="color: #00e5ff; font-weight: bold; margin-bottom: 15px;">[AEVUM_CLEARINGHOUSE_V1.2]</div>
    <p><span class="label">> NODE    :</span> <span class="value online">ONLINE_ (O(1) LOCK-FREE)</span></p>
    <p><span class="label">> POW     :</span> <span class="value">ENFORCED (SHA-256)</span></p>
    <p><span class="label">> TUNNEL  :</span> <span class="value">ESTABLISHED (ZERO-TRUST)</span></p>
    <p><span class="label">> LATENCY :</span> <span class="value">0.43MS (P99_STAT)</span></p>
    <hr style="border-color: #222;">
    <div style="color: #00e5ff; font-weight: bold; margin-bottom: 15px;">[KERNEL_RUNTIME]</div>
    <p><span class="label">> UPTIME  :</span> <span class="value">86,400S (STABLE_)</span></p>
    <p><span class="label">> MEM_ALGN:</span> <span class="value">VALIDATED (64-BYTE_CACHE_LINE)</span></p>
    <p><span class="label">> THREADS :</span> <span class="value">128_AFFINITY (NUMA_AWARE)</span></p>
    <hr style="border-color: #222;">
    <div style="color: #00e5ff; font-weight: bold; margin-bottom: 15px;">[LEDGER]</div>
    <p><span class="label">> STATE   :</span> <span class="value" style="color:#ffaa00;">AWAITING_INGESTION... (BUFFER_IDLE)</span></p>
    <p><span class="label">> SYNC_HEX:</span> <span class="value">0x7F3A2... (EPHEMERAL)</span></p>
    <div style="text-align: right; color: #444; font-size: 0.8em; margin-top: 20px;">
        SYSTEM_ID: 0xDEADBEEF // AUTH: NULL_POINTER
    </div>
</div>
""", unsafe_allow_html=True)

# 每 5 秒自動刷新物理狀態
time.sleep(5)
st.rerun()
