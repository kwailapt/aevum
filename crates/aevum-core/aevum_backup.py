import boto3
import os
import time

ACCESS_KEY = os.environ["R2_ACCESS_KEY"]
SECRET_KEY = os.environ["R2_SECRET_KEY"]
ENDPOINT_URL = os.environ["R2_ENDPOINT_URL"]
BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "aevum-ledger")

JOURNAL_PATH = "/home/ec2-user/aevum-tokyo/akashic_genes.jsonl"
CHECKPOINT_PATH = "/home/ec2-user/aevum-tokyo/checkpoint.txt"

s3 = boto3.client('s3', endpoint_url=ENDPOINT_URL, aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)

def get_last_offset():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r") as f: return int(f.read().strip())
    return 0

def save_offset(offset):
    with open(CHECKPOINT_PATH, "w") as f: f.write(str(offset))

def sync_incremental():
    if not os.path.exists(JOURNAL_PATH): return
    current_size = os.path.getsize(JOURNAL_PATH)
    last_offset = get_last_offset()

    if current_size > last_offset:
        diff_size = current_size - last_offset
        with open(JOURNAL_PATH, "rb") as f:
            f.seek(last_offset)
            new_data = f.read(diff_size)
            object_key = f"akashic_stream/events_{int(time.time())}.jsonl"
            s3.put_object(Bucket=BUCKET_NAME, Key=object_key, Body=new_data)
        save_offset(current_size)

if __name__ == "__main__":
    while True:
        try:
            sync_incremental()
        except Exception as e:
            pass # 靜默處理網路波動
        time.sleep(60) # 每 60 秒巡檢一次游標
