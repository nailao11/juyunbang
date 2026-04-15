/**
 * 剧云榜 — 数据格式化工具
 */

// 格式化大数字（例如 12345678 → 1234.6万，1234567890 → 12.35亿）
function formatNumber(num) {
  if (!num && num !== 0) return '-'
  num = Number(num)
  if (num >= 100000000) {
    return (num / 100000000).toFixed(2) + '亿'
  } else if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  } else {
    return num.toString()
  }
}

// 格式化热度值
function formatHeat(value) {
  if (!value && value !== 0) return '-'
  value = Number(value)
  if (value >= 10000) {
    return (value / 10000).toFixed(1) + '万'
  }
  return value.toFixed(0)
}

// 格式化百分比变化
function formatChange(value) {
  if (!value && value !== 0) return ''
  value = Number(value)
  if (value > 0) return '+' + value.toFixed(1) + '%'
  if (value < 0) return value.toFixed(1) + '%'
  return '0%'
}

// 格式化完整日期
function formatFullDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.getFullYear() + '-' +
    (d.getMonth() + 1).toString().padStart(2, '0') + '-' +
    d.getDate().toString().padStart(2, '0')
}

// 格式化时间
function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.getHours().toString().padStart(2, '0') + ':' +
    d.getMinutes().toString().padStart(2, '0')
}

// 获取星期几
function getWeekDay(dateStr) {
  const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const d = new Date(dateStr)
  return days[d.getDay()]
}

// 剧集状态文本
function formatStatus(status) {
  const map = {
    'airing': '热播中',
    'finished': '已完结',
    'upcoming': '待播出'
  }
  return map[status] || status
}

module.exports = {
  formatNumber,
  formatHeat,
  formatChange,
  formatFullDate,
  formatTime,
  getWeekDay,
  formatStatus
}
