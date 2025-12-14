import time
import requests
import json

# --- DATA ANDA (SUDAH DIISI) ---
TELEGRAM_BOT_TOKEN = "8474734004:AAHau41lj-xJDo2Ea33WyUUjrca4wUc3LyI"
TELEGRAM_CHAT_ID = "-1001990758935"
WATCHED_WALLET = "0xf7aCd69A02FcCe2a3962c78cc2733500D086c1a0"

# --- KONFIGURASI BSC ---
# Kita pakai RPC Ankr biar stabil
RPC_URL = "https://rpc.ankr.com/bsc"
USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"

# Topik Event Transfer (Keccak256 dari "Transfer(address,address,uint256)")
TOPIC_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

def get_block_number():
    """Ambil nomor blok terbaru"""
    payload = {"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}
    try:
        res = requests.post(RPC_URL, json=payload, timeout=5)
        return int(res.json()['result'], 16)
    except:
        return None

def get_logs(from_block, to_block):
    """Cek apakah ada transaksi USDT masuk"""
    # Format alamat wallet kita jadi format 'Topic' (padding 0 sampai 64 karakter)
    wallet_clean = WATCHED_WALLET.lower().replace("0x", "")
    topic_address = "0x" + "0" * 24 + wallet_clean
    
    params = [{
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
        "address": USDT_CONTRACT,
        "topics": [
            TOPIC_TRANSFER, # Event Transfer
            None,           # From (Siapa saja)
            topic_address   # To (Wallet Kita)
        ]
    }]
    
    payload = {"jsonrpc":"2.0","method":"eth_getLogs","params":params,"id":1}
    
    try:
        res = requests.post(RPC_URL, json=payload, timeout=10)
        data = res.json()
        if 'result' in data:
            return data['result']
    except Exception as e:
        print(f"Error Log: {e}")
    return []

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload)
    except:
        pass

def main():
    print(f"🚀 Bot Termux Berjalan!")
    print(f"👀 Memantau: {WATCHED_WALLET}")
    send_telegram(f"📱 <b>Bot Termux Online!</b>\nWallet: {WATCHED_WALLET}")
    
    last_block = get_block_number()
    if not last_block:
        print("Gagal koneksi awal. Cek internet.")
        return

    print(f"⏳ Mulai dari blok: {last_block}")

    while True:
        try:
            current_block = get_block_number()
            
            if current_block and current_block > last_block:
                # Cek logs
                logs = get_logs(last_block + 1, current_block)
                
                for log in logs:
                    tx_hash = log['transactionHash']
                    # Konversi Hex Amount ke Decimal
                    amount_hex = log['data']
                    amount_float = int(amount_hex, 16) / 10**18
                    
                    if amount_float > 0.1: # Minimal 0.1 USDT
                        print(f"💰 DAPAT: {amount_float} USDT | {tx_hash}")
                        msg = (
                            f"🚨 <b>USDT MASUK!</b>\n\n"
                            f"💵 <b>Jumlah:</b> {amount_float:,.2f} USDT\n"
                            f"🔗 <b>Tx Hash:</b> <code>{tx_hash}</code>\n\n"
                            f"<a href='https://bscscan.com/tx/{tx_hash}'>BscScan</a>"
                        )
                        send_telegram(msg)
                
                last_block = current_block
                print(f"✅ Blok {current_block} Aman...")
            
            # Istirahat 5 detik
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\nBot berhenti.")
            break
        except Exception as e:
            print(f"Error loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()