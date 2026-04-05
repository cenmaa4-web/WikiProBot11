"use strict";

const { Telegraf, Markup } = require("telegraf");
const { message } = require("telegraf/filters");
const fs = require("fs");
const path = require("path");
const {
  detectPlatform, getMediaInfo, downloadMedia,
  formatDuration, formatSize, cleanup
} = require("./downloader");
const { searchVideos } = require("./search");
const {
  addHistory, getHistory, clearHistory,
  setState, getState, clearState,
  recordSearch, getBotStats
} = require("./storage");

const activeDownloads = new Set();

// ─── Keyboards ────────────────────────────────────────────────────────────────

const MAIN_MENU = Markup.inlineKeyboard([
  [Markup.button.callback("⬇️ تحميل وسائط", "dl_prompt"),   Markup.button.callback("🔍 بحث يوتيوب", "search_prompt")],
  [Markup.button.callback("🎵 بحث موسيقى",   "music_prompt"), Markup.button.callback("📜 سجل التحميلات", "history")],
  [Markup.button.callback("📊 إحصائيات",      "stats"),        Markup.button.callback("❓ مساعدة",        "help")],
  [Markup.button.callback("🌐 المنصات المدعومة", "platforms")],
]);

const FORMAT_MENU = Markup.inlineKeyboard([
  [Markup.button.callback("🎬 720p",        "fmt_720"),  Markup.button.callback("🎬 1080p",       "fmt_1080")],
  [Markup.button.callback("🎬 480p",        "fmt_480"),  Markup.button.callback("🎬 360p",        "fmt_360")],
  [Markup.button.callback("🎵 صوت MP3",    "fmt_audio")],
  [Markup.button.callback("↩️ رجوع",       "back")],
]);

const BACK = Markup.inlineKeyboard([[Markup.button.callback("↩️ رجوع للقائمة", "back")]]);

// ─── Helpers ──────────────────────────────────────────────────────────────────

function esc(t) {
  return String(t || "").replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, "\\$&");
}

function isUrl(text) {
  try { const u = new URL(text); return u.protocol === "http:" || u.protocol === "https:"; }
  catch { return false; }
}

function progressBar(pct) {
  const filled = Math.round(pct / 10);
  return "▓".repeat(filled) + "░".repeat(10 - filled);
}

async function safeEdit(ctx, msgId, text, extra) {
  try {
    await ctx.telegram.editMessageText(ctx.chat.id, msgId, undefined, text, extra);
  } catch {}
}

// ─── Download Flow ────────────────────────────────────────────────────────────

async function handleUrl(ctx, url) {
  const userId = ctx.from.id;
  if (activeDownloads.has(userId)) {
    return ctx.reply("⏳ يوجد تحميل جارٍ، انتظر حتى ينتهي.");
  }

  const platform = detectPlatform(url);
  const loadMsg = await ctx.reply(`🔍 جاري تحليل الرابط من *${platform}*\\.\\.\\.`, { parse_mode: "MarkdownV2" });

  try {
    const info = await getMediaInfo(url);
    setState(userId, { mediaInfo: info });

    const dur = formatDuration(info.duration);
    const upldr = info.uploader ? `\n👤 *${esc(info.uploader)}*` : "";
    const text = `📹 *${esc(info.title.substring(0, 120))}*\n\n🌐 *المنصة:* ${info.platform}${upldr}\n⏱️ *المدة:* ${dur}\n\nاختر جودة التحميل:`;

    await safeEdit(ctx, loadMsg.message_id, text, { parse_mode: "MarkdownV2", ...FORMAT_MENU });
  } catch (err) {
    await safeEdit(ctx, loadMsg.message_id, `❌ ${esc(err.message)}`, { parse_mode: "MarkdownV2", ...BACK });
  }
}

