"use strict";

const userHistory = new Map();
const userStates = new Map();
const stats = { downloads: 0, searches: 0, users: new Set(), start: new Date() };

function addHistory(userId, record) {
  const h = userHistory.get(userId) || [];
  h.unshift(record);
  if (h.length > 20) h.pop();
  userHistory.set(userId, h);
  stats.downloads++;
  stats.users.add(userId);
}
function getHistory(userId) { return userHistory.get(userId) || []; }
function clearHistory(userId) { userHistory.delete(userId); }

function setState(userId, state) { userStates.set(userId, state); }
function getState(userId) { return userStates.get(userId) || {}; }
function clearState(userId) { userStates.delete(userId); }

function recordSearch(userId) { stats.searches++; stats.users.add(userId); }

function getBotStats() {
  const ms = Date.now() - stats.start.getTime();
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  return {
    downloads: stats.downloads,
    searches: stats.searches,
    users: stats.users.size,
    uptime: `${h}h ${m}m`,
  };
}

module.exports = { addHistory, getHistory, clearHistory, setState, getState, clearState, recordSearch, getBotStats };
