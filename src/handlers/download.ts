import { Context, Markup } from "telegraf";
import * as fs from "fs";
import * as path from "path";
import {
  getMediaInfo,
  downloadMedia,
  formatDuration,
  formatFileSize,
  detectPlatform,
  cleanupFile,
  MediaInfo
} from "../services/downloader";
import {
  setUserState,
  getUserState,
  clearUserState,
  addDownloadRecord
} from "../utils/storage";
import { getDownloadFormatMenu } from "./menu";

const activeDownloads = new Map<number, boolean>();

export async function handleDownloadPrompt(ctx: Context) {
  const userId = ctx.from!.id;
  setUserState(userId, { waitingFor: "download_url" });
  await ctx.editMessageText(
    `🔗 *أرسل رابط الفيديو*\n\nأرسل رابط من أي منصة (YouTube, Instagram, TikTok, Twitter...)`,
    {
      parse_mode: "Markdown",
      ...Markup.inlineKeyboard([[Markup.button.callback("↩️ إلغاء", "menu_back")]])
    }
  );
}

export async function handleUrl(ctx: Context, url: string) {
  const userId = ctx.from!.id;
  
  if (activeDownloads.get(userId)) {
    await ctx.reply("⏳ يوجد تحميل جارٍ بالفعل. انتظر حتى ينتهي.");
    return;
  }

  const platform = detectPlatform(url);
  const loadingMsg = await ctx.reply(`🔍 جاري تحليل الرابط من *${platform}*...`, {
    parse_mode: "Markdown"
  });

  try {
    const info = await getMediaInfo(url);
    setUserState(userId, { mediaInfo: info });
    
    const durationStr = formatDuration(info.duration);
    const uploaderStr = info.uploader ? `\n👤 **القناة:** ${info.uploader}` : "";
    
    const text = `
📹 *${escapeMarkdown(info.title)}*

🌐 **المنصة:** ${info.platform}${uploaderStr}
⏱️ **المدة:** ${durationStr}
${info.description ? `\n📝 ${escapeMarkdown(info.description.substring(0, 100))}...` : ""}

اختر صيغة التحميل:
    `.trim();

    await ctx.telegram.editMessageText(
      ctx.chat!.id,
      loadingMsg.message_id,
      undefined,
      text,
      {
        parse_mode: "Markdown",
        ...getDownloadFormatMenu(true)
      }
    );
  } catch (err: any) {
    await ctx.telegram.editMessageText(
      ctx.chat!.id,
      loadingMsg.message_id,
      undefined,
      `❌ ${err.message || "فشل في تحليل الرابط"}`,
      {
        parse_mode: "Markdown",
        ...Markup.inlineKeyboard([[Markup.button.callback("↩️ رجوع", "menu_back")]])
      }
    );
  }
}

