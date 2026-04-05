import { Context, Markup } from "telegraf";
import { getBotStats } from "../utils/storage";

export function getMainMenu() {
  return Markup.inlineKeyboard([
    [
      Markup.button.callback("⬇️ تحميل وسائط", "menu_download"),
      Markup.button.callback("🔍 بحث يوتيوب", "menu_search")
    ],
    [
      Markup.button.callback("🎵 بحث موسيقى", "menu_music"),
      Markup.button.callback("📜 سجل التحميلات", "menu_history")
    ],
    [
      Markup.button.callback("📊 إحصائيات البوت", "menu_stats"),
      Markup.button.callback("❓ المساعدة", "menu_help")
    ],
    [
      Markup.button.callback("🌐 المنصات المدعومة", "menu_platforms")
    ]
  ]);
}

export function getDownloadFormatMenu(hasVideo: boolean = true) {
  const buttons: any[] = [];
  if (hasVideo) {
    buttons.push([
      Markup.button.callback("🎬 فيديو 720p", "dl_720"),
      Markup.button.callback("🎬 فيديو 1080p", "dl_1080")
    ]);
    buttons.push([
      Markup.button.callback("🎬 أفضل جودة", "dl_best"),
      Markup.button.callback("🎬 جودة منخفضة", "dl_360")
    ]);
  }
  buttons.push([
    Markup.button.callback("🎵 صوت فقط (MP3)", "dl_audio")
  ]);
  buttons.push([
    Markup.button.callback("↩️ رجوع", "menu_back")
  ]);
  return Markup.inlineKeyboard(buttons);
}

export async function showMainMenu(ctx: Context, text?: string) {
  const welcomeText = text || `🤖 *بوت تحميل الوسائط*\n\nاختر ما تريد فعله:`;
  if (ctx.callbackQuery) {
    await ctx.editMessageText(welcomeText, {
      parse_mode: "Markdown",
      ...getMainMenu()
    });
  } else {
    await ctx.reply(welcomeText, {
      parse_mode: "Markdown",
      ...getMainMenu()
    });
  }
}

export async function handleMenuStats(ctx: Context) {
  const stats = getBotStats();
  const text = `
📊 *إحصائيات البوت*

⬇️ **إجمالي التحميلات:** ${stats.totalDownloads}
🔍 **إجمالي عمليات البحث:** ${stats.totalSearches}
👥 **المستخدمون النشطون:** ${stats.activeUsers}
⏱️ **وقت التشغيل:** ${stats.uptimeStr}
📅 **تاريخ البدء:** ${stats.startTime.toLocaleDateString("ar-SA")}

_البيانات محلية لهذه الجلسة_
  `.trim();

  await ctx.editMessageText(text, {
    parse_mode: "Markdown",
    ...Markup.inlineKeyboard([[Markup.button.callback("↩️ رجوع للقائمة", "menu_back")]])
  });
}

export async function handleMenuHelp(ctx: Context) {
  const text = `
❓ *دليل الاستخدام*

🔗 **تحميل فيديو/صورة/صوت:**
أرسل رابط مباشرة أو اختر "تحميل وسائط"

🔍 **بحث يوتيوب:**
اختر "بحث يوتيوب" وأرسل كلمة البحث

🎵 **بحث موسيقى:**
ابحث عن أغنية وحملها كـ MP3

📜 **السجل:**
شاهد آخر 20 تحميل قمت بها

*الأوامر المتاحة:*
/start - القائمة الرئيسية
/download - تحميل رابط مباشر
/search - بحث في يوتيوب
/music - بحث موسيقى
/history - سجل التحميلات
/stats - إحصائيات
/help - المساعدة
  `.trim();

  await ctx.editMessageText(text, {
    parse_mode: "Markdown",
    ...Markup.inlineKeyboard([[Markup.button.callback("↩️ رجوع للقائمة", "menu_back")]])
  });
}

export async function handleMenuPlatforms(ctx: Context) {
  const text = `
🌐 *المنصات المدعومة*

📺 **فيديو:**
• YouTube ✅
• TikTok ✅
• Instagram ✅
• Facebook ✅
• Twitter/X ✅
• Vimeo ✅
• Dailymotion ✅
• Twitch ✅
• Reddit ✅
• Bilibili ✅

🎵 **صوت:**
• SoundCloud ✅
• Spotify (معاينة) ✅
• Bandcamp ✅
• YouTube Music ✅

🖼️ **صور:**
• Instagram ✅
• Pinterest ✅
• Twitter/X ✅

_وأكثر من 1000 موقع آخر!_
  `.trim();

  await ctx.editMessageText(text, {
    parse_mode: "Markdown",
    ...Markup.inlineKeyboard([[Markup.button.callback("↩️ رجوع للقائمة", "menu_back")]])
  });
}
