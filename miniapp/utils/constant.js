/**
 * 剧云榜 — 常量定义
 */

// 剧集类型
const DRAMA_TYPES = [
  { value: '', label: '全部' },
  { value: 'tv_drama', label: '电视剧' },
  { value: 'web_drama', label: '网剧' },
  { value: 'variety', label: '综艺' }
]

// 地区
const REGIONS = ['内地', '港台', '韩国', '美国', '日本', '其他']

// 题材分类
const GENRES = [
  '古装', '现代', '悬疑', '爱情', '喜剧', '科幻',
  '历史', '军旅', '都市', '家庭', '奇幻', '武侠',
  '犯罪', '冒险', '恐怖', '青春', '职场', '体育'
]

// 追剧状态
const TRACKING_STATUS = [
  { value: 'watching', label: '在追' },
  { value: 'want_to_watch', label: '想看' },
  { value: 'watched', label: '看完' },
  { value: 'dropped', label: '弃剧' }
]

// 平台品牌色
const PLATFORM_COLORS = {
  'iqiyi': '#00BE06',
  'youku': '#1EBCF2',
  'tencent': '#FF6600',
  'mgtv': '#FF5F00'
}

module.exports = {
  DRAMA_TYPES,
  REGIONS,
  GENRES,
  TRACKING_STATUS,
  PLATFORM_COLORS
}
