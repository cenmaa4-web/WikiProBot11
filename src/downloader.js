"use strict";

const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");

const YTDLP = process.env.YTDLP_PATH || "yt-dlp";
const TMP_DIR = process.env.TMP_DIR || os.tmpdir();

// Ensure tmp dir exists
if (!fs.existsSync(TMP_DIR)) {
  fs.mkdirSync(TMP_DIR, { recursive: true });
}

const PLATFORM_HEADERS = {
  Instagram: "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
  Snapchat:  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
  Pinterest: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
};

function detectPlatform(url) {
  if (/youtube\.com|youtu\.be/.test(url)) return "YouTube";
  if (/instagram\.com/.test(url)) return "Instagram";
  if (/tiktok\.com/.test(url)) return "TikTok";
  if (/twitter\.com|x\.com/.test(url)) return "Twitter/X";
  if (/facebook\.com|fb\.com|fb\.watch/.test(url)) return "Facebook";
  if (/soundcloud\.com/.test(url)) return "SoundCloud";
  if (/twitch\.tv/.test(url)) return "Twitch";
  if (/vimeo\.com/.test(url)) return "Vimeo";
  if (/reddit\.com/.test(url)) return "Reddit";
  if (/pinterest\.com|pin\.it/.test(url)) return "Pinterest";
  if (/snapchat\.com|snap\.com/.test(url)) return "Snapchat";
  if (/dailymotion\.com/.test(url)) return "Dailymotion";
  if (/bilibili\.com/.test(url)) return "Bilibili";
  return "Unknown";
}

function getExtraArgs(platform) {
  const ua = PLATFORM_HEADERS[platform];
  if (ua) return ["--add-header", `User-Agent:${ua}`];
  return [];
}

// Run yt-dlp and return the downloaded file path
async function runYtDlp(args) {
  return new Promise((resolve, reject) => {
    const proc = spawn(YTDLP, args, { timeout: 120000 });
    let stdout = "";
    let stderr = "";
    let outputFile = "";

    proc.stdout.on("data", (d) => {
      const line = d.toString();
      stdout += line;

      // Detect output file from yt-dlp messages
      const patterns = [
        /\[download\] Destination: (.+)/,
        /\[Merger\] Merging formats into "(.+)"/,
        /\[ffmpeg\] Destination: (.+)/,
        /\[ExtractAudio\] Destination: (.+)/,
      ];
      for (const pat of patterns) {
        const m = line.match(pat);
        if (m) outputFile = m[1].trim();
      }
    });
    proc.stderr.on("data", (d) => { stderr += d.toString(); });

    proc.on("error", (err) => reject(new Error("yt-dlp not found: " + err.message)));
    proc.on("close", (code) => {
      if (code === 0) {
        // If we captured the file path and it exists
        if (outputFile && fs.existsSync(outputFile)) {
          return resolve(outputFile);
        }
        // Fallback: scan tmp dir for the most recently created tgbot_ file
        try {
          const files = fs.readdirSync(TMP_DIR)
            .filter(f => f.startsWith("tgbot_"))
            .map(f => ({ f, t: fs.statSync(path.join(TMP_DIR, f)).mtimeMs }))
            .sort((a, b) => b.t - a.t);
          if (files.length > 0) return resolve(path.join(TMP_DIR, files[0].f));
        } catch {}
        reject(new Error("لم يتم العثور على الملف المحمل"));
      } else {
        // Parse error reason
        const combined = stdout + stderr;
        if (/private|Private/.test(combined)) return reject(new Error("المحتوى خاص ولا يمكن تحميله"));
        if (/unavailable|not available/.test(combined)) return reject(new Error("المحتوى غير متاح أو محذوف"));
        if (/Unsupported URL|not supported/.test(combined)) return reject(new Error("هذا الرابط غير مدعوم"));
        reject(new Error("فشل التحميل. الرابط قد لا يكون مدعوماً أو المحتوى خاص"));
      }
    });
  });
}

// Get info about a URL without downloading
async function getMediaInfo(url) {
  const platform = detectPlatform(url);
  const extraArgs = getExtraArgs(platform);

  const args = [
    "--dump-json",
    "--no-playlist",
    "--socket-timeout", "30",
    ...extraArgs,
    url
  ];

  return new Promise((resolve, reject) => {
    const proc = spawn(YTDLP, args, { timeout: 45000 });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", d => stdout += d.toString());
    proc.stderr.on("data", d => stderr += d.toString());
    proc.on("error", err => reject(new Error("yt-dlp not found: " + err.message)));
    proc.on("close", code => {
      if (code !== 0 || !stdout.trim()) {
        const combined = stdout + stderr;
        if (/private|Private/.test(combined)) return reject(new Error("المحتوى خاص ولا يمكن تحميله"));
        return reject(new Error("لا يمكن تحليل هذا الرابط. تأكد أنه صحيح وعلني"));
      }
      try {
        const info = JSON.parse(stdout.trim());
        resolve({
          title: info.title || "بدون عنوان",
          duration: info.duration,
          thumbnail: info.thumbnail,
          platform,
          url,
          uploader: info.uploader || info.channel || info.creator,
        });
      } catch {
        reject(new Error("فشل في قراءة معلومات الوسائط"));
      }
    });
  });
}

