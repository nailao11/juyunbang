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
    maxHeat: 10000,
    darkMode: false,
    page: 1,
    hasMore: true
  },

  onLoad() {
    this.loadPlatforms()
    this.loadRankData()
  },

  onShow() {
    const app = getApp()
    this.setData({ darkMode: app.globalData.themeMode === 'dark' })
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true })
    this.loadRankData().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.setData({ page: this.data.page + 1 })
      this.loadRankData(true)
    }
  },

  // 加载平台列表
  async loadPlatforms() {
    try {
      const data = await api.get('/system/platforms')
      this.setData({ platforms: data || [] })
    } catch (e) {
      console.error('加载平台列表失败', e)
    }
  },

  // 加载排行数据
  async loadRankData(append = false) {
    if (!append) {
      this.setData({ loading: true })
    }

    try {
      const params = {
        platform: this.data.currentPlatform,
        type: this.data.currentType,
        limit: 20,
        page: this.data.page
      }

      const url = this.data.currentPlatform
        ? '/heat/realtime/rank'
        : '/heat/realtime/all-rank'

      const data = await api.get(url, params)

      let list = data.list || data || []

      // 格式化数据
      const maxHeat = list.length > 0
        ? Math.max(...list.map(i => Number(i.heat_value || i.avg_heat || 0)))
        : 10000

      list = list.map(item => ({
        ...item,
        heat_display: formatHeat(item.heat_value || item.avg_heat),
        heat_change_pct: item.heat_change_pct ? Math.abs(item.heat_change_pct).toFixed(1) : '',
        trend: item.trend || 'flat'
      }))

      const newList = append ? [...this.data.rankList, ...list] : list

      this.setData({
        rankList: newList,
        maxHeat,
        loading: false,
        hasMore: list.length >= 20,
        updateTime: data.update_time ? formatTime(data.update_time) : this._getCurrentTime()
      })

    } catch (e) {
      console.error('加载排行数据失败', e)
      this.setData({ loading: false })
      if (!append) {
        wx.showToast({ title: '加载失败，下拉刷新重试', icon: 'none' })
      }
    }
  },

  // 切换平台
  switchPlatform(e) {
    const platform = e.currentTarget.dataset.platform
    this.setData({ currentPlatform: platform, page: 1, rankList: [] })
    this.loadRankData()
  },

  // 切换类型
  switchType(e) {
    const type = e.currentTarget.dataset.type
    this.setData({ currentType: type, page: 1, rankList: [] })
    this.loadRankData()
  },

  // 刷新数据
  refreshData() {
    this.setData({ page: 1 })
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
  }
})
