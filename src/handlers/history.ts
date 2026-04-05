import { Context, Markup } from "telegraf";
import { getUserHistory, clearUserHistory } from "../utils/storage";

export async function handleHistory(ctx: Context) {
  const userId = ctx.from!.id;
  const history = getUserHistory(userId);

  if (history.length === 0) {
    await ctx.editMessageText(
      `📜 *سجل التحميلات*\n\nلا يوجد سجل تحميلات حتى الآن.\nابدأ بتحميل فيديو!`,
      {
        parse_mode: "Markdown",
        ...Markup.inlineKeyboard([
          [Markup.button.callback("⬇️ تحميل الآن", "menu_download")],
          [Markup.button.callback("↩️ رجوع", "menu_back")]
        ])
      }
    );
    return;
  }

  const platformEmojis: Record<string, string> = {
    "YouTube": "📺",
    "Instagram": "📸",
    "TikTok": "🎵",
    "Twitter/X": "🐦",
    "Facebook": "👥",
    "SoundCloud": "🎶",
    "Vimeo": "🎬",
    "Reddit": "🔴",
    "Unknown": "🌐"
  };

  let text = `📜 *آخر ${Math.min(history.length, 10)} تحميلات:*\n\n`;
  
  history.slice(0, 10).forEach((record, i) => {
    const emoji = platformEmojis[record.platform] || "🌐";
    const date = record.timestamp.toLocaleDateString("ar-SA");
    const time = record.timestamp.toLocaleTimeString("ar-SA", { hour: "2-digit", minute: "2-digit" });
    text += `${i + 1}. ${emoji} *${escapeMarkdown(record.title.substring(0, 50))}*\n`;
    text += `   📌 ${record.platform} • ${record.format} • ${date} ${time}\n\n`;
  });

  await ctx.editMessageText(text, {
    parse_mode: "Markdown",
    ...Markup.inlineKeyboard([
      [Markup.button.callback("🗑️ مسح السجل", "clear_history")],
      [Markup.button.callback("↩️ رجوع للقائمة", "menu_back")]
    ])
  });
}

export async function handleClearHistory(ctx: Context) {
  const userId = ctx.from!.id;
  clearUserHistory(userId);
  
  await ctx.editMessageText(
    `✅ *تم مسح سجل التحميلات بنجاح*`,
    {
      parse_mode: "Markdown",
      ...Markup.inlineKeyboard([[Markup.button.callback("↩️ رجوع للقائمة", "menu_back")]])
    }
  );
}

function escapeMarkdown(text: string): string {
  return text.replace(/[_*[\]()~`>#+\-=|{}.!]/g, "\\$&");
}