export async function handleDownloadFormat(ctx: Context, format: string) {
  const userId = ctx.from!.id;
  const state = getUserState(userId);
  
  if (!state.mediaInfo) {
    await ctx.reply("❌ لا توجد معلومات وسائط. أرسل الرابط مرة أخرى.");
    return;
  }

  if (activeDownloads.get(userId)) {
    await ctx.answerCbQuery("⏳ يوجد تحميل جارٍ بالفعل.");
    return;
  }

  const info: MediaInfo = state.mediaInfo;
  activeDownloads.set(userId, true);

  let dlFormat = "best";
  let dlLabel = "أفضل جودة";
  
  switch (format) {
    case "720": dlFormat = "bestvideo[height<=720]+bestaudio/best[height<=720]"; dlLabel = "720p"; break;
    case "1080": dlFormat = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"; dlLabel = "1080p"; break;
    case "360": dlFormat = "bestvideo[height<=360]+bestaudio/best[height<=360]"; dlLabel = "360p"; break;
    case "best": dlFormat = "best"; dlLabel = "أفضل جودة"; break;
    case "audio": dlFormat = "bestaudio"; dlLabel = "صوت MP3"; break;
  }

  let progressMsg: any;
  try {
    progressMsg = await ctx.editMessageText(
      `⬇️ جاري التحميل بجودة *${dlLabel}*...\n\n⏳ يرجى الانتظار...`,
      { parse_mode: "Markdown" }
    );
  } catch {
    progressMsg = await ctx.reply(`⬇️ جاري التحميل بجودة *${dlLabel}*...`, { parse_mode: "Markdown" });
  }

  let lastUpdate = 0;
  const onProgress = async (percent: number) => {
    const now = Date.now();
    if (now - lastUpdate < 3000) return;
    lastUpdate = now;
    try {
      const bar = createProgressBar(percent);
      await ctx.telegram.editMessageText(
        ctx.chat!.id,
        progressMsg.message_id,
        undefined,
        `⬇️ جاري التحميل بجودة *${dlLabel}*\n\n${bar} ${percent.toFixed(0)}%`,
        { parse_mode: "Markdown" }
      );
    } catch {}
  };

  let filePath = "";
  try {
    filePath = await downloadMedia(info.url, dlFormat, info.platform, onProgress);
    const stat = fs.statSync(filePath);
    const fileSize = stat.size;
    
    if (fileSize > 50 * 1024 * 1024) {
      await ctx.telegram.editMessageText(
        ctx.chat!.id,
        progressMsg.message_id,
        undefined,
        `⚠️ حجم الملف كبير جداً (${formatFileSize(fileSize)}). تلجرام يسمح بـ 50MB كحد أقصى للبوتات.\n\nحاول جودة أقل.`,
        {
          parse_mode: "Markdown",
          ...Markup.inlineKeyboard([
            [Markup.button.callback("🎬 جودة منخفضة", "dl_360")],
            [Markup.button.callback("🎵 صوت فقط", "dl_audio")],
            [Markup.button.callback("↩️ رجوع", "menu_back")]
          ])
        }
      );
      activeDownloads.delete(userId);
      cleanupFile(filePath);
      return;
    }

    await ctx.telegram.editMessageText(
      ctx.chat!.id,
      progressMsg.message_id,
      undefined,
      `📤 جاري الإرسال...`,
      { parse_mode: "Markdown" }
    );

    const ext = path.extname(filePath).toLowerCase();
    const caption = `✅ *${escapeMarkdown(info.title.substring(0, 100))}*\n\n🌐 ${info.platform} | ⚡ ${dlLabel}`;
    
    const fileStream = fs.createReadStream(filePath);
    
    if (format === "audio" || ext === ".mp3") {
      await ctx.replyWithAudio(
        { source: fileStream, filename: `${sanitizeFilename(info.title)}.mp3` },
        { caption, parse_mode: "Markdown" }
      );
    } else if ([".mp4", ".webm", ".mkv", ".avi", ".mov"].includes(ext)) {
      await ctx.replyWithVideo(
        { source: fileStream, filename: `${sanitizeFilename(info.title)}.mp4` },
        { caption, parse_mode: "Markdown" }
      );
    } else if ([".jpg", ".jpeg", ".png", ".webp"].includes(ext)) {
      await ctx.replyWithPhoto(
        { source: fileStream },
        { caption, parse_mode: "Markdown" }
      );
    } else {
      await ctx.replyWithDocument(
        { source: fileStream, filename: path.basename(filePath) },
        { caption, parse_mode: "Markdown" }
      );
    }

    addDownloadRecord(userId, {
      url: info.url,
      platform: info.platform,
      title: info.title.substring(0, 100),
      format: dlLabel,
      timestamp: new Date()
    });

    await ctx.telegram.deleteMessage(ctx.chat!.id, progressMsg.message_id).catch(() => {});
    
    await ctx.reply(
      `✅ *تم التحميل بنجاح!*\n\n${escapeMarkdown(info.title.substring(0, 80))}`,
      {
        parse_mode: "Markdown",
        ...Markup.inlineKeyboard([
          [Markup.button.callback("⬇️ تحميل آخر", "menu_download")],
          [Markup.button.callback("🏠 القائمة الرئيسية", "menu_back")]
        ])
      }
    );

    clearUserState(userId);
  } catch (err: any) {
    await ctx.telegram.editMessageText(
      ctx.chat!.id,
      progressMsg.message_id,
      undefined,
      `❌ *فشل التحميل*\n\n${err.message || "خطأ غير معروف"}\n\nتأكد أن الرابط صحيح وعلني.`,
      {
        parse_mode: "Markdown",
        ...Markup.inlineKeyboard([
          [Markup.button.callback("🔄 حاول مرة أخرى", "menu_download")],
          [Markup.button.callback("↩️ رجوع", "menu_back")]
        ])
      }
    );
  } finally {
    activeDownloads.delete(userId);
    if (filePath) cleanupFile(filePath);
  }
}

function createProgressBar(percent: number): string {
  const filled = Math.floor(percent / 10);
  const empty = 10 - filled;
  return "▓".repeat(filled) + "░".repeat(empty);
}

function escapeMarkdown(text: string): string {
  return text.replace(/[_*[\]()~`>#+\-=|{}.!]/g, "\\$&");
}

function sanitizeFilename(name: string): string {
  return name.replace(/[^\w\s\-\.]/g, "").substring(0, 50);
}
