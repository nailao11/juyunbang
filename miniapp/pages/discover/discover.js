const api = require('../../utils/request')
const { formatNumber } = require('../../utils/format')

const app = getApp()

Page({
  data: {
    darkMode: false,
    loading: true,
    currentGenre: '',
    genres: [
      { key: 'costume', name: '古装', emoji: '🏯' },
      { key: 'modern', name: '现代', emoji: '🏙' },
      { key: 'suspense', name: '悬疑', emoji: '🔍' },
      { key: 'romance', name: '爱情', emoji: '💕' },
      { key: 'comedy', name: '喜剧', emoji: '😄' },
      { key: 'action', name: '动作', emoji: '💥' },
      { key: 'fantasy', name: '奇幻', emoji: '✨' },
      { key: 'military', name: '军旅', emoji: '🎖' },
      { key: 'family', name: '家庭', emoji: '👨‍👩‍👧' },
      { key: 'scifi', name: '科幻', emoji: '🚀' }
    ],
    highScoreList: [],
    hiddenGemList: [],
    upcomingList: []
  },

  onLoad() {
    this.loadAllData()
  },

  onShow() {
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
  },

  onPullDownRefresh() {
    this.loadAllData().then(() => wx.stopPullDownRefresh())
  },

  async loadAllData() {
    this.setData({ loading: true })
    await Promise.all([
      this.loadHighScore(),
      this.loadHiddenGems(),
      this.loadUpcoming()
    ])
    this.setData({ loading: false })
  },

  // 高分推荐
  async loadHighScore() {
    try {
      const data = await api.get('/discover/high-score', { limit: 10 })
      this.setData({ highScoreList: data.list || data || [] })
    } catch (e) {
      console.error('加载高分推荐失败', e)
    }
  },

  // 冷门佳作
  async loadHiddenGems() {
    try {
      const data = await api.get('/discover/hidden-gems', { limit: 10 })
      this.setData({ hiddenGemList: data.list || data || [] })
    } catch (e) {
      console.error('加载冷门佳作失败', e)
    }
  },

  // 待播期待榜
  async loadUpcoming() {
    try {
      const data = await api.get('/discover/upcoming', { limit: 10 })
      this.setData({ upcomingList: data.list || data || [] })
    } catch (e) {
      console.error('加载待播期待榜失败', e)
    }
  },

  // 切换类型
  switchGenre(e) {
    const genre = e.currentTarget.dataset.genre
    const newGenre = this.data.currentGenre === genre ? '' : genre
    this.setData({ currentGenre: newGenre })

    // 按类型筛选重新加载
    if (newGenre) {
      this.loadGenreData(newGenre)
    } else {
      this.loadAllData()
    }
  },

  async loadGenreData(genre) {
    this.setData({ loading: true })
    try {
      const data = await api.get('/discover/by-genre', { genre, limit: 10 })
      this.setData({
        highScoreList: data.high_score || [],
        hiddenGemList: data.hidden_gems || [],
        loading: false
      })
    } catch (e) {
      console.error('加载类型数据失败', e)
      this.setData({ loading: false })
    }
  },

  // 期待/取消期待
  async toggleExpect(e) {
    const id = e.currentTarget.dataset.id
    const item = this.data.upcomingList.find(i => i.id === id)
    if (!item) return

    try {
      if (item.is_expected) {
        await api.del(`/user/expect/${id}`)
      } else {
        await api.post(`/user/expect/${id}`)
      }

      const list = this.data.upcomingList.map(i => {
        if (i.id === id) {
          return {
            ...i,
            is_expected: !i.is_expected,
            expect_count: i.is_expected ? (i.expect_count - 1) : (i.expect_count + 1)
          }
        }
        return i
      })
      this.setData({ upcomingList: list })
    } catch (e) {
      wx.showToast({ title: '操作失败', icon: 'none' })
    }
  },

  // 跳转详情
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  },

  // 跳转排行详情
  goRankDetail(e) {
    const type = e.currentTarget.dataset.type
    wx.navigateTo({ url: `/pages/rank-detail/rank-detail?type=${type}` })
  },

  // 通用导航
  navigateTo(e) {
    const url = e.currentTarget.dataset.url
    wx.navigateTo({ url })
  },

  onShareAppMessage() {
    return {
      title: '剧云榜 - 发现好剧',
      path: '/pages/discover/discover'
    }
  }
})
