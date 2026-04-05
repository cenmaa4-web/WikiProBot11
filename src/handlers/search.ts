import { Context, Markup } from "telegraf";
import {
  searchYouTube,
  searchYouTubeMusic,
  YouTubeSearchResult
} from "../services/youtube-search";
import {
  setUserState,
  getUserState,
  clearUserState,
  recordSearch
} from "../utils/storage";
import { handleUrl } from "./download";

export async function handleSearchPrompt(ctx: Context, mode: "search" | "music" = "search") {
  const userId = ctx.from!.id;
  setUserState(userId, { waitingFor: mode === "music" ? "music_search" : "search_query" });
  
  const emoji = mode === "music" ? "🎵" : "🔍";
  const label = mode === "music" ? "موسيقى" : "فيديو";
  
  await ctx.editMessageText(
    `${emoji} *بحث ${label} على يوتيوب*\n\nأرسل كلمة البحث:`,
    {
      parse_mode: "Markdown",
      ...Markup.inlineKeyboard([[Markup.button.callback("↩️ إلغاء", "menu_back")]])
    }
  );
}

export async function handleSearchQuery(ctx: Context, query: string, mode: "video" | "music" = "video") {
  const userId = ctx.from!.id;
  recordSearch(userId);

  const loadingMsg = await ctx.reply(`🔍 جاري البحث عن: *${query}*...`, { parse_mode: "Markdown" });

  try {
    const results = mode === "music" 
      ? await searchYouTubeMusic(`${query} audio music`, 8)
      : await searchYouTube(query, 8);

    if (results.length === 0) {
      await ctx.telegram.editMessageText(
        ctx.chat!.id,
        loadingMsg.message_id,
        undefined,
        `❌ لا توجد نتائج لـ "*${query}*"`,
        {
          parse_mode: "Markdown",
          ...Markup.inlineKeyboard([[Markup.button.callback("🔍 بحث جديد", mode === "music" ? "menu_music" : "menu_search")]])
        }
      );
      return;
    }

    setUserState(userId, { searchResults: results });

    const emoji = mode === "music" ? "🎵" : "📺";
    let text = `${emoji} *نتائج البحث عن:* \`${query}\`\n\n`;
    
    results.slice(0, 6).forEach((r, i) => {
      text += `${i + 1}. *${escapeMarkdown(r.title.substring(0, 60))}*\n`;
      text += `   ⏱️ ${r.duration} | 👁️ ${r.views}\n\n`;
    });

    const buttons: any[] = [];
    results.slice(0, 6).forEach((r, i) => {
      const row = Math.floor(i / 2);
      if (!buttons[row]) buttons[row] = [];
      buttons[row].push(
        Markup.button.callback(`${i + 1}. ${r.title.substring(0, 20)}...`, `search_pick_${i}`)
      );
    });
    
    buttons.push([
      Markup.button.callback("🔍 بحث جديد", mode === "music" ? "menu_music" : "menu_search"),
      Markup.button.callback("↩️ رجوع", "menu_back")
    ]);

    await ctx.telegram.editMessageText(
      ctx.chat!.id,
      loadingMsg.message_id,
      undefined,
      text,
      {
        parse_mode: "Markdown",
        ...Markup.inlineKeyboard(buttons)
      }
    );
  } catch (err: any) {
    await ctx.telegram.editMessageText(
      ctx.chat!.id,
      loadingMsg.message_id,
      undefined,
      `❌ ${err.message || "فشل البحث"}`,
      {
        parse_mode: "Markdown",
        ...Markup.inlineKeyboard([[Markup.button.callback("↩️ رجوع", "menu_back")]])
      }
    );
  }
}

export async function handleSearchPick(ctx: Context, index: number) {
  const userId = ctx.from!.id;
  const state = getUserState(userId);
  
  if (!state.searchResults || !state.searchResults[index]) {
    await ctx.answerCbQuery("❌ انتهت صلاحية النتائج. ابحث مرة أخرى.");
    return;
  }

  const result: YouTubeSearchResult = state.searchResults[index];
  
  const text = `
📺 *${escapeMarkdown(result.title)}*

📺 **القناة:** ${escapeMarkdown(result.channel)}
⏱️ **المدة:** ${result.duration}
👁️ **المشاهدات:** ${result.views}
${result.uploadedAt ? `📅 **تاريخ الرفع:** ${result.uploadedAt}` : ""}

اختر صيغة التحميل:
  `.trim();

  setUserState(userId, { mediaInfo: { url: result.url, title: result.title, platform: "YouTube", duration: 0, formats: [] } });

  await ctx.editMessageText(text, {
    parse_mode: "Markdown",
    ...Markup.inlineKeyboard([
      [
        Markup.button.callback("🎬 فيديو 720p", "dl_720"),
        Markup.button.callback("🎬 أفضل جودة", "dl_best")
      ],
      [
        Markup.button.callback("🎵 صوت MP3", "dl_audio"),
        Markup.button.callback("🔗 الرابط", "show_link")
      ],
      [Markup.button.callback("↩️ رجوع للنتائج", "back_to_results")]
    ])
  });

  (ctx as any)._pickedResult = result;
}

export async function showLink(ctx: Context) {
  const userId = ctx.from!.id;
  const state = getUserState(userId);
  if (state.mediaInfo?.url) {
    await ctx.answerCbQuery();
    await ctx.reply(`🔗 ${state.mediaInfo.url}`);
  }
}

function escapeMarkdown(text: string): string {
  return text.replace(/[_*[\]()~`>#+\-=|{}.!]/g, "\\$&");
}
