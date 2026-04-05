"use strict";

const YouTube = require("youtube-sr").default;

async function searchVideos(query, limit = 8) {
  const results = await YouTube.search(query, { limit, type: "video", safeSearch: false });
  return results.map(v => ({
    id: v.id || "",
    title: v.title || "بدون عنوان",
    url: v.url || `https://www.youtube.com/watch?v=${v.id}`,
    duration: v.durationFormatted || "غير محدد",
    thumbnail: v.thumbnail?.url || "",
    channel: v.channel?.name || "قناة مجهولة",
    views: fmtViews(v.views),
    uploadedAt: v.uploadedAt || "",
  }));
}

function fmtViews(n) {
  if (!n) return "—";
  if (n >= 1e9) return `${(n/1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n/1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n/1e3).toFixed(1)}K`;
  return String(n);
}

module.exports = { searchVideos };
