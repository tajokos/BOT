const axios = require('axios');
const express = require('express');

// --- SETTINGAN ENVIRONMENT (Diambil dari Render) ---
const TELEGRAM_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const CHAT_ID = process.env.TELEGRAM_CHAT_ID;
const WATCHED_WALLET = process.env.WATCHED_WALLET;

// --- CONFIG SAMA PERSIS V4 ---
const USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955";
const TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";

// Daftar RPC (Sama kayak V4)
const RPC_LIST = [
    "https://bsc-dataseed1.binance.org/",
    "https://bsc-dataseed.binance.org/",
    "https://rpc.ankr.com/bsc",
    "https://1rpc.io/bnb",
    "https://bscrpc.com"
];

// --- SERVER PALSU (BIAR RENDER GAK MATI) ---
const app = express();
const PORT = process.env.PORT || 10000;
app.get('/', (req, res) => res.send('Bot V4 Server is Alive!'));
app.listen(PORT, () => console.log(`Server listening on port ${PORT}`));

// --- VARIABLES ---
let activeRpc = "";
let lastCheckedBlock = 0;
let processedHashes = new Set();

// --- FUNGSI 1: CARI RPC YANG HIDUP (SAMA KAYAK V4) ---
async function findWorkingRPC() {
    console.log("🔍 Mencari RPC aktif...");
    for (const url of RPC_LIST) {
        try {
            // Test ping block number
            await axios.post(url, {
                jsonrpc: "2.0", id: 1, method: "eth_blockNumber", params: []
            }, { timeout: 5000 });
            
            console.log(`✅ Terhubung ke: ${url}`);
            activeRpc = url;
            return true;
        } catch (e) {
            continue;
        }
    }
    console.log("❌ Semua RPC Sibuk/Mati");
    return false;
}

// --- FUNGSI 2: REQUEST MENTAH (SAMA KAYAK V4) ---
async function rpcCall(method, params = []) {
    if (!activeRpc) await findWorkingRPC();
    
    try {
        const response = await axios.post(activeRpc, {
            jsonrpc: "2.0", id: Date.now(), method: method, params: params
        }, { timeout: 10000 });

        if (response.data.error) throw new Error(response.data.error.message);
        return response.data.result;
    } catch (error) {
        console.log(`⚠️ RPC Error: ${error.message}`);
        activeRpc = ""; // Reset biar cari baru
        return null;
    }
}

// --- FUNGSI 3: KIRIM TELEGRAM (CUMA HASH) ---
async function sendTelegram(txHash) {
    if(!TELEGRAM_TOKEN) return;
    try {
        const url = `https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage`;
        await axios.post(url, {
            chat_id: CHAT_ID,
            text: txHash // <--- CUMA HASH DOANG
        });
    } catch (e) {
        console.log("Gagal kirim TG");
    }
}

// --- LOGIKA UTAMA (LOOPING) ---
async function startMonitoring() {
    // Validasi
    if (!WATCHED_WALLET) {
        console.log("❌ Error: Environment Variables belum diisi!");
        return;
    }

    // Cari RPC dulu
    await findWorkingRPC();

    // Siapkan Topic Wallet (Padding 0 di depan sampai 64 karakter)
    const cleanWallet = WATCHED_WALLET.toLowerCase().replace("0x", "");
    const topicTo = "0x" + cleanWallet.padStart(64, '0');

    // Ambil Block Awal
    const blockHex = await rpcCall("eth_blockNumber");
    if (blockHex) {
        lastCheckedBlock = parseInt(blockHex, 16);
        console.log(`🚀 Mulai V4 Server dari blok: ${lastCheckedBlock}`);
        sendTelegram(`BOT V4 SERVER STARTED`);
    }

    // Loop interval 4 detik (Sama kayak V4 setInterval)
    setInterval(async () => {
        if (!activeRpc) {
            await findWorkingRPC();
            return;
        }

        const currentBlockHex = await rpcCall("eth_blockNumber");
        if (!currentBlockHex) return;

        const currentBlock = parseInt(currentBlockHex, 16);

        if (currentBlock > lastCheckedBlock) {
            // Scan Range (Max 5 blok biar aman dari limit)
            let fromBlock = lastCheckedBlock + 1;
            // Kalau ketinggalan jauh, ambil 5 terakhir aja
            if (currentBlock - fromBlock > 5) fromBlock = currentBlock - 5;

            const fromBlockHex = "0x" + fromBlock.toString(16);
            const toBlockHex = "0x" + currentBlock.toString(16);

            // console.log(`Scan: ${fromBlock} -> ${currentBlock}`);

            const logs = await rpcCall("eth_getLogs", [{
                fromBlock: fromBlockHex,
                toBlock: toBlockHex,
                address: USDT_CONTRACT,
                topics: [TRANSFER_TOPIC, null, topicTo]
            }]);

            if (logs && logs.length > 0) {
                for (const log of logs) {
                    const txHash = log.transactionHash;
                    
                    if (processedHashes.has(txHash)) continue;
                    processedHashes.add(txHash);

                    // Ambil Amount (Hex ke Decimal)
                    const amountHex = log.data;
                    const amount = parseInt(amountHex, 16) / 10**18;

                    // Filter 0.001 (Biar receh kebaca buat test)
                    if (amount >= 0.001) {
                        console.log(`💰 DETEKSI: ${amount} USDT`);
                        // KIRIM HASH SAJA
                        sendTelegram(txHash);
                    }
                }
                
                // Bersihkan cache biar memori gak penuh
                if (processedHashes.size > 1000) processedHashes.clear();
            }

            lastCheckedBlock = currentBlock;
        }
    }, 4000); // 4 Detik
}

startMonitoring();
