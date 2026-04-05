import YouTube from "youtube-sr";

export interface YouTubeSearchResult {
  id: string;
  title: string;
  url: string;
  duration: string;
  thumbnail: string;
  channel: string;
  views: string;
  uploadedAt: string;
}

export interface YouTubePlaylistResult {
  id: string;
  title: string;
  url: string;
  thumbnail: string;
  videoCount: number;
  channel: string;
}

export async function searchYouTube(query: string, limit: number = 8): Promise<YouTubeSearchResult[]> {
  try {
    const results = await YouTube.search(query, { limit, type: "video", safeSearch: false });
    return results.map(video => ({
      id: video.id || "",
      title: video.title || "بدون عنوان",
      url: video.url || `https://www.youtube.com/watch?v=${video.id}`,
      duration: video.durationFormatted || "غير محدد",
      thumbnail: video.thumbnail?.url || "",
      channel: video.channel?.name || "قناة مجهولة",
      views: formatViews(video.views),
      uploadedAt: video.uploadedAt || ""
    }));
  } catch (err) {
    throw new Error("فشل في البحث على يوتيوب. حاول مرة أخرى.");
  }
}

export async function searchYouTubeMusic(query: string, limit: number = 8): Promise<YouTubeSearchResult[]> {
  try {
    const results = await YouTube.search(query, { limit, type: "video", safeSearch: false });
    return results.map(video => ({
      id: video.id || "",
      title: video.title || "بدون عنوان",
      url: video.url || `https://www.youtube.com/watch?v=${video.id}`,
      duration: video.durationFormatted || "غير محدد",
      thumbnail: video.thumbnail?.url || "",
      channel: video.channel?.name || "قناة مجهولة",
      views: formatViews(video.views),
      uploadedAt: video.uploadedAt || ""
    }));
  } catch (err) {
    throw new Error("فشل في البحث. حاول مرة أخرى.");
  }
}

export async function getVideoInfo(videoId: string): Promise<YouTubeSearchResult | null> {
  try {
    const video = await YouTube.getVideo(`https://www.youtube.com/watch?v=${videoId}`);
    if (!video) return null;
    return {
      id: video.id || videoId,
      title: video.title || "بدون عنوان",
      url: video.url || `https://www.youtube.com/watch?v=${videoId}`,
      duration: video.durationFormatted || "غير محدد",
      thumbnail: video.thumbnail?.url || "",
      channel: video.channel?.name || "قناة مجهولة",
      views: formatViews(video.views),
      uploadedAt: video.uploadedAt || ""
    };
  } catch {
    return null;
  }
}

function formatViews(views?: number): string {
  if (!views) return "غير محدد";
  if (views >= 1_000_000_000) return `${(views / 1_000_000_000).toFixed(1)}B مشاهدة`;
  if (views >= 1_000_000) return `${(views / 1_000_000).toFixed(1)}M مشاهدة`;
  if (views >= 1_000) return `${(views / 1_000).toFixed(1)}K مشاهدة`;
  return `${views} مشاهدة`;
}
