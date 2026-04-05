export interface DownloadRecord {
  url: string;
  platform: string;
  title: string;
  format: string;
  timestamp: Date;
}

export interface UserState {
  waitingFor?: "download_url" | "search_query" | "music_search";
  searchResults?: any[];
  mediaInfo?: any;
}

const userHistory = new Map<number, DownloadRecord[]>();
const userStates = new Map<number, UserState>();
const botStats = {
  totalDownloads: 0,
  totalSearches: 0,
  startTime: new Date(),
  activeUsers: new Set<number>()
};

export function addDownloadRecord(userId: number, record: DownloadRecord): void {
  if (!userHistory.has(userId)) {
    userHistory.set(userId, []);
  }
  const history = userHistory.get(userId)!;
  history.unshift(record);
  if (history.length > 20) history.pop();
  botStats.totalDownloads++;
  botStats.activeUsers.add(userId);
}

export function getUserHistory(userId: number): DownloadRecord[] {
  return userHistory.get(userId) || [];
}

export function clearUserHistory(userId: number): void {
  userHistory.delete(userId);
}

export function setUserState(userId: number, state: UserState): void {
  userStates.set(userId, state);
}

export function getUserState(userId: number): UserState {
  return userStates.get(userId) || {};
}

export function clearUserState(userId: number): void {
  userStates.delete(userId);
}

export function recordSearch(userId: number): void {
  botStats.totalSearches++;
  botStats.activeUsers.add(userId);
}

export function getBotStats() {
  const uptime = Date.now() - botStats.startTime.getTime();
  const hours = Math.floor(uptime / 3600000);
  const minutes = Math.floor((uptime % 3600000) / 60000);
  return {
    totalDownloads: botStats.totalDownloads,
    totalSearches: botStats.totalSearches,
    activeUsers: botStats.activeUsers.size,
    uptimeStr: `${hours}h ${minutes}m`,
    startTime: botStats.startTime
  };
}
