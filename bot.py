import os
import time
import json
import requests
import threading
from flask import Flask
from web3 import Web3
from web3.middleware import geth_poa_middleware

# --- SETTINGAN ENVIRONMENT ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WATCHED_WALLET = os.getenv("WATCHED_WALLET")

# --- DAFTAR RPC (Cadangan Otomatis) ---
RPC_LIST = [
    "https://rpc.ankr.com/bsc",             # Opsi 1
    "https://bsc-dataseed.binance.org/",    # Opsi 2
    "https://bsc-dataseed1.binance.org/",   # Opsi 3
    "https://1rpc.io/bnb",                  # Opsi 4
    "https://bscrpc.com"                    # Opsi 5
]

# --- SERVER PALSU (Supaya Render Gak Tidur) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Auto-RPC is Alive!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- FUNGSI PENCARI RPC ---
def connect_to_best_rpc():
    """Mencoba connect ke RPC satu per satu sampai berhasil"""
    for rpc_url in RPC_LIST:
        try:
            print(f"🔄 Mencoba connect ke: {rpc_url} ...")
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 5}))
            
            if w3.is_connected():
                # Wajib inject middleware untuk BSC
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                print(f"✅ Terhubung ke: {rpc_url}")
                return w3, rpc_url
        except Exception as e:
            print(f"❌ Gagal ke {rpc_url}: {e}")
            continue
    
    print("⚠️ SEMUA RPC MATI! Bot akan mencoba lagi nanti.")
    return None, None

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=10)
    except:
        pass

# --- LOGIKA UTAMA BOT ---
def start_bot():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: Token Environment belum diisi!")
        return

    # Inisialisasi awal
    w3, active_rpc = connect_to_best_rpc()
    if not w3: return # Stop jika tidak ada internet

    USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
    ERC20_ABI = json.loads('[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]')
    
    contract = w3.eth.contract(address=USDT_CONTRACT, abi=ERC20_ABI)
    target_address = w3.to_checksum_address(WATCHED_WALLET)

    send_telegram(f"🤖 <b>Bot V5 (Auto-RPC) Siap!</b>\nConnected: {active_rpc}\nLimit: > 0.001 USDT")

    # Ambil blok terakhir saat ini
    try:
        last_block = w3.eth.block_number
    except:
        last_block = 0 # Fallback jika gagal ambil blok awal

    print(f"🚀 Mulai scan dari blok {last_block}")

    while True:
        try:
            # Cek koneksi dulu, kalau putus cari RPC baru
            if not w3.is_connected():
                raise Exception("Koneksi RPC Terputus")

            current_block = w3.eth.block_number

            if current_block > last_block:
                # Jaga-jaga biar gak scan terlalu jauh (max 20 blok ke belakang)
                from_block = max(last_block + 1, current_block - 20)
                
                try:
                    logs = contract.events.Transfer.get_logs(
                        fromBlock=from_block,
                        toBlock=current_block,
                        argument_filters={'to': target_address}
                    )

                    for event in logs:
                        tx_hash = event['transactionHash'].hex()
                        amount_raw = event['args']['value']
                        amount_usdt = amount_raw / 10**18
                        
                        # --- PERBAIKAN FILTER (0.001 USDT) ---
                        if amount_usdt >= 0.001: 
                            print(f"💰 DETEKSI: {amount_usdt} USDT")
                            msg = (
                                f"🚨 <b>USDT MASUK!</b>\n"
                                f"💵 {amount_usdt:,.4f} USDT\n"
                                f"🔗 <a href='https://bscscan.com/tx/{tx_hash}'>BscScan Link</a>"
                            )
                            send_telegram(msg)
                
                except Exception as log_error:
                    print(f"⚠️ Error baca log (mungkin RPC limit): {log_error}")
                    # Jangan update last_block biar discan ulang nanti
                    time.sleep(2)
                    continue 

                last_block = current_block
            
            time.sleep(4) # Jeda aman

        except Exception as e:
            print(f"⚠️ Masalah Koneksi: {e}")
            print("🔄 Mencari RPC baru...")
            w3, active_rpc = connect_to_best_rpc()
            if w3:
                contract = w3.eth.contract(address=USDT_CONTRACT, abi=ERC20_ABI)
            time.sleep(5)

if __name__ == "__main__":
    # Jalankan Server Palsu
    t = threading.Thread(target=run_web_server)
    t.start()
    
    # Jalankan Bot
    start_bot()
