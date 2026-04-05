import { execFile, spawn } from "child_process";
import { promisify } from "util";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

const execFileAsync = promisify(execFile);

export interface MediaInfo {
  title: string;
  duration?: number;
  thumbnail?: string;
  formats?: FormatInfo[];
  platform: string;
  url: string;
  filesize?: number;
  description?: string;
  uploader?: string;
}

export interface FormatInfo {
  id: string;
  ext: string;
  quality: string;
  resolution?: string;
  filesize?: number;
  type: "video" | "audio" | "image";
}

const PLATFORM_ARGS: Record<string, string[]> = {
  Instagram: ["--add-header", "User-Agent:Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"],
  Snapchat: ["--add-header", "User-Agent:Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"],
  Pinterest: ["--add-header", "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"],
  Facebook: ["--cookies-from-browser", "none"],
  default: []
};

export function detectPlatform(url: string): string {
  if (url.includes("youtube.com") || url.includes("youtu.be")) return "YouTube";
  if (url.includes("instagram.com")) return "Instagram";
  if (url.includes("tiktok.com")) return "TikTok";
  if (url.includes("twitter.com") || url.includes("x.com")) return "Twitter/X";
  if (url.includes("facebook.com") || url.includes("fb.com") || url.includes("fb.watch")) return "Facebook";
  if (url.includes("soundcloud.com")) return "SoundCloud";
  if (url.includes("twitch.tv")) return "Twitch";
  if (url.includes("vimeo.com")) return "Vimeo";
  if (url.includes("reddit.com")) return "Reddit";
  if (url.includes("pinterest.com") || url.includes("pin.it")) return "Pinterest";
  if (url.includes("snapchat.com") || url.includes("snap.com")) return "Snapchat";
  if (url.includes("dailymotion.com")) return "Dailymotion";
  if (url.includes("bilibili.com")) return "Bilibili";
  return "Unknown";
}

function getPlatformArgs(platform: string): string[] {
  return PLATFORM_ARGS[platform] || PLATFORM_ARGS.default;
}

export async function getMediaInfo(url: string): Promise<MediaInfo> {
  const platform = detectPlatform(url);
  const ytdlpPath = process.env.YTDLP_PATH || "yt-dlp";
  const extraArgs = getPlatformArgs(platform);

  try {
    const args = [
      "--dump-json",
      "--no-playlist",
      "--socket-timeout", "30",
      ...extraArgs,
      url
    ];

    const { stdout } = await execFileAsync(ytdlpPath, args, { timeout: 45000 });
    const info = JSON.parse(stdout);

    const formats: FormatInfo[] = [];

    if (info.formats) {
      const videoFormats = info.formats.filter((f: any) =>
        f.vcodec !== "none" && f.height
      );
      const uniqueRes = new Set<string>();
      for (const f of [...videoFormats].reverse()) {
        const res = `${f.height}p`;
        if (!uniqueRes.has(res) && uniqueRes.size < 4) {
          uniqueRes.add(res);
          formats.push({
            id: f.format_id,
            ext: f.ext || "mp4",
            quality: res,
            resolution: res,
            filesize: f.filesize || f.filesize_approx,
            type: "video"
          });
        }
      }
      formats.push({ id: "bestaudio", ext: "mp3", quality: "صوت فقط", type: "audio" });
    }

    return {
      title: info.title || "Untitled",
      duration: info.duration,
      thumbnail: info.thumbnail,
      formats,
      platform,
      url,
      description: info.description?.substring(0, 200),
      uploader: info.uploader || info.channel
    };
  } catch (err: any) {
    const msg = err.message || "";
    if (msg.includes("Private") || msg.includes("private")) {
      throw new Error(`المحتوى خاص ولا يمكن تحميله.`);
    }
    if (msg.includes("not supported") || msg.includes("Unsupported URL")) {
      throw new Error(`هذا الرابط غير مدعوم. تأكد أن الرابط من منصة مدعومة.`);
    }
    throw new Error(`لا يمكن تحليل هذا الرابط. تأكد أن الرابط صحيح وعلني.`);
  }
}