async function handleFormat(ctx, format) {
  const userId = ctx.from.id;
  const { mediaInfo } = getState(userId);
  if (!mediaInfo) {
    await ctx.answerCbQuery();
    return ctx.reply("❌ انتهت الجلسة، أرسل الرابط مرة أخرى.");
  }
  if (activeDownloads.has(userId)) {
    return ctx.answerCbQuery("⏳ تحميل جارٍ بالفعل");
  }

  activeDownloads.add(userId);
  const labelMap = { "720": "720p", "1080": "1080p", "480": "480p", "360": "360p", "audio": "صوت MP3", "best": "أفضل جودة" };
  const label = labelMap[format] || format;

  let progressMsgId;
  try {
    const initMsg = await ctx.editMessageText(`⬇️ جاري التحميل: *${esc(label)}*\n\n░░░░░░░░░░ 0%`, { parse_mode: "MarkdownV2" });
    progressMsgId = initMsg.message_id;
  } catch {
    const m = await ctx.reply(`⬇️ جاري التحميل: *${esc(label)}*`, { parse_mode: "MarkdownV2" });
    progressMsgId = m.message_id;
  }

  let filePath = null;
  try {
    // Progress callback
    const onProgress = async (pct) => {
      const bar = progressBar(pct);
      await safeEdit(ctx, progressMsgId,
        `⬇️ *جاري التحميل:* ${esc(label)}\n\n${bar} ${pct.toFixed(0)}%`,
        { parse_mode: "MarkdownV2" }
      );
    };

    filePath = await downloadMedia(mediaInfo.url, format, mediaInfo.platform, onProgress);

    if (!filePath || !fs.existsSync(filePath)) {
      throw new Error("الملف لم يتم إنشاؤه");
    }

    const fileStat = fs.statSync(filePath);
    const fileSize = fileStat.size;
    const MAX = 50 * 1024 * 1024;

    if (fileSize > MAX) {
      throw new Error(`حجم الملف كبير جداً (${formatSize(fileSize)})، حاول جودة أقل.`);
    }

    await safeEdit(ctx, progressMsgId, `📤 جاري الإرسال\\.\\.\\.`, { parse_mode: "MarkdownV2" });

    const ext = path.extname(filePath).toLowerCase();
    const caption = `✅ *${esc(mediaInfo.title.substring(0, 100))}*\n\n🌐 ${mediaInfo.platform} \\| ⚡ ${esc(label)}`;
    const source = { source: fs.createReadStream(filePath) };

    if (format === "audio" || ext === ".mp3") {
      await ctx.replyWithAudio(source, { caption, parse_mode: "MarkdownV2" });
    } else if ([".mp4", ".webm", ".mkv", ".avi", ".mov"].includes(ext)) {
      await ctx.replyWithVideo(source, {
        caption,
        parse_mode: "MarkdownV2",
        supports_streaming: true,
      });
    } else if ([".jpg", ".jpeg", ".png", ".webp"].includes(ext)) {
      await ctx.replyWithPhoto(source, { caption, parse_mode: "MarkdownV2" });
    } else {
      await ctx.replyWithDocument(
        { source: fs.createReadStream(filePath), filename: path.basename(filePath) },
        { caption, parse_mode: "MarkdownV2" }
      );
    }

    addHistory(userId, {
      url: mediaInfo.url,
      platform: mediaInfo.platform,
      title: mediaInfo.title.substring(0, 80),
      format: label,
      timestamp: new Date(),
    });

    await ctx.telegram.deleteMessage(ctx.chat.id, progressMsgId).catch(() => {});
    await ctx.reply("✅ *تم التحميل بنجاح\\!*", {
      parse_mode: "MarkdownV2",
      ...Markup.inlineKeyboard([
        [Markup.button.callback("⬇️ تحميل آخر", "dl_prompt")],
        [Markup.button.callback("🏠 القائمة", "back")],
      ]),
    });
    clearState(userId);
  } catch (err) {
    await safeEdit(ctx, progressMsgId,
      `❌ *فشل التحميل*\n\n${esc(err.message)}`,
      {
        parse_mode: "MarkdownV2",
        ...Markup.inlineKeyboard([
          [Markup.button.callback("🔄 جودة أقل", "fmt_360"), Markup.button.callback("🎵 صوت فقط", "fmt_audio")],
          [Markup.button.callback("↩️ رجوع", "back")],
        ]),
      }
    );
  } finally {
    activeDownloads.delete(userId);
    if (filePath) cleanup(filePath);
  }
}

