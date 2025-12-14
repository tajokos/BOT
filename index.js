const axios = require('axios');
const express = require('express');

// --- SETTINGAN ENVIRONMENT ---
// Pastikan Variables di Render sudah diisi: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WATCHED_WALLET
const TELEGRAM_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const CHAT_ID = process.env.TELEGRAM_CHAT_ID;
const WATCHED_WALLET = process.env.WATCHED_WALLET;

const USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955";
const TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";

// DAFTAR RPC (LlamaRPC prioritas pertama sesuai request)
const RPC_LIST = [
    "https://binance.llamarpc.com", 
    "https://bsc-dataseed1.binance.org",
    "https://bsc-dataseed.binance.org",
    "https://rpc.ankr.com/bsc"
];

// --- SERVER PALSU (Supaya Render Gak Tidur) ---
const app = express();
const PORT = process.env.PORT || 10000;
app.get('/', (req, res) => res.send('Bot V4 JS is Alive!'));
app.listen(PORT, () => console.log(`Server listening on port ${PORT}`));

// --- VARIABLES ---
let activeRpc = "";
let lastCheckedBlock = 0;
let processedHashes = new Set();

// --- FUNGSI CARI RPC ---
async function findWorkingRPC() {
    console.log("🔍 Mencari RPC aktif...");
    for (const url of RPC_LIST) {
        try {
            await axios.post(url, {
                jsonrpc: "2.0", id: 1, method: "eth_blockNumber", params: []
            }, { timeout: 5000 });
            
            console.log(`✅ Terhubung ke: ${url}`);
            activeRpc = url;
            return true;
        } catch (e) {
            console.log(`❌ Gagal: ${url}`);
        }
    }
    return false;
}

// --- FUNGSI REQUEST MENTAH (Sama persis V4 HTML) ---
async function rpcCall(method, params = []) {
    if (!activeRpc) await findWorkingRPC();
    
    try {
        const response = await axios.post(activeRpc, {
            jsonrpc: "2.0", id: Date.now(), method: method, params: params
        }, { timeout: 10000 });

        if (response.data.error) throw new Error(response.data.error.message);
        return response.data.result;
    } catch (error) {
        console.log(`⚠️ RPC Error (${activeRpc}): ${error.message}`);
        activeRpc = ""; // Reset biar cari baru
        return null;
    }
}

// --- FUNGSI KIRIM TELEGRAM (Cuma Hash) ---
async function sendTelegram(text) {
    if(!TELEGRAM_TOKEN) return;
    try {
        await axios.post(`https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage`, {
            chat_id: CHAT_ID,
            text: text
        });
    } catch (e) {
        console.log("Gagal kirim TG");
    }
}

// --- LOGIKA UTAMA ---
async function startMonitoring() {
    if (!WATCHED_WALLET) return console.log("❌ Variable Environment Belum Diisi!");

    // 1. Cari RPC
    await findWorkingRPC();

    // 2. Format Topic Wallet (Padding 0)
    const cleanWallet = WATCHED_WALLET.toLowerCase().replace("0x", "");
    const topicTo = "0x" + cleanWallet.padStart(64, '0');

    // 3. Ambil Blok Awal
    const blockHex = await rpcCall("eth_blockNumber");
    if (blockHex) {
        lastCheckedBlock = parseInt(blockHex, 16);
        console.log(`🚀 Mulai dari blok: ${lastCheckedBlock}`);
        sendTelegram("BOT JS STARTED - LLAMARPC");
    }

    // 4. Looping (Setiap 3 detik)
    setInterval(async () => {
        if (!activeRpc) { await findWorkingRPC(); return; }

        const currentBlockHex = await rpcCall("eth_blockNumber");
        if (!currentBlockHex) return;

        const currentBlock = parseInt(currentBlockHex, 16);

        if (currentBlock > lastCheckedBlock) {
            // Scan Max 5 Blok (Biar gak kena limit limit club)
            let fromBlock = lastCheckedBlock + 1;
            if (currentBlock - fromBlock > 5) fromBlock = currentBlock - 5;

            const fromBlockHex = "0x" + fromBlock.toString(16);
            const toBlockHex = "0x" + currentBlock.toString(16);

            // Ambil Logs
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

                    // Filter Nominal (0.001)
                    const amount = parseInt(log.data, 16) / 10**18;
                    
                    if (amount >= 0.001) {
                        console.log(`💰 DETEKSI: ${amount} USDT`);
                        sendTelegram(txHash); // <--- KIRIM HASH SAJA
                    }
                }
                if (processedHashes.size > 500) processedHashes.clear();
            }
            lastCheckedBlock = currentBlock;
        }
    }, 3000);
}

startMonitoring();
