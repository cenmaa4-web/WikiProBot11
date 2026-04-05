import { createBot } from "./bot";

const TOKEN = process.env.TELEGRAM_BOT_TOKEN;

if (!TOKEN) {
  console.error("❌ خطأ: TELEGRAM_BOT_TOKEN غير محدد في متغيرات البيئة");
  process.exit(1);
}

process.env.YTDLP_PATH = "/home/runner/.local/bin/yt-dlp-wrapper";

console.log("🤖 جاري تشغيل بوت تحميل الوسائط...");

const bot = createBot(TOKEN);

bot.telegram.getMe().then((me) => {
  console.log(`✅ البوت يعمل بنجاح!`);
  console.log(`👤 اسم البوت: @${me.username}`);
  console.log(`🎬 جاهز لتحميل الفيديوهات والوسائط من وسائل التواصل الاجتماعي`);
}).catch((err: Error) => {
  console.error("❌ فشل في الاتصال بـ Telegram:", err.message);
});

bot.launch({ dropPendingUpdates: true });

process.once("SIGINT", () => {
  console.log("\n⏹️ إيقاف البوت...");
  bot.stop("SIGINT");
});

process.once("SIGTERM", () => {
  console.log("\n⏹️ إيقاف البوت...");
  bot.stop("SIGTERM");
});
