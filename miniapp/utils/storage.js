/**
 * 剧云榜 — 本地存储工具
 */

function set(key, value) {
  try {
    wx.setStorageSync(key, value)
  } catch (e) {
    console.error('存储写入失败:', key, e)
  }
}

function get(key, defaultValue = null) {
  try {
    const value = wx.getStorageSync(key)
    return value || defaultValue
  } catch (e) {
    console.error('存储读取失败:', key, e)
    return defaultValue
  }
}

function remove(key) {
  try {
    wx.removeStorageSync(key)
  } catch (e) {
    console.error('存储删除失败:', key, e)
  }
}

function clear() {
  try {
    wx.clearStorageSync()
  } catch (e) {
    console.error('存储清理失败:', e)
  }
}

module.exports = { set, get, remove, clear }