export async function downloadMedia(
  url: string,
  format: string = "best",
  platform: string = "Unknown",
  onProgress?: (percent: number) => void
): Promise<string> {
  const tmpDir = os.tmpdir();
  const outputTemplate = path.join(tmpDir, `tgbot_${Date.now()}_%(title).50s.%(ext)s`);

  const ytdlpPath = process.env.YTDLP_PATH || "yt-dlp";
  const extraArgs = getPlatformArgs(platform);

  let formatArg: string;
  let isAudio = false;

  if (format === "bestaudio" || format === "audio") {
    isAudio = true;
    formatArg = "bestaudio/best";
  } else if (format === "best") {
    formatArg = "bestvideo[height<=720]+bestaudio/best[height<=720]/best";
  } else if (format === "360") {
    formatArg = "bestvideo[height<=360]+bestaudio/best[height<=360]/best";
  } else if (format === "720") {
    formatArg = "bestvideo[height<=720]+bestaudio/best[height<=720]/best";
  } else if (format === "1080") {
    formatArg = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best";
  } else {
    formatArg = `${format}+bestaudio/${format}/best`;
  }

  let args: string[];
  if (isAudio) {
    args = [
      "-f", formatArg,
      "--extract-audio",
      "--audio-format", "mp3",
      "--audio-quality", "0",
      "--no-playlist",
      "--socket-timeout", "30",
      "--newline",
      ...extraArgs,
      "-o", outputTemplate,
      url
    ];
  } else {
    args = [
      "-f", formatArg,
      "--merge-output-format", "mp4",
      "--no-playlist",
      "--socket-timeout", "30",
      "--newline",
      ...extraArgs,
      "-o", outputTemplate,
      url
    ];
  }

  return new Promise((resolve, reject) => {
    const proc = spawn(ytdlpPath, args);
    let outputFile = "";
    let errorOutput = "";

    proc.stdout.on("data", (data: Buffer) => {
      const line = data.toString();
      const progressMatch = line.match(/\[download\]\s+(\d+\.?\d*)%/);
      if (progressMatch && onProgress) {
        onProgress(parseFloat(progressMatch[1]));
      }
      const destMatch = line.match(/\[download\] Destination: (.+)/);
      if (destMatch) outputFile = destMatch[1].trim();
      const mergeMatch = line.match(/\[Merger\] Merging formats into "(.+)"/);
      if (mergeMatch) outputFile = mergeMatch[1].trim();
      const ffmpegMatch = line.match(/\[ffmpeg\] Destination: (.+)/);
      if (ffmpegMatch) outputFile = ffmpegMatch[1].trim();
    });

    proc.stderr.on("data", (data: Buffer) => {
      errorOutput += data.toString();
    });

    proc.on("close", (code) => {
      if (code === 0) {
        if (outputFile && fs.existsSync(outputFile)) {
          resolve(outputFile);
        } else {
          const files = fs.readdirSync(tmpDir)
            .filter(f => f.startsWith("tgbot_"))
            .map(f => path.join(tmpDir, f))
            .sort((a, b) => fs.statSync(b).mtime.getTime() - fs.statSync(a).mtime.getTime());
          if (files.length > 0 && fs.existsSync(files[0])) {
            resolve(files[0]);
          } else {
            reject(new Error("فشل في تحديد الملف المحمل"));
          }
        }
      } else {
        if (errorOutput.includes("Private") || errorOutput.includes("private")) {
          reject(new Error("المحتوى خاص ولا يمكن تحميله."));
        } else if (errorOutput.includes("not available") || errorOutput.includes("unavailable")) {
          reject(new Error("المحتوى غير متاح أو محذوف."));
        } else {
          reject(new Error("فشل التحميل. الرابط قد لا يكون مدعوماً أو المحتوى خاص."));
        }
      }
    });

    proc.on("error", (err) => {
      reject(new Error(`خطأ في تشغيل yt-dlp: ${err.message}`));
    });
  });
}

export function formatDuration(seconds?: number): string {
  if (!seconds) return "غير محدد";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function formatFileSize(bytes?: number): string {
  if (!bytes) return "غير محدد";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1000) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb.toFixed(1)} MB`;
}

export function cleanupFile(filePath: string): void {
  try {
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
  } catch {}
}
