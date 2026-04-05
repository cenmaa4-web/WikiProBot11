"use strict";

const { createBot } = require("./bot");

const TOKEN = process.env.TELEGRAM_BOT_TOKEN;
if (!TOKEN) {
  console.error("❌ TELEGRAM_BOT_TOKEN is not set!");
  process.exit(1);
}

console.log("🤖 Starting Telegram Media Bot...");

const bot = createBot(TOKEN);

bot.telegram.getMe()
  .then(me => {
    console.log(`✅ Bot running: @${me.username}`);
    console.log("🎬 Ready to download from: YouTube, Instagram, TikTok, Twitter, Facebook, Pinterest, Snapchat & more!");
  })
  .catch(err => console.error("❌ Failed to connect:", err.message));

bot.launch({ dropPendingUpdates: true });

process.once("SIGINT",  () => { console.log("Stopping..."); bot.stop("SIGINT");  });
process.once("SIGTERM", () => { console.log("Stopping..."); bot.stop("SIGTERM"); });