// Download with AUTO-FALLBACK for quality
// Tries: requested quality → 480p → 360p → audio-only
async function downloadMedia(url, format, platform, onProgress) {
  platform = platform || detectPlatform(url);
  const extraArgs = getExtraArgs(platform);

  // Build a fixed output file path (no title in name to avoid path issues)
  const ts = Date.now();
  const outPath = path.join(TMP_DIR, `tgbot_${ts}`);

  let formatArg;
  let isAudio = false;

  switch (format) {
    case "audio":
      isAudio = true;
      formatArg = "bestaudio/best";
      break;
    case "360":
      formatArg = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best";
      break;
    case "480":
      formatArg = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best";
      break;
    case "720":
      formatArg = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best";
      break;
    case "1080":
      formatArg = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best";
      break;
    default:
      // "best" → try 720p first to keep files manageable
      formatArg = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best";
  }

  let args;
  if (isAudio) {
    args = [
      "-f", formatArg,
      "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
      "--no-playlist", "--socket-timeout", "30", "--newline",
      "--no-warnings",
      ...extraArgs,
      "-o", `${outPath}.%(ext)s`,
      url
    ];
  } else {
    args = [
      "-f", formatArg,
      "--merge-output-format", "mp4",
      "--no-playlist", "--socket-timeout", "30", "--newline",
      "--no-warnings",
      ...extraArgs,
      "-o", `${outPath}.%(ext)s`,
      url
    ];
  }

  // Progress wrapper
  const argsWithProgress = args;
  let filePath = await runYtDlpWithProgress(argsWithProgress, outPath, onProgress);

  // AUTO-FALLBACK: if file > 45MB, try lower quality
  const MAX_SIZE = 45 * 1024 * 1024;
  if (!isAudio && fs.existsSync(filePath)) {
    const size = fs.statSync(filePath).size;
    if (size > MAX_SIZE) {
      // Cleanup large file
      fs.unlinkSync(filePath);

      const fallbackQualities = ["480", "360"];
      for (const q of fallbackQualities) {
        const fmtMap = {
          "480": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best",
          "360": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        };
        const tsNew = Date.now();
        const outPathNew = path.join(TMP_DIR, `tgbot_${tsNew}`);
        const fallbackArgs = [
          "-f", fmtMap[q],
          "--merge-output-format", "mp4",
          "--no-playlist", "--socket-timeout", "30", "--newline", "--no-warnings",
          ...extraArgs,
          "-o", `${outPathNew}.%(ext)s`,
          url
        ];
        try {
          filePath = await runYtDlpWithProgress(fallbackArgs, outPathNew, onProgress);
          const newSize = fs.existsSync(filePath) ? fs.statSync(filePath).size : 0;
          if (newSize <= MAX_SIZE) break;
          if (newSize > MAX_SIZE) fs.unlinkSync(filePath);
        } catch {}
      }
    }
  }

  return filePath;
}

function runYtDlpWithProgress(args, outBasePath, onProgress) {
  return new Promise((resolve, reject) => {
    const proc = spawn(YTDLP, args, { timeout: 180000 });
    let outputFile = "";
    let stderr = "";
    let lastProgress = 0;

    proc.stdout.on("data", (d) => {
      const text = d.toString();
      const progMatch = text.match(/\[download\]\s+(\d+\.?\d*)%/);
      if (progMatch && onProgress) {
        const pct = parseFloat(progMatch[1]);
        if (pct - lastProgress >= 5) { // only update every 5%
          lastProgress = pct;
          onProgress(pct).catch(() => {});
        }
      }
      const patterns = [
        /\[download\] Destination: (.+)/,
        /\[Merger\] Merging formats into "(.+)"/,
        /\[ffmpeg\] Destination: (.+)/,
        /\[ExtractAudio\] Destination: (.+)/,
      ];
      for (const pat of patterns) {
        const m = text.match(pat);
        if (m) outputFile = m[1].trim();
      }
    });

    proc.stderr.on("data", d => { stderr += d.toString(); });

    proc.on("error", err => reject(new Error("yt-dlp error: " + err.message)));

    proc.on("close", (code) => {
      if (code === 0) {
        if (outputFile && fs.existsSync(outputFile)) return resolve(outputFile);

        // Fallback: look for files starting with our base path
        const dir = require("path").dirname(outBasePath);
        const base = require("path").basename(outBasePath);
        try {
          const files = fs.readdirSync(dir)
            .filter(f => f.startsWith(base))
            .map(f => ({ f, t: fs.statSync(path.join(dir, f)).mtimeMs }))
            .sort((a, b) => b.t - a.t);
          if (files.length > 0) return resolve(path.join(dir, files[0].f));
        } catch {}
        reject(new Error("لم يتم العثور على الملف بعد التحميل"));
      } else {
        const combined = stderr;
        if (/private|Private/.test(combined)) return reject(new Error("المحتوى خاص"));
        if (/unavailable/.test(combined)) return reject(new Error("المحتوى غير متاح"));
        reject(new Error("فشل التحميل"));
      }
    });
  });
}

function formatDuration(sec) {
  if (!sec) return "غير محدد";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
  return `${m}:${String(s).padStart(2,"0")}`;
}

function formatSize(bytes) {
  if (!bytes) return "غير محدد";
  const mb = bytes / 1048576;
  return mb >= 1000 ? `${(mb/1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
}

function cleanup(filePath) {
  try { if (filePath && fs.existsSync(filePath)) fs.unlinkSync(filePath); } catch {}
}

module.exports = { detectPlatform, getMediaInfo, downloadMedia, formatDuration, formatSize, cleanup };
