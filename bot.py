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

# --- BAGIAN SERVER PALSU (Supaya jalan di Render) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Alive!", 200

def run_web_server():
    # Render butuh port environment variable, default 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- BAGIAN BOT ---
def start_bot():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Token belum diisi di Environment Variables")
        return

    BSC_RPC_URL = "https://rpc.ankr.com/bsc"
    USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
    
    w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    
    # ABI Ringkas
    ERC20_ABI = json.loads('[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]')
    contract = w3.eth.contract(address=USDT_CONTRACT, abi=ERC20_ABI)
    target_address = w3.to_checksum_address(WATCHED_WALLET)
    
    # Kirim notif saat start
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": "🤖 Bot Render Siap!"})

    last_block = w3.eth.block_number
    print(f"Mulai dari blok {last_block}")

    while True:
        try:
            current_block = w3.eth.block_number
            if current_block > last_block:
                try:
                    logs = contract.events.Transfer.get_logs(
                        fromBlock=last_block + 1,
                        toBlock=current_block,
                        argument_filters={'to': target_address}
                    )
                    
                    for event in logs:
                        tx = event['transactionHash'].hex()
                        amt = event['args']['value'] / 10**18
                        
                        if amt >= 0.1: # Filter nominal
                            msg = f"🚨 USDT MASUK!\n💵 {amt:,.2f} USDT\n🔗 {tx}"
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                                          json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
                except Exception as e:
                    print(f"Error scan: {e}")
                
                last_block = current_block
            time.sleep(4)
        except:
            time.sleep(10)

if __name__ == "__main__":
    # Jalankan Server Palsu di Thread terpisah
    t = threading.Thread(target=run_web_server)
    t.start()
    
    # Jalankan Bot Utama
    start_bot()
