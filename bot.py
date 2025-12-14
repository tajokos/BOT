import os
import time
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
# Event Signature untuk "Transfer"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# --- SERVER PALSU (Supaya Render Gak Tidur) ---
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
        # Kirim text biasa, isinya cuma tx_hash. Tanpa HTML, tanpa link.
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": tx_hash}
        requests.post(url, json=data, timeout=5)
    except:
        pass

# --- LOGIKA UTAMA ---
def main_loop():
    # Daftar RPC Stabil
    rpc_urls = [
        "https://bsc-dataseed.binance.org/",
        "https://bsc-dataseed1.binance.org/",
        "https://rpc.ankr.com/bsc"
    ]
    
    w3 = None
    
    # Koneksi Awal
    for url in rpc_urls:
        try:
            temp_w3 = Web3(Web3.HTTPProvider(url))
            if temp_w3.is_connected():
                temp_w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                w3 = temp_w3
                print(f"✅ Terhubung ke: {url}")
                break
        except: continue
    
    if not w3: 
        print("❌ Gagal connect RPC")
        return

    # Siapkan filter wallet (Padding 0 di depan)
    clean_wallet = WATCHED_WALLET.lower().replace("0x", "")
    my_topic = "0x000000000000000000000000" + clean_wallet

    # Kirim tanda bot nyala ke Telegram
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": "BOT STARTED - HASH ONLY"})
    except: pass

    # Mulai dari blok saat ini saja (jangan mundur kejauhan biar gak kena limit error)
    try:
        last_block = w3.eth.block_number
    except:
        last_block = 0

    processed = set()

    while True:
        try:
            current_block = w3.eth.block_number
            
            # Scan hanya jika ada blok baru
            if current_block > last_block:
                
                # REVISI PENTING: Jangan scan lebih dari 5 blok sekaligus biar RPC gak marah
                scan_from = last_block + 1
                scan_to = current_block
                
                # Kalau gap terlalu jauh, potong jadi 5 blok terakhir saja
                if scan_to - scan_from > 5:
                    scan_from = scan_to - 5

                print(f"Scanning blok {scan_from} -> {scan_to}")

                logs = w3.eth.get_logs({
                    'fromBlock': scan_from,
                    'toBlock': scan_to,
                    'address': USDT_CONTRACT,
                    'topics': [TRANSFER_TOPIC, None, my_topic]
                })

                for log in logs:
                    tx_hash = log['transactionHash'].hex()
                    
                    if tx_hash in processed: continue
                    processed.add(tx_hash)

                    # Ambil amount buat filter spam (biar gak menuhin grup sama recehan)
                    # Filter: Minimal 0.001 USDT
                    raw_amount = int(log['data'], 16)
                    amount = raw_amount / 10**18

                    if amount >= 0.001: 
                        print(f"Dapat: {tx_hash}")
                        # INI PERMINTAAN KAMU: KIRIM HASH SAJA
                        send_hash_only(tx_hash)

                last_block = current_block
                
                # Bersihkan cache
                if len(processed) > 500: processed.clear()

            # Jeda 5 detik (Sabar, jangan spam RPC)
            time.sleep(5)

        except Exception as e:
            print(f"Error: {e}")
            # Kalau kena limit, istirahat agak lama (10 detik)
            time.sleep(10)
            # Coba reconnect sederhana kalau object w3 error
            try:
                if not w3.is_connected():
                    w3 = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/"))
                    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            except: pass

if __name__ == "__main__":
    t = threading.Thread(target=run_web_server)
    t.start()
    main_loop()
