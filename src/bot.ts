import { Telegraf, Context, Markup } from "telegraf";
import { message } from "telegraf/filters";
import {
  showMainMenu,
  handleMenuStats,
  handleMenuHelp,
  handleMenuPlatforms
} from "./handlers/menu";
import { handleDownloadPrompt, handleDownloadFormat, handleUrl } from "./handlers/download";
import { handleSearchPrompt, handleSearchQuery, handleSearchPick, showLink } from "./handlers/search";
import { handleHistory, handleClearHistory } from "./handlers/history";
import { getUserState, clearUserState } from "./utils/storage";

export function createBot(token: string): Telegraf {
  const bot = new Telegraf(token);

  bot.start(async (ctx) => {
    const name = ctx.from.first_name || "صديقي";
    await ctx.reply(
      `👋 *أهلاً ${name}!*\n\nأنا بوت تحميل الوسائط من وسائل التواصل الاجتماعي 🎬\n\nيمكنني تحميل فيديوهات، صور وملفات صوتية من:\nYouTube • Instagram • TikTok • Twitter • Facebook وأكثر!\n\nأرسل لي رابطاً مباشرةً أو اختر من القائمة:`,
      {
        parse_mode: "Markdown",
        ...Markup.inlineKeyboard([
          [
            Markup.button.callback("⬇️ تحميل وسائط", "menu_download"),
            Markup.button.callback("🔍 بحث يوتيوب", "menu_search")
          ],
          [
            Markup.button.callback("🎵 بحث موسيقى", "menu_music"),
            Markup.button.callback("📜 سجل التحميلات", "menu_history")
          ],
          [
            Markup.button.callback("📊 إحصائيات", "menu_stats"),
            Markup.button.callback("❓ مساعدة", "menu_help")
          ],
          [
            Markup.button.callback("🌐 المنصات المدعومة", "menu_platforms")
          ]
        ])
      }
    );
  });

  bot.command("download", async (ctx) => {
    const args = ctx.message.text.split(" ").slice(1).join(" ").trim();
    if (args && isValidUrl(args)) {
      await handleUrl(ctx as any, args);
    } else {
      await ctx.reply("🔗 أرسل رابط الفيديو:", {
        parse_mode: "Markdown",
        ...Markup.inlineKeyboard([[Markup.button.callback("↩️ إلغاء", "menu_back")]])
      });
      const userId = ctx.from.id;
      const { setUserState } = await import("./utils/storage");
      setUserState(userId, { waitingFor: "download_url" });
    }
  });

  bot.command("search", async (ctx) => {
    const query = ctx.message.text.split(" ").slice(1).join(" ").trim();
    if (query) {
      await handleSearchQuery(ctx as any, query, "video");
    } else {
      await ctx.reply("🔍 أرسل كلمة البحث:", {
        ...Markup.inlineKeyboard([[Markup.button.callback("↩️ إلغاء", "menu_back")]])
      });
      const { setUserState } = await import("./utils/storage");
      setUserState(ctx.from.id, { waitingFor: "search_query" });
    }
  });

  bot.command("music", async (ctx) => {
    const query = ctx.message.text.split(" ").slice(1).join(" ").trim();
    if (query) {
      await handleSearchQuery(ctx as any, query, "music");
    } else {
      await ctx.reply("🎵 أرسل اسم الأغنية:", {
        ...Markup.inlineKeyboard([[Markup.button.callback("↩️ إلغاء", "menu_back")]])
      });
      const { setUserState } = await import("./utils/storage");
      setUserState(ctx.from.id, { waitingFor: "music_search" });
    }
  });

  bot.command("history", async (ctx) => {
    const userId = ctx.from.id;
    const { getUserHistory } = await import("./utils/storage");
    const history = getUserHistory(userId);

    if (history.length === 0) {
      await ctx.reply("📜 لا يوجد سجل تحميلات حتى الآن.");
      return;
    }

    let text = `📜 *آخر ${Math.min(history.length, 10)} تحميلات:*\n\n`;
    history.slice(0, 10).forEach((record, i) => {
      const date = record.timestamp.toLocaleDateString("ar-SA");
      text += `${i + 1}. *${record.title.substring(0, 50)}*\n   ${record.platform} • ${record.format} • ${date}\n\n`;
    });

    await ctx.reply(text, { parse_mode: "Markdown" });
  });

  bot.command("stats", async (ctx) => {
    const { getBotStats } = await import("./utils/storage");
    const stats = getBotStats();
    await ctx.reply(
      `📊 *إحصائيات البوت*\n\n⬇️ التحميلات: ${stats.totalDownloads}\n🔍 عمليات البحث: ${stats.totalSearches}\n👥 المستخدمون: ${stats.activeUsers}\n⏱️ وقت التشغيل: ${stats.uptimeStr}`,
      { parse_mode: "Markdown" }
    );
  });

  bot.command("help", async (ctx) => {
    await ctx.reply(
      `❓ *المساعدة*\n\n🔗 أرسل رابطاً مباشرة لتحميله\n/download [رابط] - تحميل مباشر\n/search [بحث] - بحث يوتيوب\n/music [أغنية] - بحث موسيقى\n/history - سجل التحميلات\n/stats - الإحصائيات\n/help - المساعدة`,
      { parse_mode: "Markdown" }
    );
  });

  bot.on(message("text"), async (ctx) => {
    const text = ctx.message.text.trim();
    const userId = ctx.from.id;
    const state = getUserState(userId);

    if (isValidUrl(text)) {
      await handleUrl(ctx as any, text);
      return;
    }

    if (state.waitingFor === "download_url") {
      if (isValidUrl(text)) {
        clearUserState(userId);
        await handleUrl(ctx as any, text);
      } else {
        await ctx.reply("⚠️ هذا ليس رابطاً صحيحاً. أرسل رابطاً صحيحاً أو اضغط إلغاء.");
      }
      return;
    }

    if (state.waitingFor === "search_query") {
      clearUserState(userId);
      await handleSearchQuery(ctx as any, text, "video");
      return;
    }

    if (state.waitingFor === "music_search") {
      clearUserState(userId);
      await handleSearchQuery(ctx as any, text, "music");
      return;
    }

    await ctx.reply(
      `📱 أرسل لي رابطاً لتحميله، أو اختر من القائمة:`,
      {
        ...Markup.inlineKeyboard([
          [
            Markup.button.callback("⬇️ تحميل وسائط", "menu_download"),
            Markup.button.callback("🔍 بحث يوتيوب", "menu_search")
          ],
          [
            Markup.button.callback("🎵 بحث موسيقى", "menu_music"),
            Markup.button.callback("❓ مساعدة", "menu_help")
          ]
        ])
      }
    );
  });

  bot.action("menu_back", async (ctx) => {
    await ctx.answerCbQuery();
    clearUserState(ctx.from!.id);
    await showMainMenu(ctx as any);
  });

  bot.action("menu_download", async (ctx) => {
    await ctx.answerCbQuery();
    await handleDownloadPrompt(ctx as any);
  });

  bot.action("menu_search", async (ctx) => {
    await ctx.answerCbQuery();
    await handleSearchPrompt(ctx as any, "search");
  });

  bot.action("menu_music", async (ctx) => {
    await ctx.answerCbQuery();
    await handleSearchPrompt(ctx as any, "music");
  });

  bot.action("menu_history", async (ctx) => {
    await ctx.answerCbQuery();
    await handleHistory(ctx as any);
  });

  bot.action("menu_stats", async (ctx) => {
    await ctx.answerCbQuery();
    await handleMenuStats(ctx as any);
  });

  bot.action("menu_help", async (ctx) => {
    await ctx.answerCbQuery();
    await handleMenuHelp(ctx as any);
  });

  bot.action("menu_platforms", async (ctx) => {
    await ctx.answerCbQuery();
    await handleMenuPlatforms(ctx as any);
  });

  bot.action(/^dl_(.+)$/, async (ctx) => {
    await ctx.answerCbQuery("⏳ جاري التحميل...");
    const format = ctx.match[1];
    await handleDownloadFormat(ctx as any, format);
  });

  bot.action(/^search_pick_(\d+)$/, async (ctx) => {
    await ctx.answerCbQuery();
    const index = parseInt(ctx.match[1]);
    await handleSearchPick(ctx as any, index);
  });

  bot.action("show_link", async (ctx) => {
    await ctx.answerCbQuery();
    await showLink(ctx as any);
  });

  bot.action("clear_history", async (ctx) => {
    await ctx.answerCbQuery();
    await handleClearHistory(ctx as any);
  });

  bot.action("back_to_results", async (ctx) => {
    await ctx.answerCbQuery("↩️ رجوع...");
    clearUserState(ctx.from!.id);
    await showMainMenu(ctx as any, "🏠 *القائمة الرئيسية*\n\nاختر ما تريد فعله:");
  });

  bot.catch((err: any, ctx) => {
    console.error(`❌ خطأ في البوت:`, err.message || err);
    ctx.reply("❌ حدث خطأ غير متوقع. حاول مرة أخرى.").catch(() => {});
  });

  return bot;
}

function isValidUrl(text: string): boolean {
  try {
    const url = new URL(text);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}