// ─── Search Flow ──────────────────────────────────────────────────────────────

async function handleSearchQuery(ctx, query, mode) {
  const userId = ctx.from.id;
  recordSearch(userId);

  const searchQuery = mode === "music" ? `${query} music audio` : query;
  const loadMsg = await ctx.reply(`🔍 جاري البحث عن: *${esc(query)}*`, { parse_mode: "MarkdownV2" });

  try {
    const results = await searchVideos(searchQuery, 6);
    if (!results.length) throw new Error("لا توجد نتائج");

    setState(userId, { searchResults: results, searchMode: mode });

    const emoji = mode === "music" ? "🎵" : "📺";
    let text = `${emoji} *نتائج البحث: ${esc(query)}*\n\n`;
    results.forEach((r, i) => {
      text += `${i + 1}\\. *${esc(r.title.substring(0, 55))}*\n`;
      text += `   ⏱️ ${esc(r.duration)} \\| 👁️ ${esc(r.views)}\n\n`;
    });

    const rows = [];
    for (let i = 0; i < results.length; i += 2) {
      const row = [Markup.button.callback(`${i + 1}. ${results[i].title.substring(0, 18)}`, `pick_${i}`)];
      if (results[i + 1]) row.push(Markup.button.callback(`${i + 2}. ${results[i + 1].title.substring(0, 18)}`, `pick_${i + 1}`));
      rows.push(row);
    }
    rows.push([
      Markup.button.callback("🔍 بحث جديد", mode === "music" ? "music_prompt" : "search_prompt"),
      Markup.button.callback("↩️ رجوع", "back"),
    ]);

    await safeEdit(ctx, loadMsg.message_id, text, { parse_mode: "MarkdownV2", ...Markup.inlineKeyboard(rows) });
  } catch (err) {
    await safeEdit(ctx, loadMsg.message_id, `❌ ${esc(err.message)}`, { parse_mode: "MarkdownV2", ...BACK });
  }
}

async function handleSearchPick(ctx, index) {
  const userId = ctx.from.id;
  const { searchResults } = getState(userId);
  if (!searchResults?.[index]) return ctx.answerCbQuery("❌ انتهت صلاحية النتائج");

  const r = searchResults[index];
  setState(userId, { mediaInfo: { url: r.url, title: r.title, platform: "YouTube", duration: null, uploader: r.channel } });

  const text = `📺 *${esc(r.title)}*\n\n📺 *القناة:* ${esc(r.channel)}\n⏱️ *المدة:* ${esc(r.duration)}\n👁️ *المشاهدات:* ${esc(r.views)}\n\nاختر جودة التحميل:`;
  await ctx.editMessageText(text, { parse_mode: "MarkdownV2", ...FORMAT_MENU });
}

// ─── Static Menus ─────────────────────────────────────────────────────────────

function statsText() {
  const s = getBotStats();
  return `📊 *إحصائيات البوت*\n\n⬇️ التحميلات: *${s.downloads}*\n🔍 البحث: *${s.searches}*\n👥 المستخدمون: *${s.users}*\n⏱️ وقت التشغيل: *${esc(s.uptime)}*`;
}

const HELP_TEXT = `❓ *دليل الاستخدام*\n\n🔗 أرسل رابطاً مباشرة لتحميله\n\n*الأوامر:*\n/start \\- القائمة الرئيسية\n/dl \\[رابط\\] \\- تحميل مباشر\n/search \\[نص\\] \\- بحث يوتيوب\n/music \\[نص\\] \\- بحث موسيقى\n/history \\- سجل التحميلات\n/stats \\- الإحصائيات`;

