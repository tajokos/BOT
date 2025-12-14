import os
import time
import json
import requests
import threading
from flask import Flask
from web3 import Web3
from web3.middleware import geth_poa_middleware

# --- SETTINGAN ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WATCHED_WALLET = os.getenv("WATCHED_WALLET")
USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# --- SERVER PALSU (Syarat Render) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Hash Only is Alive", 200
def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- FUNGSI KIRIM TELEGRAM (CUMA HASH) ---
def send_hash_only(tx_hash):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        # Kirim text biasa, isinya cuma tx_hash
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": tx_hash}
        requests.post(url, json=data, timeout=5)
    except:
        pass

# --- LOGIKA UTAMA ---
def main_loop():
    # Koneksi RPC (Auto-switch sederhana)
    rpc_urls = ["https://rpc.ankr.com/bsc", "https://bsc-dataseed.binance.org/"]
    w3 = None
    
    for url in rpc_urls:
        try:
            temp_w3 = Web3(Web3.HTTPProvider(url))
            if temp_w3.is_connected():
                temp_w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                w3 = temp_w3
                break
        except: continue
    
    if not w3: return # Stop jika tidak ada koneksi

    # Siapkan filter wallet
    clean_wallet = WATCHED_WALLET.lower().replace("0x", "")
    my_topic = "0x000000000000000000000000" + clean_wallet

    # Kirim tanda bot nyala (Opsional, biar tau aja bot gak mati)
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": "BOT STARTED"})
    except: pass

    # Scan mulai dari 50 blok ke belakang (jaga-jaga ada yg kelewat pas restart)
    last_block = w3.eth.block_number - 50
    processed = set()

    while True:
        try:
            current_block = w3.eth.block_number
            
            if current_block > last_block:
                # Ambil Logs
                logs = w3.eth.get_logs({
                    'fromBlock': last_block + 1,
                    'toBlock': current_block,
                    'address': USDT_CONTRACT,
                    'topics': [TRANSFER_TOPIC, None, my_topic]
                })

                for log in logs:
                    tx_hash = log['transactionHash'].hex()
                    
                    if tx_hash in processed: continue
                    processed.add(tx_hash)

                    # Ambil amount cuma buat filter spam (biar debu 0.00001 gak menuhin grup)
                    # Kalau mau SEMUA masuk, hapus if ini.
                    raw_amount = int(log['data'], 16)
                    amount = raw_amount / 10**18

                    if amount >= 0.001: 
                        # INI YANG KAMU MAU: KIRIM HASH SAJA
                        send_hash_only(tx_hash)

                last_block = current_block
                # Bersihkan memori cache
                if len(processed) > 500: processed.clear()

            time.sleep(3)

        except Exception:
            time.sleep(5) # Kalau error, diem dulu 5 detik terus lanjut

if __name__ == "__main__":
    t = threading.Thread(target=run_web_server)
    t.start()
    main_loop()

