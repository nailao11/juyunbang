const api = require('../../utils/request')
const { formatHeat, formatChange, formatTime } = require('../../utils/format')

Page({
  data: {
    rankList: [],
    platforms: [],
    currentPlatform: '',
    currentType: '',
    loading: true,
    updateTime: '',
    darkMode: false,
    hasMore: false
  },

  onLoad() {
    this.loadPlatforms()
    this.loadRankData()
  },

  onShow() {
    const app = getApp()
    const darkMode = app.globalData.themeMode === 'dark'
    this.setData({ darkMode })
    wx.setBackgroundColor({
      backgroundColor: darkMode ? '#171923' : '#f4f5f7',
      backgroundColorTop: darkMode ? '#171923' : '#f4f5f7',
      backgroundColorBottom: darkMode ? '#171923' : '#f4f5f7'
    })
  },

  onPullDownRefresh() {
    this.loadRankData().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 加载平台列表
  async loadPlatforms() {
    try {
      const data = await api.get('/system/platforms')
      // 按 short_name 去重，防止后端返回重复平台
      const seen = new Set()
      const unique = (data || []).filter(p => {
        if (seen.has(p.short_name)) return false
        seen.add(p.short_name)
        return true
      })
      this.setData({ platforms: unique })
    } catch (e) {
      console.error('加载平台列表失败', e)
    }
  },

  // 加载排行数据（最多30条，不分页）
  async loadRankData() {
    this.setData({ loading: true })

    try {
      const params = {
        platform: this.data.currentPlatform,
        type: this.data.currentType,
        limit: 30
      }

      const url = this.data.currentPlatform
        ? '/heat/realtime/rank'
        : '/heat/realtime/all-rank'

      const data = await api.get(url, params)

      let list = data.list || data || []

      // 格式化数据 — 全平台聚合榜返回 avg_heat，单平台榜返回 heat_value
      const getHeat = (i) => Number(i.heat_value || i.avg_heat || 0)
      const maxHeat = list.length > 0
        ? Math.max(...list.map(getHeat))
        : 10000

      list = list.map(item => {
        const heat = getHeat(item)
        return {
          ...item,
          heat_display: formatHeat(heat),
          heat_bar_width: maxHeat > 0 ? Math.round(heat / maxHeat * 100) : 0,
          heat_change_pct: item.heat_change_pct ? Math.abs(item.heat_change_pct).toFixed(1) : '',
          trend: item.trend || 'flat'
        }
      })

      this.setData({
        rankList: list,
        loading: false,
        hasMore: false,
        updateTime: data.update_time ? formatTime(data.update_time) : this._getCurrentTime()
      })

    } catch (e) {
      console.error('加载排行数据失败', e)
      this.setData({ loading: false })
      wx.showToast({ title: '加载失败，下拉刷新重试', icon: 'none' })
    }
  },

  // 切换平台
  switchPlatform(e) {
    const platform = e.currentTarget.dataset.platform
    this.setData({ currentPlatform: platform, rankList: [] })
    this.loadRankData()
  },

  // 切换类型
  switchType(e) {
    const type = e.currentTarget.dataset.type
    this.setData({ currentType: type, rankList: [] })
    this.loadRankData()
  },

  // 刷新数据
  refreshData() {
    this.loadRankData()
    wx.showToast({ title: '数据已刷新', icon: 'success', duration: 1000 })
  },

  // 跳转搜索
  goSearch() {
    wx.navigateTo({ url: '/pages/search/search' })
  },

  // 跳转剧集详情
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/drama-detail/drama-detail?id=${id}` })
  },

  _getCurrentTime() {
    const now = new Date()
    return now.getHours().toString().padStart(2, '0') + ':' +
           now.getMinutes().toString().padStart(2, '0')
  },

  onShareAppMessage() {
    return {
      title: '热剧榜 — 实时热度排行',
      path: '/pages/index/index'
    }
  }
})