const PLATFORMS_TEXT = `🌐 *المنصات المدعومة*\n\n📺 YouTube ✅\n📸 Instagram ✅\n🎵 TikTok ✅\n🐦 Twitter\\/X ✅\n👥 Facebook ✅\n📌 Pinterest ✅\n👻 Snapchat ✅\n🎶 SoundCloud ✅\n🎬 Vimeo ✅\n🔴 Reddit ✅\n\n_وأكثر من 1000 موقع آخر\\!_`;

// ─── Bot Factory ──────────────────────────────────────────────────────────────

function createBot(token) {
  const bot = new Telegraf(token);

  // /start
  bot.start(async (ctx) => {
    const name = esc(ctx.from.first_name || "صديقي");
    await ctx.reply(
      `👋 *أهلاً ${name}\\!*\n\nأنا بوت تحميل الوسائط من وسائل التواصل الاجتماعي 🎬\n\nأرسل رابطاً مباشرةً أو اختر من القائمة:`,
      { parse_mode: "MarkdownV2", ...MAIN_MENU }
    );
  });

  // Commands
  bot.command("dl", async (ctx) => {
    const url = ctx.message.text.split(" ").slice(1).join("").trim();
    if (isUrl(url)) return handleUrl(ctx, url);
    setState(ctx.from.id, { waitingFor: "url" });
    await ctx.reply("🔗 أرسل رابط الفيديو:", BACK);
  });

  bot.command("search", async (ctx) => {
    const q = ctx.message.text.split(" ").slice(1).join(" ").trim();
    if (q) return handleSearchQuery(ctx, q, "video");
    setState(ctx.from.id, { waitingFor: "search" });
    await ctx.reply("🔍 أرسل كلمة البحث:", BACK);
  });

  bot.command("music", async (ctx) => {
    const q = ctx.message.text.split(" ").slice(1).join(" ").trim();
    if (q) return handleSearchQuery(ctx, q, "music");
    setState(ctx.from.id, { waitingFor: "music" });
    await ctx.reply("🎵 أرسل اسم الأغنية:", BACK);
  });

  bot.command("history", async (ctx) => {
    const h = getHistory(ctx.from.id);
    if (!h.length) return ctx.reply("📜 لا يوجد سجل بعد.");
    let text = `📜 *آخر ${Math.min(h.length, 10)} تحميلات:*\n\n`;
    h.slice(0, 10).forEach((r, i) => {
      const d = new Date(r.timestamp).toLocaleDateString("ar");
      text += `${i + 1}\\. *${esc(r.title.substring(0, 50))}*\n   ${esc(r.platform)} • ${esc(r.format)} • ${d}\n\n`;
    });
    await ctx.reply(text, { parse_mode: "MarkdownV2" });
  });

  bot.command("stats", async (ctx) => ctx.reply(statsText(), { parse_mode: "MarkdownV2" }));
  bot.command("help",  async (ctx) => ctx.reply(HELP_TEXT,  { parse_mode: "MarkdownV2" }));

  // Text messages → detect URL or waiting state
  bot.on(message("text"), async (ctx) => {
    const text = ctx.message.text.trim();
    const userId = ctx.from.id;
    const state = getState(userId);

    if (isUrl(text)) { clearState(userId); return handleUrl(ctx, text); }

    if (state.waitingFor === "url") {
      if (isUrl(text)) { clearState(userId); return handleUrl(ctx, text); }
      return ctx.reply("⚠️ ليس رابطاً صحيحاً، أرسل رابطاً يبدأ بـ http/https");
    }
    if (state.waitingFor === "search") { clearState(userId); return handleSearchQuery(ctx, text, "video"); }
    if (state.waitingFor === "music")  { clearState(userId); return handleSearchQuery(ctx, text, "music"); }

    await ctx.reply("📱 أرسل رابطاً لتحميله أو اختر من القائمة:", MAIN_MENU);
  });

  // Callback actions
  bot.action("back", async (ctx) => {
    await ctx.answerCbQuery();
    clearState(ctx.from.id);
    await ctx.editMessageText("🏠 *القائمة الرئيسية*\n\nاختر ما تريد:", { parse_mode: "MarkdownV2", ...MAIN_MENU });
  });

  bot.action("dl_prompt", async (ctx) => {
    await ctx.answerCbQuery();
    setState(ctx.from.id, { waitingFor: "url" });
    await ctx.editMessageText("🔗 *أرسل رابط الفيديو*\n\nمن أي منصة \\(YouTube, Instagram, TikTok\\.\\.\\.\\)", { parse_mode: "MarkdownV2", ...BACK });
  });

  bot.action("search_prompt", async (ctx) => {
    await ctx.answerCbQuery();
    setState(ctx.from.id, { waitingFor: "search" });
    await ctx.editMessageText("🔍 *بحث في يوتيوب*\n\nأرسل كلمة البحث:", { parse_mode: "MarkdownV2", ...BACK });
  });

  bot.action("music_prompt", async (ctx) => {
    await ctx.answerCbQuery();
    setState(ctx.from.id, { waitingFor: "music" });
    await ctx.editMessageText("🎵 *بحث موسيقى*\n\nأرسل اسم الأغنية أو الفنان:", { parse_mode: "MarkdownV2", ...BACK });
  });

  bot.action("history", async (ctx) => {
    await ctx.answerCbQuery();
    const h = getHistory(ctx.from.id);
    if (!h.length) return ctx.editMessageText("📜 لا يوجد سجل تحميلات بعد\\.", { parse_mode: "MarkdownV2", ...BACK });
    let text = `📜 *آخر ${Math.min(h.length, 10)} تحميلات:*\n\n`;
    h.slice(0, 10).forEach((r, i) => {
      const d = new Date(r.timestamp).toLocaleDateString("ar");
      text += `${i + 1}\\. *${esc(r.title.substring(0, 50))}*\n   ${esc(r.platform)} • ${esc(r.format)} • ${d}\n\n`;
    });
    await ctx.editMessageText(text, {
      parse_mode: "MarkdownV2",
      ...Markup.inlineKeyboard([
        [Markup.button.callback("🗑️ مسح السجل", "clear_history")],
        [Markup.button.callback("↩️ رجوع", "back")],
      ]),
    });
  });

  bot.action("clear_history", async (ctx) => {
    await ctx.answerCbQuery();
    clearHistory(ctx.from.id);
    await ctx.editMessageText("✅ تم مسح السجل\\.", { parse_mode: "MarkdownV2", ...BACK });
  });

  bot.action("stats",     async (ctx) => { await ctx.answerCbQuery(); await ctx.editMessageText(statsText(),      { parse_mode: "MarkdownV2", ...BACK }); });
  bot.action("help",      async (ctx) => { await ctx.answerCbQuery(); await ctx.editMessageText(HELP_TEXT,        { parse_mode: "MarkdownV2", ...BACK }); });
  bot.action("platforms", async (ctx) => { await ctx.answerCbQuery(); await ctx.editMessageText(PLATFORMS_TEXT,   { parse_mode: "MarkdownV2", ...BACK }); });

  bot.action(/^fmt_(.+)$/, async (ctx) => {
    await ctx.answerCbQuery("⏳ جاري التحميل...");
    await handleFormat(ctx, ctx.match[1]);
  });

  bot.action(/^pick_(\d+)$/, async (ctx) => {
    await ctx.answerCbQuery();
    await handleSearchPick(ctx, parseInt(ctx.match[1]));
  });

  bot.catch((err, ctx) => {
    console.error("Bot error:", err?.message || err);
    ctx.reply("❌ خطأ، حاول مرة أخرى.").catch(() => {});
  });

  return bot;
}

module.exports = { createBot };
