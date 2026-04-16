#!/bin/bash

# Aevum 暗星金庫快照守護者 (Cron Snapshot)
BASE_DIR="/home/ec2-user/aevum-tokyo"
SNAP_DIR="$BASE_DIR/snapshots"
TIMESTAMP=$(date +"%Y%m%d_%H%M")

# 1. 執行絕對物理拷貝 (無鎖快照)
cp $BASE_DIR/ledger.bin $SNAP_DIR/ledger_${TIMESTAMP}.bin
cp $BASE_DIR/ledger_audit.jsonl $SNAP_DIR/ledger_audit_${TIMESTAMP}.jsonl

# 2. 歷史淨化：冷酷地抹除超過 48 小時 (2天) 的舊快照，防止硬碟耗盡
find $SNAP_DIR -type f -name "ledger_*.bin" -mtime +2 -delete
find $SNAP_DIR -type f -name "ledger_audit_*.jsonl" -mtime +2 -delete

echo "✅ [Aevum Snapshot] $TIMESTAMP 備份完成並已執行淨化。"
